"""Synthetic fixture for private Node/Python integration tests; never a live tool."""
from pathlib import Path
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from awsops.approval.decisions import DecisionStore
from awsops.domain.freeze import freeze_finding
from awsops.domain.models import Finding

if __name__ == '__main__':
    DecisionStore(Path(sys.argv[1]))
    now = int(time.time())
    finding = Finding('finding-' + 'a'*20, 'lab-dev', 's3_ssl', 'bucket-ref-' + 'b'*20,
                      'ap-southeast-1', 'NON_COMPLIANT', 'c'*64, now)
    print(json.dumps(freeze_finding(finding, now=now).public_dict()))
