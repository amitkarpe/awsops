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

`issue90-isolated-launcher.sh` is a separate, bounded operator entrypoint for
the exact `/opt/awsops-native-canary` root. After the reviewed bundle and
runtime config are installed, the fixed commands are:

```sh
sudo /opt/awsops-native-canary/awsops/integration/runtime/issue90-isolated-launcher.sh start
sudo /opt/awsops-native-canary/awsops/integration/runtime/issue90-isolated-launcher.sh stop
```

It starts only three uniquely named transient units for MongoDB, the
deterministic local model stimulus, and LibreChat. Each has a 30-minute hard
runtime and is stopped with exact PID, process start-time, and cgroup checks.
The app receives the existing `AWSOPS_NATIVE_CONFIG` and `AWSOPS_READ_CONFIG`
paths and must listen only on `127.0.0.1:4311`; the fixture and database must
listen only on `127.0.0.1:4312` and `127.0.0.1:27111`. Wildcard and extra
listeners fail closed. The UI remains host-local; this launcher creates no
route, public domain, or tunnel. A previously authorized private interactive
path must be independently available before a real human review can occur.

The deterministic fixture can emit only a
`SYNTHETIC_MODEL_STIMULUS_ONLY; HUMAN_DECISION_REQUIRED` canary tool request.
That request is not a decision, authentication, or approval. Only the real
authenticated owner's Reject in the existing UI creates a decision. No
synthetic or automated browser action counts as human evidence. The launcher
does not contact AWS or create cloud resources.
