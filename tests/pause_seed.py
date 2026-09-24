"""Test process only: synthetic provider, genuine fresh service and SQLite ledger."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_s3_ssl import FakeClient, bindings, collect
from awsops.approval.decisions import DecisionStore
from awsops.runtime.prepare_pause import prepare_and_register
from awsops.runtime.s3_ssl_service import S3SslService

bound = bindings()
clients = {b.alias: FakeClient(b.account_id) for b in bound}
service = S3SslService(lambda: collect(bound, lambda b: clients[b.alias]))
store = DecisionStore(Path(sys.argv[1]))
if len(sys.argv) == 3 and sys.argv[2] == "candidate":
    f = service.status()["findings"][0]
    result = {"control": "s3_ssl", "account_alias": f["account_alias"],
              "resource_ref": f["resource_ref"], "expected_evidence_digest": f["evidence_digest"]}
else:
    result = prepare_and_register(service, store, json.load(sys.stdin))
    assert sum(c.calls.count("policy") for c in clients.values()) == 4
print(json.dumps(result, separators=(",", ":")))
