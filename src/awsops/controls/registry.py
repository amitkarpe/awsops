"""Small control capability registry. Metadata never authorizes execution."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ControlCapability:
    key: str
    resource_type: str
    detect: bool
    explain: bool
    prepare: bool
    remediate: bool
    verify: bool
    requires_human_approval: bool

    @property
    def live_execution_authorized(self) -> bool:
        return False


CONTROLS = {
    "s3_ssl": ControlCapability(
        key="s3_ssl",
        resource_type="AWS::S3::Bucket",
        detect=True,
        explain=True,
        prepare=True,
        remediate=False,
        verify=True,
        requires_human_approval=False,
    )
}


def capability(control_key: str) -> ControlCapability:
    try:
        return CONTROLS[control_key]
    except KeyError as exc:
        raise ValueError("unsupported control") from exc
