"""KISS resource ledger model with public-safe logical rows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

COST_LABELS = {"ACTUAL", "EST", "USAGE-BASED", "DIRECT-$0", "UNKNOWN"}
DECISIONS = {"RETAIN", "REVIEW", "CLEANUP-CANDIDATE"}
SOURCES = {"LIVE", "REPO-EVIDENCE", "FIRST-SEEN"}


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    return None


def _text(value: Any) -> str:
    text = " ".join(str(value).replace("|", "/").split())
    if not text:
        raise ValueError("ledger text cannot be empty")
    return text


@dataclass(frozen=True)
class LedgerRow:
    project: str
    account_alias: str
    resource_class: str
    count: int
    state: str
    purpose: str
    cost_label: str
    decision: str
    source: str
    created: date | None = None
    first_seen: date | None = None
    monthly_usd: float | None = None

    def __post_init__(self) -> None:
        for name in ("project", "account_alias", "resource_class", "state", "purpose"):
            object.__setattr__(self, name, _text(getattr(self, name)))
        if self.count < 1:
            raise ValueError("count must be positive")
        if self.cost_label not in COST_LABELS or self.decision not in DECISIONS or self.source not in SOURCES:
            raise ValueError("invalid ledger enum")
        if self.monthly_usd is not None and self.monthly_usd < 0:
            raise ValueError("monthly cost cannot be negative")

    def age(self, as_of: date) -> str:
        start = self.created or self.first_seen
        if not start:
            return "UNKNOWN"
        basis = "created" if self.created else "first_seen"
        return f"{max(0, (as_of - start).days)}d ({basis})"

    def cost(self) -> str:
        if self.monthly_usd is None:
            return self.cost_label
        return f"{self.cost_label} ~${self.monthly_usd:.2f}/mo"


def right_size_t3(host: dict[str, Any]) -> dict[str, Any]:
    needed = ("mem_total_gib", "mem_available_gib", "swap_total_gib", "cpu_14d_avg_pct", "root_used_pct")
    if not all(isinstance(host.get(key), (int, float)) for key in needed):
        return {"recommendation": "NEEDS-EVIDENCE", "reason": "host metrics incomplete"}
    used = float(host["mem_total_gib"]) - float(host["mem_available_gib"])
    small_headroom = 2.0 - used
    if float(host["swap_total_gib"]) <= 0 and small_headroom < 0.5:
        recommendation = "KEEP-t3.medium"
        reason = f"projected t3.small RAM headroom is only {small_headroom:.2f} GiB with no swap"
    elif float(host["cpu_14d_avg_pct"]) > 15:
        recommendation = "KEEP-t3.medium"
        reason = "sustained CPU is too high for the smaller target"
    else:
        recommendation = "t3.small-CANDIDATE"
        reason = f"projected t3.small RAM headroom is {small_headroom:.2f} GiB"
    if float(host["root_used_pct"]) >= 85:
        reason += f"; root filesystem is {float(host['root_used_pct']):.0f}% used"
    return {"recommendation": recommendation, "reason": reason, "projected_small_headroom_gib": round(small_headroom, 2)}


def render_markdown(rows: Iterable[LedgerRow], *, verified_at: str, coverage: str, sizing: dict[str, Any]) -> str:
    rows = list(rows)
    as_of = datetime.fromisoformat(verified_at.replace("Z", "+00:00")).date()
    lines = [
        "# AWS Resources", "",
        "> KISS public ledger. Logical resource classes and account aliases only.", "",
        f"- Last verified: `{verified_at}`",
        f"- Represented resources: **{sum(row.count for row in rows)}**",
        f"- Coverage: {coverage}", "",
        "## Retained host right-sizing", "",
        f"**{sizing['recommendation']}** — {sizing['reason']}.", "",
        "## Resource ledger", "",
        "| Project | Account | Resource class | Qty | State | Age | Purpose | Cost | Decision | Evidence |",
        "| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append("| " + " | ".join((row.project, row.account_alias, row.resource_class, str(row.count), row.state,
                                         row.age(as_of), row.purpose, row.cost(), row.decision, row.source)) + " |")
    lines += ["", "TTL is a review date, never automatic deletion.", ""]
    return "\n".join(lines)
