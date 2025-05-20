---
marp: true
theme: default
paginate: true
---

# AWS CloudWatch Overview

Presented by: [Amit Karpe]

---

## What is AWS CloudWatch?

* AWS CloudWatch is a monitoring and observability service for AWS resources and applications.
* Collects metrics, logs, and events from AWS services and custom sources.
* Enables real-time monitoring, visualization, and automated response to changes in your environment.

---

## CloudWatch Use Case: EC2 Monitoring

* **Scenario:**
  * Monitor CPU utilization of EC2 instances.
* **How it helps:**
  * Automatically collect metrics (CPU, disk, network, etc.).
  * Set alarms to notify when CPU usage is high.
  * Take automated actions (e.g., scale out, send notifications).

---

## What is AWS CloudWatch Dashboard?

* A customizable, interactive visual interface in CloudWatch.
* Allows you to display and monitor metrics and logs from multiple AWS resources in one place.
* Supports widgets: graphs, numbers, text, and more.
* Useful for real-time and historical analysis.

---

## CloudWatch Dashboard Use Case: Application Health Board

* **Scenario:**
  * Create a dashboard to visualize health and performance of a web application.
* **How it helps:**
  * Combine metrics from EC2, RDS, ELB, and Lambda on a single screen.
  * Quickly identify issues and trends.
  * Share dashboards with your team for collaborative monitoring.

---

## What is AWS CloudWatch Alert?

* CloudWatch Alerts (Alarms) monitor metrics and trigger actions when thresholds are breached.
* Can send notifications (SNS, email, SMS), trigger Auto Scaling, or run Lambda functions.
* Supports static and anomaly detection thresholds.

---

## CloudWatch Alert Use Case: Proactive Incident Response

* **Scenario:**
  * Set an alarm to detect when RDS database CPU exceeds 80% for 5 minutes.
* **How it helps:**
  * Notifies the operations team via email/SNS.
  * Can trigger automated remediation (e.g., scale up DB instance).
  * Reduces downtime and improves reliability.

---

## Q&A

* Questions?
* Discussion
