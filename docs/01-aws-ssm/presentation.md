---
marp: true
theme: default
paginate: true
---

# AWS Systems Manager (SSM) Training - [Date]

Presented by: [Your Name/Team]

---

## Agenda

*   Introduction to SSM
*   Inventory Management
*   Session Manager
*   Patch Manager
*   Compliance Scanning
*   Run Command (Documents)
*   Q&A

---

## Introduction to SSM

*   What is AWS Systems Manager?
    *   Unified interface for managing AWS resources.
    *   Helps automate operational tasks across your AWS resources.
*   Key Capabilities:
    *   Operations Management (OpsCenter, Explorer)
    *   Application Management (AppConfig, Parameter Store)
    *   Change Management (Automation, Change Calendar, Change Manager)
    *   Node Management (Inventory, Session Manager, Patch Manager, Run Command, State Manager)
*   Core Concept: SSM Agent
    *   Needs to be installed and running on managed instances (EC2, on-premises).
    *   Requires appropriate IAM permissions.

---

## Inventory Management

*   Collects metadata from your managed instances.
*   Information includes:
    *   Applications installed
    *   AWS Components (e.g., SSM Agent version)
    *   Network configuration
    *   Operating system details
    *   Services, Windows Roles, Updates, etc.
*   How it works:
    *   SSM Agent gathers data based on configured inventory types.
    *   Data is stored in the Systems Manager Inventory data store.
*   Use Cases:
    *   View configuration and installed applications.
    *   Query data across fleets of instances.
    *   Track changes over time.

```bash
# Example: Query inventory data (requires setup)
aws ssm list-inventory-entries --instance-id <instance-id> --type-name AWS:Application
```

---

## Session Manager

*   Provides secure instance management without needing SSH keys, bastion hosts, or open inbound ports.
*   Access via:
    *   AWS Management Console
    *   AWS CLI (requires Session Manager plugin)
*   Benefits:
    *   Improved security posture.
    *   Centralized access control using IAM policies.
    *   Auditing capabilities (logs commands and output to S3/CloudWatch Logs).

```bash
# Prerequisite: Install Session Manager Plugin
# https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html

# Example: Start a session via CLI
aws ssm start-session --target <instance-id>
```

---

## Patch Manager

*   Automates patching managed instances (OS and applications).
*   Supports Windows Server, Amazon Linux, Ubuntu Server, RHEL, CentOS, etc.
*   Key Concepts:
    *   **Patch Baselines:** Define rules for auto-approving patches (e.g., Critical updates approved after 7 days). Includes approved/rejected patches lists.
    *   **Patch Groups:** Organize instances for patching (e.g., "Production Web Servers", "Dev DB Servers"). Can be based on tags.
    *   **Maintenance Windows:** Define recurring schedules when patching operations can run.
*   Workflow:
    1.  Define Patch Baselines.
    2.  (Optional) Create Patch Groups using tags.
    3.  Configure patching operation (e.g., Scan only or Scan and Install) via Maintenance Windows or Run Command.

---

## Compliance Scanning

*   Scans managed instances for patch compliance against defined Patch Baselines.
*   Reports compliance status (Compliant, Non-Compliant, Not Applicable).
*   Can be run on-demand or scheduled (often integrated with Patch Manager scans).
*   Helps identify systems missing critical updates.
*   View results in Systems Manager console under Compliance.

```bash
# Example: Get compliance summary by instance
aws ssm list-compliance-summaries
```

---

## Run Command (Documents)

*   Remotely and securely execute commands on managed instances.
*   Uses SSM Documents (pre-defined or custom scripts).
    *   AWS provides many pre-defined documents (e.g., `AWS-RunShellScript`, `AWS-RunPowerShellScript`, `AWS-InstallApplication`).
    *   You can create custom documents (YAML or JSON).
*   Execution:
    *   Target instances by ID, tags, or resource groups.
    *   Control concurrency and error thresholds.
    *   Output logged to S3 or CloudWatch Logs.
*   Use Cases:
    *   Install/uninstall software.
    *   Run shell scripts or PowerShell commands.
    *   Configure services.
    *   Bootstrap instances.

```bash
# Example: Run a shell script on a Linux instance
aws ssm send-command \
    --instance-ids "i-xxxxxxxxxxxxxxxxx" \
    --document-name "AWS-RunShellScript" \
    --parameters '{"commands":["#!/bin/bash","yum update -y"]}' \
    --output-s3-bucket-name "your-s3-bucket-for-logs"
```

---

## Q&A

*   Questions?
*   Discussion

---

## Thank You!

*   Next Training Topic: [Next Topic]
*   Resources:
    *   [AWS Systems Manager Documentation](https://docs.aws.amazon.com/systems-manager/latest/userguide/what-is-systems-manager.html)
