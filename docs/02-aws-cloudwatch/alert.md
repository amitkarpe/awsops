---
marp: true
theme: default
paginate: true
---

# AWS CloudWatch Alerts: Concepts & Best Practices

Presented by: [Amit Karpe]

---

## What are AWS CloudWatch Alerts?

* **CloudWatch Alerts (Alarms):**
  * Monitor AWS resource metrics (e.g., EC2, RDS, Lambda).
  * Trigger actions when thresholds are breached.
  * Actions: Send notifications, auto-scale, run Lambda, etc.
* **Common Metrics:**
  * CPU, memory, disk, network, custom metrics

---

## Monitoring EC2 Instances with CloudWatch

* **Default Metrics:**
  * CPUUtilization, NetworkIn/Out, DiskRead/WriteOps
* **Custom Metrics:**
  * Memory and disk space require CloudWatch Agent
* **Steps:**
  1. Install/Configure CloudWatch Agent on EC2
  2. Collect memory, disk, and other OS-level metrics
  3. View metrics in CloudWatch console

---

## Setting Up Alerts for EC2: Memory, CPU, Free Disk

1. **Install CloudWatch Agent** (for memory/disk):
   * [CloudWatch Agent Docs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Install-CloudWatch-Agent.html)
2. **Publish Metrics:**
   * Agent sends memory and disk metrics to CloudWatch
3. **Create Alarms:**
   * Go to CloudWatch > Alarms > Create Alarm
   * Select metric (e.g., CPUUtilization, mem_used_percent, disk_free)
   * Set threshold (e.g., CPU > 80%, Memory > 75%, Disk < 10% free)
   * Choose actions (SNS, Auto Scaling, etc.)

---

## Best Practices for Configuring Alerts

* **Set Meaningful Thresholds:**
  * Avoid alert fatigue (e.g., CPU > 90% for 5 min, not 1 min)
* **Use Anomaly Detection:**
  * Detect unusual patterns, not just static thresholds
* **Group Related Alerts:**
  * Use composite alarms to reduce noise
* **Test Alerts Regularly:**
  * Simulate conditions to ensure notifications work
* **Document and Review:**
  * Keep alerting strategy up to date

---

## Integrating CloudWatch Alerts with SNS Topics

* **Why SNS?**
  * Simple Notification Service (SNS) delivers alerts to email, SMS, Lambda, HTTP endpoints
* **How to Integrate:**
  1. Create an SNS Topic (e.g., "ec2-alerts-topic")
  2. Subscribe email/SMS endpoints to the topic
  3. In CloudWatch Alarm, set action to "Send notification to SNS topic"

---

## Sending Email and SMS with SNS

1. **Create SNS Topic:**
   * In AWS Console: SNS > Topics > Create topic
2. **Add Subscriptions:**
   * Email: Enter email address, confirm via email
   * SMS: Enter phone number, confirm via SMS
3. **Test Notification:**
   * Publish a test message to the topic
4. **Connect to CloudWatch Alarm:**
   * Set alarm action to notify your SNS topic

---

## Example: Alert for EC2 Memory Usage

```bash
# Install CloudWatch Agent (Amazon Linux)
sudo yum install amazon-cloudwatch-agent

# Configure agent (interactive)
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard

# Start agent
sudo systemctl start amazon-cloudwatch-agent
```
* Create alarm on `mem_used_percent` metric
* Set SNS topic as notification target

---

## Q&A

* Questions?
* Discussion
