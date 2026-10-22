# Runtime reproducibility contract

Owner: Issue #56 under roadmap #1.

This directory records the **non-secret** runtime facts needed to rebuild the
accepted NEW `config2` + `sec2` demo without reverse-engineering the retained EC2
filesystem.

## What is canonical

| Runtime | Git source | Local port | Rebuild status |
| --- | --- | ---: | --- |
| `config2` dashboard | `integration/config_dashboard/` | 4313 | canonical in `main` |
| Compliance Agent MCP | `integration/compliance_agent/` | stdio | canonical in `main` |
| `sec2` LibreChat | `librechat-runtime.json` pinned upstream | 4311 | rebuild from upstream pin |
| `sec2` MongoDB | `home/docker-compose.yaml` or persistent host unit | 27111 | reproducible |
| Issue #11 fixture model | PR #13 exact head | 4312 | deferred reference only |

The live EC2 audit found the Issue #11 fixture model still running, but the
accepted read-only Compliance Agent demo does not require it. Its source remains
preserved in draft PR #13 and its launch contract is recorded only so a future
Issue #11 recovery does not depend on `/run/systemd/transient` state.

## Private state that must stay out of Git

Never commit:

- Config target account bindings or aggregator identity;
- Harness ARN or credentials;
- LibreChat `.env` secrets, JWT/session/credential encryption keys;
- MongoDB contents;
- login/browser state, cookies or Playwright storage state;
- TLS private keys or Basic-auth password files;
- raw AWS findings or provider identifiers.

Only the **key names/schema** are versioned in `env/*.example` and
`home/home-demo.env.example`.

## Retained-host service templates

`systemd/` converts the previously host-only/transient startup knowledge into
reviewable source. These files are templates/reference artifacts; Issue #56 does
**not** install, enable, restart or stop services.

- `awsops-config2-app.service` matches the accepted persistent config2 unit.
- `awsops-sec2-db.service` and `awsops-sec2-app.service` capture the persistent
  equivalent of the accepted isolated sec2 db/app launch boundaries.
- `awsops-sec2-model-issue11.service` is explicitly deferred Issue #11-only
  reference and is not part of the Home read-only demo.

## Home-first rule

Normal development and the reconstructed NEW demo run from Home DEV. AWS remains
provider/read evidence where the active Issue allows it; EC2 is not the default
developer workstation.

See `home/README.md` and `docs/architecture/HOME_DEMO_RUNTIME.md`.

## Issue90 isolated activation source contract

The Issue90 runtime-only operator requires a Python interpreter with `boto3`
and `botocore` available. Select only an existing interpreter whose SDK
environment is verified for this operator; the default `/usr/bin/python3`
currently lacks both modules in the Home checkout. If imports are unavailable,
the operator refuses with `BOTO3_RUNTIME_DEPENDENCY_MISSING` before constructing
the provider or making provider calls. Fake-provider tests do not establish
that a live SDK environment is ready.

`issue90-isolated-launcher.sh` is a separate, bounded operator entrypoint for
the exact `/opt/awsops-native-canary` root. After the reviewed bundle and
runtime config are installed, the fixed commands are:

```sh
sudo /bin/bash /opt/awsops-native-canary/awsops/integration/runtime/issue90-isolated-launcher.sh start
sudo /bin/bash /opt/awsops-native-canary/awsops/integration/runtime/issue90-isolated-launcher.sh stop
```

It starts only three uniquely named transient units for MongoDB, the
deterministic local model stimulus, and LibreChat. The migration installs this
script as mode `0644`, so invoke it through `/bin/bash` as shown. Each unit has
a 30-minute `RuntimeMaxSec` process limit and is stopped with exact PID,
process start-time, and cgroup checks. That limit does not stop the EC2 host or
bound instance billing: the outer authorized host window must enforce its
separate 30-minute deadline, invoke `stop`, and verify the instance is stopped.
The app receives the existing `AWSOPS_NATIVE_CONFIG` and `AWSOPS_READ_CONFIG`
paths and must listen only on `127.0.0.1:4311`; the fixture and database must
listen only on `127.0.0.1:4312` and `127.0.0.1:27111`. Wildcard and extra
listeners fail closed. The UI remains host-local; this launcher creates no
route, public domain, or tunnel. A previously authorized private interactive
path must be independently available before a real human review can occur.

### Resuming an already completed d090 migration

The accepted 41-target migration is not replayed. The config-only resume uses
its own `.awsops-issue90-config-resume-v1` journal and exact d090 prestate
hashes. Before any write, run the staged `runtime_config.cjs
preflight-config-resume` with the target source revision and the private binding
and receipt-database baseline hashes. It accepts only the empty/unconfigured or
exact historical/current fixture shape. Then the root installer runs
`isolated_migration.py apply-config-resume`; it installs the runtime config,
TCP-filter launcher, and `SOURCE_REVISION` last. The unchanged
`native_store.cjs` dependency is checked against its d090 hash and is not
replaced. As `ssm-user`, run `runtime_config.cjs resume-config-only` with the
same three pins; it rechecks the native binding/database baselines, writes a
separate native-config backup, updates only `source_revision`, and applies the
YAML transformation using its own versioned backup. The receipt database and
the original 41-target journal/backups remain unchanged.

For rollback, inspect the config-resume journal first. Run
`runtime_config.cjs rollback-config-only` as `ssm-user` to validate both config
backups before restoring YAML and native config. Then run
`isolated_migration.py rollback-config-resume` as root; it prevalidates every
source backup and restores runtime files before returning `SOURCE_REVISION` to
d090. A mixed or unknown state is reported for reconciliation; neither path
replays the original migration or deletes its evidence.

The deterministic fixture can emit only a
`SYNTHETIC_MODEL_STIMULUS_ONLY; HUMAN_DECISION_REQUIRED` canary tool request.
That request is not a decision, authentication, or approval. Only the real
authenticated owner's Reject in the existing UI creates a decision. No
synthetic or automated browser action counts as human evidence. The launcher
does not contact AWS or create cloud resources.

The tracked runtime-only outer operator is `src/awsops/runtime/issue90_operator.py`.
It uses the explicit `amit`/`ap-southeast-1` Boto3 session for exact-ID,
read-only checks of the attached security groups, volumes, address, and subnet
before any lifecycle request. Its private config must pin the SHA-256 of the
four existing activation property snapshots; absent, changed, or mismatching
snapshots refuse before Start. It does not enumerate resources. The native
READY delivery is caller-bound per invocation. CLI callers must provide an
explicit canonical UUID with `--ready-reply-to`; a Python caller may instead
inject a notifier carrying the same `reply_to` binding. Missing, malformed, or
mismatched routing refuses before provider construction. The default adapter
uses the fixed local `/home/dev/.local/bin/codex` executable, a bounded
no-shell queue call, and accepts a receipt only when its thread exactly matches
the supplied UUID. There is no machine-specific default receiver; the actual
Home thread belongs only in the private invocation contract. Receipt checks
reopen the canonical application ledger and do not claim provider readback.
The notifier must deliver a private pointer while the owner window is active;
synthetic fixture stimulus is not an owner decision.

Runtime predecessor evidence supports two explicit contracts. The retained
legacy `previous_window` reference is unchanged. For a completed runtime-only
**prelaunch refusal**, use `format: runtime-only-stopped/v1` with the exact
`run_id`, `instance_id`, prior `operator_source_head`, `result_path` and
`result_sha256`, plus `start_claim`, `stop_claim`, and `cleanup` references
(each exactly `{path, sha256}`). These private, owned files must agree on the
run, target, source, Stop intent, chronology and independently read-back stopped
state. Only the supported readback/probe-refused no-launch outcomes qualify;
unknown outcomes or incomplete cleanup require reconciliation. Do not rewrite
historical results into the legacy format or reset their consumed claims.

Ledger refusal diagnostics retain only production-defined codes and stages.
An empty refusal count object never means an empty ledger: every accepted
refusal still blocks launch and saves a value-free `ssm-refusal` record.

### One-command FILE_LOOKUP diagnostic

`python -m awsops.runtime.issue90_ledger_diagnostic` is a separate, fixed
Issue90 diagnostic entrypoint. It requires `--execute-ledger-diagnostic`,
`--private-config`, `--config-sha256`, and `--request`. The private config reuses
the existing exact LAB binding/property baselines, pins the executing Git HEAD
and genuine latest stopped predecessor, and names fresh exclusive claims.
The request file must match the source-pinned accepted request bytes; the
command, target and Comment are not regenerated for another target/run label.
The actual run ID is separately recorded in local claims/evidence.

Local validation precedes SDK construction. Fresh identity, stopped target,
property and Start/Stop DryRun checks precede Start. The lifecycle has five
active minutes plus ten stop-reserve minutes, including a final SDK-call margin.
Only the pinned 30-second ledger command can be sent. Recognized refusal is a
useful diagnostic result, never permission to launch or repair. Unknown send is
not resent; only acknowledged command readback may be polled. Finally cleanup
attempts exact Stop independently of SSM/evidence/pre-stop-read failures and
requires independent STOPPED readback. Interrupts enter the same cleanup.

There is no launcher, READY notifier, interactive session, forwarding, ledger
provisioning, config mutation or S3 path. Session termination is not applicable.
The USD1 operational estimate within the existing USD100 total authority is not
a hard billing cap. Source acceptance and offline tests are not live permission,
current guest evidence or proof of an actual human Reject. Manager must accept
and merge the exact source before the already-authorized diagnostic window.
