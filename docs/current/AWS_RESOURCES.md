# AWS Resources

> KISS public ledger. **Canonical account names are `amit` and `vagent`.**
> Raw AWS account IDs and provider identifiers stay out of this public repository.

- Last verified: `2026-09-27T12:14:50+08:00`
- Scope: personal LAB / `ap-southeast-1`
- Cost period: `2026-09-01..2026-09-27`
- Current rule: **look at the red/high-cost tables first**
- **Protection rule (2026-09-27): legacy Lightsail and the `vagent` retained `t3.small` are DO NOT TOUCH.** Read-only inspection is allowed; stop/start/terminate/delete/resize/repurpose/tag/IAM/network changes require a new explicit user authorization.

## 🔴 Cost watch — check this first

| Priority | Account | Resource / service | State | Cost evidence | Action |
| --- | --- | --- | --- | ---: | --- |
| 🔴 **HIGH** | **amit** | **EC2 `agentcore-issue19-librechat-poc-r01` / `t3.medium`** | running | **USD 31.52 MTD actual**; ~**USD 38.54/mo** compute list-price | **KEEP `t3.medium`** |
| 🛡️ **PROTECTED** | **amit** | **Amazon Lightsail** | 1 running + 1 stopped legacy instance | **USD 8.28 MTD actual** | **DO NOT TOUCH** |
| 🛡️ **PROTECTED** | **vagent** | **EC2 `seccop-project1-old-ami-host-r01` / `t3.small`** | running; old demo TTL expired | Cost Explorer reports **USD 0.00 MTD**; list-price/public-IPv4 exposure still exists | **DO NOT TOUCH** |

## Account cost summary

| Account | Actual Cost Explorer MTD | Current inventory signal | What to check first |
| --- | ---: | --- | --- |
| **amit** | **USD 58.51** | 1 running EC2, 18 S3 buckets, 140 tagged resources | **EC2, Lightsail, VPC, Bedrock** |
| **vagent** | **USD 0.00 reported** | 1 running EC2, 109 S3 buckets, 219 tagged resources | **protected EC2 + retained 100-bucket fleet** |

> Cost Explorer is account/service billing evidence, not proof that every dollar belongs to `awsops` or `aws-secops`.
> A reported zero does not mean a running resource is guaranteed to be free.

### `amit` top billed services this month

| Service | MTD actual |
| --- | ---: |
| **Amazon EC2 - Compute** | **USD 31.52** |
| **Amazon Lightsail** | **USD 8.28** |
| Tax | USD 4.83 |
| Amazon VPC | USD 3.00 |
| Amazon Bedrock | USD 2.67 |
| EC2 - Other | USD 1.84 |
| AWS Config | USD 1.60 |
| Amazon Bedrock AgentCore | USD 1.48 |
| Amazon Inspector | USD 1.41 |
| Amazon Route 53 | USD 0.65 |
| AWS Key Management Service | USD 0.63 |
| CodeBuild | USD 0.45 |

## 🔴 EC2 / always-on compute

Always-on compute is intentionally separated because it is the first cost lever to check.

| Account | EC2 name | Project | Compute | State | Age | Estimated monthly | Decision |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| **amit** | **`agentcore-issue19-librechat-poc-r01`** | shared-runtime | **`t3.medium`** | running | 26d | **~USD 38.54 compute** | **RETAIN** |
| **vagent** | **`seccop-project1-old-ami-host-r01`** | Security Copilot | **`t3.small`** | running + public IPv4 | 27d | **~USD 19.27 compute list-price** | **RETAIN / DO NOT TOUCH** |

## `amit` retained host

**KEEP `t3.medium`**.

- 14-day CPU: **1.63% average**, **77.89% observed maximum**.
- Memory snapshot: **3.74 GiB total**, **2.05 GiB available**, **no swap**.
- Main retained services: LibreChat ~623.5 MiB, Ops service ~215.8 MiB, MongoDB ~148.6 MiB.
- `t3.small` would leave only about **0.31 GiB theoretical RAM headroom** at the sampled working set.
- Therefore the ~USD 19/month compute saving is not worth the memory risk today.

### Disk expansion completed

| Item | Before | After |
| --- | ---: | ---: |
| EBS gp3 volume | 20 GiB | **30 GiB** |
| Root filesystem | 18.3 GiB | **28 GiB** |
| Root filesystem used | 92% | **60%** |
| Retained services | active | **active** |

The partition and ext4 filesystem were grown online. No instance stop/restart or instance-type change occurred.
Approximate incremental gp3 cost: **~USD 0.96/month**.

## 🧹 2026-09-27 read-only audit

| Account | Live finding | Decision |
| --- | --- | --- |
| **amit** | 1 running t3.medium; 30 GiB encrypted gp3; 18 S3 buckets; 140 tagged resources | **RETAIN** runtime; legacy Lightsail **DO NOT TOUCH** |
| **vagent** | 1 running t3.small with public IPv4; 20 GiB encrypted gp3; 0 Elastic IPs; 109 S3 buckets; 219 tagged resources | host **DO NOT TOUCH**; bucket fleet **REVIEW** |

Direct vagent host dependencies observed: **1 ENI, 1 security group, 1 instance profile / 1 role**. The ENI is untagged; no mutation or cleanup was performed.

## Full resource ledger

| Project | Account | Name | Resource class | Qty | State | Age | Purpose | Cost | Decision | Evidence |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| shared-runtime | **amit** | `agentcore-issue19-librechat-poc-r01` | EC2 retained demo host | 1 | running | 26d | LibreChat + Ops retained personal-LAB runtime | EST ~USD 38.54/mo compute | RETAIN | LIVE |
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
| Security Copilot | **vagent** | `seccop-project1-old-ami-host-r01` | EC2 retained learning host | 1 | running | 27d | Inspector-to-SSM old-package learning demo | EST ~USD 19.27/mo compute | RETAIN | LIVE |
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
