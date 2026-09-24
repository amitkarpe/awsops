"""In-process adapter contract; it is not authentication or a public endpoint.

Call only after native middleware verifies ownership/tenant/action/TTL and the
caller wins the platform's paused-job claim. No provider, executor, browser or
LibreChat dependency is allowed here. Runtime-specific wiring is still pending.
"""
from __future__ import annotations

from dataclasses import dataclass

from awsops.approval.decisions import DecisionError, DecisionReceipt, DecisionStore, NativeBinding


@dataclass(frozen=True)
class RejectedContinuation:
    tool_call_id: str
    reason: str
    receipt: DecisionReceipt

    def resolution(self) -> dict:
        return {self.tool_call_id: {"type": "reject", "reason": self.reason}}


class NativeDecisionAdapter:
    def __init__(self, store: DecisionStore):
        self.store = store

    def after_native_claim(self, *, batch_id: str, scope_hash: str,
                           binding: NativeBinding, decision: str) -> RejectedContinuation:
        """A receipt failure propagates; no continuation or retry is emitted."""
        receipt = self.store.record(batch_id=batch_id, scope_hash=scope_hash,
                                    binding=binding, decision=decision)
        expected = {"reject": "REJECTED", "approve": "APPROVE_BLOCKED"}.get(decision)
        if (type(receipt) is not DecisionReceipt or receipt.outcome != expected
                or receipt.batch_id != batch_id or receipt.scope_hash != scope_hash):
            raise DecisionError("INVALID_RECEIPT_RESPONSE")
        reason = "REJECTED" if receipt.outcome == "REJECTED" else "LIVE_EXECUTION_NOT_AUTHORIZED"
        return RejectedContinuation(binding.tool_call_id, reason, receipt)
