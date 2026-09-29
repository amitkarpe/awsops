"""Evidence-grounded read-only Compliance Agent for the awsops config2 demo."""
from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config_backend import ALIASES, CONTROLS, current_evidence
from .harness_client import invoke


def _record_harness_result(status: str, latency_ms: int) -> None:
    """Share only bounded, last-call telemetry with the local config2 cockpit."""
    filename = os.environ.get("AWSOPS_HARNESS_TELEMETRY_FILE")
    if not filename:
        return
    try:
        target = Path(filename)
        if not target.is_absolute() or target.parent.is_symlink():
            return
        payload = {
            "version": 1,
            "status": status,
            "latency_ms": max(0, min(latency_ms, 90000)),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        descriptor, temporary = tempfile.mkstemp(prefix=".harness-", dir=target.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(payload, output, separators=(",", ":"))
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    except (OSError, ValueError):
        # Telemetry is optional and must never change the agent answer or error.
        return


def _request(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise ValueError("user request is invalid")
    return value.strip()


def _response_mode(user_request: str) -> str:
    request = _request(user_request).lower()
    if any(token in request for token in ("plan", "remediat", "fix", "apply", "execute")):
        return "PLAN"
    if any(token in request for token in ("explain", "attention", "why")):
        return "EXPLAIN"
    return "STATUS"


def _mode_layout(mode: str) -> str:
    if mode == "STATUS":
        return """STATUS MODE:
- After the matrix, add exactly one summary sentence. If attention items exist, use: "N of 8 checks need attention." with the evidence-derived N. Otherwise use: "All 8 checks are compliant or not applicable."
- Do not add any second table, explanation table, remediation table, suggestion or implementation detail."""
    if mode == "EXPLAIN":
        return """EXPLAIN MODE:
- After the matrix, add exactly one compact table:
  | Needs attention | Why | Affected |
- Include only evidence-backed NON_COMPLIANT or insufficient-data items.
- Format Needs attention as "<alias> — <S3 BPA|Restricted SSH>".
- For S3 NON_COMPLIANT, the reason is only: bucket-level Block Public Access is not in the compliant configuration.
- For restricted SSH NON_COMPLIANT, the reason is only: unrestricted SSH ingress is present.
- For INSUFFICIENT_DATA, the reason is only: evidence is insufficient; Affected is "Unknown".
- Use aliases and aggregate counts only.
- Do not include suggested changes, remediation steps, priorities or an execution column."""
    return """PLAN MODE:
- After the matrix, add exactly one compact table:
  | Alias | Control | Evidence | Suggested change | Execution |
- Include one row for each NON_COMPLIANT alias/control check and no other rows.
- Evidence must use the same status and aggregate affected_resources count as the matrix.
- For S3 NON_COMPLIANT, suggest only bringing bucket-level Block Public Access into the compliant configuration.
- For restricted SSH NON_COMPLIANT, suggest only removing unrestricted SSH ingress and, if access is still required, replacing it with an approved source.
- Every Execution cell must be "🚫 Not executed".
- Do not include a separate attention/explanation table."""


def build_prompt(user_request: str, evidence: dict[str, Any]) -> str:
    request = _request(user_request)
    mode = _response_mode(request)
    packet = json.dumps(evidence, separators=(",", ":"), sort_keys=True)
    layout = _mode_layout(mode)
    return f"""USER_REQUEST:
{request}

RESPONSE_MODE:
{mode}

AUTHORITATIVE_EVIDENCE_JSON:
{packet}

RULES:
- Answer only from AUTHORITATIVE_EVIDENCE_JSON.
- This Issue #39 migration slice is read-only. Never claim that a change was applied, approved, executed or verified.
- Name the registered LAB aliases and exact supported controls when relevant.
- Missing, partial, stale or unavailable evidence is not compliant evidence.
- affected_resources is an aggregate count only; no resource or account identifiers are available.
- AWS Config is asynchronous evidence. Do not infer exposure, exploitability, activity, data sensitivity, authentication behavior, or unrelated controls.
- Do not invent identifiers, policies, ports, CIDRs, resource names or implementation details.
- If asked to fix/apply/remediate now, RESPONSE_MODE must be PLAN and no change may be claimed.

OUTPUT CONTRACT:
- Use compact Markdown only. Be KISS and demo-friendly.
- Do not add greetings, preambles, conclusions, or repeat a table in prose.
- Always show the exact four-account x two-control matrix first:
  | Account | 🪣 S3 BPA | 🔐 Restricted SSH |
  | --- | --- | --- |
  | lab-dev | ... | ... |
  | lab-poc | ... | ... |
  | lab-qa | ... | ... |
  | lab-sec | ... | ... |
- Render evidence statuses only as:
  ✅ COMPLIANT
  🔴 NON_COMPLIANT (N affected), where N is the exact aggregate affected_resources count
  ⚠️ INSUFFICIENT_DATA
  ⚪ NOT_APPLICABLE
- Never turn missing, stale, partial, unavailable or warning evidence into a green status.
- RESPONSE_MODE is authoritative. Follow only MODE_LAYOUT below.
- Keep the full answer under about 220 words unless the user explicitly asks for detail.
- End every answer with exactly this final line:
  🛡️ **Read-only:** No AWS changes executed.
- The final guardrail is plain Markdown: do not prefix it with `>`, do not wrap it in straight or curly quotation marks, and do not append any text after it.

MODE_LAYOUT:
{layout}
"""


CONTROL_S3, CONTROL_SSH = CONTROLS


def _status_text(check: dict[str, Any]) -> str:
    status = check.get("status")
    if status == "COMPLIANT":
        return "✅ COMPLIANT"
    if status == "NON_COMPLIANT":
        count = check.get("affected_resources")
        if not isinstance(count, int) or count < 0:
            raise ValueError("non-compliant evidence count is invalid")
        return f"🔴 NON_COMPLIANT ({count} affected)"
    if status == "INSUFFICIENT_DATA":
        return "⚠️ INSUFFICIENT_DATA"
    if status == "NOT_APPLICABLE":
        return "⚪ NOT_APPLICABLE"
    raise ValueError("unsupported evidence status")


def _check_map(evidence: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    checks = evidence.get("checks")
    if not isinstance(checks, list) or len(checks) != 8:
        raise ValueError("evidence matrix is invalid")
    mapped: dict[tuple[str, str], dict[str, Any]] = {}
    for check in checks:
        key = (check.get("account_alias"), check.get("control"))
        if key in mapped:
            raise ValueError("evidence matrix contains duplicates")
        mapped[key] = check
    expected = {(alias, control) for alias in ALIASES for control in (CONTROL_S3, CONTROL_SSH)}
    if set(mapped) != expected:
        raise ValueError("evidence matrix is incomplete")
    return mapped


def _canonical_answer(user_request: str, evidence: dict[str, Any]) -> str:
    mode = _response_mode(user_request)
    checks = _check_map(evidence)
    lines = [
        "| Account | 🪣 S3 BPA | 🔐 Restricted SSH |",
        "| --- | --- | --- |",
    ]
    for alias in ALIASES:
        lines.append(
            f"| {alias} | {_status_text(checks[(alias, CONTROL_S3)])} | "
            f"{_status_text(checks[(alias, CONTROL_SSH)])} |"
        )

    attention = [
        check for alias in ALIASES for control in (CONTROL_S3, CONTROL_SSH)
        if (check := checks[(alias, control)]).get("status") in ("NON_COMPLIANT", "INSUFFICIENT_DATA")
    ]

    if mode == "STATUS":
        lines.extend([
            "",
            f"{len(attention)} of 8 checks need attention."
            if attention else "All 8 checks are compliant or not applicable.",
        ])
    elif mode == "EXPLAIN":
        lines.extend([
            "",
            "| Needs attention | Why | Affected |",
            "| --- | --- | --- |",
        ])
        for check in attention:
            alias = check["account_alias"]
            control = check["control"]
            label = "S3 BPA" if control == CONTROL_S3 else "Restricted SSH"
            if check["status"] == "INSUFFICIENT_DATA":
                why, affected = "evidence is insufficient.", "Unknown"
            elif control == CONTROL_S3:
                why = "bucket-level Block Public Access is not in the compliant configuration."
                affected = str(check["affected_resources"])
            else:
                why = "unrestricted SSH ingress is present."
                affected = str(check["affected_resources"])
            lines.append(f"| {alias} — {label} | {why} | {affected} |")
    else:
        non_compliant = [check for check in attention if check.get("status") == "NON_COMPLIANT"]
        lines.extend([
            "",
            "| Alias | Control | Evidence | Suggested change | Execution |",
            "| --- | --- | --- | --- | --- |",
        ])
        for check in non_compliant:
            alias = check["account_alias"]
            control = check["control"]
            label = "S3 BPA" if control == CONTROL_S3 else "Restricted SSH"
            guidance = (
                "Bring bucket-level Block Public Access into the compliant configuration."
                if control == CONTROL_S3
                else "Remove unrestricted SSH ingress; if access is required, replace it with an approved source."
            )
            lines.append(
                f"| {alias} | {label} | {_status_text(check)} | {guidance} | 🚫 Not executed |"
            )

    lines.extend(["", "🛡️ **Read-only:** No AWS changes executed."])
    return "\n".join(lines)


def _bounded_model_answer(user_request: str, evidence: dict[str, Any], model_answer: Any) -> str:
    canonical = _canonical_answer(user_request, evidence)
    if isinstance(model_answer, str) and model_answer.strip() == canonical:
        return model_answer.strip()
    return canonical


def answer(
    user_request: str,
    *,
    backend_url: str | None = None,
    harness_arn: str | None = None,
    harness_call: Callable[..., dict[str, Any]] = invoke,
) -> dict[str, Any]:
    backend_url = backend_url or os.environ.get("AWSOPS_CONFIG_BACKEND_URL", "http://127.0.0.1:4313")
    harness_arn = harness_arn or os.environ.get("COMPLIANCE_AGENT_V1_HARNESS_ARN", "")
    evidence = current_evidence(backend_url)
    started = time.monotonic()
    try:
        result = harness_call(
            build_prompt(_request(user_request), evidence),
            harness_arn,
            region=os.environ.get("AWS_REGION", "ap-southeast-1"),
        )
    except Exception:
        _record_harness_result("DEGRADED", round((time.monotonic() - started) * 1000))
        raise
    _record_harness_result("READY", round((time.monotonic() - started) * 1000))
    return {
        "version": 2,
        "agent": "awsops Compliance Agent",
        "answer": _bounded_model_answer(user_request, evidence, result.get("answer")),
        "evidence": {
            "source": evidence["source"],
            "fetched_at": evidence["fetched_at"],
            "aliases": evidence["aliases"],
            "controls": evidence["controls"],
            "checks": evidence["checks"],
            "identifiers_available": False,
        },
        "mutation": False,
    }
