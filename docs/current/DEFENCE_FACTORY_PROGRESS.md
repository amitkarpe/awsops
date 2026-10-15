# Defence Factory current progress

15 October 2026. Issue90 owns this delivery; Dot implements directly.

## Accepted source

PR91/92 merged the shared contract, bounded synthetic CSV/JSON intake, candidate
control catalog, immutable offline scope and non-executing approval seam. Existing
synthetic intake/freeze/Reject checks pass. Imported or MOCK data cannot authorize
REAL execution; unknown/partial evidence is never converted into compliance.
The existing #86 Config read proof is reused, not rerun.

## Current design review

PR93 supersedes the former five-action S3-only proposal with one reusable personal-LAB
PowerUserAccess pattern behind a narrow OIDC controller and registered dispatcher.
Read the [sanitized review packet](../proposals/defence-lab-execution/README.md).
Detailed source/tests and exact bindings are owner-private. 75 local checks pass;
AWS policy simulation and actual effective access are NOT_VERIFIED.

The earlier connection-expiry note and narrow installation request are superseded.
The remaining prerequisite is approved non-root private target/effective-policy
verification, then one exact revised installation-only decision. Source merge is
not AWS authorization. IAM installation and REAL dispatch remain HELD.

No AWS call, resource creation, public-access change or Issue89 mutation occurred
in this design revision. No new infrastructure cost. Future API costs are not assumed
free; USD10 total experiment limit requires preflight and is not enforced by alerts.
Companion MOCK GUI/source acceptance remains separate from actual viewer and REAL
provider evidence. The roadmap is not fully live-complete.
