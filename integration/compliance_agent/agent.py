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


def build_prompt(user_request: str, evidence: dict[str, Any]) -> str:
    request = _request(user_request)
    mode = _response_mode(request)
    packet = json.dumps(evidence, separators=(",", ":"), sort_keys=True)
    return f"""USER_REQUEST:
{request}

RESPONSE_MODE:
{mode}

AUTHORITATIVE_EVIDENCE_JSON:
{packet}

RULES:
- Answer only from AUTHORITATIVE_EVIDENCE_JSON.
- This Issue #39 migration slice is read-only. Never claim that a change was applied, approved, executed or verified.
- You may answer current status, explain one current finding, and provide a no-change remediation plan.
- Name the registered LAB aliases and exact supported controls when relevant.
- Missing, partial, stale or unavailable evidence is not compliant evidence.
- affected_resources is an aggregate count only; no resource or account identifiers are available.
- For S3 NON_COMPLIANT, say only that bucket-level Block Public Access should be brought into the compliant configuration.
- For restricted SSH NON_COMPLIANT, say only that unrestricted SSH ingress should be removed and, if access is still required, replaced with an approved source.
- AWS Config is asynchronous evidence. Do not infer exposure, exploitability, activity, data sensitivity, authentication behavior, or unrelated controls.
- Do not invent identifiers, policies, ports, CIDRs, resource names or implementation details.
- If asked to fix/apply/remediate now, provide a plan only and state that no change is executed in this migration slice.

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
  🔴 NON_COMPLIANT (include the aggregate affected_resources count when present)
  ⚠️ INSUFFICIENT_DATA
  ⚪ NOT_APPLICABLE
- Never turn missing, stale, partial, unavailable or warning evidence into a green status.
- RESPONSE_MODE is authoritative. Produce only the layout for that one mode; never combine modes.
- STATUS: after the matrix, add at most one short summary sentence. Do not include attention or plan tables.
- EXPLAIN: after the matrix, add exactly one compact table:
  | Needs attention | Why | Affected |
  Include only evidence-backed NON_COMPLIANT or insufficient-data items. Use aliases and aggregate counts only.
  Do not include a remediation-plan table or suggested changes.
- PLAN: after the matrix, add exactly one compact table:
  | Priority | Control | Suggested change | Execution |
  Use only the bounded S3 BPA / restricted-SSH guidance above. Every Execution cell must be "🚫 Not executed".
  Do not include a separate attention/explanation table.
- Keep the full answer under about 220 words unless the user explicitly asks for detail.
- End every answer with exactly:
  > 🛡️ **Read-only:** No AWS changes executed.
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
