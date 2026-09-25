# AWS Resources

> KISS public ledger. Logical classes and aliases only; raw AWS identifiers stay private.

- Last verified: `2026-09-25T11:30:00+08:00`
- Scope: personal LAB / ap-southeast-1
- Ledger rows: **19**; represented resources: **122**
- Cleanup candidates: **4** (review only; this file never authorizes deletion)
- Coverage: 21 live project-tagged aws-secops resources + retained shared host; vagent 100-bucket fleet is repo evidence pending live refresh

## Retained host right-sizing

**KEEP-t3.medium** — CPU is light, but projected t3.small RAM headroom is only 0.31 GiB with no swap; root filesystem is 92% used and needs separate capacity cleanup.

## Resource ledger

| Project | Account | Resource class | Qty | State | Age | Purpose | Cost | Decision | Evidence |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| shared-runtime | personal-lab | EC2 retained demo host | 1 | running | 23d (created) | LibreChat + Ops retained personal-LAB runtime | EST ~$38.54/mo compute | RETAIN | LIVE |
| aws-secops | personal-lab | AWS Config rule | 2 | present | UNKNOWN | issue-88-config-evidence | USAGE-BASED | REVIEW | LIVE |
| aws-secops | personal-lab | AgentCore Gateway | 1 | present | 16d (created) | governed-harmless-tool | USAGE-BASED | CLEANUP-CANDIDATE | LIVE |
| aws-secops | personal-lab | AgentCore Harness | 3 | present | UNKNOWN | compliance-agent-v1 | USAGE-BASED | RETAIN | LIVE |
| aws-secops | personal-lab | AgentCore Policy engine | 1 | present | 16d (created) | dev-only-gateway-policy | USAGE-BASED | CLEANUP-CANDIDATE | LIVE |
| aws-secops | personal-lab | AgentCore Runtime | 2 | present | UNKNOWN | compliance-agent-v1 | USAGE-BASED | RETAIN | LIVE |
| aws-secops | personal-lab | AgentCore workload identity | 1 | present | UNKNOWN | compliance-agent-v1 | USAGE-BASED | RETAIN | LIVE |
| aws-secops | personal-lab | CloudFormation stack | 1 | present | UNKNOWN | compliance-agent-v1 | DIRECT-$0 | RETAIN | LIVE |
| aws-secops | personal-lab | CloudWatch log group | 1 | present | 16d (created) | governed-tool-evidence | USAGE-BASED | CLEANUP-CANDIDATE | LIVE |
| aws-secops | personal-lab | CloudWatch log group | 1 | present | 16d (created) | pilot-exact-sg-remediation | USAGE-BASED | RETAIN | LIVE |
| aws-secops | personal-lab | CodeBuild project | 1 | present | 7d (created) | issue-100-four-account-executor | USAGE-BASED | RETAIN | LIVE |
| aws-secops | personal-lab | Lambda function | 1 | present | 16d (created) | governed-harmless-tool | USAGE-BASED | CLEANUP-CANDIDATE | LIVE |
| aws-secops | personal-lab | Lambda function | 1 | present | 16d (created) | pilot-exact-sg-remediation | USAGE-BASED | RETAIN | LIVE |
| aws-secops | personal-lab | Lambda function | 1 | present | 16d (created) | pilot-provider-read | USAGE-BASED | RETAIN | LIVE |
| aws-secops | personal-lab | S3 bucket | 1 | present | UNKNOWN | issue-88-config-delivery | USAGE-BASED | REVIEW | LIVE |
| aws-secops | personal-lab | S3 bucket | 1 | present | 15d (created) | versioning-exception-demo | USAGE-BASED | RETAIN | LIVE |
| aws-secops | personal-lab | Security Group | 1 | present | 16d (created) | pilot-compliance-demo | DIRECT-$0 | RETAIN | LIVE |
| aws-secops | personal-lab | Security Group rule | 1 | present | 15d (created) | authenticated-ui-https | DIRECT-$0 | RETAIN | LIVE |
| aws-secops | vagent | S3 bounded demo fleet | 100 | retained (repo evidence) | 14d (first_seen) | bounded S3 Block Public Access scale demo | USAGE-BASED | REVIEW | REPO-EVIDENCE |

## Host evidence

- Current type: `t3.medium` (2 vCPU / 4 GiB class).
- 14-day CPU: **1.63% average**, **77.89% observed maximum**; CPU credit balance stayed effectively full.
- Memory snapshot: **3.74 GiB total**, **2.05 GiB available**, **no swap**.
- Main retained services: LibreChat ~623.5 MiB, Ops service ~215.8 MiB, MongoDB ~148.6 MiB at the sampled point.
- Root volume: **20 GiB gp3**, filesystem **92% used**. Storage pressure is the immediate capacity concern.
- `t3.small` would halve RAM to 2 GiB. With the sampled working set it leaves only about **0.31 GiB theoretical headroom**, before workload spikes or filesystem cache. Keep `t3.medium` for now.
- Current Singapore Linux on-demand reference: `t3.medium` **$0.0528/h (~$38.54/mo)** vs `t3.small` **$0.0264/h (~$19.27/mo)** at 730 h. Theoretical compute saving is ~**$19.27/mo**, but the memory risk is not justified yet.
- 20 GiB gp3 baseline storage is ~**$1.92/mo** at $0.096/GiB-month; one in-use public IPv4 is ~**$3.65/mo** at $0.005/h. Approximate retained-host base run-rate is therefore **$44.11/mo** before data transfer, logs or other service usage.

## Coverage gaps

- `awsops` currently has **0** resources carrying `project=awsops`; it reuses the shared retained LAB host and read roles.
- The vagent 100-bucket fleet is included from accepted repo evidence and must be live-refreshed before any cleanup/cost decision.
- IAM roles and service resources that are untagged or not returned by Resource Groups Tagging API are not represented as live-verified rows yet. The collector is intentionally read-only and may add bounded service-specific discovery later.
- Exact monthly billing is shown only when attribution is defensible. The collector tries the AWS Pricing API for EC2 list price; usage-based services remain labeled rather than guessed.
- Current list-price references are a point-in-time estimate, not Cost Explorer billing. Refresh before making a savings commitment.

## Cost labels

- `ACTUAL`: measured billing attribution is reliable for this scope.
- `EST`: formula/list-price estimate; not a billing claim.
- `USAGE-BASED`: spend depends on requests, storage, logs, model/runtime use, or executions.
- `DIRECT-$0`: the resource itself has no direct hourly charge; dependencies can still cost money.
- `UNKNOWN`: attribution is not defensible yet.

## Operating rule

Refresh before/after major demos and before cleanup decisions. TTL means review date, not automatic deletion.
This ledger is read-only evidence and does not grant AWS mutation authority.
