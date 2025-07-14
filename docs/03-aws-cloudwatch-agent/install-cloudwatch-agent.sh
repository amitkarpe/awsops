#!/bin/bash
#
# AWS CloudWatch Agent Installation Script
# For Amazon Linux 2
# 
# This script installs the CloudWatch Agent on Amazon Linux 2 instances
# Supports both x86_64 and arm64 architectures
# 
# Usage: sudo bash install-cloudwatch-agent.sh
#
# Prerequisites:
# - EC2 instance with Amazon Linux 2
# - IAM role attached with CloudWatchAgentServerRole policy
# - Internet connectivity for package download
#

set -euo pipefail

# Configuration
SCRIPT_NAME="install-cloudwatch-agent"
LOG_FILE="/var/log/cloudwatch-agent-install.log"
CW_AGENT_VERSION="latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error_exit "This script must be run as root. Use 'sudo bash $0'"
    fi
}

# Check if running on Amazon Linux 2
check_os() {
    if [[ ! -f /etc/system-release ]]; then
        error_exit "This script is designed for Amazon Linux 2"
    fi
    
    if ! grep -q "Amazon Linux 2" /etc/system-release; then
        error_exit "This script is designed for Amazon Linux 2"
    fi
    
    success "Running on Amazon Linux 2"
}

# Detect architecture
detect_architecture() {
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)
            ARCH_SUFFIX="amd64"
            ;;
        aarch64)
            ARCH_SUFFIX="arm64"
            ;;
        *)
            error_exit "Unsupported architecture: $ARCH"
            ;;
    esac
    info "Detected architecture: $ARCH ($ARCH_SUFFIX)"
}

# Check IAM permissions
check_iam_permissions() {
    info "Checking IAM permissions..."
    
    # Check if instance has IAM role
    if ! curl -s --connect-timeout 5 http://169.254.169.254/latest/meta-data/iam/security-credentials/; then
        error_exit "No IAM role attached to this instance. Please attach CloudWatchAgentServerRole"
    fi
    
    # Test CloudWatch permissions
    if ! aws cloudwatch list-metrics --max-items 1 --region $(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone | sed 's/[a-z]$//') > /dev/null 2>&1; then
        warning "CloudWatch permissions test failed. Ensure CloudWatchAgentServerRole is attached"
    else
        success "CloudWatch permissions verified"
    fi
}

# Download CloudWatch Agent
download_agent() {
    info "Downloading CloudWatch Agent..."
    
    cd /tmp
    
    # Download the agent package
    DOWNLOAD_URL="https://s3.amazonaws.com/amazoncloudwatch-agent/amazon_linux/${ARCH_SUFFIX}/${CW_AGENT_VERSION}/amazon-cloudwatch-agent.rpm"
    
    if wget -q --timeout=30 "$DOWNLOAD_URL" -O amazon-cloudwatch-agent.rpm; then
        success "CloudWatch Agent downloaded successfully"
    else
        error_exit "Failed to download CloudWatch Agent from $DOWNLOAD_URL"
    fi
}

# Install CloudWatch Agent
install_agent() {
    info "Installing CloudWatch Agent..."
    
    cd /tmp
    
    # Install the RPM package
    if yum localinstall -y amazon-cloudwatch-agent.rpm; then
        success "CloudWatch Agent installed successfully"
    else
        error_exit "Failed to install CloudWatch Agent"
    fi
    
    # Clean up
    rm -f amazon-cloudwatch-agent.rpm
}

# Configure agent service
configure_service() {
    info "Configuring CloudWatch Agent service..."
    
    # Enable the service
    if systemctl enable amazon-cloudwatch-agent; then
        success "CloudWatch Agent service enabled"
    else
        error_exit "Failed to enable CloudWatch Agent service"
    fi
    
    # Create cloudwatch-agent user if not exists
    if ! id -u cwagent > /dev/null 2>&1; then
        useradd -r -s /bin/false cwagent
        info "Created cwagent user"
    fi
    
    # Set proper permissions
    chown -R cwagent:cwagent /opt/aws/amazon-cloudwatch-agent/
    chmod 755 /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent
}

# Create default configuration directory
create_config_dir() {
    info "Creating configuration directory..."
    
    CONFIG_DIR="/opt/aws/amazon-cloudwatch-agent/etc"
    
    if [[ ! -d "$CONFIG_DIR" ]]; then
        mkdir -p "$CONFIG_DIR"
        chown cwagent:cwagent "$CONFIG_DIR"
        chmod 755 "$CONFIG_DIR"
        success "Configuration directory created: $CONFIG_DIR"
    fi
}

# Display installation summary
display_summary() {
    info "Installation Summary:"
    echo "===================="
    echo "✓ CloudWatch Agent installed successfully"
    echo "✓ Service configured and enabled"
    echo "✓ Configuration directory created"
    echo ""
    echo "Next Steps:"
    echo "1. Configure the agent using Parameter Store:"
    echo "   sudo ./configure-cloudwatch-agent.sh -p AmazonCloudWatch-linux/basic"
    echo ""
    echo "2. Or create a custom configuration:"
    echo "   sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard"
    echo ""
    echo "3. Start the agent:"
    echo "   sudo systemctl start amazon-cloudwatch-agent"
    echo ""
    echo "4. Check agent status:"
    echo "   sudo systemctl status amazon-cloudwatch-agent"
    echo ""
    echo "Logs are available at: $LOG_FILE"
}

# Main execution
main() {
    log "${GREEN}Starting CloudWatch Agent Installation${NC}"
    log "Timestamp: $(date)"
    log "===================="
    
    check_root
    check_os
    detect_architecture
    check_iam_permissions
    download_agent
    install_agent
    configure_service
    create_config_dir
    display_summary
    
    success "CloudWatch Agent installation completed successfully!"
}

# Run main function
main "$@"