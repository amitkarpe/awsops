# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is the **awsops** repository containing AWS Operations training materials and documentation. The repository is focused on creating educational content for AWS services, specifically Systems Manager (SSM) and CloudWatch.

## Repository Structure

- `docs/` - Main documentation directory organized by AWS service
  - `01-aws-ssm/` - AWS Systems Manager training materials
  - `02-aws-cloudwatch/` - AWS CloudWatch training materials
  - `rule.md` - Contains Marp presentation generation rules
- `issues.md` - Issue tracking for repository tasks
- `README.md` - Basic repository description

## Common Commands

### Presentation Generation
This repository uses Marp for converting Markdown presentations to HTML/PowerPoint:

```bash
# Generate HTML presentation from Markdown
marp presentation.md -o ssm-presentation.html

# Generate PowerPoint presentation
marp presentation.md --pptx -o ssm-presentation.pptx
```

Note: Marp must be installed separately. See https://github.com/marp-team/marp

## Content Standards

### Presentation Format
- All presentations use Marp with YAML frontmatter:
  ```yaml
  ---
  marp: true
  theme: default
  paginate: true
  ---
  ```
- Standard presenter attribution: "Presented by: [Amit Karpe]"

### Documentation Structure
- Each AWS service gets its own numbered directory (e.g., `01-aws-ssm/`, `02-aws-cloudwatch/`)
- Content includes both `.md` source files and generated `.html` presentations
- Training materials follow a consistent agenda structure with practical examples

## Architecture Notes

This is a documentation-only repository with no application code. The architecture is purely organizational:

1. **Training Materials**: Structured by AWS service with progressive numbering
2. **Content Types**: 
   - Markdown source files for presentations
   - Generated HTML presentations for delivery
   - Installation and setup guides
3. **Content Flow**: Markdown → Marp → HTML/PowerPoint for training delivery

## Current Content Areas

- **AWS Systems Manager (SSM)**: Inventory management, Session Manager, Patch Manager, Compliance scanning, Run Command
- **AWS CloudWatch**: Alerts, monitoring, SNS integration, best practices

All content focuses on practical implementation with command-line examples and step-by-step procedures.