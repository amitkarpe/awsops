# Cloud CI parity — Roadmap v3 M1

Owner: [#77/M1](https://github.com/amitkarpe/awsops/issues/77), implementing the
Phase 2 direction from [#73](https://github.com/amitkarpe/awsops/issues/73).
Delivery: [draft PR #78](https://github.com/amitkarpe/awsops/pull/78).
Repository/CI only; no merge or live acceptance is part of this task.

## Revisions and clean environment

On 2026-10-02, verified origin `https://github.com/amitkarpe/awsops.git`, merged
PR #76, and current remote main:
`2ffbfec4f01ccc804708237eccb448b4c405a5b2`. No base mismatch or competing M1 PR.
Issue #77 already contains M1 intent, acceptance and the explicit GO comment;
it is reused rather than duplicated. PR #74/#76 are not reimplemented.

The same approved Codex Cloud environment remained available. The retained
worktree was clean and preserved. Created `/workspace/awsops-ci-parity` from
fetched main with `git worktree add -b dot/77-ci-parity ... origin/main`.
Reviewed the repository router and durable instructions; AGENTS/CONTEXT/SPEC/
ROADMAP were unchanged from the previously read checkout. #77 and its current
comments define this bounded work; #62 retains AWS mutation authority.

Implementation commit: `fbdab2dbaca57c6f5c2fca629c6a1dfb73dd75fa`.
A second detached worktree, `/workspace/awsops-phase2-proof`, was created at this
commit. Before bootstrap, verified a clean Git status and absence of all three:
`artifacts/native-upstream`, dashboard `node_modules`, dashboard `dist`.
No Home files or existing installed project dependencies were copied.
The final PR head adds only this evidence document; its exact SHA and CI run
are recorded in the PR body to avoid a self-referential commit hash.

Toolchain: Debian 13, Python 3.12.14, Node 24.19.0, npm 11.9.0,
Docker Compose 2.40.3. CI retains Ubuntu, Python 3.12, Node 24, the existing
`test` job name, ten-minute timeout and contents-read permissions. GitHub PR
CI validates the merge ref associated with the recorded head; it is not a
merge of the draft PR into main.

## One required command

```bash
npm_config_cache=/tmp/awsops-phase2-clean-npm python scripts/cloud_verify.py --bootstrap
```

GitHub Actions calls `python scripts/cloud_verify.py --bootstrap` directly.
The npm cache override is only for this sandbox's writable-root constraint;
Actions has a writable normal npm cache. No redundant workflow command list
remains. The wrapper owns the meaningful contract in both environments:

- public source fixture fetch with immutable Git-blob verification;
- clean locked dashboard install (`npm ci --no-audit`);
- explicit `npm audit --audit-level=high`;
- Python/native contracts, cockpit projection and runtime prerequisites;
- Compose configuration parsing and pinned LibreChat source prepare/verify;
- dashboard lint, Conformance Pack validation, TypeScript/Vite build and
  generated artifact read/traversal permissions.

Audit policy: high/critical findings or audit errors make verification fail.
Lower-severity advisories are still printed; a passing gate is not a claim of
zero vulnerabilities or security-clean software. No audit fix or upgrade runs.
Install's implicit audit is disabled to avoid duplicate/optional audit behavior;
the explicit audit is required even if ambient npm configuration disables
install-time auditing. Dependencies/lockfile are unchanged by M1.

`python scripts/cloud_verify.py` without `--bootstrap` remains a useful local
iteration mode: lint/contracts/build run, while public downloads, online audit
and source reconstruction are explicitly SKIP. It is not full CI parity or a
network-enforced sandbox. The full command needs public GitHub/raw GitHub/npm
network access; it requires no private secret or AWS identity.

## Executed evidence

Baseline at exact main: original `cloud_verify.py --bootstrap` passed from the
first clean worktree; separate `npm run lint` passed (exit 0). No baseline
lint/build/test failure was found. Existing fixture/source preparation scripts
were inspected previously and remain unchanged: public source retrieval only,
not Home execution, AWS calls, container/service startup or browser acceptance.

At the implementation commit, executed the full command above from the second
clean worktree. Set `GITHUB_STEP_SUMMARY=/tmp/awsops-phase2-clean-summary.md`
to inspect the same sanitized summary mechanism used in Actions.

| Command/check | Result |
| --- | --- |
| `python scripts/fetch_native_fixture.py` | PASS; both pinned fixtures verified |
| `npm ci --no-audit` (dashboard) | PASS; fresh locked install, 3.6 s |
| `npm audit --audit-level=high` (dashboard) | PASS; exit 0, zero vulnerabilities reported at execution time |
| `AWSOPS_REQUIRE_NATIVE_FIXTURE=1 python -m unittest discover -s tests -p 'test_*.py'` | PASS; 161 tests, 14.7 s; controller sub-suite 30/30, zero skipped |
| `node --test tests/demo_cockpit.test.cjs` | PASS; 2 tests |
| `python scripts/home_demo.py check` | PASS |
| `docker compose -f integration/runtime/home/docker-compose.yaml config -q` | PASS; no containers started |
| `python scripts/home_demo.py prepare <fresh-temp-target>` and `verify <same-target>` | PASS; immutable LibreChat source, prepare 7.8 s |
| `npm run lint` (dashboard) | PASS; exit 0, 1.3 s |
| `npm run validate:pack` (dashboard) | PASS; validator and 3 tests |
| `npm run build` and `npm run prepare:runtime` (dashboard) | PASS; TypeScript/Vite and asset permissions |
| Full wrapper | PASS; exit 0, `CLOUD_VERIFY PASS failures=0`, about 31 s |
| Default wrapper without `--bootstrap` | PASS; lint/contracts/build ran, online audit/downloads/source reconstruction explicitly SKIP |
| YAML parse / CI entrypoint inspection | PASS; one run step, exactly the canonical bootstrap command |
| `git diff --check` | PASS |

A one-off synthetic failure check mocked subprocess results for audit and lint
separately. Each caused exit 1 and a FAIL row/overall FAIL in the summary;
independent build checks were still attempted. No advisory payload was executed,
no live audit failure was manufactured, and these synthetic checks are not live
service acceptance. No new tests were added for this small orchestration change.

The Actions job summary contains only fixed check labels and result statuses,
including skipped boundary reasons. Raw child output, credentials and private
state are never copied into that summary. Full public-safe command output stays
in normal CI logs; no additional artifact retention or service is introduced.
A summary write error also fails the command rather than hiding evidence loss.

Implementation CI: [run 37009625151](https://github.com/amitkarpe/awsops/actions/runs/37009625151): **SUCCESS**.
Final documentation-inclusive CI outcome, exact head and run link are maintained
in PR #78's body. Acceptance must use that final result, not assume it from a
local PASS. The roadmap's later milestones are not closed by this M1 PR.

## Explicitly outside cloud acceptance

- Actual Playwright/owner-login/browser journeys: only existing contract tests
  run; real private services, sessions and evidence remain separate. Mock/static
  browser migration belongs to #77 M2, not this change.
- Home runtime validation and Tailscale/Funnel lifecycle: not executed.
- Four-account provider readback: no AWS calls or AWS authentication used.
- IAM/OIDC, Config Pack deployment, remediation, DNS/TLS/public exposure,
  retained hosts and all deployment operations: not executed or authorized here.
- Deferred native Reject #11/#13 remains deferred. Native offline contracts are
  preserved without activating that canary.
- CI self-acceptance: wrapper explicitly delegates exact-head CI verification
  to the external PR run; its own local PASS cannot certify that run.

No Home/office fallback, private secret access, AWS credential, AWS mutation,
new public surface or merge occurred. Existing Git transport/connected GitHub
app supplied repository publication and CI readback without credential changes.
Owner review is the next gate for this draft. Any next M2/browser or AWS milestone
requires its own bounded scope; M1 does not expand authority.

HANDOFF: DOT
