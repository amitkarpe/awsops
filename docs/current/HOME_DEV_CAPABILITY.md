# Home DEV capability

Verified: 2026-09-28

This is the public-safe capability record for Amit's Home development workstation.
It contains no network addresses, keys, credentials, private identifiers, or secret values.

## Host baseline

- Native Ubuntu 24.04 LTS on x86-64 desktop hardware.
- 8 logical CPUs, 31 GiB RAM, and sufficient free local storage for the Home demo.
- Git 2.43, Python 3.12, Node.js 24, npm 11, Docker Engine 29, and Docker Compose v2.
- AWS CLI v2 is installed in the owner-local tool path.
- GitHub CLI and Google Chrome are available.

## Issue #56 runtime result

- PR #58 uses a separate clean checkout; the pre-existing unrelated Home checkout remains untouched.
- The pinned LibreChat source reconstructs from GitHub without retained-EC2 files.
- The isolated MongoDB binds to loopback only.
- Config2 builds and serves on loopback only.
- Owner-private runtime values live outside Git under the documented private config directory.
- Read-only config2 evidence is READY, non-partial, and contains exactly four aliases by two controls.

## Boundaries

- Never copy retained-host environment files, databases, certificates, cookies, browser state, or credentials.
- Keep runtime secrets and AWS profile configuration outside this public repository.
- Preserve unrelated Home checkouts and worktrees.
- Public tunnel work starts only after local M2/M3 acceptance.
