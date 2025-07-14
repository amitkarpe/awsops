# AWS CloudWatch Agent Installation and Configuration

This directory contains comprehensive scripts and documentation for installing and configuring the AWS CloudWatch Agent on Amazon Linux 2 instances. The solution supports both individual instance management and fleet-wide deployment using AWS Systems Manager.

## 📁 Files Overview

| File | Description |
|------|-------------|
| `install-cloudwatch-agent.sh` | Installation script for Amazon Linux 2 |
| `configure-cloudwatch-agent.sh` | Configuration script with Parameter Store integration |
| `ssm-document-install-cloudwatch-agent.json` | SSM Document for fleet management |
| `ssm-commands.sh` | SSM Run Command examples and utilities |
| `README.md` | This comprehensive documentation |

## 🚀 Quick Start

### Individual Instance Setup

```bash
# 1. Install CloudWatch Agent
sudo bash install-cloudwatch-agent.sh

# 2. Create sample configurations in Parameter Store
sudo bash configure-cloudwatch-agent.sh -c

# 3. Configure with MongoDB monitoring
sudo bash configure-cloudwatch-agent.sh -p AmazonCloudWatch-linux/mongo

# 4. Or configure with GitLab monitoring
sudo bash configure-cloudwatch-agent.sh -p AmazonCloudWatch-linux/gitlab
```

### Fleet Management Setup

```bash
# 1. Create SSM Document
bash ssm-commands.sh create-document

# 2. Create sample configurations
bash ssm-commands.sh create-configs

# 3. Install on all managed instances
bash ssm-commands.sh install-all

# 4. Configure MongoDB monitoring on tagged instances
bash ssm-commands.sh configure-mongo
```

## 📋 Prerequisites

### IAM Permissions

Your EC2 instances must have an IAM role with the following policies:

#### Required Policies
- `CloudWatchAgentServerPolicy` (AWS managed policy)
- `AmazonSSMReadOnlyAccess` (AWS managed policy)
- Custom policy for Parameter Store access:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:PutParameter"
            ],
            "Resource": "arn:aws:ssm:*:*:parameter/AmazonCloudWatch-linux/*"
        }
    ]
}
```

### System Requirements

- **Operating System**: Amazon Linux 2
- **Architecture**: x86_64 or ARM64
- **Network**: Internet connectivity for package downloads
- **SSM Agent**: Installed and running (default on Amazon Linux 2)

## 🛠️ Installation Scripts

### install-cloudwatch-agent.sh

Installs the AWS CloudWatch Agent on Amazon Linux 2 instances.

**Features:**
- Automatic architecture detection (x86_64/ARM64)
- IAM permission verification
- Service configuration and user creation
- Comprehensive logging and error handling

**Usage:**
```bash
sudo bash install-cloudwatch-agent.sh
```

**Output:**
- Installation logs: `/var/log/cloudwatch-agent-install.log`
- Service enabled but not started (requires configuration)

### configure-cloudwatch-agent.sh

Configures the CloudWatch Agent using Parameter Store configurations.

**Features:**
- Parameter Store integration
- Pre-built configurations for MongoDB and GitLab
- Configuration validation
- Automatic service management

**Usage:**
```bash
# Configure with existing parameter
sudo bash configure-cloudwatch-agent.sh -p AmazonCloudWatch-linux/mongo

# Create sample configurations
sudo bash configure-cloudwatch-agent.sh -c

# Show help
sudo bash configure-cloudwatch-agent.sh -h
```

## 🏗️ Fleet Management

### SSM Document

The `ssm-document-install-cloudwatch-agent.json` provides a complete SSM document for fleet-wide management.

**Features:**
- Install-only mode support
- Parameter Store configuration
- Sample configuration creation
- Multi-step verification process

**Parameters:**
- `parameterStoreConfig`: Configuration parameter name
- `installOnly`: Install without configuration (true/false)
- `createSampleConfigs`: Create sample configurations (true/false)

### SSM Commands Utility

The `ssm-commands.sh` script provides utilities for managing CloudWatch Agent across your fleet.

**Available Commands:**
```bash
bash ssm-commands.sh create-document    # Create SSM document
bash ssm-commands.sh install-all        # Install on all instances
bash ssm-commands.sh configure-mongo    # Configure MongoDB monitoring
bash ssm-commands.sh configure-gitlab   # Configure GitLab monitoring
bash ssm-commands.sh create-configs     # Create sample configurations
bash ssm-commands.sh check-status       # Check agent status
bash ssm-commands.sh start-agent        # Start agent on all instances
bash ssm-commands.sh stop-agent         # Stop agent on all instances
bash ssm-commands.sh list-instances     # List managed instances
```

## 📊 Monitoring Configurations

### Parameter Store Configurations

The scripts support three pre-built configurations stored in AWS Parameter Store:

#### 1. MongoDB Configuration (`AmazonCloudWatch-linux/mongo`)
```json
{
  \"namespace\": \"MongoDB\",
  \"metrics_collected\": {
    \"disk\": {
      \"resources\": [\"/\", \"/var/lib/mongo\"],
      \"measurement\": [\"used_percent\"]
    },
    \"mem\": {
      \"measurement\": [\"mem_used_percent\"]
    },
    \"cpu\": {
      \"measurement\": [\"cpu_usage_idle\", \"cpu_usage_user\", \"cpu_usage_system\"]
    },
    \"procstat\": [{
      \"pattern\": \"mongod\",
      \"measurement\": [\"cpu_usage\", \"memory_rss\", \"memory_vms\"]
    }]
  }
}
```

#### 2. GitLab Configuration (`AmazonCloudWatch-linux/gitlab`)
```json
{
  \"namespace\": \"GitLab\",
  \"metrics_collected\": {
    \"disk\": {
      \"resources\": [\"/\", \"/var/opt/gitlab\"],
      \"measurement\": [\"used_percent\"]
    },
    \"procstat\": [
      {\"pattern\": \"gitlab\", \"measurement\": [\"cpu_usage\", \"memory_rss\"]},
      {\"pattern\": \"nginx\", \"measurement\": [\"cpu_usage\", \"memory_rss\"]},
      {\"pattern\": \"postgres\", \"measurement\": [\"cpu_usage\", \"memory_rss\"]}
    ]
  }
}
```

#### 3. Basic Configuration (`AmazonCloudWatch-linux/basic`)
Standard system monitoring with CPU, memory, and disk metrics.

### Parameter Store ARN Examples

As mentioned in the training requirements, configurations are stored using the following ARN format:
- `arn:aws:ssm:ap-southeast-1:021577063369:parameter/AmazonCloudWatch-linux/mongo`
- `arn:aws:ssm:ap-southeast-1:021577063369:parameter/AmazonCloudWatch-linux/gitlab`

## 🔧 Configuration Management

### Creating Custom Configurations

1. **Using the Configuration Wizard:**
   ```bash
   sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard
   ```

2. **Manual Configuration:**
   ```bash
   # Create JSON configuration
   sudo nano /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
   
   # Apply configuration
   sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent \
       -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json \
       -a fetch-config
   ```

3. **Using Parameter Store:**
   ```bash
   # Create parameter
   aws ssm put-parameter \
       --name \"AmazonCloudWatch-linux/custom\" \
       --type \"String\" \
       --value file://my-config.json \
       --description \"Custom CloudWatch Agent configuration\"
   
   # Apply from Parameter Store
   sudo bash configure-cloudwatch-agent.sh -p AmazonCloudWatch-linux/custom
   ```

## 🏷️ Tagging Strategy

For fleet management, use consistent tagging:

### Recommended Tags
- `Service`: MongoDB, GitLab, WebServer, etc.
- `Environment`: Production, Staging, Development
- `SSMManaged`: true (for SSM-managed instances)
- `MonitoringLevel`: Basic, Advanced, Custom

### Example Fleet Commands with Tags
```bash
# Configure MongoDB monitoring on all MongoDB instances
aws ssm send-command \
    --document-name \"InstallCloudWatchAgent\" \
    --parameters \"parameterStoreConfig=AmazonCloudWatch-linux/mongo\" \
    --targets \"Key=tag:Service,Values=MongoDB\"

# Configure GitLab monitoring on all GitLab instances
aws ssm send-command \
    --document-name \"InstallCloudWatchAgent\" \
    --parameters \"parameterStoreConfig=AmazonCloudWatch-linux/gitlab\" \
    --targets \"Key=tag:Service,Values=GitLab\"
```

## 🎯 Troubleshooting

### Common Issues

#### 1. Permission Errors
```bash
# Check IAM role
curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/

# Verify CloudWatch permissions
aws cloudwatch list-metrics --max-items 1

# Check SSM permissions
aws ssm get-parameter --name \"/aws/service/global-infrastructure/regions\"
```

#### 2. Agent Not Starting
```bash
# Check service status
sudo systemctl status amazon-cloudwatch-agent

# Check logs
sudo journalctl -u amazon-cloudwatch-agent -f

# Validate configuration
python -m json.tool /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
```

#### 3. Configuration Issues
```bash
# Check Parameter Store access
aws ssm get-parameter --name \"AmazonCloudWatch-linux/mongo\"

# Manual configuration test
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json \
    -a fetch-config
```

### Log Files
- Installation logs: `/var/log/cloudwatch-agent-install.log`
- Configuration logs: `/var/log/cloudwatch-agent-configure.log`
- Service logs: `sudo journalctl -u amazon-cloudwatch-agent`

## 📈 Monitoring and Alerting

### CloudWatch Metrics

After configuration, metrics will appear in CloudWatch under the configured namespace:
- **MongoDB**: `MongoDB` namespace
- **GitLab**: `GitLab` namespace
- **Basic**: `CWAgent` namespace

### Setting Up Alarms

```bash
# CPU utilization alarm
aws cloudwatch put-metric-alarm \
    --alarm-name \"MongoDB-HighCPU\" \
    --alarm-description \"MongoDB process high CPU usage\" \
    --metric-name \"procstat_cpu_usage\" \
    --namespace \"MongoDB\" \
    --statistic \"Average\" \
    --period 300 \
    --threshold 80 \
    --comparison-operator \"GreaterThanThreshold\" \
    --evaluation-periods 2

# Memory utilization alarm
aws cloudwatch put-metric-alarm \
    --alarm-name \"System-HighMemory\" \
    --alarm-description \"System high memory usage\" \
    --metric-name \"mem_used_percent\" \
    --namespace \"MongoDB\" \
    --statistic \"Average\" \
    --period 300 \
    --threshold 85 \
    --comparison-operator \"GreaterThanThreshold\" \
    --evaluation-periods 2
```

## 🔒 Security Best Practices

### IAM Permissions
- Use least privilege principle
- Separate roles for different environments
- Regular permission audits

### Parameter Store Security
- Use SecureString for sensitive configurations
- Implement proper access controls
- Enable CloudTrail for audit logging

### Agent Security
- Run agent as non-root user (cwagent)
- Secure configuration file permissions
- Regular security updates

## 🚦 Operational Procedures

### Regular Maintenance
1. **Monthly**: Review and update configurations
2. **Quarterly**: Audit IAM permissions
3. **Annually**: Update agent versions

### Emergency Procedures
```bash
# Stop agent on all instances
bash ssm-commands.sh stop-agent

# Emergency configuration rollback
aws ssm send-command \
    --document-name \"InstallCloudWatchAgent\" \
    --parameters \"parameterStoreConfig=AmazonCloudWatch-linux/basic\" \
    --targets \"Key=tag:SSMManaged,Values=true\"
```

## 📚 Additional Resources

### AWS Documentation
- [CloudWatch Agent User Guide](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Install-CloudWatch-Agent.html)
- [CloudWatch Agent Configuration Reference](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-Configuration-File-Details.html)
- [Systems Manager User Guide](https://docs.aws.amazon.com/systems-manager/latest/userguide/what-is-systems-manager.html)

### Training Materials
- AWS CloudWatch Agent & EC2 Monitoring Training (see `agent.md`)
- AWS Systems Manager Training (see `../01-aws-ssm/`)

## 🤝 Contributing

When adding new configurations:

1. Test thoroughly in a development environment
2. Document all parameters and their effects
3. Update this README with new configuration details
4. Follow the existing naming conventions for Parameter Store

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review CloudWatch Agent logs
3. Verify IAM permissions
4. Check AWS service status

---

**Note**: Always test configurations in a development environment before deploying to production. This documentation assumes familiarity with AWS services and Amazon Linux 2 administration.