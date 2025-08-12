#!/bin/bash
#
# AWS CloudWatch Agent Configuration Script
# For Amazon Linux 2 with Parameter Store Integration
# 
# This script configures the CloudWatch Agent using configurations stored in AWS Parameter Store
# Supports MongoDB and GitLab monitoring configurations
# 
# Usage: 
#   sudo bash configure-cloudwatch-agent.sh -p <parameter-name>
#   sudo bash configure-cloudwatch-agent.sh -c  # Create sample configurations
#
# Examples:
#   sudo bash configure-cloudwatch-agent.sh -p AmazonCloudWatch-linux/mongo
#   sudo bash configure-cloudwatch-agent.sh -p AmazonCloudWatch-linux/gitlab
#   sudo bash configure-cloudwatch-agent.sh -c  # Create sample configs in Parameter Store
#
# Prerequisites:
# - CloudWatch Agent installed
# - IAM role with CloudWatchAgentServerRole and SSM permissions
# - Parameter Store configurations created
#

set -euo pipefail

# Configuration
SCRIPT_NAME="configure-cloudwatch-agent"
LOG_FILE="/var/log/cloudwatch-agent-configure.log"
CONFIG_FILE="/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json"
AGENT_BIN="/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Global variables
PARAMETER_NAME=""
CREATE_SAMPLES=false
REGION=""

# Logging function
log() {
    echo -e "${1}" | tee -a "${LOG_FILE}"
}

# Error handling
error_exit() {
    log "${RED}ERROR: ${1}${NC}"
    exit 1
}

# Success message
success() {
    log "${GREEN}SUCCESS: ${1}${NC}"
}

# Info message
info() {
    log "${BLUE}INFO: ${1}${NC}"
}

# Warning message
warning() {
    log "${YELLOW}WARNING: ${1}${NC}"
}

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    -p <parameter-name>    Parameter Store name containing CloudWatch Agent config
    -c                     Create sample configurations in Parameter Store
    -h                     Show this help message

Examples:
    $0 -p AmazonCloudWatch-linux/mongo     # Configure with MongoDB monitoring
    $0 -p AmazonCloudWatch-linux/gitlab    # Configure with GitLab monitoring
    $0 -c                                   # Create sample configurations

Parameter Store Examples:
    - arn:aws:ssm:ap-southeast-1:021577063369:parameter/AmazonCloudWatch-linux/mongo
    - arn:aws:ssm:ap-southeast-1:021577063369:parameter/AmazonCloudWatch-linux/gitlab

EOF
}

# Parse command line arguments
parse_args() {
    while getopts "p:ch" opt; do
        case $opt in
            p)
                PARAMETER_NAME="$OPTARG"
                ;;
            c)
                CREATE_SAMPLES=true
                ;;
            h)
                usage
                exit 0
                ;;
            \?)
                error_exit "Invalid option: -$OPTARG"
                ;;
            :)
                error_exit "Option -$OPTARG requires an argument"
                ;;
        esac
    done
    
    if [[ -z "$PARAMETER_NAME" && "$CREATE_SAMPLES" = false ]]; then
        error_exit "Please specify -p <parameter-name> or -c. Use -h for help"
    fi
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error_exit "This script must be run as root. Use 'sudo bash $0'"
    fi
}

# Get current region
get_region() {
    REGION=$(curl -s --connect-timeout 5 http://169.254.169.254/latest/meta-data/placement/availability-zone | sed 's/[a-z]$//')
    if [[ -z "$REGION" ]]; then
        error_exit "Unable to determine AWS region"
    fi
    info "Using region: $REGION"
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."
    
    # Check if CloudWatch Agent is installed
    if [[ ! -f "$AGENT_BIN" ]]; then
        error_exit "CloudWatch Agent not found. Please install it first using install-cloudwatch-agent.sh"
    fi
    
    # Check if AWS CLI is available
    if ! command -v aws &> /dev/null; then
        error_exit "AWS CLI not found. Please install it first"
    fi
    
    # Check IAM permissions
    if ! aws ssm get-parameter --name "/aws/service/global-infrastructure/regions" --region "$REGION" > /dev/null 2>&1; then
        error_exit "SSM permissions not available. Ensure IAM role has SSM permissions"
    fi
    
    success "Prerequisites check passed"
}

# Create MongoDB configuration
create_mongo_config() {
    cat << 'EOF'
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "cwagent"
  },
  "metrics": {
    "namespace": "MongoDB",
    "metrics_collected": {
      "disk": {
        "measurement": [
          "used_percent"
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "/",
          "/var/lib/mongo"
        ],
        "append_dimensions": {
          "Group": "Mongo"
        }
      },
      "mem": {
        "measurement": [
          "mem_used_percent"
        ],
        "metrics_collection_interval": 60
      },
      "cpu": {
        "measurement": [
          "cpu_usage_idle",
          "cpu_usage_iowait",
          "cpu_usage_user",
          "cpu_usage_system"
        ],
        "metrics_collection_interval": 60,
        "totalcpu": true
      },
      "procstat": [
        {
          "pattern": "mongod",
          "measurement": [
            "cpu_usage",
            "memory_rss",
            "memory_vms"
          ],
          "append_dimensions": {
            "Process": "MongoDB"
          }
        }
      ]
    },
    "append_dimensions": {
      "InstanceName": "${aws:Tag/Name}",
      "Environment": "${aws:Tag/Environment}"
    }
  }
}
EOF
}

# Create GitLab configuration
create_gitlab_config() {
    cat << 'EOF'
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "cwagent"
  },
  "metrics": {
    "namespace": "GitLab",
    "metrics_collected": {
      "disk": {
        "measurement": [
          "used_percent"
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "/",
          "/var/opt/gitlab"
        ],
        "append_dimensions": {
          "Group": "GitLab"
        }
      },
      "mem": {
        "measurement": [
          "mem_used_percent"
        ],
        "metrics_collection_interval": 60
      },
      "cpu": {
        "measurement": [
          "cpu_usage_idle",
          "cpu_usage_iowait",
          "cpu_usage_user",
          "cpu_usage_system"
        ],
        "metrics_collection_interval": 60,
        "totalcpu": true
      },
      "procstat": [
        {
          "pattern": "gitlab",
          "measurement": [
            "cpu_usage",
            "memory_rss"
          ],
          "append_dimensions": {
            "Process": "GitLab"
          }
        },
        {
          "pattern": "nginx",
          "measurement": [
            "cpu_usage",
            "memory_rss"
          ],
          "append_dimensions": {
            "Process": "Nginx"
          }
        },
        {
          "pattern": "postgres",
          "measurement": [
            "cpu_usage",
            "memory_rss"
          ],
          "append_dimensions": {
            "Process": "PostgreSQL"
          }
        }
      ]
    },
    "append_dimensions": {
      "InstanceName": "${aws:Tag/Name}",
      "Environment": "${aws:Tag/Environment}"
    }
  }
}
EOF
}

# Create basic configuration
create_basic_config() {
    cat << 'EOF'
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "cwagent"
  },
  "metrics": {
    "namespace": "CWAgent",
    "metrics_collected": {
      "disk": {
        "measurement": [
          "used_percent"
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "/"
        ]
      },
      "mem": {
        "measurement": [
          "mem_used_percent"
        ],
        "metrics_collection_interval": 60
      },
      "cpu": {
        "measurement": [
          "cpu_usage_idle",
          "cpu_usage_iowait",
          "cpu_usage_user",
          "cpu_usage_system"
        ],
        "metrics_collection_interval": 60,
        "totalcpu": true
      }
    },
    "append_dimensions": {
      "InstanceName": "${aws:Tag/Name}",
      "Environment": "${aws:Tag/Environment}"
    }
  }
}
EOF
}

# Create sample configurations in Parameter Store
create_sample_configs() {
    info "Creating sample configurations in Parameter Store..."
    
    # Create MongoDB configuration
    info "Creating MongoDB configuration..."
    if aws ssm put-parameter \
        --name "AmazonCloudWatch-linux/mongo" \
        --type "String" \
        --value "$(create_mongo_config)" \
        --description "CloudWatch Agent configuration for MongoDB monitoring" \
        --region "$REGION" \
        --overwrite > /dev/null 2>&1; then
        success "MongoDB configuration created: AmazonCloudWatch-linux/mongo"
    else
        warning "Failed to create MongoDB configuration (may already exist)"
    fi
    
    # Create GitLab configuration
    info "Creating GitLab configuration..."
    if aws ssm put-parameter \
        --name "AmazonCloudWatch-linux/gitlab" \
        --type "String" \
        --value "$(create_gitlab_config)" \
        --description "CloudWatch Agent configuration for GitLab monitoring" \
        --region "$REGION" \
        --overwrite > /dev/null 2>&1; then
        success "GitLab configuration created: AmazonCloudWatch-linux/gitlab"
    else
        warning "Failed to create GitLab configuration (may already exist)"
    fi
    
    # Create basic configuration
    info "Creating basic configuration..."
    if aws ssm put-parameter \
        --name "AmazonCloudWatch-linux/basic" \
        --type "String" \
        --value "$(create_basic_config)" \
        --description "CloudWatch Agent basic configuration" \
        --region "$REGION" \
        --overwrite > /dev/null 2>&1; then
        success "Basic configuration created: AmazonCloudWatch-linux/basic"
    else
        warning "Failed to create basic configuration (may already exist)"
    fi
    
    info "Sample configurations created successfully!"
    echo ""
    echo "Available configurations:"
    echo "- AmazonCloudWatch-linux/mongo  (MongoDB monitoring)"
    echo "- AmazonCloudWatch-linux/gitlab (GitLab monitoring)" 
    echo "- AmazonCloudWatch-linux/basic  (Basic system monitoring)"
    echo ""
    echo "Usage examples:"
    echo "sudo $0 -p AmazonCloudWatch-linux/mongo"
    echo "sudo $0 -p AmazonCloudWatch-linux/gitlab"
    echo "sudo $0 -p AmazonCloudWatch-linux/basic"
}

# Fetch configuration from Parameter Store
fetch_config() {
    info "Fetching configuration from Parameter Store: $PARAMETER_NAME"
    
    local config_content
    if config_content=$(aws ssm get-parameter --name "$PARAMETER_NAME" --region "$REGION" --query "Parameter.Value" --output text 2>/dev/null); then
        success "Configuration retrieved from Parameter Store"
        echo "$config_content" > "$CONFIG_FILE"
        chown cwagent:cwagent "$CONFIG_FILE"
        chmod 644 "$CONFIG_FILE"
        success "Configuration saved to $CONFIG_FILE"
    else
        error_exit "Failed to retrieve configuration from Parameter Store: $PARAMETER_NAME"
    fi
}

# Validate configuration
validate_config() {
    info "Validating configuration..."
    
    if [[ ! -f "$CONFIG_FILE" ]]; then
        error_exit "Configuration file not found: $CONFIG_FILE"
    fi
    
    # Check if configuration is valid JSON
    if ! python -m json.tool "$CONFIG_FILE" > /dev/null 2>&1; then
        error_exit "Invalid JSON in configuration file"
    fi
    
    success "Configuration validation passed"
}

# Configure and start agent
configure_agent() {
    info "Configuring CloudWatch Agent..."
    
    # Stop the agent if running
    if systemctl is-active --quiet amazon-cloudwatch-agent; then
        info "Stopping CloudWatch Agent..."
        systemctl stop amazon-cloudwatch-agent
    fi
    
    # Configure the agent
    if sudo -u cwagent "$AGENT_BIN" -c file:"$CONFIG_FILE" -a fetch-config; then
        success "Agent configured successfully"
    else
        error_exit "Failed to configure agent"
    fi
    
    # Start the agent
    info "Starting CloudWatch Agent..."
    if systemctl start amazon-cloudwatch-agent; then
        success "CloudWatch Agent started successfully"
    else
        error_exit "Failed to start CloudWatch Agent"
    fi
    
    # Enable auto-start
    systemctl enable amazon-cloudwatch-agent
}

# Check agent status
check_agent_status() {
    info "Checking agent status..."
    
    if systemctl is-active --quiet amazon-cloudwatch-agent; then
        success "CloudWatch Agent is running"
        
        # Show agent status
        echo ""
        echo "Agent Status:"
        systemctl status amazon-cloudwatch-agent --no-pager -l
        
        echo ""
        echo "Recent logs:"
        journalctl -u amazon-cloudwatch-agent --no-pager -l --since "5 minutes ago"
        
    else
        error_exit "CloudWatch Agent is not running"
    fi
}

# Display configuration summary
display_summary() {
    info "Configuration Summary:"
    echo "===================="
    echo "✓ Configuration retrieved from Parameter Store"
    echo "✓ Agent configured and started"
    echo "✓ Service enabled for auto-start"
    echo ""
    echo "Configuration Details:"
    echo "- Parameter: $PARAMETER_NAME"
    echo "- Config File: $CONFIG_FILE"
    echo "- Region: $REGION"
    echo ""
    echo "Useful Commands:"
    echo "- Check status: sudo systemctl status amazon-cloudwatch-agent"
    echo "- View logs: sudo journalctl -u amazon-cloudwatch-agent -f"
    echo "- Restart: sudo systemctl restart amazon-cloudwatch-agent"
    echo ""
    echo "Logs are available at: $LOG_FILE"
}

# Main execution
main() {
    log "${GREEN}Starting CloudWatch Agent Configuration${NC}"
    log "Timestamp: $(date)"
    log "===================="
    
    parse_args "$@"
    check_root
    get_region
    check_prerequisites
    
    if [[ "$CREATE_SAMPLES" = true ]]; then
        create_sample_configs
    else
        fetch_config
        validate_config
        configure_agent
        check_agent_status
        display_summary
    fi
    
    success "CloudWatch Agent configuration completed successfully!"
}

# Run main function
main "$@"