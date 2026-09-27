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
