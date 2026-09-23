# AWS Ops

Clean successor to [aws-secops](https://github.com/amitkarpe/aws-secops).

`awsops` keeps only proven security-operation contracts and rebuilds them behind a small layered architecture. The old repository remains the reference/archive until migration cutover.

## Current status

Roadmap Autopilot migration is tracked in Issue #1. M1 establishes the clean contract and migration inventory; no AWS mutation is part of M1.

## Test

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
