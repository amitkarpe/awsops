# awsops Compliance Agent — Issue #39 recovery slice

Owner: https://github.com/amitkarpe/awsops/issues/39

This package reuses the proven Compliance Agent v1 evidence-first pattern while
keeping the current migration slice strictly read-only.

Flow:

```text
sec2 LibreChat
  -> ask_compliance_agent
  -> config2 loopback API
  -> exact 4 LAB aliases x 2 controls
  -> tool-free AgentCore Harness reasoning
  -> status / explanation / no-change plan
```

The evidence adapter accepts only:

- `lab-dev`, `lab-poc`, `lab-qa`, `lab-sec`;
- `s3-bucket-level-public-access-prohibited`;
- `restricted-ssh`;
- public-safe status/count/freshness fields.

It rejects partial matrices and unexpected fields. Account IDs, resource IDs,
raw Config rule metadata, credentials and private findings are not exposed to
the model.

Runtime inputs stay private:

- `AWSOPS_CONFIG_BACKEND_URL` — defaults to `http://127.0.0.1:4313`;
- `COMPLIANCE_AGENT_V1_HARNESS_ARN` — existing approved tool-free Harness;
- `AWS_REGION` — defaults to `ap-southeast-1`.

No remediation, re-arm, generic AWS tool or Issue #11 flow is included here.
