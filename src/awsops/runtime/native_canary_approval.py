"""Internal adapter for a trusted native owner-decision callback.

This is not an endpoint, identity verifier, or runtime installation. The host
must authenticate the owner, bind the native principal to the frozen canary
principal, and win its paused-job compare-and-set before constructing the
immutable context. No current host integration provides that callback, so the
production operator remains fail-closed until one is mounted and reviewed.

The existing application ledger is the single-use packet claim and audit
record. This adapter does not consume the reject-only DecisionStore, whose
APPROVE_BLOCKED result must remain non-dispatching.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from awsops.application.s3_canary_approval import (
    CanaryApprovalApplication,
    FrozenCanaryAuthority,
    OwnerApprovalPacket,
    OwnerApprovalVerifier,
)
from awsops.domain.models import canonical_digest, require_text

_BATCH = re.compile(r"batch-canary-[a-f0-9]{32}")
_HEX64 = re.compile(r"[a-f0-9]{64}")
_CANARY_TOOL = "approve_s3_canary_once"


@dataclass(frozen=True, repr=False)
class NativeCanaryBinding:
    principal_id: str
    tenant_id: str
    conversation_id: str
    action_id: str
    generation_id: str
    tool_call_id: str
    tool: str = _CANARY_TOOL

    def __post_init__(self) -> None:
        for value in (self.principal_id, self.tenant_id, self.conversation_id,
                      self.action_id, self.generation_id, self.tool_call_id):
            require_text(value, r"[A-Za-z0-9_.:-]{1,128}", "native identity")
        if self.tool != _CANARY_TOOL:
            raise ValueError("UNSUPPORTED_NATIVE_CANARY_TOOL")

    def digest(self) -> str:
        return canonical_digest({"principal_id": self.principal_id, "tenant_id": self.tenant_id,
                                 "conversation_id": self.conversation_id, "action_id": self.action_id,
                                 "generation_id": self.generation_id, "tool_call_id": self.tool_call_id,
                                 "tool": self.tool})


@dataclass(frozen=True, repr=False)
class NativeCanaryDecision:
    """Frozen server context returned by the native gate after the winning CAS.

    Native identity is kept as identity, never converted into an owner digest by
    this caller-facing structure. A separate trusted owner verifier must map it
    to the frozen packet principal. The host gate produces this value from
    req.user and the exact running generation; callers cannot assert a claim
    boolean to manufacture it.
    """

    batch_id: str
    authority_digest: str
    scope_digest: str
    source_revision: str
    principal_id: str
    tenant_id: str
    decision: str
    native_binding: NativeCanaryBinding
    decided_at: int
    expires_at: int

    def __post_init__(self) -> None:
        if type(self.native_binding) is not NativeCanaryBinding:
            raise ValueError("INVALID_NATIVE_BINDING")
        require_text(self.batch_id, _BATCH.pattern, "canary batch")
        for value, label in (
            (self.authority_digest, "authority digest"),
            (self.scope_digest, "scope digest"),
            (self.native_binding.digest(), "native binding digest"),
        ):
            require_text(value, _HEX64.pattern, label)
        require_text(self.source_revision, r"[a-f0-9]{40}", "source revision")
        if self.decision not in ("approve", "reject"):
            raise ValueError("UNSUPPORTED_DECISION")
        require_text(self.principal_id, r"[A-Za-z0-9_.:-]{1,128}", "native principal")
        require_text(self.tenant_id, r"(?:system:single-tenant|tenant:[A-Za-z0-9_.:-]{1,128})", "native tenant")
        if (type(self.decided_at) is not int or type(self.expires_at) is not int
                or self.decided_at < 0 or self.expires_at <= self.decided_at):
            raise ValueError("INVALID_NATIVE_DECISION_CONTEXT")

    @classmethod
    def from_host_callback(cls, callback: dict, authority: FrozenCanaryAuthority,
                           *, received_at: int) -> "NativeCanaryDecision":
        """Bind the native gate's post-CAS handoff to the saved packet.

        This validates source output; it is not owner authentication. Production
        still needs an independent OwnerApprovalVerifier before application use.
        """
        if type(callback) is not dict or callback.get("version") != 1 or callback.get("operation") != "native_canary_choice":
            raise ValueError("INVALID_NATIVE_CALLBACK")
        binding = callback.get("binding")
        expected = {"principal_id", "tenant_id", "conversation_id", "action_id", "generation_id", "tool_call_id", "tool"}
        if type(binding) is not dict or set(binding) != expected:
            raise ValueError("INVALID_NATIVE_CALLBACK")
        if binding.get("tool") != _CANARY_TOOL:
            raise ValueError("UNSUPPORTED_NATIVE_CANARY_TOOL")
        if (callback.get("batch_id") != authority.batch_id
                or callback.get("scope_digest") != authority.scope_digest
                or callback.get("authority_digest") != authority.digest
                or callback.get("expires_at") != authority.decision_expires_at
                or callback.get("decision") not in ("approve", "reject")
                or callback.get("expires_at") <= received_at):
            raise ValueError("NATIVE_OWNER_DECISION_BINDING_MISMATCH")
        native = NativeCanaryBinding(
            binding["principal_id"], binding["tenant_id"], binding["conversation_id"],
            binding["action_id"], binding["generation_id"], binding["tool_call_id"], binding["tool"],
        )
        return cls(
            batch_id=authority.batch_id, authority_digest=authority.digest,
            scope_digest=authority.scope_digest, source_revision=authority.source_revision,
            principal_id=binding["principal_id"], tenant_id=binding["tenant_id"],
            decision=callback["decision"], native_binding=native,
            decided_at=received_at, expires_at=callback["expires_at"],
        )

    @property
    def digest(self) -> str:
        """Stable private packet proof reference; never authentication alone."""
        return canonical_digest({
            "batchId": self.batch_id,
            "authorityDigest": self.authority_digest,
            "scopeDigest": self.scope_digest,
            "sourceRevision": self.source_revision,
            "principalId": self.principal_id,
            "tenantId": self.tenant_id,
            "decision": self.decision,
            "nativeBindingDigest": self.native_binding.digest(),
            "decidedAt": self.decided_at,
            "expiresAt": self.expires_at,
        })


class NativeCanaryApprovalAdapter:
    """Bridge one immutable host callback into the app's atomic one-use ledger.

    `verifier` must be provided by a mounted independently trusted host. With
    none, the existing application's TRUSTED_HUMAN_APPROVAL_BINDING_REQUIRED
    denial remains in force. This adapter never enables simulation or changes
    the live operator's default-deny path.
    """

    def __init__(self, application: CanaryApprovalApplication,
                 verifier: OwnerApprovalVerifier | None = None):
        self.application = application
        self.verifier = verifier

    def _bound_application(self, context: NativeCanaryDecision) -> tuple[CanaryApprovalApplication, OwnerApprovalPacket]:
        if type(context) is not NativeCanaryDecision:
            raise ValueError("INVALID_NATIVE_CALLBACK")
        authority, _saved = self.application._load_authority(context.batch_id)
        self.application._assert_current_authority(authority)
        if (context.authority_digest != authority.digest
                or context.scope_digest != authority.scope_digest
                or context.source_revision != authority.source_revision
                or context.expires_at > authority.decision_expires_at):
            raise ValueError("NATIVE_OWNER_DECISION_BINDING_MISMATCH")
        packet = OwnerApprovalPacket(
            packet_id="native-" + context.digest[:32],
            authority_digest=authority.digest,
            principal_binding_digest=authority.principal_binding_digest,
            decision="APPROVE_ONCE" if context.decision == "approve" else "REJECT",
            issued_at=context.decided_at,
            expires_at=authority.lifecycle_expires_at,
            proof=context.digest,
        )
        bound = CanaryApprovalApplication(
            self.application.path,
            self.application.binding,
            source_revision=self.application.revision,
            source_version=self.application.version,
            adapter_factory=self.application.adapter_factory,
            mode=self.application.mode,
            verifier=self.verifier,
            clock=self.application.clock,
        )
        return bound, packet

    def decide(self, context: NativeCanaryDecision) -> dict:
        application, packet = self._bound_application(context)
        return application.decide(packet)

    def cleanup(self, context: NativeCanaryDecision) -> dict:
        application, packet = self._bound_application(context)
        return application.cleanup(packet)

    def receipt(self, context: NativeCanaryDecision) -> list[dict]:
        application, packet = self._bound_application(context)
        return application.receipt(packet)

    def audit(self, context: NativeCanaryDecision) -> dict:
        application, packet = self._bound_application(context)
        return application.audit(packet)
