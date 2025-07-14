---

marp: true
theme: default
paginate: true
--------------

# AWS CloudWatch Agent & EC2 Monitoring Training

Presented by: \[Amit Karpe]

---

## Introduction to Amazon CloudWatch

* **Amazon CloudWatch** is AWS’s monitoring service for cloud resources and applications. It collects metrics (CPU, network, etc.), logs, and events in real time.
* **Metrics & Dashboards:** Many AWS services publish default metrics to CloudWatch automatically. You can visualize them on **dashboards** (custom or pre-built).
* **Alarms & SNS:** You can set **alarms** on metrics to trigger notifications or actions (e.g., send an SNS email, scale an ASG) when thresholds are breached.
* **Need for CloudWatch Agent:** By default, EC2 provides basic metrics (CPU, disk I/O). To collect **OS-level** metrics like memory, disk usage, or per-process metrics, you install the CloudWatch Agent.

---

## AWS CloudWatch Agent Overview

* **CloudWatch Agent** is a configurable OS agent (Linux/Windows) that collects system metrics and logs and sends them to CloudWatch. It’s required for metrics like memory usage, disk space, and custom application metrics.
* **Installation:** The agent can be installed via AWS SSM or manually. (e.g., using SSM Run Command `AWS-ConfigureAWSPackage` to install `AmazonCloudWatchAgent` or running the installer).
* **Configuration File:** The agent uses a JSON config file (`cloudwatch-agent.json`) with sections for **metrics** and **logs**. You can create it using the provided wizard or manually edit it. The config defines what metrics/logs to collect and their frequency.
* **Default vs Custom Namespace:** By default, agent metrics go to the **CWAgent** namespace. You can specify a custom namespace (e.g., "MongoDB") in the config to group metrics logically.

---

## Monitoring Linux Services (Procstat Plugin)

* CloudWatch Agent’s **procstat** plugin allows monitoring specific processes on Linux. This is useful for services like Docker, GitLab, MongoDB, etc..
* **Configuration:** In the agent JSON, add a `procstat` section under `metrics_collected` for each process. You can identify processes by name (`exe`), command pattern, or PID file.
* **Example:** To monitor CPU usage of Docker and GitLab processes:

```json
"metrics": {
  "metrics_collected": {
    "procstat": [
      { "pattern": "docker", "measurement": ["cpu_usage"] },
      { "pattern": "gitlab", "measurement": ["cpu_usage"] }
    ]
  }
}
```

* **Measurements:** You can collect metrics like CPU, memory, thread count, etc., for each process. In our setup, we monitor processes such as `ds_agent`, `splunkd`, `nessus-service`, etc., by CPU usage. These metrics appear in CloudWatch with names like `procstat_cpu_usage` and a dimension for the process name.

---

## Collecting System Metrics (Disk, Memory)

* The agent can collect **system metrics** beyond the defaults. For example, disk utilization on specific mount points and memory usage:

```json
"metrics": {
  "metrics_collected": {
    "disk": {
      "resources": [ "/", "/var/lib/mongo" ],
      "measurement": [
        { "name": "used_percent", "rename": "Disk_Used", "unit": "%" }
      ],
      "metrics_collection_interval": 60
    },
    "mem": {
      "measurement": [ "mem_used_percent" ],
      "metrics_collection_interval": 60
    }
  }
}
```

* **Disk Metrics:** In this example, the agent reports `%` used on the root partition and MongoDB data directory. The metric is renamed to `Disk_Used` for clarity. We set the collection interval to 60 seconds.
* **Memory Metrics:** The `mem` plugin reports percentage of memory used (`mem_used_percent`). This also requires the agent (since EC2 default metrics don’t include memory).
* **Viewing Metrics:** These custom metrics are sent to CloudWatch (in the specified namespace, e.g., **MongoDB**), and can be graphed or alarmed on just like default metrics.

---

## Using AWS Systems Manager for Agent Config

* **Parameter Store:** Instead of maintaining the JSON config on each instance, we store the CloudWatch agent configuration in AWS Systems Manager **Parameter Store**. For example, a parameter `/AmazonCloudWatch-linux/mongo2` contains the JSON config for MongoDB instances. Storing configs centrally makes updates easier.
* **SSM Run Command:** AWS provides the **AmazonCloudWatch-ManageAgent** SSM document to manage the agent across instances. Using Run Command, we can push a new config to all EC2s:

  1. Put the updated JSON in Parameter Store (one parameter per config).
  2. Run Command with document *AmazonCloudWatch-ManageAgent* – choose **Action**: “configure”, **Configuration Source**: “ssm”, and specify the Parameter Store name. Set **Optional Restart** to “yes” to reload the agent.
  3. This applies the new config to all targeted instances in one go.
* **Benefits:** Using SSM ensures consistency. New AMI with new instance IDs? As long as the instance is managed by SSM and has the correct IAM role (CloudWatchAgentServerRole), it will retrieve the latest config from Parameter Store at startup or on command.

---

## Leveraging Tags & Dimensions for Dynamic Resources

* **Challenge:** EC2 instance IDs change when replacing instances (e.g., yearly AMI upgrades). Hard-coding instance IDs in dashboards or alarms is not ideal.
* **Solution – Append Dimensions:** CloudWatch agent config can append resource tags as metric dimensions. For example, we use:

```json
"append_dimensions": {  
  "InstanceName": "${aws:Tag/Name}"  
}
```

This adds the EC2 **Name tag** value as an `InstanceName` dimension on all reported metrics.

* **Use Case:** Instead of alarm on a specific InstanceId, we can alarm on all instances with `InstanceName = "MongoDB-Server"` (for example). As long as new instances carry the same Name tag, the alarm/dashboards automatically include them.
* We also use custom dimensions like **Group** in metrics (e.g., `Group: "Mongo"` for MongoDB disks) to aggregate metrics by role. This is set via the agent config’s `append_dimensions` or per-metric dimensions (see disk example where `Group` was set to "Mongo").
* **Best Practice:** Design metrics and dashboards using logical dimensions (tags, groups) rather than static instance IDs. This makes your monitoring resilient to infrastructure changes.

---

## CloudWatch Dashboards (Custom & Automatic)

* **Custom Dashboards:** CloudWatch allows creating dashboards to visualize multiple metrics. We can mix graphs for EC2 metrics, custom agent metrics, and alarms in one view. For example, we have a “Services-on-EC2” dashboard showing CPU usage for processes like `ds_agent`, `splunkd`, etc., across our fleet.

  * Dashboards can be defined via the Console or JSON. Our sample JSON (shown in repo) defines widgets for each service’s `procstat_cpu_usage` metric per instance.
  * Tip: Instead of listing individual InstanceIds in the dashboard, use metrics with a common dimension. E.g., a widget can display all metrics where `InstanceName = X` without needing updates for new instances.
* **Automatic Dashboards:** CloudWatch provides **automatic dashboards** for many services. We are using the built-in **ECS Cluster** dashboard which shows cluster-level CPU and memory utilization. Similarly, there are automatic dashboards for each EC2 instance and other resources. Leverage these for quick overviews.
* **Updating Dashboards:** To add new metrics (say, monitoring a new service process), you would update the dashboard: either edit the widget in the console to include the new metric, or update the JSON definition and use `PutDashboard` API. Always ensure the metric exists (agent is pushing it) before adding to dashboard.

---

## CloudWatch Alarms & SNS Notifications

* **CloudWatch Alarms:** Alarms continuously monitor a single metric (or a metric math expression) and change state if a threshold is crossed. For each critical metric we collect (CPU, memory, disk, or process health), we set up alarms. For example, an alarm on `mem_used_percent` if memory > 80%, or on `Disk_Used` if disk usage > 90%.

  * When creating an alarm, you choose the metric and define the threshold and evaluation period (e.g., “if CPU > 85% for 5 minutes”).
  * We often configure a **breaching period** (e.g., 3 out of 5 data points) to avoid noise from brief spikes.
* **SNS Integration:** Alarms can trigger actions; the most common is sending a notification via **Amazon SNS**. We have an SNS topic (e.g., *ops-alerts*) subscribed by the Ops team email. Each alarm is set to **Notify this SNS topic on ALARM state**. This way, when a service (e.g., Splunk or Docker) exceeds its threshold, the team gets an email.

  * **Setup:** Ensure an SNS topic is created and subscriptions (email/SMS) confirmed. Then, in the alarm’s configuration, add the SNS topic under the notification options.
  * We also use SNS for aggregation – multiple alarms can notify the same topic. The email subject will indicate which alarm/name triggered.
* **Future Ops Alerts:** After this training, the Ops team should recognize alerts (emails) for these services and know they come from CloudWatch alarms. For example, an email “ALARM: Docker CPU High on InstanceName=GitLab-Server” indicates the CloudWatch agent reported high CPU for the Docker process on the GitLab server.

---

## Monitoring ECS Clusters (Brief Overview)

* While our focus is on EC2 instances, note that **Amazon ECS** clusters also publish metrics to CloudWatch automatically. You get cluster-level CPU and memory utilization metrics for free. These are visible in the ECS console and CloudWatch. We utilize the *ECS-Cluster-Pro* dashboard which shows aggregate usage across the cluster.
* For more granular container/application metrics on ECS, AWS offers **CloudWatch Container Insights**. This can be enabled on the cluster to collect per-task and container metrics (CPU, memory, network) and even generate automatic dashboards. Container Insights uses a CloudWatch agent (embedded in the ECS agent or Fluentd) and incurs additional costs.
* **Best Practice:** Even with ECS, don’t forget the underlying EC2 instances (if using EC2 launch type). Those container host instances should run CloudWatch agent for things like disk and OS metrics. AWS recommends monitoring the EC2 infrastructure separately (e.g., if your ECS tasks are on EC2, use our CloudWatch agent setup on those instances).
* In summary, ECS gives service-level health metrics, while CloudWatch agent on EC2 gives OS-level insights. Both are important for a complete picture.

---

## Q\&A

* Questions?
* Discussion

---

## Thank You!

* Next Training Topic: \[Next Topic]
* Resources:

  * [Amazon CloudWatch User Guide](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/WhatIsCloudWatch.html) – Official documentation for CloudWatch (metrics, dashboards, alarms, etc.)
  * [CloudWatch Agent Configuration Guide](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-Configuration-File-Details.html) – Details on the agent JSON config and available settings
  * [Using CloudWatch Agent with Systems Manager](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/download-CloudWatch-Agent-on-EC2-Instance-SSM-first.html) – How to deploy and configure the agent across instances using SSM
