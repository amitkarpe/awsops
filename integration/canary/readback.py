"""Private post-Reject evidence runner for the isolated Issue #11 canary."""
from __future__ import annotations
import argparse, json, os, sqlite3, stat, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from awsops.approval.decisions import DecisionStore, NativeBinding
from awsops.aws.boto3_s3_ssl import assume_role_factory
from awsops.aws.s3_ssl import REGION, collect
from awsops.runtime.prepare_pause import readback_after_reject
from awsops.runtime.read_probe import load_config
from awsops.runtime.s3_ssl_service import S3SslService


def private_file(path: Path) -> None:
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError("PRIVATE_FILE_REQUIRED")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("PRIVATE_FILE_REQUIRED")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise ValueError("PRIVATE_FILE_OWNER_MISMATCH")


def main() -> int:
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root",type=Path,required=True)
    args=parser.parse_args()
    root=args.root.resolve(strict=True)
    manifest=json.loads((root/"manifest.json").read_text())
    if manifest.get("purpose")!="awsops-issue11-isolated-auth-canary":
        raise ValueError("CANARY_REQUIRED")
    binding_file=root/"state/decision-binding.json"
    read_file=root/"state/read.json"
    database=root/"state/receipt.sqlite3"
    for p in (binding_file,read_file,database): private_file(p)
    binding=NativeBinding(**json.loads(binding_file.read_text()))

    with sqlite3.connect(database) as db:
        batches=[row[0] for row in db.execute("SELECT DISTINCT batch_id FROM events ORDER BY sequence")]
    store=DecisionStore(database)
    matches=[]
    for batch in batches:
        try:
            events=store.timeline(batch,binding)
        except Exception:
            continue
        if len(events)==2 and events[-1]["kind"]=="NATIVE_DECISION" and events[-1]["payload"].get("outcome")=="REJECTED":
            matches.append(events)
    if len(matches)!=1: raise ValueError("EXACT_REJECT_RECEIPT_REQUIRED")
    events=matches[0]
    frozen=events[0]["payload"]["frozen"]

    import boto3
    config,bindings=load_config(read_file)
    source=boto3.Session(profile_name=config["profile"],region_name=REGION)
    factory=assume_role_factory(source,expected_source_account=config["source_account_id"])
    service=S3SslService(lambda: collect(bindings,factory))
    result=readback_after_reject(service,store,{
        "version":1,"operation":"readback","binding":json.loads(binding_file.read_text()),
        "batch_id":events[0]["batch_id"],"scope_hash":frozen["scope_hash"],
    })
    dispatch=root/"state/dispatch-attempts.jsonl"
    attempts=len([x for x in dispatch.read_text().splitlines() if x]) if dispatch.exists() else 0
    if not (result.get("ok") is True and result.get("unchanged") is True and
            result.get("state")=="NON_COMPLIANT" and result.get("read_only") is True and
            result.get("dispatch_allowed") is False and attempts==0 and
            result.get("receipt_event_hash")==events[-1]["event_hash"]):
        raise ValueError("CANARY_READBACK_NOT_ACCEPTED")
    print(json.dumps({
        "version":1,"outcome":"READBACK_PASS","batch_id":result["batch_id"],
        "scope_hash":result["scope_hash"],"receipt_event_hash":result["receipt_event_hash"],
        "state":result["state"],"unchanged":True,"dispatch_attempts":0,"aws_writes":0,
    },sort_keys=True))
    return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception:
        print('{"version":1,"outcome":"READBACK_BLOCKED","dispatch_attempts":"UNKNOWN"}')
        raise SystemExit(2)
