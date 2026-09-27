"""Evidence-grounded read-only Compliance Agent for the awsops config2 demo."""
from __future__ import annotations

import json
import os
from typing import Any, Callable

from .config_backend import current_evidence
from .harness_client import invoke


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
    result = harness_call(
        build_prompt(_request(user_request), evidence),
        harness_arn,
        region=os.environ.get("AWS_REGION", "ap-southeast-1"),
    )
    return {
        "version": 2,
        "agent": "awsops Compliance Agent",
        "answer": result["answer"],
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
