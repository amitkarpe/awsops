---
marp: true
theme: default
paginate: true
---

# Using AWS SSM Document: RunShellScript-ds_agent

Presented by: [Amit Karpe]

---

## Why Use SSM Documents?

* **Automate Operations:** Run scripts and commands on EC2 or on-premises servers without SSH or RDP.
* **Security:** No need to open inbound ports or manage SSH keys.
* **Consistency:** Standardize operational tasks across environments.
* **Auditability:** All executions are logged in AWS.
* **Parameterization:** Pass variables to scripts for flexible automation.

---

## What is an SSM Document?

* **Definition:**
  * A JSON or YAML file that defines actions for AWS Systems Manager to perform on managed instances.
* **Types:**
  * Predefined by AWS (e.g., AWS-RunShellScript)
  * Custom (like our RunShellScript-ds_agent)
* **Main Components:**
  * `schemaVersion`, `description`, `parameters`, `mainSteps`

---

## How to Use SSM Documents

1. **Create or Use an Existing Document**
   * In AWS Console: Systems Manager > Documents
   * Or via AWS CLI/API
2. **Attach IAM Role**
   * Ensure your instance has the right permissions (e.g., `AmazonSSMManagedInstanceCore`)
3. **Send Command**
   * Use the document to run commands on target instances

```bash
aws ssm send-command \
  --instance-ids "i-xxxxxxxxxxxxxxxxx" \
  --document-name "RunShellScript-ds_agent" \
  --parameters '{"POLICYID":["6"]}'
```

---

## Using Parameters in SSM Documents

* **Why Parameters?**
  * Make scripts reusable and flexible
* **How to Define:**
  * In the `parameters` section of the document
* **How to Use:**
  * Reference in the script using `{{ PARAMETER_NAME }}`
* **Example:**
  * `POLICYID: String` — "Policy ID for Trend Micro agent activation."
  * Passed at runtime to customize agent activation

---

## Example: RunShellScript-ds_agent

* **Purpose:**
  * Automate installation and configuration of Trend Micro Deep Security Agent
* **Key Steps:**
  1. Print hostname and IP
  2. Reset agent
  3. Set DSM and Relay proxies
  4. Activate agent with `POLICYID` parameter
  5. Get configuration and check Security Profile ID
* **Parameterization:**
  * `POLICYID` is injected into the activation command

---

## RunShellScript-ds_agent: Code Walkthrough

```yaml
parameters:
  POLICYID:
    type: "String"
    description: "Policy ID for Trend Micro agent activation."
    default: "6"
mainSteps:
- action: "aws:runShellScript"
  name: "runTrendMicroCommands"
  inputs:
    runCommand:
      - |
        #!/bin/bash
        ...
        sudo /opt/ds_agent/dsa_control -a dsm://... "policyid:{{ POLICYID }}"
        ...
```
* **At execution:**
  * You can override `POLICYID` as needed for different environments or policies.

---

## How to Run the Document

1. **From AWS Console:**
   * Go to Systems Manager > Run Command
   * Select your document (e.g., RunShellScript-ds_agent)
   * Specify target instances and parameters (e.g., POLICYID)
2. **From CLI:**
   * Use `aws ssm send-command` as shown earlier

---

## Q&A

* Questions?
* Discussion
