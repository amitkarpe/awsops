# AWS Resources

> KISS public ledger. **Canonical account names are `amit` and `vagent`.**
> Raw AWS account IDs and provider identifiers stay out of this public repository.

- Latest bounded read: `2026-10-21` (`amit` only, personal LAB / `ap-southeast-1`; Cost Explorer and Pricing used documented global endpoints)
- Scope: two project-tag filters and the exact tagged retained host; not an account-wide resource sweep
- `amit` Cost Explorer period: `2026-10-01..2026-10-21` (partial month; AWS marked it Estimated; credits/refunds excluded)
- `vagent` resource and cost facts remain historical from `2026-09-27/28`; no `vagent` profile or data was refreshed
- Current rule: **look at the red/high-cost tables first**
- **Protection rule (2026-09-27): legacy Lightsail and the `vagent` retained `t3.small` are DO NOT TOUCH.** Read-only inspection is allowed; stop/start/terminate/delete/resize/repurpose/tag/IAM/network changes require a new explicit user authorization.

## 🔴 Cost watch — check this first

| Priority | Account | Resource / service | State | Cost evidence | Action |
| --- | --- | --- | --- | ---: | --- |
| 1 | **amit** | **EC2 - Other (account-wide)** | not attributed to one resource | **USD 7.20 MTD; Estimated period** | **Review account evidence only; no cleanup or attribution** |
| 2 | **amit** | **Amazon Lightsail** | legacy instances remain protected | **USD 6.50 MTD; Estimated period** | **DO NOT TOUCH** |
| 3 | **amit** | **Amazon EC2 - Compute (account-wide)** | tagged retained host is stopped | **USD 6.01 MTD; Estimated period** | Do not attribute account charges to one host; no start/stop/resize |
| 4 | **vagent** | **EC2 t3.small** | last reported running 2026-09-27; not refreshed | Historical report: **USD 0.00 MTD** | **DO NOT TOUCH; no vagent read was made** |

## Account cost summary

| Account | Cost Explorer MTD | Current inventory signal | What to check first |
| --- | ---: | --- | --- |
| **amit** | **USD 29.52 estimated** | 21 `aws-secops` and 1 `awsops` project-tagged resources; one exact retained host stopped | **account-wide cost; not all attributed to awsops** |
| **vagent** | **USD 0.00 reported 2026-09-27; stale** | Historical 2026-09-27/28 inventory only | **protected host + retained 100-bucket fleet; no refresh** |

> Cost Explorer is account/service billing evidence, not proof that every dollar belongs to `awsops` or `aws-secops`. The current `amit` period is partial and AWS marked it Estimated. A reported zero does not mean a running resource is guaranteed to be free.

### `amit` top billed services this month

| Service | MTD USD (AWS marked current period Estimated) |
| --- | ---: |
| **EC2 - Other** | **USD 7.20** |
| **Amazon Lightsail** | **USD 6.50** |
| **Amazon EC2 - Compute** | **USD 6.01** |
| **Amazon Virtual Private Cloud** | **USD 4.84** |
| Tax | USD 2.44 |
| Amazon Route 53 | USD 0.65 |
| AWS Key Management Service | USD 0.65 |
| AWS Config | USD 0.56 |
| AWS Secrets Manager | USD 0.26 |
| AWS Cost Explorer | USD 0.25 |
| Amazon Bedrock AgentCore | USD 0.06 |
| Amazon Simple Storage Service | USD 0.05 |

## 🔴 EC2 / always-on compute

Always-on compute is intentionally separated because it is the first cost lever to check.

| Account | EC2 name | Project | Compute | State | Age | Estimated monthly | Decision |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| **amit** | **`agentcore-issue19-librechat-poc-r01`** | shared-runtime | **`t3.medium`** | **stopped (observed 2026-10-21)** | prior age evidence retained; not recalculated from restart time | stopped instance; account-level EC2 costs are not attributable to this host | **KEEP type if reactivated; no resize** |
| **vagent** | **`seccop-project1-old-ami-host-r01`** | Security Copilot | **`t3.small`** | last reported running 2026-09-27; not refreshed | historical age only | historical EST ~USD 19.27/mo list-price; not refreshed | **RETAIN / DO NOT TOUCH** |

## 2026-10-21 bounded read-only refresh

The live resource-tag read used only the explicit `amit` profile and `ap-southeast-1` project-tag filters. It returned 21 `aws-secops` and 1 `awsops` tagged resources. These are project-tag matches, not a full account inventory; untagged dependencies and other accounts were not searched.

| Project | Resource class | Count | TTL-derived disposition |
| --- | --- | ---: | --- |
| aws-secops | AWS Config rule | 2 | REVIEW |
| aws-secops | AgentCore Gateway | 1 | REVIEW (expired TTL; ownership not screened) |
| aws-secops | AgentCore Harness | 3 | RETAIN |
| aws-secops | AgentCore Policy engine | 1 | REVIEW (expired TTL; ownership not screened) |
| aws-secops | AgentCore Runtime | 2 | RETAIN |
| aws-secops | AgentCore workload identity | 1 | RETAIN |
| aws-secops | CloudFormation stack | 1 | RETAIN |
| aws-secops | CloudWatch log group | 2 | REVIEW (expired TTL; ownership not screened) |
| aws-secops | CodeBuild project | 1 | RETAIN |
| aws-secops | Lambda function | 3 | REVIEW (expired TTL; ownership not screened) |
| aws-secops | S3 bucket | 1 | RETAIN |
| aws-secops | S3 bucket | 1 | REVIEW |
| aws-secops | Security Group | 1 | REVIEW (expired TTL; ownership not screened) |
| aws-secops | Security Group rule | 1 | REVIEW (expired TTL; ownership not screened) |
| awsops | Secrets Manager resource | 1 | RETAIN |

Expired TTL is a review signal only. These rows were not checked against the private protected Issue #89 mapping, so the report does not imply they are safe cleanup candidates. Ownership and protection decisions override tags. No cleanup or deletion was authorized or performed.

The exact retained `amit` EC2 host was read as **stopped, `t3.medium`**. CloudWatch returned 13 hourly datapoints in the 14-day window; their mean was 2.31% and maximum 45.78%. That sparse set is not a representative full-window workload sample. Current Linux/shared Singapore On-Demand price was USD 0.0528/hour, or USD 38.54 under a 730-hour assumption; this is a list-price reference, not actual host spend, and the host is stopped. The 2026-09-25 memory/swap snapshot remains the sizing basis: keep `t3.medium` if the host is separately reactivated; no resize is authorized.

The account-level `amit` Cost Explorer read covered 2026-10-01 through 2026-10-21 (end exclusive 2026-10-22), excluded Credits and Refunds, and was marked Estimated by AWS. The grouped UnblendedCost total was USD 29.52. It is account baseline, not project attribution or cumulative Issue #90 experiment spend. The `vagent` cost and resource observations above remain historical; no vagent profile was used.

## Historical `amit` host metrics (2026-09-25)

- Memory snapshot: **3.74 GiB total**, **2.05 GiB available**, **no swap**.
- Main retained services: LibreChat ~623.5 MiB, Ops service ~215.8 MiB, MongoDB ~148.6 MiB.
- `t3.small` would leave only about **0.31 GiB theoretical RAM headroom** at the sampled working set.
- These are historical guest/service facts; the stopped host was not booted for a new sample.

### Disk expansion completed

| Item | Before | After |
| --- | ---: | ---: |
| EBS gp3 volume | 20 GiB | **30 GiB** |
| Root filesystem | 18.3 GiB | **28 GiB** |
| Root filesystem used | 92% | **60%** |
| Retained services | active | **active** |

The partition and ext4 filesystem were grown online. No instance stop/restart or instance-type change occurred.
Approximate incremental gp3 cost: **~USD 0.96/month**.

## Historical 2026-09-27 read-only audit

| Account | Live finding | Decision |
| --- | --- | --- |
| **amit** | 1 running t3.medium; 30 GiB encrypted gp3; 18 S3 buckets; 140 tagged resources | **RETAIN** runtime; legacy Lightsail **DO NOT TOUCH** |
| **vagent** | 1 running t3.small with public IPv4; 20 GiB encrypted gp3; 0 Elastic IPs; 109 S3 buckets; 219 tagged resources | host **DO NOT TOUCH**; bucket fleet **REVIEW** |

Direct vagent host dependencies observed: **1 ENI, 1 security group, 1 instance profile / 1 role**. The ENI is untagged; no mutation or cleanup was performed.


## ✅ 2026-09-28 Home cutover

- The exact retained `amit` host was verified by account alias, Region, Name,
  instance type and current provider state before the stop.
- One encrypted 30 GiB gp3 volume remains attached and one Elastic IP remains
  associated. Nothing was terminated, detached, released or deleted.
- The instance reached `stopped`. Git plus the Home rebuild path are the NEW
  demo source of truth; stopped EBS is recovery state only.
- After the stop, the Home HTTPS sec2 tunnel remained healthy, config2 remained
  READY/non-partial at four aliases and eight checks, and the accepted remote
  Status / Explain / no-change Plan proof remained valid.
- Legacy Lightsail and `vagent` were untouched.

## Historical full resource ledger (2026-09-28 snapshot)

| Project | Account | Name | Resource class | Qty | State | Age | Purpose | Cost | Decision | Evidence |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| shared-runtime | **amit** | `agentcore-issue19-librechat-poc-r01` | EC2 retained demo host | 1 | **stopped** | 26d at audit | recovery state; Home is NEW demo source of truth | EBS/EIP usage remains; active compute stopped | RETAIN STOPPED | LIVE |
| aws-secops | **amit** | - | AWS Config rule | 2 | present | UNKNOWN | issue-88-config-evidence | USAGE-BASED | REVIEW | LIVE |
| aws-secops | **amit** | - | AgentCore Gateway | 1 | present | 16d | governed-harmless-tool | USAGE-BASED | CLEANUP-CANDIDATE | LIVE |
| aws-secops | **amit** | - | AgentCore Harness | 3 | present | UNKNOWN | compliance-agent-v1 | USAGE-BASED | RETAIN | LIVE |
| aws-secops | **amit** | - | AgentCore Policy engine | 1 | present | 16d | dev-only-gateway-policy | USAGE-BASED | CLEANUP-CANDIDATE | LIVE |
| aws-secops | **amit** | - | AgentCore Runtime | 2 | present | UNKNOWN | compliance-agent-v1 | USAGE-BASED | RETAIN | LIVE |
| aws-secops | **amit** | - | AgentCore workload identity | 1 | present | UNKNOWN | compliance-agent-v1 | USAGE-BASED | RETAIN | LIVE |
| aws-secops | **amit** | - | CloudFormation stack | 1 | present | UNKNOWN | compliance-agent-v1 | DIRECT-$0 | RETAIN | LIVE |
| aws-secops | **amit** | - | CloudWatch log group | 1 | present | 16d | governed-tool-evidence | USAGE-BASED | CLEANUP-CANDIDATE | LIVE |
| aws-secops | **amit** | - | CloudWatch log group | 1 | present | 16d | pilot-exact-sg-remediation | USAGE-BASED | RETAIN | LIVE |
| aws-secops | **amit** | - | CodeBuild project | 1 | present | 7d | issue-100-four-account-executor | USAGE-BASED | RETAIN | LIVE |
| aws-secops | **amit** | - | Lambda function | 1 | present | 16d | governed-harmless-tool | USAGE-BASED | CLEANUP-CANDIDATE | LIVE |
| aws-secops | **amit** | - | Lambda function | 1 | present | 16d | pilot-exact-sg-remediation | USAGE-BASED | RETAIN | LIVE |
| aws-secops | **amit** | - | Lambda function | 1 | present | 16d | pilot-provider-read | USAGE-BASED | RETAIN | LIVE |
| aws-secops | **amit** | - | S3 bucket | 1 | present | UNKNOWN | issue-88-config-delivery | USAGE-BASED | REVIEW | LIVE |
| aws-secops | **amit** | - | S3 bucket | 1 | present | 15d | versioning-exception-demo | USAGE-BASED | RETAIN | LIVE |
| aws-secops | **amit** | - | Security Group | 1 | present | 16d | pilot-compliance-demo | DIRECT-$0 | RETAIN | LIVE |
| aws-secops | **amit** | - | Security Group rule | 1 | present | 15d | authenticated-ui-https | DIRECT-$0 | RETAIN | LIVE |
| Security Copilot | **vagent** | `seccop-project1-old-ami-host-r01` | EC2 retained learning host | 1 | last reported running 2026-09-27; not refreshed | 27d at prior audit | Inspector-to-SSM old-package learning demo | historical EST ~USD 19.27/mo compute | RETAIN | REPO-EVIDENCE |
| aws-secops | **vagent** | - | S3 bounded demo fleet | 100 | retained | 14d first-seen | bounded S3 Block Public Access scale demo | USAGE-BASED | REVIEW | REPO-EVIDENCE |

## Cost labels

- `ACTUAL`: measured Cost Explorer/billing evidence for the account/service.
- `EST`: formula/list-price estimate; not a billing claim.
- `USAGE-BASED`: spend depends on requests, storage, logs, model/runtime use, or executions.
- `DIRECT-$0`: resource itself has no direct hourly charge; dependencies can still cost money.
- `UNKNOWN`: attribution is not defensible yet.

## Operating rule

Refresh before/after major demos and before cleanup decisions.
TTL means **review date**, never automatic deletion. **Protected resources remain unchanged until Amit gives a new exact authorization.**
