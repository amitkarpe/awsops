#!/bin/bash
#
# AWS Systems Manager Run Command Examples for CloudWatch Agent
# This script provides utilities and examples for managing CloudWatch Agent across EC2 fleet
#
# Usage:
#   bash ssm-commands.sh <command> [options]
#
# Commands:
#   create-document    - Create the SSM document
#   install-all        - Install CloudWatch Agent on all managed instances
#   configure-mongo    - Configure MongoDB monitoring on tagged instances
#   configure-gitlab   - Configure GitLab monitoring on tagged instances
#   create-configs     - Create sample configurations in Parameter Store
#   check-status       - Check CloudWatch Agent status across fleet
#   start-agent        - Start CloudWatch Agent on all instances
#   stop-agent         - Stop CloudWatch Agent on all instances
#   list-instances     - List all managed instances
#   help               - Show this help message
#
# Prerequisites:
# - AWS CLI configured with appropriate permissions
# - EC2 instances with SSM Agent installed and managed
# - IAM permissions for SSM and CloudWatch
#

set -euo pipefail

# Configuration
SCRIPT_NAME="ssm-commands"
DOCUMENT_NAME="InstallCloudWatchAgent"
REGION="${AWS_DEFAULT_REGION:-$(aws configure get region)}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${1}"
}

error_exit() {
    log "${RED}ERROR: ${1}${NC}"
    exit 1
}

success() {
    log "${GREEN}SUCCESS: ${1}${NC}"
}

info() {
    log "${BLUE}INFO: ${1}${NC}"
}

warning() {
    log "${YELLOW}WARNING: ${1}${NC}"
}

# Usage information
usage() {
    cat << EOF
AWS Systems Manager CloudWatch Agent Management

Usage: $0 <command> [options]

Commands:
    create-document         Create the SSM document for CloudWatch Agent
    install-all            Install CloudWatch Agent on all managed instances
    configure-mongo        Configure MongoDB monitoring on tagged instances
    configure-gitlab       Configure GitLab monitoring on tagged instances
    create-configs         Create sample configurations in Parameter Store
    check-status           Check CloudWatch Agent status across fleet
    start-agent            Start CloudWatch Agent on all instances
    stop-agent             Stop CloudWatch Agent on all instances
    list-instances         List all managed instances
    help                   Show this help message

Examples:
    $0 create-document
    $0 install-all
    $0 configure-mongo
    $0 configure-gitlab
    $0 check-status
    $0 list-instances

Prerequisites:
    - AWS CLI configured with appropriate permissions
    - EC2 instances with SSM Agent installed and managed
    - IAM permissions for SSM and CloudWatch

EOF
}

# Check prerequisites
check_prerequisites() {
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        error_exit "AWS CLI not found. Please install it first"
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity > /dev/null 2>&1; then
        error_exit "AWS credentials not configured. Please run 'aws configure'"
    fi
    
    # Check region
    if [[ -z "$REGION" ]]; then
        error_exit "AWS region not set. Please set AWS_DEFAULT_REGION or configure default region"
    fi
    
    info "Prerequisites check passed"
    info "Using region: $REGION"
    info "Account ID: $ACCOUNT_ID"
}

# Create SSM document
create_document() {
    info "Creating SSM document: $DOCUMENT_NAME"
    
    # Check if document already exists
    if aws ssm describe-document --name "$DOCUMENT_NAME" --region "$REGION" > /dev/null 2>&1; then
        warning "Document $DOCUMENT_NAME already exists. Updating..."
        
        # Update the document
        if aws ssm update-document \
            --name "$DOCUMENT_NAME" \
            --content file://ssm-document-install-cloudwatch-agent.json \
            --document-format JSON \
            --region "$REGION" > /dev/null 2>&1; then
            success "Document $DOCUMENT_NAME updated successfully"
        else
            error_exit "Failed to update document $DOCUMENT_NAME"
        fi
    else
        # Create new document
        if aws ssm create-document \
            --name "$DOCUMENT_NAME" \
            --document-type "Command" \
            --document-format JSON \
            --content file://ssm-document-install-cloudwatch-agent.json \
            --region "$REGION" > /dev/null 2>&1; then
            success "Document $DOCUMENT_NAME created successfully"
        else
            error_exit "Failed to create document $DOCUMENT_NAME"
        fi
    fi
    
    # Set default version
    aws ssm update-document-default-version \
        --name "$DOCUMENT_NAME" \
        --document-version '$LATEST' \
        --region "$REGION" > /dev/null 2>&1 || true
    
    info "Document ARN: arn:aws:ssm:$REGION:$ACCOUNT_ID:document/$DOCUMENT_NAME"
}

# List managed instances
list_instances() {
    info "Listing managed instances..."
    
    # Get all managed instances
    local instances
    instances=$(aws ssm describe-instance-information \
        --query 'InstanceInformationList[?PingStatus==`Online`].[InstanceId,Name,PlatformType,PlatformVersion]' \
        --output table \
        --region "$REGION" 2>/dev/null)
    
    if [[ -n "$instances" ]]; then
        echo "$instances"
    else
        warning "No managed instances found"
    fi
}

# Run command on all instances
run_command_all() {
    local document_name="$1"
    local parameters="$2"
    local comment="$3"
    
    info "Running command on all managed instances..."
    
    # Get list of online instances
    local instance_ids
    instance_ids=$(aws ssm describe-instance-information \
        --query 'InstanceInformationList[?PingStatus==`Online`].InstanceId' \
        --output text \
        --region "$REGION" 2>/dev/null)
    
    if [[ -z "$instance_ids" ]]; then
        error_exit "No online managed instances found"
    fi
    
    info "Found $(echo $instance_ids | wc -w) online instances"
    
    # Execute command
    local command_id
    command_id=$(aws ssm send-command \
        --document-name "$document_name" \
        --parameters "$parameters" \
        --targets "Key=instanceids,Values=$instance_ids" \
        --comment "$comment" \
        --region "$REGION" \
        --query 'Command.CommandId' \
        --output text 2>/dev/null)
    
    if [[ -n "$command_id" ]]; then
        success "Command executed successfully. Command ID: $command_id"
        
        # Wait for command to complete
        info "Waiting for command to complete..."
        aws ssm wait command-executed \
            --command-id "$command_id" \
            --region "$REGION" 2>/dev/null || true
        
        # Show command status
        show_command_status "$command_id"
    else
        error_exit "Failed to execute command"
    fi
}

# Run command on tagged instances
run_command_tagged() {
    local document_name="$1"
    local parameters="$2"
    local comment="$3"
    local tag_key="$4"
    local tag_value="$5"
    
    info "Running command on instances with tag $tag_key=$tag_value..."
    
    # Execute command on tagged instances
    local command_id
    command_id=$(aws ssm send-command \
        --document-name "$document_name" \
        --parameters "$parameters" \
        --targets "Key=tag:$tag_key,Values=$tag_value" \
        --comment "$comment" \
        --region "$REGION" \
        --query 'Command.CommandId' \
        --output text 2>/dev/null)
    
    if [[ -n "$command_id" ]]; then
        success "Command executed successfully. Command ID: $command_id"
        
        # Wait for command to complete
        info "Waiting for command to complete..."
        aws ssm wait command-executed \
            --command-id "$command_id" \
            --region "$REGION" 2>/dev/null || true
        
        # Show command status
        show_command_status "$command_id"
    else
        error_exit "Failed to execute command"
    fi
}

# Show command status
show_command_status() {
    local command_id="$1"
    
    info "Command execution results:"
    echo "========================"
    
    # Get command invocations
    local results
    results=$(aws ssm list-command-invocations \
        --command-id "$command_id" \
        --details \
        --region "$REGION" 2>/dev/null)
    
    if [[ -n "$results" ]]; then
        echo "$results" | jq -r '.CommandInvocations[] | "Instance: \(.InstanceId) | Status: \(.Status) | Output: \(.CommandPlugins[0].Output // \"No output\")"' 2>/dev/null || echo "$results"
    else
        warning "No command results found"
    fi
}

# Install CloudWatch Agent on all instances
install_all() {
    info "Installing CloudWatch Agent on all managed instances..."
    
    run_command_all \
        "$DOCUMENT_NAME" \
        "parameterStoreConfig=AmazonCloudWatch-linux/basic,installOnly=false,createSampleConfigs=false" \
        "Install and configure CloudWatch Agent on all instances"
}

# Configure MongoDB monitoring
configure_mongo() {
    info "Configuring MongoDB monitoring on tagged instances..."
    
    run_command_tagged \
        "$DOCUMENT_NAME" \
        "parameterStoreConfig=AmazonCloudWatch-linux/mongo,installOnly=false,createSampleConfigs=false" \
        "Configure CloudWatch Agent for MongoDB monitoring" \
        "Service" \
        "MongoDB"
}

# Configure GitLab monitoring
configure_gitlab() {
    info "Configuring GitLab monitoring on tagged instances..."
    
    run_command_tagged \
        "$DOCUMENT_NAME" \
        "parameterStoreConfig=AmazonCloudWatch-linux/gitlab,installOnly=false,createSampleConfigs=false" \
        "Configure CloudWatch Agent for GitLab monitoring" \
        "Service" \
        "GitLab"
}

# Create sample configurations
create_configs() {
    info "Creating sample configurations in Parameter Store..."
    
    # Run on any single instance to create configs
    local instance_id
    instance_id=$(aws ssm describe-instance-information \
        --query 'InstanceInformationList[?PingStatus==`Online`].InstanceId' \
        --output text \
        --region "$REGION" \
        --max-items 1 2>/dev/null | head -n1)
    
    if [[ -z "$instance_id" ]]; then
        error_exit "No online managed instances found"
    fi
    
    local command_id
    command_id=$(aws ssm send-command \
        --document-name "$DOCUMENT_NAME" \
        --parameters "createSampleConfigs=true,installOnly=true" \
        --targets "Key=instanceids,Values=$instance_id" \
        --comment "Create sample configurations in Parameter Store" \
        --region "$REGION" \
        --query 'Command.CommandId' \
        --output text 2>/dev/null)
    
    if [[ -n "$command_id" ]]; then
        success "Configuration creation command executed. Command ID: $command_id"
        
        # Wait for command to complete
        info "Waiting for command to complete..."
        aws ssm wait command-executed \
            --command-id "$command_id" \
            --region "$REGION" 2>/dev/null || true
        
        # Show command status
        show_command_status "$command_id"
    else
        error_exit "Failed to create sample configurations"
    fi
}

# Check CloudWatch Agent status
check_status() {
    info "Checking CloudWatch Agent status across fleet..."
    
    # Use AWS-RunShellScript to check status
    local command_id
    command_id=$(aws ssm send-command \
        --document-name "AWS-RunShellScript" \
        --parameters 'commands=["systemctl is-active amazon-cloudwatch-agent || echo \"NOT_RUNNING\"", "systemctl is-enabled amazon-cloudwatch-agent || echo \"NOT_ENABLED\"", "rpm -q amazon-cloudwatch-agent || echo \"NOT_INSTALLED\""]' \
        --targets "Key=tag:SSMManaged,Values=true" \
        --comment "Check CloudWatch Agent status" \
        --region "$REGION" \
        --query 'Command.CommandId' \
        --output text 2>/dev/null)
    
    if [[ -n "$command_id" ]]; then
        success "Status check command executed. Command ID: $command_id"
        
        # Wait for command to complete
        info "Waiting for command to complete..."
        aws ssm wait command-executed \
            --command-id "$command_id" \
            --region "$REGION" 2>/dev/null || true
        
        # Show command status
        show_command_status "$command_id"
    else
        error_exit "Failed to check status"
    fi
}

# Start CloudWatch Agent
start_agent() {
    info "Starting CloudWatch Agent on all instances..."
    
    run_command_all \
        "AWS-RunShellScript" \
        'commands=["systemctl start amazon-cloudwatch-agent", "systemctl enable amazon-cloudwatch-agent", "systemctl status amazon-cloudwatch-agent --no-pager -l"]' \
        "Start CloudWatch Agent on all instances"
}

# Stop CloudWatch Agent
stop_agent() {
    info "Stopping CloudWatch Agent on all instances..."
    
    run_command_all \
        "AWS-RunShellScript" \
        'commands=["systemctl stop amazon-cloudwatch-agent", "systemctl status amazon-cloudwatch-agent --no-pager -l"]' \
        "Stop CloudWatch Agent on all instances"
}

# Main function
main() {
    local command="${1:-}"
    
    if [[ -z "$command" ]]; then
        usage
        exit 1
    fi
    
    case "$command" in
        create-document)
            check_prerequisites
            create_document
            ;;
        install-all)
            check_prerequisites
            install_all
            ;;
        configure-mongo)
            check_prerequisites
            configure_mongo
            ;;
        configure-gitlab)
            check_prerequisites
            configure_gitlab
            ;;
        create-configs)
            check_prerequisites
            create_configs
            ;;
        check-status)
            check_prerequisites
            check_status
            ;;
        start-agent)
            check_prerequisites
            start_agent
            ;;
        stop-agent)
            check_prerequisites
            stop_agent
            ;;
        list-instances)
            check_prerequisites
            list_instances
            ;;
        help)
            usage
            ;;
        *)
            error_exit "Unknown command: $command. Use 'help' for usage information"
            ;;
    esac
}

# Execute main function
main "$@"