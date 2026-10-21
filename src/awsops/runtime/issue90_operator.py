"""Fixed, bounded Issue 90 runtime-only owner-Reject operator.

This is a local operator path, not an API or model-controlled tool. Its only
provider operations are exact-target EC2 lifecycle reads/start/stop and the
fixed AWS-RunShellScript contract below. Private identity, target, command
evidence, claims, and run output stay in an owner-private directory.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
import uuid
import zlib
from typing import Any, Callable

REGION = "ap-southeast-1"
PROFILE = "amit"
MAX_ACTIVE_SECONDS = 20 * 60
STOP_RESERVE_SECONDS = 10 * 60
MAX_WINDOW_SECONDS = MAX_ACTIVE_SECONDS + STOP_RESERVE_SECONDS
MAX_SSM_BYTES = 4096
MAX_SSM_COMMENT_CHARS = 100
SSM_DOCUMENT = "AWS-RunShellScript"
NATIVE_MANAGER_THREAD = "01a142e5-6c7f-7801-bc3d-2bca3c3ad3fc"
NATIVE_CODEX_EXECUTABLE = "/home/dev/.local/bin/codex"
NATIVE_QUEUE_TIMEOUT_SECONDS = 10
OWNER_COST_DIRECTIVE = "https://github.com/amitkarpe/awsops/issues/90#issuecomment-6319701453"
TOTAL_INCREMENTAL_CEILING_USD = "100.00"
ISOLATED_ROOT = "/opt/awsops-native-canary"
ISOLATED_STATE = f"{ISOLATED_ROOT}/state"
ISOLATED_LAUNCHER = f"{ISOLATED_ROOT}/awsops/integration/runtime/issue90-isolated-launcher.sh"
RUNTIME_OWNER_UID = 1001
RUNTIME_OWNER_GID = 1001
PRIVATE_LANE = Path.home() / ".AGENTS-temp/manager/issue90-live-activation"
TARGET_PROPERTY_FILES = {
    "security_groups": "activation-security-groups.private.json",
    "volumes": "activation-volumes.private.json",
    "addresses": "activation-address.private.json",
    "subnets": "activation-subnet.private.json",
}
READY_MARKER = (
    "ISSUE90_ISOLATED_RUNTIME_STARTED; SYNTHETIC_MODEL_STIMULUS_ONLY; "
    "HUMAN_REJECT_REQUIRED; STOP_AFTER_REVIEW"
)
STOP_MARKER = "ISSUE90_ISOLATED_RUNTIME_STOPPED"
EXPECTED_TARGET_REVISION = "948e8bb6b1d6915d2f585e2a2e5c20cc7caf3ced"
EXPECTED_TARGET_ARCHIVE_SHA256 = "e7ede04d45e7d3086a8d5c6b85e7d6193b61a92dbc990d7d0687e23d7d3d0fe8"
EXPECTED_PREDECESSOR_REVISION = "d090c98561e87e4be1ad234891f3f78bc665aa6f"
EXPECTED_PREDECESSOR_ARCHIVE_SHA256 = "3932ba704ce02ccde6393a362a28e6bf2e7ea0b4f883dbd9043f90b0b13877e3"
EXPECTED_PREDECESSOR_MANIFEST_SHA256 = "5638c7ff290385ecf1839e42171aab9d6ec7ac71b0da9322c6b3352f95c72460"
EXPECTED_RUNTIME_MANIFEST_SHA256 = "90d5453d94c027f23ca1e9498dffe437fd0cc350701e806c743455348c7ace7d"
EXPECTED_RUNTIME_SOURCE_MANIFEST_SHA256 = "3c8e23d83954f433830251f8f98be44415afd72e621d587aee1851297777532f"
EXPECTED_INSTALLED_RUNTIME_CONFIG_SHA256 = "feb3aea5db396a3c64f61bb0f57fae56e7b95973752acecf76f9b082135c045a"
EXPECTED_INSTALLED_NATIVE_STORE_SHA256 = "d7f7df44625bc67da0638cf72fa471695834e2e4609e10d7417623e8d84118e1"
EXPECTED_INSTALLED_LAUNCHER_SHA256 = "5070df7ffd5ec608d203e17c53dc0d158a827a173244c6e7e4322e29608f9dc5"
EXPECTED_PREDECESSOR_MIGRATION_SHA256 = "72628fa7f2a898da6525d123815470e63efe2cfd5de08aa9bd6a6d3548502524"
EXPECTED_PREDECESSOR_MIGRATION_GIT_BLOB = "635dca4dcf36c8809c19df8ee5a7fa594226a2e9"
EXPECTED_RUNTIME_MIGRATION_SHA256 = "b949129984ef289b8304fd3d2c66d848a9c766a8e8cace8725dd045414346fcc"
EXPECTED_RUNTIME_MIGRATION_GIT_BLOB = "17d892306faf161de2bd04af11de3845996a204a"
EXPECTED_STEPS = (
    "stage_readback",
    "composed_state_readback",
    "native_binding_readback",
    "ledger_readback",
    "launcher_start",
    "owner_reject_readback",
    "launcher_stop",
)
TERMINAL_SSM = frozenset({
    "Success", "Failed", "TimedOut", "Cancelled", "Cancelling",
    "DeliveryTimedOut", "ExecutionTimedOut", "Undeliverable", "Terminated",
})
RUNTIME_AUTHORITY = {
    "directive": OWNER_COST_DIRECTIVE,
    "mode": "OWNER_LOGIN_REJECT_ONLY",
    "total_incremental_ceiling_usd": TOTAL_INCREMENTAL_CEILING_USD,
    "max_active_seconds": MAX_ACTIVE_SECONDS,
    "stop_reserve_seconds": STOP_RESERVE_SECONDS,
    "historical_cost_gate": "SUPERSEDED_FOR_REJECT_ONLY",
    "monthly_reset": False,
    "remediation_writes": False,
}
NATIVE_QUEUE_RECEIPT = re.compile(
    r"Queued message ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}) "
    r"for thread ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.\n?\Z"
)


class RuntimeRefused(RuntimeError):
    """A safe precondition or reconciliation refusal, identified by code."""


@dataclass(frozen=True)
class Step:
    name: str
    command: str
    execution_timeout: int
    expected_stdout: str | None = None
    json_state: str | None = None


def _strict_json(raw: str) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()))
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeRefused("SSM_JSON_INVALID") from exc
    if type(value) is not dict:
        raise RuntimeRefused("SSM_JSON_OBJECT_REQUIRED")
    return value


def _load_private_json(path: Path, *, expected_uid: int | None = None) -> dict[str, Any]:
    try:
        info = path.lstat()
    except OSError as exc:
        raise RuntimeRefused("PRIVATE_INPUT_UNAVAILABLE") from exc
    if (not path.is_file() or path.is_symlink() or info.st_mode & 0o777 != 0o600
            or (expected_uid is not None and info.st_uid != expected_uid)):
        raise RuntimeRefused("PRIVATE_INPUT_METADATA_REFUSED")
    value = _strict_json(path.read_text(encoding="utf-8"))
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise RuntimeRefused("TARGET_TIMESTAMP_FORMAT_REFUSED")
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, dict):
        normalized = {}
        for key in sorted(value):
            item = value[key]
            if key in {"CreateTime", "AttachTime"} and type(item) is str:
                try:
                    parsed = datetime.fromisoformat(item.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise RuntimeRefused("TARGET_TIMESTAMP_FORMAT_REFUSED") from exc
                if parsed.tzinfo is None or parsed.utcoffset() is None:
                    raise RuntimeRefused("TARGET_TIMESTAMP_FORMAT_REFUSED")
                item = parsed
            normalized[key] = _canonical(item)
        return normalized
    if isinstance(value, list):
        rows = [_canonical(item) for item in value]
        return sorted(rows, key=lambda item: json.dumps(item, sort_keys=True))
    return value


def _private_file(path: Path, expected_hash: str, *, mode: int = 0o600) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise RuntimeRefused("PRIVATE_PIN_UNAVAILABLE") from exc
    if (not path.is_file() or path.is_symlink() or info.st_uid != os.getuid()
            or info.st_mode & 0o777 != mode
            or _sha256(path) != expected_hash):
        raise RuntimeRefused("PRIVATE_PIN_REFUSED")


def validate_runtime_authority(authority: Any) -> None:
    """Pin the owner-authorized bounded Reject-only runtime contract.

    This does not measure spend or reconstruct historical costs. It prevents
    this operator from widening the USD100 total ceiling, adding a monthly
    reset, extending the fixed runtime bounds, or enabling remediation writes.
    """
    if type(authority) is not dict or authority != RUNTIME_AUTHORITY:
        raise RuntimeRefused("RUNTIME_AUTHORITY_REFUSED")


def make_native_manager_notifier(codex_executable: str) -> Callable[[str, str], str | None]:
    """Build the one-shot notifier for the existing local Codex queue route."""
    if type(codex_executable) is not str or not os.path.isabs(codex_executable):
        raise RuntimeRefused("READY_NOTIFIER_EXECUTABLE_REFUSED")

    def notify(_run_id: str, message: str) -> str | None:
        if type(message) is not str or not message or "\x00" in message:
            return None
        argv = [codex_executable, "queue", "--thread", NATIVE_MANAGER_THREAD,
                "--message", message]
        try:
            response = subprocess.run(argv, shell=False, capture_output=True,
                                      text=True, timeout=NATIVE_QUEUE_TIMEOUT_SECONDS,
                                      check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if (response.returncode != 0 or response.stderr != ""
                or type(response.stdout) is not str):
            return None
        match = NATIVE_QUEUE_RECEIPT.fullmatch(response.stdout)
        if match is None or match.group(2) != NATIVE_MANAGER_THREAD:
            return None
        return match.group(1)

    return notify


def _compressed_python(script: str, args: list[str], *, as_root: bool,
                      as_owner: bool = False, compression: str = "zlib") -> str:
    if as_root and as_owner:
        raise RuntimeRefused("SSM_EXECUTION_IDENTITY_CONFLICT")
    if compression == "zlib":
        encoded = base64.b64encode(zlib.compress(script.encode("utf-8"), 9)).decode("ascii")
        decoder = ("import base64,sys,zlib;source=zlib.decompress(base64.b64decode(sys.argv[1]));"
                   "sys.argv=sys.argv[1:];exec(source)")
    elif compression == "lzma":
        import lzma
        encoded = base64.b85encode(lzma.compress(script.encode("utf-8"), preset=9)).decode("ascii")
        decoder = ("import base64,lzma,sys;source=lzma.decompress(base64.b85decode(sys.argv[1]));"
                   "sys.argv=sys.argv[1:];exec(source)")
    else:
        raise RuntimeRefused("SSM_COMPRESSION_REFUSED")
    # sys.argv[1] is the compressed program. Shift it away before the decoded
    # program consumes its own argv, matching the previously reviewed probe.
    if as_owner:
        prefix = "sudo -u ssm-user -- /usr/bin/python3 -I -B -c "
    elif as_root:
        prefix = "sudo /usr/bin/python3 -I -B -c "
    else:
        # AWS-RunShellScript starts as root. A bare command is not owner-scoped.
        prefix = "/usr/bin/python3 -I -B -c "
    return prefix + shlex.quote(decoder) + " " + shlex.quote(encoded) + " " + " ".join(
        shlex.quote(value) for value in args
    )


def _stage_probe(config: dict[str, Any], instance_id: str) -> str:
    script = r'''import hashlib,json,os,stat,sys,tarfile
from pathlib import Path
root,old,new,instance,old_run,new_run,old_rev,old_archive,rev,archive,old_manifest,new_manifest,source_manifest,old_name,new_name=sys.argv[1:]
def refuse(code): print(json.dumps({'state':'REFUSED','code':code},separators=(',',':'))); raise SystemExit(0)
def directory(path,uid,gid,mode):
 try: s=path.lstat()
 except OSError: return False
 return stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode) and (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))==(uid,gid,mode) and path.resolve(strict=True)==path
def file(path,digest,uid,gid,mode):
 try: s=path.lstat(); data=path.read_bytes()
 except OSError: return False
 return stat.S_ISREG(s.st_mode) and not stat.S_ISLNK(s.st_mode) and (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))==(uid,gid,mode) and hashlib.sha256(data).hexdigest()==digest
try:
 root=Path(root); old=Path(old); new=Path(new)
 if not directory(root,1001,1001,0o700) or not directory(old,0,0,0o700) or not directory(new,0,0,0o700): refuse('ROOT_OR_STAGE_METADATA')
 old_marker=f'{old_run}|{instance}|{old_rev}|{old_archive}\n'; new_marker=f'{new_run}|{instance}|{rev}|{archive}\n'
 for stage,marker in ((old,old_marker),(new,new_marker)):
  claim=stage/'.transfer-claim'
  if not file(claim,hashlib.sha256(marker.encode()).hexdigest(),0,0,0o600) or claim.read_text()!=marker: refuse('TRANSFER_MARKER')
 for path,digest in ((old/old_name,old_archive),(old/'migration.private.json',old_manifest),
                     (new/new_name,archive),(new/'config-resume.private.json',new_manifest),
                     (new/'source-manifest.private.json',source_manifest)):
  if not file(path,digest,0,0,0o600): refuse('STAGE_ASSET_HASH')
 payload=new/'payload'
 if not directory(payload,0,0,0o700): refuse('PAYLOAD_METADATA')
 raw=(new/'source-manifest.private.json').read_bytes(); manifest=json.loads(raw)
 if manifest.get('source_revision')!=rev or manifest.get('private_binding_included') is not False or manifest.get('private_runtime_config_included') is not False: refuse('SOURCE_MANIFEST')
 expected={row['path']:row['sha256'] for row in manifest.get('files',[]) if type(row) is dict}
 if len(expected)!=5: refuse('SOURCE_MEMBER_SET')
 actual={}
 for path in payload.rglob('*'):
  s=path.lstat()
  if stat.S_ISLNK(s.st_mode): refuse('PAYLOAD_SYMLINK')
  if stat.S_ISREG(s.st_mode):
   if (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode),s.st_nlink)!=(0,0,0o644,1): refuse('PAYLOAD_FILE_METADATA')
   actual[str(path.relative_to(payload))]=hashlib.sha256(path.read_bytes()).hexdigest()
  elif not stat.S_ISDIR(s.st_mode) or (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))!=(0,0,0o755): refuse('PAYLOAD_ENTRY_TYPE')
 if actual!=expected: refuse('PAYLOAD_HASH_SET')
 for archive_path in (old/old_name,new/new_name):
  with tarfile.open(archive_path,'r:gz') as tf:
   if any(not m.isfile() for m in tf.getmembers()): refuse('ARCHIVE_MEMBER_TYPE')
 print(json.dumps({'state':'PRESERVED_STAGES_VALID','old_archive':'PINNED','config_archive':'PINNED','payload_members':5},separators=(',',':')))
except SystemExit: raise
except Exception: refuse('STAGE_READBACK')
'''
    remote = config["remote"]
    args = [remote["root"], remote["old_stage"], remote["runtime_stage"],
            instance_id, remote["old_stage_run_id"], remote["runtime_stage_run_id"],
            EXPECTED_PREDECESSOR_REVISION, EXPECTED_PREDECESSOR_ARCHIVE_SHA256,
            EXPECTED_TARGET_REVISION, EXPECTED_TARGET_ARCHIVE_SHA256,
            EXPECTED_PREDECESSOR_MANIFEST_SHA256, EXPECTED_RUNTIME_MANIFEST_SHA256,
            EXPECTED_RUNTIME_SOURCE_MANIFEST_SHA256, remote["old_archive_name"],
            remote["runtime_archive_name"]]
    return _compressed_python(script, args, as_root=True)


def _composed_probe(config: dict[str, Any]) -> str:
    script = r'''import hashlib,importlib.util,json,os,stat,sys,tarfile,types
from pathlib import Path
old_name,new_name=sys.argv[1:]
def refuse(code): print(json.dumps({'state':'REFUSED','code':code},separators=(',',':'))); raise SystemExit(0)
def sha(data): return hashlib.sha256(data).hexdigest()
def git_blob(data): return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def read_fixed(path,uid,gid,mode):
 st=path.lstat()
 if not stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode) or (st.st_uid,st.st_gid,stat.S_IMODE(st.st_mode))!=(uid,gid,mode) or path.resolve(strict=True)!=path: raise ValueError('FILE_METADATA')
 fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
 try:
  opened=os.fstat(fd)
  if (opened.st_dev,opened.st_ino,opened.st_uid,opened.st_gid,opened.st_mode)!=(st.st_dev,st.st_ino,st.st_uid,st.st_gid,st.st_mode): raise ValueError('FILE_CHANGED')
  with os.fdopen(fd,'rb',closefd=False) as stream: return stream.read()
 finally: os.close(fd)
def archive_member(archive,target):
 with tarfile.open(archive,'r:gz') as tf:
  matches=[m for m in tf.getmembers() if m.isfile() and (Path(m.name).as_posix()==target or Path(m.name).as_posix().endswith('/'+target))]
  if len(matches)!=1: raise ValueError('ARCHIVE_MEMBER')
  member=matches[0]
  parts=Path(member.name).parts
  if Path(member.name).is_absolute() or '..' in parts or not member.isfile(): raise ValueError('ARCHIVE_MEMBER')
  stream=tf.extractfile(member)
  if stream is None: raise ValueError('ARCHIVE_MEMBER')
  return stream.read()
def execute_source(data,path,name):
 module=types.ModuleType(name); module.__file__=str(path); module.__package__=''
 exec(compile(data,str(path),'exec'),module.__dict__)
 return module
try:
    root=Path('/opt/awsops-native-canary')
    if ('/' in old_name or old_name in {'.','..'} or not old_name.startswith('.issue90-stage-')
        or '/' in new_name or new_name in {'.','..'} or not new_name.startswith('.issue90-config-resume-948e8bb6-')):
        refuse('STAGE_ROOT_BINDING')
    old_stage=root/old_name; new_stage=root/new_name
    op=old_stage/'payload'; np=new_stage/'payload'
    old_manifest=old_stage/'migration.private.json'
    old_archive=old_stage/'awsops-native-canary-d090c98-final.tar.gz'
    new_manifest=new_stage/'config-resume.private.json'
    new_archive=new_stage/'awsops-config-resume-948e8bb6.tar.gz'
    old_manifest_sha='5638c7ff290385ecf1839e42171aab9d6ec7ac71b0da9322c6b3352f95c72460'
    old_archive_sha='3932ba704ce02ccde6393a362a28e6bf2e7ea0b4f883dbd9043f90b0b13877e3'
    new_source_manifest_sha='3c8e23d83954f433830251f8f98be44415afd72e621d587aee1851297777532f'
    old_helper=root/'awsops/integration/librechat/isolated_migration.py'
    new_helper=np/'awsops/integration/librechat/isolated_migration.py'
    old_manifest_bytes=read_fixed(old_manifest,0,0,0o600)
    old_archive_bytes=read_fixed(old_archive,0,0,0o600)
    # The transfer contract keeps the source manifest beside payload/, at the
    # runtime stage root. It is not a payload member.
    new_source_manifest_bytes=read_fixed(new_stage/'source-manifest.private.json',0,0,0o600)
    if sha(old_manifest_bytes)!=old_manifest_sha or sha(old_archive_bytes)!=old_archive_sha: refuse('PINNED_PREDECESSOR_ARTIFACT')
    if sha(new_source_manifest_bytes)!=new_source_manifest_sha: refuse('PINNED_RUNTIME_SOURCE_MANIFEST')
    old_manifest_value=json.loads(old_manifest_bytes)
    old_rows=[r for r in old_manifest_value.get('files',[]) if type(r) is dict and r.get('target')=='awsops/integration/librechat/isolated_migration.py']
    old_bytes=read_fixed(old_helper,1001,1001,0o644)
    old_member=archive_member(old_archive,'awsops/integration/librechat/isolated_migration.py')
    if (len(old_rows)!=1 or old_rows[0].get('sha256')!='72628fa7f2a898da6525d123815470e63efe2cfd5de08aa9bd6a6d3548502524' or old_rows[0].get('sha256')!=sha(old_bytes) or git_blob(old_bytes)!='635dca4dcf36c8809c19df8ee5a7fa594226a2e9' or old_member!=old_bytes): refuse('INSTALLED_PREDECESSOR_HELPER_PIN')
    new_bytes=read_fixed(new_helper,0,0,0o644)
    if sha(new_bytes)!='b949129984ef289b8304fd3d2c66d848a9c766a8e8cace8725dd045414346fcc' or git_blob(new_bytes)!='17d892306faf161de2bd04af11de3845996a204a': refuse('STAGED_RUNTIME_HELPER_PIN')
    old=execute_source(old_bytes,old_helper,'old_migration')
    new=execute_source(new_bytes,new_helper,'runtime_migration')
    om,of=old.load_manifest(op,old_manifest,root); old.verify_archive(om,old_archive)
    nm,nf=new._config_resume_manifest(np,new_manifest,root); new.verify_archive(nm,new_archive)
    raw=old.inspect_migration(op,old_manifest,old_archive,root)
    current=new.inspect_config_resume(np,new_manifest,new_archive,root)
    journal,files=new._config_resume_read_journal(root,nf,nm['migration_id'])
    if journal is None: refuse('CONFIG_RESUME_JOURNAL')
    overlaps={'T06':'C03','T12':'C01','T14':'C02'}
    tmap={f'T{i:02d}':r['target'] for i,r in enumerate(of,1)}; cby={r['target']:r for r in nf}
    jby={r['target']:r for r in journal['files']}
    for tk,ck in overlaps.items():
        target=tmap[tk]; c=cby.get(target); j=jby.get(target)
        if c is None or j is None or not j.get('prior'): refuse('OVERLAY_BINDING')
        old_bytes=(op/target).read_bytes(); backup=(root/new.CONFIG_RESUME_BACKUP/j['prior']).read_bytes(); pre=c.get('recovery_preconditions')
        if type(pre) is not list or len(pre)!=1 or backup!=old_bytes or hashlib.sha256(old_bytes).hexdigest()!=pre[0].get('sha256') or pre[0].get('uid')!=1001 or pre[0].get('gid')!=1001 or pre[0].get('mode')!='0644': refuse('OVERLAY_PREDECESSOR')
    states={r['key']:r['state'] for r in raw.get('targets',[]) if type(r) is dict}
    if raw.get('journal')!='INVALID' or raw.get('backup')!='ROOT_0700' or raw.get('state')!='JOURNAL_RECONCILE_REQUIRED': refuse('ORIGINAL_JOURNAL')
    if any(states.get(f'T{i:02d}')!='INSTALLED_EXACT' for i in range(1,42) if f'T{i:02d}' not in overlaps): refuse('ORIGINAL_UNAFFECTED_TARGET')
    if any(states.get(k)!='TARGET_DRIFT' for k in overlaps): refuse('ORIGINAL_OVERLAY_TARGET')
    new_states={r['key']:r['state'] for r in current.get('targets',[]) if type(r) is dict}
    if current.get('state')!='INSTALLED' or current.get('journal')!='VALID' or current.get('backup')!='PRESENT' or new_states!={f'C{i:02d}':'INSTALLED_EXACT' for i in range(1,4)}: refuse('CONFIG_RESUME_STATE')
    original=old._inspect_target; by={r['target']:r for r in nf}
    def composed(check_root,item,manifest):
        c=by.get(item['target'])
        if c is None: return original(check_root,item,manifest)
        state=new._config_resume_current(root/item['target'])
        if state is not None and state['sha256']==c['sha256'] and state['uid']==1001 and state['gid']==1001 and state['mode']==c['mode']: return 'INSTALLED_EXACT'
        return 'TARGET_DRIFT'
    old._inspect_target=composed
    try: jstate,bstate=old._inspect_journal(root,om,of)
    finally: old._inspect_target=original
    if jstate!='VALID' or bstate!='ROOT_0700': refuse('COMPOSED_BACKUP')
    print(json.dumps({'state':'COMPOSED_RUNTIME_READY','original41_journal':'VALID','original41_backup':'ROOT_0700','original41_unaffected_exact':38,'overlay_target_count':3,'overlay_predecessor_bytes_exact':3,'config_resume_journal':'VALID','config_resume_backup':'PRESENT','config_targets_exact':3},separators=(',',':')))
except SystemExit: raise
except Exception: refuse('COMPOSED_INSPECTION')
'''
    remote = config["remote"]
    args = [PurePosixPath(remote["old_stage"]).name,
            PurePosixPath(remote["runtime_stage"]).name]
    return _compressed_python(script, args, as_root=True, compression="lzma")


def _native_probe(config: dict[str, Any]) -> str:
    script = r'''const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),Module=require('node:module');
const root=process.argv[1],revision=process.argv[2],bindingHash=process.argv[3],ownerUid=Number(process.argv[4]),ownerGid=Number(process.argv[5]);
function refuse(code='NATIVE_BINDING_VALIDATION'){process.stdout.write(JSON.stringify({state:'REFUSED',code})+'\n');process.exit(0)}
function pinnedBytes(file,hash,uid,gid,mode){
 const st=fs.lstatSync(file);
 if(!st.isFile()||st.isSymbolicLink()||st.uid!==uid||st.gid!==gid||(st.mode&0o777)!==mode||fs.realpathSync(file)!==file) throw Error('PIN');
 const fd=fs.openSync(file,fs.constants.O_RDONLY|(fs.constants.O_NOFOLLOW||0));
 try {const opened=fs.fstatSync(fd);if(opened.dev!==st.dev||opened.ino!==st.ino||opened.uid!==uid||opened.gid!==gid||opened.mode!==st.mode)throw Error('PIN');
  const chunks=[];for(;;){const b=Buffer.allocUnsafe(65536),n=fs.readSync(fd,b,0,b.length,null);if(!n)break;chunks.push(b.subarray(0,n));}
  const data=Buffer.concat(chunks);if(hash&&crypto.createHash('sha256').update(data).digest('hex')!==hash)throw Error('PIN');return data;
 } finally {fs.closeSync(fd)}
}
function executePinned(file,data,name){const m=new Module(file,module);m.filename=file;m.paths=Module._nodeModulePaths(path.dirname(file));require.cache[file]=m;try{m._compile(data.toString('utf8'),file);return m.exports;}catch(e){delete require.cache[file];throw e;}}
try {if(root!==__ISOLATED_ROOT__||path.resolve(root)!==root||!Number.isSafeInteger(ownerUid)||!Number.isSafeInteger(ownerGid))refuse('NATIVE_PROBE_ARGUMENTS');
 const rootStat=fs.lstatSync(root);if(!rootStat.isDirectory()||rootStat.isSymbolicLink()||rootStat.uid!==ownerUid||rootStat.gid!==ownerGid||(rootStat.mode&0o777)!==0o700)refuse('NATIVE_ROOT_OWNER');
 const state=path.join(root,'state'),awsops=path.join(root,'awsops');
 const markerPath=path.join(awsops,'SOURCE_REVISION');
 const stateStat=fs.lstatSync(state);if(!stateStat.isDirectory()||stateStat.isSymbolicLink()||stateStat.uid!==ownerUid||stateStat.gid!==ownerGid||(stateStat.mode&0o777)!==0o700)refuse('NATIVE_STATE_OWNER');
 const marker=pinnedBytes(markerPath,null,ownerUid,ownerGid,0o644);
 if(marker.toString('ascii')!==revision+'\n')refuse('NATIVE_SOURCE_MARKER');
 const launcher=path.join(awsops,'integration/runtime/issue90-isolated-launcher.sh');
 pinnedBytes(launcher,'5070df7ffd5ec608d203e17c53dc0d158a827a173244c6e7e4322e29608f9dc5',ownerUid,ownerGid,0o644);
 const storePath=path.join(awsops,'integration/librechat/native_store.cjs');
 const storeBytes=pinnedBytes(storePath,'d7f7df44625bc67da0638cf72fa471695834e2e4609e10d7417623e8d84118e1',ownerUid,ownerGid,0o644);
 executePinned(storePath,storeBytes,'issue90_pinned_native_store');
 const configPath=path.join(awsops,'integration/librechat/runtime_config.cjs');
 const configBytes=pinnedBytes(configPath,'feb3aea5db396a3c64f61bb0f57fae56e7b95973752acecf76f9b082135c045a',ownerUid,ownerGid,0o644);
 const runtimeConfig=executePinned(configPath,configBytes,'issue90_pinned_runtime_config');
 const np=path.join(state,'native.json'),rp=path.join(state,'read.json'),bp=path.join(state,'binding.private.json');
 const ns=fs.lstatSync(np);
 const nativeBytes=pinnedBytes(np,null,ownerUid,ownerGid,0o600);
 const readBytes=pinnedBytes(rp,null,ownerUid,ownerGid,0o600);
 const bindingBytes=pinnedBytes(bp,bindingHash,ownerUid,ownerGid,0o600);
 const n=JSON.parse(nativeBytes.toString('utf8')),r=JSON.parse(readBytes.toString('utf8'));
 runtimeConfig.validateNativeConfig(n,root,ns,awsops); runtimeConfig.validateReadConfig(r);
 if(n.source_revision!==revision||n.source_root!==awsops||n.database!==path.join(state,'receipt.sqlite3')||n.application_database!==path.join(state,'canary.sqlite')||n.application_binding!==path.join(state,'binding.private.json')) refuse();
 if(crypto.createHash('sha256').update(bindingBytes).digest('hex')!==bindingHash) refuse();
 process.stdout.write(JSON.stringify({state:'NATIVE_BINDING_VALID'})+'\n');
} catch {refuse()}
'''.replace("__ISOLATED_ROOT__", json.dumps(ISOLATED_ROOT))
    remote = config["remote"]
    encoded = base64.b64encode(zlib.compress(script.encode(), 9)).decode("ascii")
    decoder = ("const argv=process.argv.slice(2),z=require('node:zlib'),"
               "b=Buffer.from(process.argv[1],'base64');process.argv=[process.argv[0],...argv];"
               "eval(z.inflateSync(b).toString('utf8'))")
    return ("/usr/bin/node -e " + shlex.quote(decoder) + " " + shlex.quote(encoded) + " "
            + shlex.quote(remote["root"]) + " " + EXPECTED_TARGET_REVISION + " "
            + remote["binding_sha256"] + " " + str(RUNTIME_OWNER_UID) + " "
            + str(RUNTIME_OWNER_GID))


def _ledger_probe(config: dict[str, Any]) -> str:
    script = r'''import json,sqlite3,stat,sys
from pathlib import Path
p=Path(sys.argv[1]); owner=int(sys.argv[2])
def out(state,code=None,counts=None): print(json.dumps({'state':state,'code':code,'prior_record_count':counts or {}},separators=(',',':')))
try:
 st=p.lstat()
 for suffix in ('-journal','-wal','-shm'):
  try: Path(str(p)+suffix).lstat(); out('REFUSED','LEDGER_SIDECAR'); raise SystemExit(0)
  except FileNotFoundError: pass
 parent=p.parent.lstat()
 if (p.is_symlink() or p.resolve(strict=True)!=p or p.parent.is_symlink()
     or not stat.S_ISDIR(parent.st_mode) or parent.st_uid!=owner
     or not stat.S_ISREG(st.st_mode) or (st.st_uid,st.st_gid,stat.S_IMODE(st.st_mode))!=(owner,owner,0o600)): out('REFUSED','LEDGER_METADATA'); raise SystemExit(0)
 db=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True,timeout=2)
 tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}; required={'canaries','operations','application_authority'}
 if not required<=tables: out('REFUSED','LEDGER_SCHEMA'); raise SystemExit(0)
 counts={name:db.execute('SELECT COUNT(*) FROM "'+name+'"').fetchone()[0] for name in sorted(required)}
 counts['native_owner_decisions']=db.execute('SELECT COUNT(*) FROM native_owner_decisions').fetchone()[0] if 'native_owner_decisions' in tables else 0
 db.close()
 out('NO_PRIOR_RECORDS' if not sum(counts.values()) else 'PRIOR_RECORDS_RECONCILE',None,counts)
except SystemExit: raise
except Exception: out('REFUSED','LEDGER_READONLY')
'''
    return _compressed_python(script, [config["remote"]["application_database"],
                                      str(config["remote"]["owner_uid"])],
                              as_root=False, as_owner=True)


def _receipt_probe(config: dict[str, Any], started_epoch: int) -> str:
    # This bounded read-only query accepts only the canonical application Reject
    # record, native winning CAS, frozen target binding and zero-write Run.
    script = r'''import hashlib,json,sqlite3,stat,sys
from pathlib import Path
db=Path(sys.argv[1]); revision=sys.argv[2]; started=int(sys.argv[3]); owner=int(sys.argv[4])
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def verify():
 try:
  s=db.lstat()
  if db.is_symlink() or not stat.S_ISREG(s.st_mode) or s.st_uid!=owner or stat.S_IMODE(s.st_mode)!=0o600:return False
  parent=db.parent.lstat()
  if db.parent.is_symlink() or not stat.S_ISDIR(parent.st_mode) or parent.st_uid!=owner:return False
  con=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=2)
  rows=con.execute("SELECT a.batch_id,a.authority_json,a.authority_digest,a.principal_digest,a.packet_digest,a.assurance,a.verifier_id,a.choice,a.verified_at,n.record_json,n.record_hash,c.payload,c.principal,c.decision,c.result FROM application_authority a JOIN native_owner_decisions n ON n.batch_id=a.batch_id JOIN canaries c ON c.batch_id=a.batch_id WHERE a.choice='REJECT' AND a.assurance='OWNER_AUTHENTICATED' AND a.verifier_id='LIBRECHAT_NATIVE_CAS'").fetchall()
  for row in rows:
   batch,raw,ad,pd,packet,assurance,verifier,choice,verified,rawn,nh,rawb,principal,rawd,rawresult=row
   a=json.loads(raw); n=json.loads(rawn); b=json.loads(rawb); d=json.loads(rawd); result=json.loads(rawresult); binding=n['binding']; run=result.get('run',{}); rr=run.get('record',{})
   if (digest(a)!=ad or a.get('batchId')!=batch or a.get('sourceRevision')!=revision or a.get('principalBindingDigest')!=pd or n.get('batch_id')!=batch or n.get('authority_digest')!=ad or n.get('scope_digest')!=a.get('scopeDigest') or n.get('source_revision')!=revision or n.get('decision')!='reject' or type(n.get('decided_at')) is not int or n['decided_at']<started or n.get('expires_at')!=a.get('decisionExpiresAt') or n['decided_at']>=n['expires_at'] or n.get('operation')!='native_canary_reject' or n.get('version')!=1 or digest(n)!=nh or verified!=n['decided_at'] or choice!='REJECT' or type(packet) is not str or len(packet)!=64 or a.get('accountAlias')!='amit' or a.get('resourceAlias')!='resource-disposable-s3-canary' or a.get('region')!='ap-southeast-1' or a.get('allowedActions')!=['create','tags','public_block','policy'] or b.get('batchId')!=batch or b.get('scopeDigest')!=a.get('scopeDigest') or digest({k:v for k,v in b.items() if k!='scopeDigest'})!=b.get('scopeDigest') or b.get('mode')!='APPROVED_LAB_WRITE' or d.get('choice')!='REJECT' or d.get('batchId')!=batch or d.get('scopeDigest')!=a.get('scopeDigest') or principal!=pd or digest({'principal_id':binding['principal_id'],'tenant_id':binding['tenant_id']})!=pd or binding.get('tool')!='approve_s3_canary_once' or run.get('schemaVersion')!='defence-factory/1' or run.get('kind')!='Run' or rr.get('batchId')!=batch or rr.get('mode')!='APPROVED_LAB_WRITE' or rr.get('status')!='REJECTED' or rr.get('realWrites')!=0 or rr.get('simulatedWrites')!=0): continue
   native=digest({'principal_id':binding['principal_id'],'tenant_id':binding['tenant_id'],'conversation_id':binding['conversation_id'],'action_id':binding['action_id'],'generation_id':binding['generation_id'],'tool_call_id':binding['tool_call_id'],'tool':binding['tool']})
   context=digest({'batchId':batch,'authorityDigest':ad,'scopeDigest':a['scopeDigest'],'sourceRevision':revision,'principalId':binding['principal_id'],'tenantId':binding['tenant_id'],'decision':'reject','nativeBindingDigest':native,'decidedAt':n['decided_at'],'expiresAt':n['expires_at']})
   lifecycle=a['cleanup']['expires_at'] if a['cleanup']['enabled'] else a['decisionExpiresAt']
   expected=digest({'packetId':'native-'+context[:32],'authorityDigest':ad,'principalBindingDigest':pd,'decision':'REJECT','issuedAt':n['decided_at'],'expiresAt':lifecycle,'proofDigest':digest(nh)})
   if packet!=expected or con.execute('SELECT COUNT(*) FROM operations WHERE batch_id=?',(batch,)).fetchone()[0]!=0: continue
   evidence=result.get('evidence',{}); er=evidence.get('record',{})
   if (evidence.get('schemaVersion')!='defence-factory/1' or evidence.get('kind')!='Evidence' or er.get('sourceRevision')!=revision or er.get('provenance')!='TRUSTED_PROVIDER_READ' or er.get('limitation')!='FRESHNESS_NOT_VERIFIED' or er.get('realWrites')!=0): continue
   return True
  return False
 except Exception:return False
print('OWNER_REJECT_RECEIPT_VERIFIED' if verify() else 'RECEIPT_NOT_VERIFIED')
'''
    return _compressed_python(script, [config["remote"]["application_database"],
        EXPECTED_TARGET_REVISION, str(started_epoch),
        str(config["remote"]["owner_uid"])], as_root=False, as_owner=True)


def _launcher_command(action: str) -> str:
    if action not in {"start", "stop"}:
        raise RuntimeRefused("LAUNCHER_ACTION_REFUSED")
    script = r'''import hashlib,os,stat,subprocess,sys
path,expected,action=sys.argv[1:]
try:
 st=os.lstat(path)
 if not stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode) or (st.st_uid,st.st_gid,stat.S_IMODE(st.st_mode))!=(1001,1001,0o644) or os.path.realpath(path)!=path: raise ValueError()
 fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
 try:
  opened=os.fstat(fd)
  if (opened.st_dev,opened.st_ino,opened.st_uid,opened.st_gid,opened.st_mode)!=(st.st_dev,st.st_ino,st.st_uid,st.st_gid,st.st_mode): raise ValueError()
  chunks=[]
  while True:
   block=os.read(fd,65536)
   if not block: break
   chunks.append(block)
 finally: os.close(fd)
 data=b''.join(chunks)
 if hashlib.sha256(data).hexdigest()!=expected: raise ValueError()
 result=subprocess.run(['/bin/bash','-s',action],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
 sys.stdout.buffer.write(result.stdout); sys.stderr.buffer.write(result.stderr)
 raise SystemExit(result.returncode)
except SystemExit: raise
except Exception:
 sys.stderr.write('ISSUE90_LAUNCHER_PIN_REFUSED\n'); raise SystemExit(2)
'''
    return _compressed_python(script, [ISOLATED_LAUNCHER,
                                      EXPECTED_INSTALLED_LAUNCHER_SHA256, action],
                              as_root=True)


def build_steps(config: dict[str, Any], instance_id: str, run_id: str,
                started_epoch: int = 0) -> tuple[Step, ...]:
    return (
        Step("stage_readback", _stage_probe(config, instance_id), 30,
             json_state="PRESERVED_STAGES_VALID"),
        Step("composed_state_readback", _composed_probe(config), 30,
             json_state="COMPOSED_RUNTIME_READY"),
        Step("native_binding_readback", _native_probe(config), 30,
             json_state="NATIVE_BINDING_VALID"),
        Step("ledger_readback", _ledger_probe(config), 30,
             json_state="NO_PRIOR_RECORDS"),
        Step("launcher_start", _launcher_command("start"), 360,
             expected_stdout=READY_MARKER + "\n"),
        Step("owner_reject_readback", _receipt_probe(config, started_epoch), 10,
             expected_stdout="OWNER_REJECT_RECEIPT_VERIFIED\n"),
        Step("launcher_stop", _launcher_command("stop"), 60,
             expected_stdout=STOP_MARKER + "\n"),
    )


def build_ssm_request(instance_id: str, run_id: str, step: Step) -> dict[str, Any]:
    comment = f"i90-{hashlib.sha256((run_id + step.name).encode()).hexdigest()[:12]}-{step.name}"
    request = {
        "InstanceIds": [instance_id], "DocumentName": SSM_DOCUMENT,
        "Parameters": {"commands": [step.command],
                        "executionTimeout": [str(step.execution_timeout)]},
        "TimeoutSeconds": 30, "MaxConcurrency": "1", "MaxErrors": "0",
        "Comment": comment[:MAX_SSM_COMMENT_CHARS],
    }
    validate_ssm_request(request)
    return request


def _valid_probe_shape(name: str, value: dict[str, Any]) -> bool:
    if value.get("state") == "REFUSED":
        return set(value) == {"state", "code"} and type(value.get("code")) is str
    if name == "stage_readback":
        return value == {"state": "PRESERVED_STAGES_VALID", "old_archive": "PINNED",
                         "config_archive": "PINNED", "payload_members": 5}
    if name == "composed_state_readback":
        return value == {"state": "COMPOSED_RUNTIME_READY", "original41_journal": "VALID",
                         "original41_backup": "ROOT_0700", "original41_unaffected_exact": 38,
                         "overlay_target_count": 3, "overlay_predecessor_bytes_exact": 3,
                         "config_resume_journal": "VALID", "config_resume_backup": "PRESENT",
                         "config_targets_exact": 3}
    if name == "native_binding_readback":
        return value == {"state": "NATIVE_BINDING_VALID"}
    if name == "ledger_readback":
        counts = value.get("prior_record_count")
        return (set(value) == {"state", "code", "prior_record_count"}
                and value.get("state") in {"NO_PRIOR_RECORDS", "PRIOR_RECORDS_RECONCILE"}
                and value.get("code") is None and type(counts) is dict
                and set(counts) == {"canaries", "operations", "application_authority",
                                    "native_owner_decisions"}
                and all(type(count) is int and count >= 0 for count in counts.values()))
    return False


def validate_ssm_request(request: dict[str, Any]) -> None:
    expected = {"InstanceIds", "DocumentName", "Parameters", "TimeoutSeconds",
                "MaxConcurrency", "MaxErrors", "Comment"}
    if type(request) is not dict or set(request) != expected:
        raise RuntimeRefused("SSM_REQUEST_FIELDS")
    ids = request["InstanceIds"]
    if (type(ids) is not list or len(ids) != 1 or type(ids[0]) is not str
            or not re.fullmatch(r"i-[0-9a-f]{8}(?:[0-9a-f]{9})?", ids[0])):
        raise RuntimeRefused("SSM_TARGET_INVALID")
    if request["DocumentName"] != SSM_DOCUMENT:
        raise RuntimeRefused("SSM_DOCUMENT_INVALID")
    if (type(request["TimeoutSeconds"]) is not int or not 30 <= request["TimeoutSeconds"] <= 2592000
            or request["MaxConcurrency"] != "1" or request["MaxErrors"] != "0"):
        raise RuntimeRefused("SSM_REQUEST_LIMIT")
    if type(request["Comment"]) is not str or not 1 <= len(request["Comment"]) <= MAX_SSM_COMMENT_CHARS:
        raise RuntimeRefused("SSM_COMMENT_LIMIT")
    parameters = request["Parameters"]
    if type(parameters) is not dict or set(parameters) != {"commands", "executionTimeout"}:
        raise RuntimeRefused("SSM_PARAMETER_FIELDS")
    commands, timeouts = parameters["commands"], parameters["executionTimeout"]
    if type(commands) is not list or len(commands) != 1 or type(commands[0]) is not str:
        raise RuntimeRefused("SSM_COMMAND_INVALID")
    if type(timeouts) is not list or len(timeouts) != 1 or type(timeouts[0]) is not str or not timeouts[0].isdigit():
        raise RuntimeRefused("SSM_EXECUTION_TIMEOUT_INVALID")
    if not 1 <= int(timeouts[0]) <= 172800:
        raise RuntimeRefused("SSM_EXECUTION_TIMEOUT_INVALID")
    if len(json.dumps(request, separators=(",", ":"), ensure_ascii=False).encode("utf-8")) > MAX_SSM_BYTES:
        raise RuntimeRefused("SSM_REQUEST_TOO_LARGE")


class PrivateEvidence:
    def __init__(self, root: Path):
        self.root = root
        _ensure_private_dir(root)

    def create_run_dir(self, run_id: str) -> Path:
        path = self.root / run_id
        path.mkdir(mode=0o700)
        os.chmod(path, 0o700)
        return path

    def write_once(self, path: Path, value: dict[str, Any]) -> None:
        data = (json.dumps(value, sort_keys=True, separators=(",", ":"),
                           allow_nan=False) + "\n").encode()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        dfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)

    def write(self, path: Path, value: dict[str, Any]) -> None:
        data = (json.dumps(value, sort_keys=True, separators=(",", ":"),
                           allow_nan=False) + "\n").encode()
        temp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
            os.chmod(path, 0o600)
            dfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        finally:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass


def _ensure_private_dir(path: Path) -> None:
    if path.exists() or path.is_symlink():
        st = path.lstat()
        if (not path.is_dir() or path.is_symlink() or st.st_uid != os.getuid()
                or st.st_mode & 0o077):
            raise RuntimeRefused("PRIVATE_DIRECTORY_METADATA")
        return
    path.mkdir(mode=0o700, parents=True)
    os.chmod(path, 0o700)


class Boto3RuntimeProvider:
    """Explicit amit/Singapore client set, with SDK retries disabled."""
    def __init__(self):
        try:
            import boto3
            from botocore.config import Config
            from botocore.exceptions import ClientError
        except ImportError as exc:
            raise RuntimeRefused("BOTO3_RUNTIME_DEPENDENCY_MISSING") from exc
        cfg = Config(retries={"total_max_attempts": 1, "mode": "standard"},
                     connect_timeout=5, read_timeout=20)
        self.session = boto3.Session(profile_name=PROFILE, region_name=REGION)
        self.sts = self.session.client("sts", region_name=REGION, config=cfg)
        self.ec2 = self.session.client("ec2", region_name=REGION, config=cfg)
        self.ssm = self.session.client("ssm", region_name=REGION, config=cfg)
        self._client_error = ClientError

    @staticmethod
    def _request_id(response: dict[str, Any]) -> str | None:
        meta = response.get("ResponseMetadata", {})
        value = meta.get("RequestId") if type(meta) is dict else None
        return value if type(value) is str else None

    def identity(self) -> tuple[dict[str, Any], str | None]:
        response = self.sts.get_caller_identity()
        return response, self._request_id(response)

    def describe_instance(self, instance_id: str) -> tuple[dict[str, Any] | None, str | None]:
        response = self.ec2.describe_instances(InstanceIds=[instance_id])
        reservations = response.get("Reservations", [])
        instances = [item for reservation in reservations for item in reservation.get("Instances", [])]
        if len(instances) != 1 or instances[0].get("InstanceId") != instance_id:
            raise RuntimeRefused("TARGET_READBACK_MISMATCH")
        return instances[0], self._request_id(response)

    def _describe_exact(self, operation: str, argument: str,
                        identifiers: list[str], result_key: str,
                        identifier_key: str) -> tuple[list[dict[str, Any]], str | None]:
        try:
            response = getattr(self.ec2, operation)(**{argument: identifiers})
        except Exception as exc:
            raise RuntimeRefused("TARGET_PROPERTY_READ_FAILED") from exc
        if type(response) is not dict:
            raise RuntimeRefused("TARGET_PROPERTY_READBACK_MISMATCH")
        rows = response.get(result_key, [])
        if (type(rows) is not list or len(rows) != len(identifiers)
                or any(type(row) is not dict for row in rows)
                or sorted(row.get(identifier_key) for row in rows) != sorted(identifiers)):
            raise RuntimeRefused("TARGET_PROPERTY_READBACK_MISMATCH")
        return rows, self._request_id(response)

    def describe_security_groups(self, group_ids: list[str]) -> tuple[list[dict[str, Any]], str | None]:
        return self._describe_exact("describe_security_groups", "GroupIds", group_ids,
                                    "SecurityGroups", "GroupId")

    def describe_volumes(self, volume_ids: list[str]) -> tuple[list[dict[str, Any]], str | None]:
        return self._describe_exact("describe_volumes", "VolumeIds", volume_ids,
                                    "Volumes", "VolumeId")

    def describe_addresses(self, allocation_ids: list[str]) -> tuple[list[dict[str, Any]], str | None]:
        return self._describe_exact("describe_addresses", "AllocationIds", allocation_ids,
                                    "Addresses", "AllocationId")

    def describe_subnets(self, subnet_ids: list[str]) -> tuple[list[dict[str, Any]], str | None]:
        return self._describe_exact("describe_subnets", "SubnetIds", subnet_ids,
                                    "Subnets", "SubnetId")

    def dry_run(self, action: str, instance_id: str) -> bool:
        try:
            if action == "start":
                self.ec2.start_instances(InstanceIds=[instance_id], DryRun=True)
            elif action == "stop":
                self.ec2.stop_instances(InstanceIds=[instance_id], DryRun=True)
            else:
                raise RuntimeRefused("DRY_RUN_ACTION_INVALID")
        except self._client_error as exc:
            response = getattr(exc, "response", {})
            code = response.get("Error", {}).get("Code") if type(response) is dict else None
            if code == "DryRunOperation":
                return True
            if code == "UnauthorizedOperation":
                return False
            raise RuntimeRefused("DRY_RUN_UNAVAILABLE") from exc
        return False

    def start_once(self, instance_id: str) -> tuple[dict[str, Any], str | None]:
        response = self.ec2.start_instances(InstanceIds=[instance_id])
        return response, self._request_id(response)

    def stop_once(self, instance_id: str) -> tuple[dict[str, Any], str | None]:
        response = self.ec2.stop_instances(InstanceIds=[instance_id])
        return response, self._request_id(response)

    def ssm_online(self, instance_id: str) -> tuple[bool, str | None]:
        response = self.ssm.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}])
        rows = response.get("InstanceInformationList", [])
        return len(rows) == 1 and rows[0].get("PingStatus") == "Online", self._request_id(response)

    def validate_ssm_request(self, request: dict[str, Any]) -> None:
        validate_ssm_request(request)
        try:
            from botocore.validate import validate_parameters
            shape = self.ssm.meta.service_model.operation_model("SendCommand").input_shape
            validate_parameters(request, shape)
        except RuntimeRefused:
            raise
        except Exception as exc:
            raise RuntimeRefused("SSM_MODEL_VALIDATION_FAILED") from exc

    def send_once(self, request: dict[str, Any]) -> tuple[str | None, str | None]:
        response = self.ssm.send_command(**request)
        command = response.get("Command", {})
        command_id = command.get("CommandId") if type(command) is dict else None
        return command_id if type(command_id) is str else None, self._request_id(response)

    def invocation(self, command_id: str, instance_id: str) -> tuple[dict[str, Any], str | None]:
        response = self.ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        return response, self._request_id(response)


def _safe_error_code(exc: BaseException) -> str:
    response = getattr(exc, "response", None)
    if type(response) is dict:
        error = response.get("Error")
        if type(error) is dict and type(error.get("Code")) is str:
            value = error["Code"]
            return value[:80] if re.fullmatch(r"[A-Za-z0-9_.-]+", value) else "PROVIDER_ERROR"
    return type(exc).__name__[:80]


def _request_ok(provider: Any, request: dict[str, Any]) -> None:
    provider.validate_ssm_request(request)


class RuntimeOperator:
    def __init__(self, config: dict[str, Any], provider: Any,
                 notifier: Callable[[str, str], str | None] | None, *,
                 monotonic: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep,
                 repo_root: Path | None = None):
        self.config, self.provider, self.notifier = config, provider, notifier
        self.monotonic, self.sleep = monotonic, sleep
        self.repo_root = repo_root or Path(__file__).resolve().parents[3]

    def _verify_config(self) -> None:
        required = {
            "schema", "aws_profile", "region", "target_source_revision",
            "target_archive_sha256", "operator_source_head", "instance_id",
            "instance_type", "expected_account_id", "expected_principal_arn",
            "target_tags", "target_attachments", "target_property_baselines",
            "previous_window", "remote", "runtime_authority",
            "evidence_root", "start_claim_path",
            "stop_claim_path",
        }
        if type(self.config) is not dict or set(self.config) != required:
            raise RuntimeRefused("RUNTIME_CONFIG_FIELDS")
        if self.config.get("schema") != "issue90-runtime-only-private/v2":
            raise RuntimeRefused("RUNTIME_CONFIG_SCHEMA")
        if self.config.get("aws_profile") != PROFILE or self.config.get("region") != REGION:
            raise RuntimeRefused("RUNTIME_IDENTITY_SCOPE")
        if self.config.get("target_source_revision") != EXPECTED_TARGET_REVISION:
            raise RuntimeRefused("RUNTIME_SOURCE_PIN")
        if self.config.get("target_archive_sha256") != EXPECTED_TARGET_ARCHIVE_SHA256:
            raise RuntimeRefused("RUNTIME_ARCHIVE_PIN")
        if (type(self.config.get("expected_account_id")) is not str
                or not re.fullmatch(r"[0-9]{12}", self.config["expected_account_id"])):
            raise RuntimeRefused("RUNTIME_ACCOUNT_BINDING_MISSING")
        principal = self.config.get("expected_principal_arn")
        if (type(principal) is not str or ":root" in principal
                or not re.fullmatch(r"arn:aws:(?:iam::[0-9]{12}:(?:user|role)/[A-Za-z0-9+=,.@_/-]+|sts::[0-9]{12}:assumed-role/[A-Za-z0-9+=,.@_/-]+)", principal)
                or principal.split(":")[4] != self.config["expected_account_id"]):
            raise RuntimeRefused("RUNTIME_PRINCIPAL_BINDING_MISSING")
        if (type(self.config.get("operator_source_head")) is not str
                or not re.fullmatch(r"[0-9a-f]{40}", self.config["operator_source_head"])):
            raise RuntimeRefused("RUNTIME_OPERATOR_SOURCE_PIN_MISSING")
        instance = self.config.get("instance_id")
        if type(instance) is not str or not re.fullmatch(r"i-[0-9a-f]{8}(?:[0-9a-f]{9})?", instance):
            raise RuntimeRefused("RUNTIME_TARGET_INVALID")
        if os.getuid() == 0:
            raise RuntimeRefused("RUNTIME_MUST_BE_NONROOT")
        if (type(self.config.get("target_tags")) is not dict or not self.config["target_tags"]
                or any(type(k) is not str or type(v) is not str or not k or not v
                       for k, v in self.config["target_tags"].items())):
            raise RuntimeRefused("RUNTIME_TARGET_BINDING_MISSING")
        if (type(self.config.get("target_attachments")) is not dict
                or set(self.config["target_attachments"]) != {
                    "subnet_id", "vpc_id", "security_group_ids",
                    "network_interface_ids", "volume_ids"}
                or any(type(self.config["target_attachments"].get(k)) is not str
                       or not self.config["target_attachments"][k]
                       for k in ("subnet_id", "vpc_id"))
                or any(type(self.config["target_attachments"].get(k)) is not list
                       or not self.config["target_attachments"][k]
                       or any(type(v) is not str or not v for v in self.config["target_attachments"][k])
                       for k in ("security_group_ids", "network_interface_ids", "volume_ids"))):
            raise RuntimeRefused("RUNTIME_ATTACHMENT_BINDING_MISSING")
        baselines = self.config.get("target_property_baselines")
        if (type(baselines) is not dict or set(baselines) != set(TARGET_PROPERTY_FILES)
                or any(type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value)
                       for value in baselines.values())):
            raise RuntimeRefused("RUNTIME_TARGET_PROPERTY_BASELINE_REQUIRED")
        if type(self.config.get("previous_window")) is not dict:
            raise RuntimeRefused("RUNTIME_PREVIOUS_WINDOW_MISSING")
        self._verify_remote_scope(self.config.get("remote"))
        self._verify_private_paths()
        if not callable(self.notifier):
            raise RuntimeRefused("RUNTIME_READY_NOTIFIER_UNAVAILABLE")
        validate_runtime_authority(self.config.get("runtime_authority"))

    @staticmethod
    def _remote_path(value: Any, expected: str, code: str) -> None:
        if type(value) is not str or value != expected:
            raise RuntimeRefused(code)

    def _verify_remote_scope(self, remote: Any) -> None:
        expected_fields = {
            "root", "old_stage", "runtime_stage", "old_stage_run_id",
            "runtime_stage_run_id", "old_archive_sha256", "runtime_archive_sha256",
            "old_manifest_sha256", "runtime_manifest_sha256",
            "runtime_source_manifest_sha256", "old_archive_name",
            "runtime_archive_name", "old_payload", "runtime_payload",
            "old_manifest", "runtime_manifest", "old_archive", "runtime_archive",
            "launcher", "binding_sha256", "application_database", "owner_uid",
        }
        if type(remote) is not dict or set(remote) != expected_fields:
            raise RuntimeRefused("RUNTIME_REMOTE_SCOPE_FIELDS")
        self._remote_path(remote.get("root"), ISOLATED_ROOT, "RUNTIME_ROOT_REFUSED")
        if type(remote.get("owner_uid")) is not int or remote["owner_uid"] != RUNTIME_OWNER_UID:
            raise RuntimeRefused("RUNTIME_OWNER_UID_REFUSED")
        old_stage = remote.get("old_stage")
        new_stage = remote.get("runtime_stage")
        for value, pattern, code in (
            (old_stage, r"/opt/awsops-native-canary/\.issue90-stage-[a-z0-9-]{1,96}",
             "RUNTIME_OLD_STAGE_REFUSED"),
            (new_stage, r"/opt/awsops-native-canary/\.issue90-config-resume-948e8bb6-[a-z0-9-]{1,96}",
             "RUNTIME_STAGE_REFUSED"),
        ):
            if type(value) is not str or not re.fullmatch(pattern, value):
                raise RuntimeRefused(code)
            path = PurePosixPath(value)
            if path.parent.as_posix() != ISOLATED_ROOT or ".." in path.parts:
                raise RuntimeRefused(code)
        fixed_paths = {
            "old_payload": f"{old_stage}/payload",
            "runtime_payload": f"{new_stage}/payload",
            "old_manifest": f"{old_stage}/migration.private.json",
            "runtime_manifest": f"{new_stage}/config-resume.private.json",
            "runtime_archive": f"{new_stage}/awsops-config-resume-948e8bb6.tar.gz",
            "old_archive": f"{old_stage}/awsops-native-canary-d090c98-final.tar.gz",
            "application_database": f"{ISOLATED_STATE}/canary.sqlite",
            "launcher": ISOLATED_LAUNCHER,
            "old_archive_name": "awsops-native-canary-d090c98-final.tar.gz",
            "runtime_archive_name": "awsops-config-resume-948e8bb6.tar.gz",
        }
        for key, expected in fixed_paths.items():
            self._remote_path(remote.get(key), expected, "RUNTIME_REMOTE_PATH_REFUSED")
        for key, expected in (
            ("old_archive_sha256", EXPECTED_PREDECESSOR_ARCHIVE_SHA256),
            ("runtime_archive_sha256", EXPECTED_TARGET_ARCHIVE_SHA256),
            ("old_manifest_sha256", EXPECTED_PREDECESSOR_MANIFEST_SHA256),
            ("runtime_manifest_sha256", EXPECTED_RUNTIME_MANIFEST_SHA256),
            ("runtime_source_manifest_sha256", EXPECTED_RUNTIME_SOURCE_MANIFEST_SHA256),
        ):
            self._remote_path(remote.get(key), expected, "RUNTIME_REMOTE_ARTIFACT_PIN_REFUSED")
        for key in ("binding_sha256",):
            value = remote.get(key)
            if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise RuntimeRefused("RUNTIME_PRIVATE_BINDING_PIN_REFUSED")
        for key in ("old_stage_run_id", "runtime_stage_run_id"):
            value = remote.get(key)
            if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
                raise RuntimeRefused("RUNTIME_STAGE_RUN_ID_REFUSED")

    @staticmethod
    def _private_lane_path(value: Any, code: str, *, direct: bool = False) -> Path:
        if type(value) is not str:
            raise RuntimeRefused(code)
        path = Path(value)
        lane = PRIVATE_LANE
        try:
            rel = path.relative_to(lane)
        except ValueError as exc:
            raise RuntimeRefused(code) from exc
        if (not path.is_absolute() or ".." in rel.parts or not rel.parts
                or (direct and len(rel.parts) != 1)):
            raise RuntimeRefused(code)
        return path

    def _verify_private_paths(self) -> None:
        evidence_root = self._private_lane_path(self.config.get("evidence_root"),
                                                "RUNTIME_EVIDENCE_PATH_REFUSED", direct=True)
        claim_paths = []
        for key in ("start_claim_path", "stop_claim_path"):
            path = self._private_lane_path(self.config.get(key), "RUNTIME_CLAIM_PATH_REFUSED", direct=True)
            if not path.name.endswith(".private.json"):
                raise RuntimeRefused("RUNTIME_CLAIM_PATH_REFUSED")
            claim_paths.append(path)
        if claim_paths[0] == claim_paths[1] or evidence_root in claim_paths:
            raise RuntimeRefused("RUNTIME_CLAIM_PATH_REFUSED")
        previous = self.config.get("previous_window")
        if (type(previous) is not dict
                or set(previous) != {"result_path", "result_sha256", "instance_id"}
                or previous.get("instance_id") != self.config.get("instance_id")
                or type(previous.get("result_sha256")) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", previous["result_sha256"])):
            raise RuntimeRefused("RUNTIME_PREVIOUS_TARGET_BINDING_REFUSED")
        self._private_lane_path(previous.get("result_path"),
                                "RUNTIME_PREVIOUS_RESULT_PATH_REFUSED", direct=True)

    def _verify_source(self) -> str:
        root = self.repo_root
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, check=True).stdout.strip()
        expected = self.config.get("operator_source_head")
        if type(expected) is not str or head != expected or dirty:
            raise RuntimeRefused("RUNTIME_OPERATOR_SOURCE_DRIFT")
        return head

    def _validate_previous(self) -> dict[str, Any]:
        previous = self.config["previous_window"]
        path = Path(previous["result_path"])
        _private_file(path, previous["result_sha256"])
        result = _load_private_json(path, expected_uid=os.getuid())
        stop = result.get("stop")
        if (result.get("source_revision") != EXPECTED_TARGET_REVISION
                or result.get("outcome") != "OWNER_INTERACTION_DEADLINE"
                or result.get("owner_reject", {}).get("verified") is not False
                or type(stop) is not dict or stop.get("verified") is not True
                or stop.get("final_state") != "stopped"):
            raise RuntimeRefused("RUNTIME_PREVIOUS_STOP_EVIDENCE_REFUSED")
        return result

    def _verify_target(self, instance: dict[str, Any], expected_account: str,
                       principal: str) -> None:
        if instance.get("State", {}).get("Name") != "stopped":
            raise RuntimeRefused("TARGET_NOT_STOPPED")
        if instance.get("InstanceType") != self.config.get("instance_type"):
            raise RuntimeRefused("TARGET_TYPE_DRIFT")
        actual_tags = {row.get("Key"): row.get("Value") for row in instance.get("Tags", [])}
        for key, value in self.config["target_tags"].items():
            if actual_tags.get(key) != value:
                raise RuntimeRefused("TARGET_TAG_BINDING_MISMATCH")
        attachments = self.config["target_attachments"]
        observed = {
            "subnet_id": instance.get("SubnetId"),
            "vpc_id": instance.get("VpcId"),
            "security_group_ids": sorted(g.get("GroupId") for g in instance.get("SecurityGroups", [])),
            "network_interface_ids": sorted(i.get("NetworkInterfaceId") for i in instance.get("NetworkInterfaces", [])),
            "volume_ids": sorted(m.get("Ebs", {}).get("VolumeId") for m in instance.get("BlockDeviceMappings", [])),
        }
        if observed != attachments:
            raise RuntimeRefused("TARGET_ATTACHMENT_BINDING_MISMATCH")
        if self.config.get("expected_account_id") != expected_account:
            raise RuntimeRefused("RUNTIME_ACCOUNT_BINDING_MISMATCH")
        if self.config.get("expected_principal_arn") != principal or ":root" in principal:
            raise RuntimeRefused("RUNTIME_PRINCIPAL_BINDING_MISMATCH")

    def _target_property_baseline(self, name: str) -> dict[str, Any]:
        if name not in TARGET_PROPERTY_FILES:
            raise RuntimeRefused("TARGET_PROPERTY_NAME_REFUSED")
        try:
            lane = PRIVATE_LANE.lstat()
        except OSError as exc:
            raise RuntimeRefused("TARGET_PROPERTY_BASELINE_UNAVAILABLE") from exc
        if (not PRIVATE_LANE.is_dir() or PRIVATE_LANE.is_symlink()
                or lane.st_uid != os.getuid() or lane.st_mode & 0o077):
            raise RuntimeRefused("TARGET_PROPERTY_BASELINE_DIRECTORY_REFUSED")
        path = PRIVATE_LANE / TARGET_PROPERTY_FILES[name]
        expected = self.config["target_property_baselines"][name]
        _private_file(path, expected)
        return _load_private_json(path, expected_uid=os.getuid())

    def _verify_target_properties(self, instance: dict[str, Any]) -> dict[str, str | None]:
        """Compare exact current target properties with the pinned approved baseline."""
        attachments = self.config["target_attachments"]
        sg_baseline = self._target_property_baseline("security_groups").get("SecurityGroups")
        volume_baseline = self._target_property_baseline("volumes").get("Volumes")
        address_baseline = self._target_property_baseline("addresses").get("Addresses")
        subnet_baseline = self._target_property_baseline("subnets").get("Subnets")
        if any(type(rows) is not list or not rows
               for rows in (sg_baseline, volume_baseline, address_baseline, subnet_baseline)):
            raise RuntimeRefused("TARGET_PROPERTY_BASELINE_SCHEMA_REFUSED")

        attached_sgs = sorted(row.get("GroupId") for row in instance.get("SecurityGroups", [])
                              if type(row) is dict)
        baseline_sg_ids = sorted(row.get("GroupId") for row in sg_baseline
                                 if type(row) is dict)
        expected_sg_ids = sorted(attachments["security_group_ids"])
        if attached_sgs != baseline_sg_ids or baseline_sg_ids != expected_sg_ids:
            raise RuntimeRefused("TARGET_SECURITY_GROUP_BINDING_MISMATCH")
        current_sgs, sg_request = self.provider.describe_security_groups(expected_sg_ids)
        if _canonical(current_sgs) != _canonical(sg_baseline):
            raise RuntimeRefused("TARGET_SECURITY_GROUP_PROPERTIES_CHANGED")

        attached_volumes = sorted(
            row.get("Ebs", {}).get("VolumeId") for row in instance.get("BlockDeviceMappings", [])
            if type(row) is dict and type(row.get("Ebs")) is dict and row["Ebs"].get("VolumeId"))
        baseline_volume_ids = sorted(row.get("VolumeId") for row in volume_baseline
                                     if type(row) is dict)
        expected_volume_ids = sorted(attachments["volume_ids"])
        if attached_volumes != baseline_volume_ids or baseline_volume_ids != expected_volume_ids:
            raise RuntimeRefused("TARGET_VOLUME_BINDING_MISMATCH")
        current_volumes, volume_request = self.provider.describe_volumes(expected_volume_ids)
        if _canonical(current_volumes) != _canonical(volume_baseline):
            raise RuntimeRefused("TARGET_VOLUME_PROPERTIES_CHANGED")

        allocation_ids = sorted(row.get("AllocationId") for row in address_baseline
                                if type(row) is dict and row.get("AllocationId"))
        instance_id = self.config["instance_id"]
        if (len(address_baseline) != 1 or len(allocation_ids) != 1
                or address_baseline[0].get("InstanceId") != instance_id):
            raise RuntimeRefused("TARGET_ADDRESS_BINDING_MISMATCH")
        current_addresses, address_request = self.provider.describe_addresses(allocation_ids)
        if _canonical(current_addresses) != _canonical(address_baseline):
            raise RuntimeRefused("TARGET_ADDRESS_PROPERTIES_CHANGED")

        subnet_id = attachments["subnet_id"]
        if (len(subnet_baseline) != 1 or subnet_baseline[0].get("SubnetId") != subnet_id
                or subnet_baseline[0].get("VpcId") != attachments["vpc_id"]
                or instance.get("SubnetId") != subnet_id or instance.get("VpcId") != attachments["vpc_id"]):
            raise RuntimeRefused("TARGET_SUBNET_BINDING_MISMATCH")
        current_subnets, subnet_request = self.provider.describe_subnets([subnet_id])
        stable = ("SubnetId", "VpcId", "CidrBlock", "State", "MapPublicIpOnLaunch",
                  "AssignIpv6AddressOnCreation", "Ipv6Native")
        if (len(current_subnets) != 1
                or any(current_subnets[0].get(key) != subnet_baseline[0].get(key)
                       for key in stable)):
            raise RuntimeRefused("TARGET_SUBNET_PROPERTIES_CHANGED")
        return {"security_groups": sg_request, "volumes": volume_request,
                "addresses": address_request, "subnets": subnet_request}

    def _ssm_call(self, evidence: PrivateEvidence, run_dir: Path, instance: str,
                  run_id: str, index: int, step: Step, started_epoch: int,
                  hard_deadline: float | None = None) -> tuple[str, dict[str, Any]]:
        if step.name == "owner_reject_readback":
            # Replace the fixed epoch placeholder after the actual start time.
            step = Step(step.name, _receipt_probe(self.config, started_epoch), step.execution_timeout,
                        step.expected_stdout, step.json_state)
        request = build_ssm_request(instance, run_id, step)
        _request_ok(self.provider, request)
        if hard_deadline is not None and self.monotonic() + 1 >= hard_deadline:
            return "DEADLINE_BEFORE_SEND", {}
        request_path = run_dir / f"ssm-request-{index:02d}.private.json"
        evidence.write_once(request_path, request)
        try:
            command_id, send_request_id = self.provider.send_once(request)
        except Exception as exc:
            evidence.write(run_dir / f"ssm-result-{index:02d}.private.json", {
                "step": step.name, "state": "SEND_UNKNOWN_NO_REPLAY",
                "error_code": _safe_error_code(exc), "request_id": None})
            return "SEND_UNKNOWN_NO_REPLAY", {}
        if not command_id:
            evidence.write(run_dir / f"ssm-result-{index:02d}.private.json", {
                "step": step.name, "state": "SEND_UNKNOWN_NO_REPLAY",
                "request_id": send_request_id})
            return "SEND_UNKNOWN_NO_REPLAY", {}
        deadline = self.monotonic() + step.execution_timeout + 120
        if hard_deadline is not None:
            deadline = min(deadline, hard_deadline)
        response = None
        read_request_id = None
        while self.monotonic() < deadline:
            try:
                response, read_request_id = self.provider.invocation(command_id, instance)
            except Exception as exc:
                if _safe_error_code(exc) == "InvocationDoesNotExist":
                    # GetCommandInvocation is eventually consistent after an
                    # acknowledged SendCommand. Retry only this bounded
                    # readback; never resend the command.
                    self.sleep(min(2, max(0.1, deadline - self.monotonic())))
                    continue
                response = {"Status": "READBACK_UNKNOWN", "SafeError": _safe_error_code(exc)}
                break
            if response.get("Status") in TERMINAL_SSM:
                break
            self.sleep(2)
        if type(response) is not dict or response.get("Status") not in TERMINAL_SSM:
            state = "READBACK_UNKNOWN_NO_REPLAY"
        else:
            state = response.get("Status")
        stdout = response.get("StandardOutputContent", "") if type(response) is dict else ""
        stderr = response.get("StandardErrorContent", "") if type(response) is dict else ""
        evidence.write_once(run_dir / f"ssm-output-{index:02d}.private.json", {
            "step": step.name, "command_id": command_id, "status": state,
            "response_code": response.get("ResponseCode") if type(response) is dict else None,
            "stdout": stdout, "stderr": stderr})
        evidence.write(run_dir / f"ssm-result-{index:02d}.private.json", {
            "step": step.name, "state": state, "command_id": command_id,
            "send_request_id": send_request_id,
            "read_request_id": read_request_id if 'read_request_id' in locals() else None})
        if state != "Success" or type(response) is not dict or response.get("ResponseCode") != 0 or stderr != "":
            return "SSM_STEP_REFUSED_NO_REPLAY", response if type(response) is dict else {}
        if step.expected_stdout is not None and stdout != step.expected_stdout:
            return "SSM_MARKER_MISMATCH_NO_REPLAY", response
        if step.json_state:
            if type(stdout) is not str or type(stderr) is not str:
                return "SSM_READBACK_REFUSED", {}
            value = _strict_json(stdout)
            if not _valid_probe_shape(step.name, value):
                return "SSM_READBACK_REFUSED", value
            if value.get("state") == "REFUSED":
                return "SSM_PROBE_REFUSED_NO_REPLAY", value
            if value.get("state") != step.json_state:
                if (step.name == "ledger_readback"
                        and value.get("state") == "PRIOR_RECORDS_RECONCILE"):
                    return "Success", value
                return "SSM_PROBE_STATE_MISMATCH_NO_REPLAY", value
            return "Success", value
        return "Success", response

    def _notify_ready(self, evidence: PrivateEvidence, run_dir: Path, run_id: str,
                      source_head: str, start_epoch: int, active_deadline: float) -> bool:
        pointer = run_dir / "READY.private.json"
        remaining = max(0, int(active_deadline - self.monotonic()))
        value = {
            "status": "READY", "run_id": run_id, "operator_source_head": source_head,
            "target_source_revision": EXPECTED_TARGET_REVISION,
            "started_epoch": start_epoch, "remaining_owner_window_seconds": remaining,
            "receipt": "HUMAN_REJECT_REQUIRED", "synthetic_model_stimulus_only": True,
        }
        evidence.write_once(pointer, value)
        message = (
            f"Issue90 runtime READY; genuine owner login/Reject required. "
            f"Run {run_id}; source {source_head}; {remaining}s remain. "
            f"Private pointer: {pointer}"
        )
        if not callable(self.notifier):
            return False
        remaining_for_notify = active_deadline - self.monotonic() - 60
        timeout = min(15.0, max(0.0, remaining_for_notify))
        if timeout <= 0:
            evidence.write_once(run_dir / "READY-notification.private.json", {
                "state": "NOT_CONFIRMED_DEADLINE_NO_RETRY"})
            return False
        outcome: dict[str, Any] = {}

        def send_once() -> None:
            try:
                outcome["receipt"] = self.notifier(run_id, message)
            except BaseException as exc:
                outcome["error_code"] = _safe_error_code(exc)

        worker = threading.Thread(target=send_once, name="issue90-ready-notify",
                                  daemon=True)
        worker.start()
        worker.join(timeout)
        if worker.is_alive():
            evidence.write_once(run_dir / "READY-notification.private.json", {
                "state": "NOT_CONFIRMED_TIMEOUT_NO_RETRY"})
            return False
        if "error_code" in outcome:
            evidence.write(run_dir / "READY-notification.private.json", {
                "state": "NOT_CONFIRMED_NO_RETRY", "error_code": outcome["error_code"]})
            return False
        receipt = outcome.get("receipt")
        evidence.write_once(run_dir / "READY-notification.private.json", {
            "state": "QUEUED" if receipt else "UNKNOWN_NO_RETRY", "receipt": receipt})
        return bool(receipt)

    def run(self) -> dict[str, Any]:
        self._verify_config()
        source_head = self._verify_source()
        previous = self._validate_previous()
        identity, sts_request_id = self.provider.identity()
        if (identity.get("Account") != self.config.get("expected_account_id")
                or identity.get("Arn") != self.config.get("expected_principal_arn")
                or ":root" in str(identity.get("Arn", ""))):
            raise RuntimeRefused("RUNTIME_IDENTITY_MISMATCH")
        instance_id = self.config["instance_id"]
        instance, describe_request_id = self.provider.describe_instance(instance_id)
        if instance is None:
            raise RuntimeRefused("TARGET_NOT_FOUND")
        self._verify_target(instance, identity["Account"], identity["Arn"])
        target_property_request_ids = self._verify_target_properties(instance)
        if not self.provider.dry_run("start", instance_id) or not self.provider.dry_run("stop", instance_id):
            raise RuntimeRefused("LIFECYCLE_PERMISSION_DRY_RUN_REFUSED")
        run_id = "i90-runtime-" + uuid.uuid4().hex
        evidence = PrivateEvidence(Path(self.config["evidence_root"]))
        run_dir = evidence.create_run_dir(run_id)
        start_claim = Path(self.config["start_claim_path"])
        stop_claim = Path(self.config["stop_claim_path"])
        if any(p.exists() or p.is_symlink() for p in (start_claim, stop_claim)):
            raise RuntimeRefused("ONE_USE_CLAIM_COLLISION")
        steps = build_steps(self.config, instance_id, run_id)
        if tuple(s.name for s in steps) != EXPECTED_STEPS:
            raise RuntimeRefused("FIXED_STEP_ORDER_REFUSED")
        for index, step in enumerate(steps, 1):
            _request_ok(self.provider, build_ssm_request(instance_id, run_id, step))
        evidence.write(run_dir / "preflight.private.json", {
            "status": "PASS", "operator_source_head": source_head,
            "target_source_revision": EXPECTED_TARGET_REVISION,
            "identity_request_id": sts_request_id,
            "target_read_request_id": describe_request_id,
            "target_property_read_request_ids": target_property_request_ids,
            "previous_stop_evidence_sha256": self.config["previous_window"]["result_sha256"],
            "fixed_ssm_requests": len(steps), "all_request_shapes_validated": True,
            "runtime_authority": RUNTIME_AUTHORITY,
            "historical_spend_reconstruction": "NOT_REQUIRED_FOR_REJECT_ONLY"})

        now = datetime.now(timezone.utc).isoformat()
        evidence.write_once(start_claim, {
            "phase": "START_INTENT", "run_id": run_id,
            "operator_source_head": source_head,
            "target_source_revision": EXPECTED_TARGET_REVISION,
            "previous_result_sha256": self.config["previous_window"]["result_sha256"],
            "issued_at_utc": now, "request_count": 0,
        })
        started = False
        launch_may_have_started = False
        result: dict[str, Any] = {
            "run_id": run_id, "status": "START_NOT_SENT",
            "provider_readback": "NOT_VERIFIED",
        }
        active_deadline = self.monotonic() + MAX_ACTIVE_SECONDS
        stop_deadline = active_deadline + STOP_RESERVE_SECONDS
        started_epoch = int(time.time())
        old_handlers = {}

        def request_stop(signum, _frame):
            raise KeyboardInterrupt(f"signal-{signum}")

        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            old_handlers[sig] = signal.signal(sig, request_stop)
        try:
            started = True
            response, request_id = self.provider.start_once(instance_id)
            evidence.write_once(run_dir / "start-response.private.json", {
                "request_id": request_id, "response": response})
            result["start_request_id"] = request_id
            running_deadline = min(active_deadline - STOP_RESERVE_SECONDS,
                                   self.monotonic() + 180)
            state = None
            while self.monotonic() < running_deadline:
                row, read_id = self.provider.describe_instance(instance_id)
                state = row.get("State", {}).get("Name") if row else None
                if state == "running" or state in {"stopping", "stopped", "shutting-down", "terminated"}:
                    break
                self.sleep(5)
            if state != "running":
                result["status"] = "START_READBACK_UNKNOWN_NO_REPLAY"
            else:
                online_deadline = min(active_deadline - STOP_RESERVE_SECONDS,
                                      self.monotonic() + 150)
                online = False
                while self.monotonic() < online_deadline:
                    online, _ssm_id = self.provider.ssm_online(instance_id)
                    if online:
                        break
                    self.sleep(5)
                if not online:
                    result["status"] = "SSM_OFFLINE_NO_REPLAY"
                else:
                    result["status"] = self._inspect_and_launch(
                        evidence, run_dir, run_id, source_head, instance_id,
                        steps, started_epoch, active_deadline, stop_deadline)
                    launch_may_have_started = self._launch_may_have_started
        except KeyboardInterrupt:
            result["status"] = "INTERRUPTED_CLEANUP_REQUIRED"
        except BaseException as exc:
            result["status"] = "RUNTIME_ERROR_CLEANUP_REQUIRED"
            evidence.write(run_dir / "runtime-error.private.json", {
                "error_code": _safe_error_code(exc), "error_type": type(exc).__name__})
        finally:
            for sig in old_handlers:
                signal.signal(sig, signal.SIG_IGN)
            try:
                cleanup = self._cleanup(evidence, run_dir, run_id, instance_id,
                                        launch_may_have_started or self._launch_may_have_started,
                                        started, stop_deadline)
                result["cleanup"] = cleanup
                if cleanup.get("final_state") != "stopped":
                    result["status"] = "STOPPED_NOT_VERIFIED"
                try:
                    evidence.write(run_dir / "result.private.json", result)
                except BaseException:
                    result["result_evidence"] = "WRITE_FAILED"
            except BaseException as exc:
                result["status"] = "STOPPED_NOT_VERIFIED"
                result["cleanup"] = {"state": "CLEANUP_ERROR", "error_code": _safe_error_code(exc)}
            finally:
                for sig, handler in old_handlers.items():
                    signal.signal(sig, handler)
        return result

    @property
    def _launch_may_have_started(self) -> bool:
        return getattr(self, "_launch_possible", False)

    def _inspect_and_launch(self, evidence, run_dir, run_id, source_head,
                            instance_id, steps, started_epoch, active_deadline,
                            stop_deadline):
        self._launch_possible = False
        for index, step in enumerate(steps[:4], 1):
            status, value = self._ssm_call(evidence, run_dir, instance_id, run_id,
                                           index, step, started_epoch, active_deadline)
            if status != "Success":
                return f"{status}_NO_LAUNCH"
            if step.name == "ledger_readback":
                counts = value.get("prior_record_count")
                expected_keys = {"canaries", "operations", "application_authority", "native_owner_decisions"}
                if (value.get("code") is not None or type(counts) is not dict
                        or set(counts) != expected_keys
                        or any(type(n) is not int or n < 0 for n in counts.values())):
                    return "LEDGER_RESPONSE_INVALID_NO_LAUNCH"
                if value.get("state") != "NO_PRIOR_RECORDS" or any(counts.values()):
                    return "PRIOR_OR_AMBIGUOUS_RECORD_BLOCKS_LAUNCH"
        launcher = steps[4]
        if self.monotonic() + launcher.execution_timeout + 120 >= active_deadline:
            return "INSUFFICIENT_ACTIVE_WINDOW_NO_LAUNCH"
        self._launch_possible = True
        status, _ = self._ssm_call(evidence, run_dir, instance_id, run_id,
                                   5, launcher, started_epoch, active_deadline)
        if status != "Success":
            return "LAUNCH_UNKNOWN_NO_REPLAY"
        if not self._notify_ready(evidence, run_dir, run_id, source_head,
                                  started_epoch, active_deadline):
            return "READY_NOTIFICATION_NOT_CONFIRMED"
        receipt_deadline = active_deadline - 60
        while self.monotonic() < receipt_deadline:
            self.sleep(min(5, max(0.1, receipt_deadline - self.monotonic())))
        receipt = steps[5]
        status, _ = self._ssm_call(evidence, run_dir, instance_id, run_id,
                                   6, receipt, started_epoch, stop_deadline)
        if status == "Success":
            return "OWNER_REJECT_RECEIPT_VERIFIED"
        return "OWNER_REJECT_NOT_VERIFIED"

    def _cleanup(self, evidence, run_dir, run_id, instance_id,
                 launch_may_have_started, started, stop_deadline):
        summary = {"launcher_stop": "NOT_NEEDED", "stop_request_id": None,
                   "final_state": "UNKNOWN"}
        def save(name: str, value: dict[str, Any], *, once: bool = False) -> bool:
            try:
                writer = evidence.write_once if once else evidence.write
                writer(run_dir / name, value)
                return True
            except BaseException:
                summary["evidence_write"] = "FAILED"
                return False

        if launch_may_have_started and self.monotonic() < stop_deadline:
            try:
                step = build_steps(self.config, instance_id, run_id)[6]
                status, _ = self._ssm_call(evidence, run_dir, instance_id, run_id,
                                           9001, step, int(time.time()), stop_deadline)
                summary["launcher_stop"] = status
            except BaseException as exc:
                summary["launcher_stop"] = _safe_error_code(exc)
        if started:
            state = None
            try:
                current, _ = self.provider.describe_instance(instance_id)
                state = current.get("State", {}).get("Name") if current else None
            except BaseException as exc:
                summary["pre_stop_read"] = _safe_error_code(exc)
                state = None
            if state == "stopped":
                claim = Path(self.config["stop_claim_path"])
                save_claim = {"phase": "ALREADY_STOPPED", "run_id": run_id,
                              "issued_at_utc": datetime.now(timezone.utc).isoformat(),
                              "request_count": 0}
                try:
                    evidence.write_once(claim, save_claim)
                    summary["stop_intent"] = "ALREADY_STOPPED_READBACK"
                except BaseException as exc:
                    summary["stop_intent"] = "ALREADY_STOPPED_CLAIM_REFUSED"
                    summary["stop_claim_error_code"] = _safe_error_code(exc)
                summary["final_state"] = "stopped"
                summary["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
            elif self.monotonic() < stop_deadline:
                # A failed pre-stop read cannot suppress the one exact-target
                # stop intent. Persist the one-use claim before issuing Stop;
                # after an uncertain Stop outcome, never issue it again.
                claim = Path(self.config["stop_claim_path"])
                claim_value = {"phase": "STOP_INTENT", "run_id": run_id,
                               "instance_id": instance_id,
                               "issued_at_utc": datetime.now(timezone.utc).isoformat(),
                               "request_count": 1}
                should_stop = False
                try:
                    evidence.write_once(claim, claim_value)
                    summary["stop_intent"] = "PERSISTED"
                    should_stop = True
                except FileExistsError as exc:
                    # An existing intent could represent an earlier Stop.
                    # Never overwrite it or replay an uncertain request.
                    summary["stop_intent"] = "CLAIM_COLLISION_NO_STOP_REPLAY"
                    summary["stop_claim_error_code"] = _safe_error_code(exc)
                except BaseException as exc:
                    # The already-durable start claim prevents this window
                    # from being replayed. Still make its one exact Stop call.
                    summary["stop_intent"] = "CLAIM_WRITE_FAILED_STOP_ONCE"
                    summary["stop_claim_error_code"] = _safe_error_code(exc)
                    should_stop = True
                if should_stop:
                    try:
                        response, request_id = self.provider.stop_once(instance_id)
                        summary["stop_request_id"] = request_id
                        save("stop-response.private.json", {
                            "request_id": request_id, "response": response}, once=True)
                    except BaseException as exc:
                        summary["stop_request"] = "UNKNOWN_NO_REPLAY"
                        summary["stop_error_code"] = _safe_error_code(exc)
            else:
                summary["stop_intent"] = "DEADLINE_EXPIRED"

            # Readback may be retried within the fixed deadline; Stop itself is
            # never retried. Continue polling even when an individual read or
            # private evidence write fails.
            state = None
            while self.monotonic() < stop_deadline:
                try:
                    current, _ = self.provider.describe_instance(instance_id)
                    state = current.get("State", {}).get("Name") if current else None
                except BaseException as exc:
                    summary["stop_readback_error_code"] = _safe_error_code(exc)
                    state = None
                if state == "stopped":
                    summary["final_state"] = "stopped"
                    summary["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
                    break
                self.sleep(min(5, max(0.1, stop_deadline - self.monotonic())))
            if summary["final_state"] != "stopped":
                summary["final_state"] = state or "unknown"
        save("cleanup.private.json", summary)
        return summary


def main(argv: list[str] | None = None, *,
         notifier: Callable[[str, str], str | None] | None = None,
         provider_factory: Callable[[], Any] = Boto3RuntimeProvider) -> int:
    parser = argparse.ArgumentParser(description="Run the fixed Issue90 runtime-only owner Reject window.")
    parser.add_argument("--execute-runtime-only", action="store_true")
    parser.add_argument("--private-config", type=Path,
                        default=Path.home() / ".AGENTS-temp/manager/issue90-live-activation/runtime-only.private.json")
    args = parser.parse_args(argv)
    if not args.execute_runtime_only:
        parser.error("the fixed lifecycle requires --execute-runtime-only")
    try:
        config = _load_private_json(args.private_config, expected_uid=os.getuid())
        if notifier is None:
            if (not Path(NATIVE_CODEX_EXECUTABLE).is_file()
                    or not os.access(NATIVE_CODEX_EXECUTABLE, os.X_OK)):
                raise RuntimeRefused("RUNTIME_READY_NOTIFIER_UNAVAILABLE")
            notifier = make_native_manager_notifier(NATIVE_CODEX_EXECUTABLE)
        if not callable(notifier):
            raise RuntimeRefused("RUNTIME_READY_NOTIFIER_UNAVAILABLE")
        provider = provider_factory()
        result = RuntimeOperator(config, provider, notifier).run()
    except RuntimeRefused as exc:
        print(f"RUNTIME_REFUSED={exc}")
        return 2
    print(f"RUNTIME_STATUS={result['status']}")
    return 0 if result["status"] == "OWNER_REJECT_RECEIPT_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
