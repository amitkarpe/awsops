# DOT cloud pilot — Phase 1

Owning issue: [#73](https://github.com/amitkarpe/awsops/issues/73), including
[the preflight](https://github.com/amitkarpe/awsops/issues/73#issuecomment-5950265934).
Draft delivery: [PR #74](https://github.com/amitkarpe/awsops/pull/74).
Scope: repository and CI only; no merge or live acceptance.

## Proven checkout and environment

- Opened the saved Codex Cloud `awsops` environment at `/workspace/awsops`.
  This was a clean existing checkout, not an agent-performed clone. Initial
  `git status --short --branch` showed only `## work` (no changes).
- Origin: `https://github.com/amitkarpe/awsops.git`.
- Expected, actual starting HEAD and remote `main` all matched
  `22800ab47b8f78a82a86296991d5586ec368d198`; verified with
  `git remote get-url origin`, `git rev-parse HEAD` and
  `git ls-remote origin refs/heads/main` before changes. No mismatch.
- Implementation head: `f3495ae2ed290676261d49bac7c30e5d02551412`.
  The successful bootstrap run tested this code tree; the subsequent default
  run tested this committed head. Later commits only add this evidence document.
  The PR description records the final documentation-inclusive head and its CI
  run; a file cannot contain its own commit hash.
- Read `AGENTS.md`, `CONTEXT.md`, `SPEC.md`, issue/comments and `ROADMAP.md`.
  No repository `.agents/skills` directory or additional nested `AGENTS.md`
  was found; the environment's exposed `.agents` directory had no files.
- Cloud OS: Debian GNU/Linux 13; Python 3.12.14, Node 24.19.0, npm 11.9.0,
  Docker Compose 2.40.3. Existing CI uses Ubuntu, Python 3.12 and Node 24.
  Docker was used only to parse Compose configuration; no containers started.

## Small improvement and bootstrap

`python scripts/cloud_verify.py --bootstrap` runs the existing CI command set,
continues independent checks after failure, reports command exit codes/timings,
and exits nonzero if any required check fails. It requires both native fixtures,
so absence cannot silently remove producer coverage. Existing workflows and
application safety checks are unchanged.

Requirements: Linux, Python 3.12+, Node 24+, npm, Git, Docker Compose, outbound
public GitHub/raw GitHub/npm access, writable workspace and npm cache. Python
contract tests use the standard library and fake SDKs; no boto3, MCP runtime,
Playwright browser install or Python package install is needed for this subset.
Dashboard dependencies belong in `integration/config_dashboard`, not repo root.

Executed full command in this sandbox:

```bash
npm_config_cache=/tmp/awsops-npm-clean-proof python scripts/cloud_verify.py --bootstrap
```

The temporary npm cache was fresh; `npm ci` replaced the dashboard install from
the committed lockfile (208 packages). `home_demo.py prepare` used a fresh
wrapper-owned temporary directory, verified LibreChat
`cdfe54c3498818b21b33fb609fee02f2742b37ea` / `v0.8.8-rc1`, and cleaned that
source checkout afterward. The fixture downloader verified the pinned Git blobs.
Both preparation scripts were inspected before execution: they retrieve public
source, do not connect to Home or AWS, and do not start services.

Subsequent command: `python scripts/cloud_verify.py`. It requests no downloads,
uses installed dependencies/fixtures and explicitly skips source reconstruction.
This is an offline-oriented command set, not an OS-enforced network sandbox.
The unit suite briefly serves synthetic health data on cloud loopback; no
provider request is made. `HOME_DEMO_VALIDATION_OK` in unit output is mocked
contract evidence, not live Home validation.

## Executed results

| Command (repo root unless noted) | Result |
| --- | --- |
| `python scripts/fetch_native_fixture.py` | PASS; both immutable source blobs verified; 0.2 s |
| `npm ci` in `integration/config_dashboard`, writable cache | PASS; clean install, 208 packages; 3.6 s |
| `AWSOPS_REQUIRE_NATIVE_FIXTURE=1 python -m unittest discover -s tests -p 'test_*.py'` | PASS; 161 tests; 14.8 s; includes agent/browser contracts, fake provider boundaries and native subprocess tests |
| Native controller suite within Python tests | PASS; 30 tests, 0 failures, 0 skips |
| `node --test tests/pause_runtime.test.cjs` (explicit count check) | PASS; 13 tests, 0 failures, 0 skips; 3.2 s |
| `node --test tests/demo_cockpit.test.cjs` | PASS; 2 tests, 0 skips; 0.2 s |
| `python scripts/home_demo.py check` | PASS; 0.1 s |
| `docker compose -f integration/runtime/home/docker-compose.yaml config -q` | PASS; 0.1 s; configuration only |
| `python scripts/home_demo.py prepare <fresh-temporary-target>` | PASS; public pinned source reconstruction; 11.4 s |
| `python scripts/home_demo.py verify <same-target>` | PASS; exact commit/release; 0.1 s |
| `npm run validate:pack` in dashboard | PASS; offline pack validation plus 3 tests; 0.3 s |
| `npm run build` in dashboard | PASS; TypeScript check + Vite, 328 modules; 1.7 s |
| `npm run prepare:runtime` in dashboard | PASS; generated artifact read/traversal permissions; 0.1 s |
| Full wrapper with `--bootstrap` | PASS; `CLOUD_VERIFY PASS failures=0`; approximately 33 s |
| Default wrapper without `--bootstrap` | PASS; `CLOUD_VERIFY PASS failures=0`; downloads/source reconstruction explicitly skipped |
| `git diff --check` | PASS |

### Failed attempts and recovery

- Initial `npm ci --prefix integration/config_dashboard`, then the first wrapper
  install, failed with exit 254 / `ENOENT` creating
  `/home/agent/.npm/_cacache`. The default home cache was outside writable roots.
  Tarball/cleanup warnings followed this failure. Selecting a new `/tmp` cache
  resolved it without changing versions, lockfile, permissions or access controls.
- First wrapper unit run: 161 tests, one failure in
  `test_explicit_inputs_and_private_output_are_required`. Cloud `umask 0077`
  filtered `mkdir(mode=0755)` to 0700, invalidating the deliberately unsafe
  directory fixture. The fixture now explicitly `chmod(0755)` before asserting
  rejection. Production validation remains unchanged. The rerun passed with the
  original restrictive umask. This is a test portability correction, not a waiver.
- First wrapper correctly returned `CLOUD_VERIFY FAIL failures=2`; independent
  checks still ran. No failed result was relabeled as passing.
- `gh api user`, CLI PR creation (GraphQL), and CLI Actions run listing returned
  `Forbidden`. Existing environment Git access successfully read and pushed the
  branch; the already-connected GitHub app read issue/comments, created the draft
  PR and inspected CI. No credential was printed, copied, created or changed.
  Connector argument-schema errors were corrected using the required field names.

## Capability classification and explicit skips

“Cloud PASS” below means executed repository evidence, not live acceptance.
CI results are tracked separately by exact head in the PR.

| Capability | Codex Cloud | GitHub Actions | Home required | AWS auth required |
| --- | --- | --- | --- | --- |
| Repo edit/build/unit tests | PASS | Existing CI coverage | No | No |
| config2 static/build tests | PASS, including artifact permissions | Existing CI coverage | No | No |
| Compliance Agent contract tests | PASS | Existing Python suite coverage | No | No |
| Pinned fixture and Home source/artifact preparation | PASS | Existing CI coverage | No; name is incidental | No |
| Playwright/browser acceptance | SKIP; only contract tests ran | No live browser job in current workflow | Current accepted path needs private owner session/services; portability unproven | Current end-to-end evidence needs provider access in its backend |
| Tailscale/Funnel lifecycle | SKIP; no commands run | No lifecycle job | Current supported route is Home-owned | No AWS auth; separate tailnet authority required |
| Four-account Config readback | SKIP | No live readback job | Current setup is Home; not inherently required by provider API | Yes; scoped identity and separate authorization |
| Conformance Pack deployment | SKIP; offline template validation only | Offline validation only | Not inherently required | Yes; separate mutation gate remains closed |
| Remediation canary | SKIP; no execution | No live execution job | Portability not established | Yes; unauthorized in this pilot |

Also skipped: `home_demo.py validate`, public lifecycle commands, actual browser
runner, service/container startup, LibreChat runtime dependency install and full
application startup, live provider reads, IAM/OIDC, DNS/TLS/public access,
deployments and merge. These are outside Phase 1. No Home/office execution or
fallback occurred. No AWS call, secret/private state access or cloud mutation
was needed. Public downloads and authenticated GitHub publication did require
outbound Internet; existing GitHub platform authentication was sufficient.

## Friction, CI and next step

Work began approximately 10:28 UTC on 2026-10-02; environment readiness took about
9 seconds. First fixture/install attempt was at 10:29:47. Full successful
bootstrap completed by 10:33, so setup/debug friction was approximately 3 minutes
(about 5 minutes including instruction/source inspection and implementation).
Successful full loop runtime was approximately 33 seconds. CI/publication and
final documentation took additional time recorded in the final handoff.

Implementation CI: [run 36996116114](https://github.com/amitkarpe/awsops/actions/runs/36996116114)
for implementation head `f3495ae2ed290676261d49bac7c30e5d02551412`: **SUCCESS**.
The `test` job and every applicable step passed, including fixture fetch, unit
tests, cockpit, runtime source preparation/verification and config2 artifact.
Final documentation-inclusive CI and exact head are recorded in PR #74's body.

Accidental dependencies: writable home npm cache, umask-sensitive test fixtures,
stale README Node version, and Home naming on public source preparation. This
pilot removes the test assumption, corrects the version, and documents the cache
requirement. Genuine current integration dependencies are private authenticated
services/browser evidence, the Home-owned public route and scoped AWS identity.
They cannot be replaced by a green contract/build run.

Next bounded step after G/Dot review: assess Phase 2 CI parity using this wrapper
and these results, with exact-head CI required. Do not introduce OIDC or migrate
live/browser acceptance as part of this PR. Phase 1 stays draft and unmerged.

HANDOFF: DOT
