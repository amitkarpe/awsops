# AWS Operations Training Repository

This repository contains comprehensive AWS Operations training materials and documentation, focusing on practical implementation of AWS services including Systems Manager (SSM) and CloudWatch.

## Repository Structure

- `docs/` - Main documentation organized by AWS service
  - `01-aws-ssm/` - AWS Systems Manager training materials
  - `02-aws-cloudwatch/` - AWS CloudWatch training materials
  - `rule.md` - Marp presentation generation guidelines
- `issues.md` - Task tracking and repository issues
- `README.md` - This file

## Content Overview

### AWS Systems Manager (SSM)
- Inventory management
- Session Manager
- Patch Manager  
- Compliance scanning
- Run Command

### AWS CloudWatch
- Alerts and monitoring
- SNS integration
- Best practices

## Presentation Generation

This repository uses [Marp](https://github.com/marp-team/marp) for converting Markdown to presentations:

```bash
# Generate HTML presentation
marp presentation.md -o ssm-presentation.html

# Generate PowerPoint presentation  
marp presentation.md --pptx -o ssm-presentation.pptx
```

## GitHub Integration with Claude

Claude Code can interact with this repository through GitHub integration by:

1. **Direct Repository Access**: When connected to GitHub, Claude can read, edit, and create files in your repository
2. **Branch Management**: Claude can create new branches, switch between branches, and merge changes
3. **Commit Creation**: Claude can stage changes and create commits with appropriate messages
4. **Pull Request Management**: Claude can create pull requests and manage the review process

### Setting Up GitHub Integration

To enable Claude to write to your GitHub repository:

1. **Authentication**: Ensure Claude Code has proper GitHub authentication tokens
2. **Repository Permissions**: Grant appropriate read/write permissions to the repository
3. **Branch Protection**: Configure branch protection rules if needed for main branch

### Workflow with Claude

```bash
# Claude can perform these operations:
git status                    # Check repository status
git add .                     # Stage changes
git commit -m "message"       # Create commits
git push origin branch-name   # Push to remote
gh pr create                  # Create pull requests
```

Claude follows best practices by:
- Creating descriptive commit messages
- Following existing code conventions
- Running tests before committing (if available)
- Using proper Git workflow patterns

## Contributing

This repository focuses on educational AWS operations content. All materials emphasize practical, hands-on implementation with real-world examples and step-by-step procedures.
