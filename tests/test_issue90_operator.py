import base64
import copy
import hashlib
import json
import lzma
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
import unittest
import zlib
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from awsops.runtime import issue90_operator as operator  # noqa: E402
from awsops.approval.decisions import DecisionStore  # noqa: E402
from awsops.domain.models import canonical_digest  # noqa: E402
from test_issue90_approval_e2e import make_case  # noqa: E402


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.invocations = 0

    def validate_ssm_request(self, request):
        operator.validate_ssm_request(request)

    def send_once(self, request):
        self.requests.append(request)
        return f"command-{len(self.requests)}", f"send-{len(self.requests)}"

    def invocation(self, _command_id, _instance_id):
        self.invocations += 1
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        status, stdout, stderr = response
        return {"Status": status, "ResponseCode": 0 if status == "Success" else 1,
                "StandardOutputContent": stdout, "StandardErrorContent": stderr}, "read"


def _probe_success(name):
    if name == "stage_readback":
        return {"state": "PRESERVED_STAGES_VALID", "old_archive": "PINNED",
                "config_archive": "PINNED", "payload_members": 5}
    if name == "composed_state_readback":
        return {"state": "COMPOSED_RUNTIME_READY", "original41_journal": "VALID",
                "original41_backup": "ROOT_0700", "original41_unaffected_exact": 38,
                "overlay_target_count": 3, "overlay_predecessor_bytes_exact": 3,
                "config_resume_journal": "VALID", "config_resume_backup": "PRESENT",
                "config_targets_exact": 3}
    if name == "native_binding_readback":
        return {"state": "NATIVE_BINDING_VALID"}
    return {"state": "NO_PRIOR_RECORDS", "code": None,
            "prior_record_count": {"canaries": 0, "operations": 0,
                "application_authority": 0, "native_owner_decisions": 0}}


def _make_production_reject_fixture(temp: str | Path, now: int):
    """Create the canonical synthetic Reject ledger through the real app path."""
    principal_digest = canonical_digest({
        "principal_id": "test-owner", "tenant_id": "tenant:test-tenant"})
    app, fake_s3, _clock, _factory, _batch, authority, _packet, _ = make_case(
        temp, source_revision=operator.EXPECTED_TARGET_REVISION,
        mode="APPROVED_LAB_WRITE", principal_digest=principal_digest, clock=[now])
    native_db = Path(temp) / "native.sqlite"
    DecisionStore(native_db)
    binding_path = Path(temp) / "binding.private.json"
    binding_path.write_text(json.dumps({
        "account_id": app.binding.account_id, "bucket": app.binding.bucket}))
    binding_path.chmod(0o600)
    native_record = {
        "version": 1, "operation": "native_canary_reject",
        "batch_id": authority.batch_id, "authority_digest": authority.digest,
        "scope_digest": authority.scope_digest,
        "source_revision": authority.source_revision, "decision": "reject",
        "decided_at": now, "expires_at": authority.decision_expires_at,
        "binding": {"principal_id": "test-owner", "tenant_id": "tenant:test-tenant",
            "conversation_id": "conversation-test", "action_id": "action-test",
            "generation_id": str(now), "tool_call_id": "call-test",
            "tool": "approve_s3_canary_once"},
    }
    source = r"""
const gate = require(process.argv[1]);
const config = {version:1, enabled:true, agent_id:'test-agent', python:process.argv[2],
  source_root:process.argv[3], database:process.argv[4], source_revision:process.argv[7],
  application_database:process.argv[5], application_binding:process.argv[6], source_version:'v1.0.0-mock'};
const record = JSON.parse(process.argv[8]);
(async () => {
  const first = await gate.dispatchNativeCanaryReject(config, record);
  const reopened = await gate.dispatchNativeCanaryReject(config, record);
  process.stdout.write(JSON.stringify({first, reopened}));
})().catch((error) => { process.stderr.write(String(error && error.message || error)); process.exitCode = 2; });
"""
    try:
        produced = subprocess.run([
            "node", "-e", source, str(ROOT / "integration/librechat/native_gate.cjs"),
            sys.executable, str(ROOT), str(native_db), str(app.path), str(binding_path),
            authority.source_revision, json.dumps(native_record, separators=(",", ":")),
        ], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise AssertionError(f"synthetic production Reject fixture failed: {exc.stderr}") from exc
    generated = json.loads(produced.stdout)
    return app, fake_s3, authority, generated


def _write_private(path: Path, value: dict):
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")))
    path.chmod(0o600)


def _make_runtime_case(lane: Path, repo: Path, *, now: int):
    """Create private synthetic inputs satisfying the production run gates."""
    lane.mkdir(mode=0o700)
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "fixture.txt").write_text("synthetic source pin\n")
    subprocess.run(["git", "-C", str(repo), "add", "fixture.txt"], check=True)
    subprocess.run([
        "git", "-C", str(repo), "-c", "user.name=Fixture", "-c",
        "user.email=fixture@example.invalid", "commit", "-qm", "synthetic source",
    ], check=True)
    source_head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True).stdout.strip()

    baseline_rows = {
        "security_groups": {"SecurityGroups": [{
            "GroupId": "sg-fixture", "IpPermissions": [{"FromPort": 4311,
                "ToPort": 4311, "IpProtocol": "tcp", "IpRanges": []}],
        }]},
        "volumes": {"Volumes": [{"VolumeId": "vol-fixture", "State": "in-use",
            "Encrypted": True, "CreateTime": "2026-10-20T01:02:03.000000Z",
            "Attachments": [{"VolumeId": "vol-fixture",
                "AttachTime": "2026-10-20T01:04:05.000000Z"}]}]},
        "addresses": {"Addresses": [{"AllocationId": "eipalloc-fixture",
            "InstanceId": "i-" + "a" * 17}]},
        "subnets": {"Subnets": [{"SubnetId": "subnet-fixture", "VpcId": "vpc-fixture",
            "CidrBlock": "10.0.0.0/24", "State": "available",
            "MapPublicIpOnLaunch": False, "AssignIpv6AddressOnCreation": False,
            "Ipv6Native": False}]},
    }
    property_hashes = {}
    for name, value in baseline_rows.items():
        path = lane / operator.TARGET_PROPERTY_FILES[name]
        _write_private(path, value)
        property_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    budget_path = lane / "incremental-spend.private.json"
    _write_private(budget_path, {
        "schema": "issue90-incremental-spend/v1", "status": "RECONCILED",
        "total_authorized_usd": "100.00", "cumulative_incremental_spend_usd": "0.00",
    })
    previous_path = lane / "previous-result.private.json"
    _write_private(previous_path, {
        "source_revision": operator.EXPECTED_TARGET_REVISION,
        "outcome": "OWNER_INTERACTION_DEADLINE",
        "owner_reject": {"verified": False},
        "stop": {"verified": True, "final_state": "stopped"},
    })

    account = "".join(str((index + 1) % 10) for index in range(12))
    instance_id = "i-" + "a" * 17
    old_stage = f"{operator.ISOLATED_ROOT}/.issue90-stage-fixture"
    runtime_stage = f"{operator.ISOLATED_ROOT}/.issue90-config-resume-948e8bb6-fixture"
    remote = {
        "root": operator.ISOLATED_ROOT,
        "old_stage": old_stage, "runtime_stage": runtime_stage,
        "old_stage_run_id": "old-run-fixture", "runtime_stage_run_id": "resume-run-fixture",
        "old_archive_sha256": operator.EXPECTED_PREDECESSOR_ARCHIVE_SHA256,
        "runtime_archive_sha256": operator.EXPECTED_TARGET_ARCHIVE_SHA256,
        "old_manifest_sha256": operator.EXPECTED_PREDECESSOR_MANIFEST_SHA256,
        "runtime_manifest_sha256": operator.EXPECTED_RUNTIME_MANIFEST_SHA256,
        "runtime_source_manifest_sha256": operator.EXPECTED_RUNTIME_SOURCE_MANIFEST_SHA256,
        "old_archive_name": "awsops-native-canary-d090c98-final.tar.gz",
        "runtime_archive_name": "awsops-config-resume-948e8bb6.tar.gz",
        "old_payload": f"{old_stage}/payload", "runtime_payload": f"{runtime_stage}/payload",
        "old_manifest": f"{old_stage}/migration.private.json",
        "runtime_manifest": f"{runtime_stage}/config-resume.private.json",
        "old_archive": f"{old_stage}/awsops-native-canary-d090c98-final.tar.gz",
        "runtime_archive": f"{runtime_stage}/awsops-config-resume-948e8bb6.tar.gz",
        "launcher": operator.ISOLATED_LAUNCHER,
        "binding_sha256": "b" * 64,
        "application_database": f"{operator.ISOLATED_STATE}/canary.sqlite",
        "owner_uid": os.getuid(),
    }
    config = {
        "schema": "issue90-runtime-only-private/v1", "aws_profile": operator.PROFILE,
        "region": operator.REGION, "target_source_revision": operator.EXPECTED_TARGET_REVISION,
        "target_archive_sha256": operator.EXPECTED_TARGET_ARCHIVE_SHA256,
        "operator_source_head": source_head, "instance_id": instance_id,
        "instance_type": "t3.micro", "expected_account_id": account,
        "expected_principal_arn": f"arn:aws:iam::{account}:user/synthetic-runtime-test",
        "target_tags": {"Name": "synthetic-runtime-target"},
        "target_attachments": {"subnet_id": "subnet-fixture", "vpc_id": "vpc-fixture",
            "security_group_ids": ["sg-fixture"], "network_interface_ids": ["eni-fixture"],
            "volume_ids": ["vol-fixture"]},
        "target_property_baselines": property_hashes,
        "previous_window": {"result_path": str(previous_path),
            "result_sha256": hashlib.sha256(previous_path.read_bytes()).hexdigest(),
            "instance_id": instance_id},
        "remote": remote,
        "incremental_budget": {"evidence_path": str(budget_path),
            "evidence_sha256": hashlib.sha256(budget_path.read_bytes()).hexdigest(),
            "planned_reserve_usd": "1.00"},
        "evidence_root": str(lane / "evidence"),
        "start_claim_path": str(lane / "start-claim.private.json"),
        "stop_claim_path": str(lane / "stop-claim.private.json"),
    }
    return config, instance_id, baseline_rows


class FakeLifecycleClock:
    def __init__(self):
        self.value = 1000.0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class FakeRuntimeProvider:
    """External calls are faked; RuntimeOperator.run and its parsers are real."""
    def __init__(self, config, baseline_rows, *, scenario="success", receipt_db=None):
        self.config = config
        self.baseline_rows = copy.deepcopy(baseline_rows)
        self.scenario = scenario
        self.receipt_db = receipt_db
        self.state = "stopped"
        self.start_calls = 0
        self.stop_calls = 0
        self.dry_runs = []
        self.sends = []
        self.commands = {}
        self.steps = {}
        self.invocation_reads = 0
        self.instance = {
            "InstanceId": config["instance_id"], "State": {"Name": "stopped"},
            "InstanceType": config["instance_type"], "Tags": [
                {"Key": key, "Value": value}
                for key, value in config["target_tags"].items()],
            "SubnetId": "subnet-fixture", "VpcId": "vpc-fixture",
            "SecurityGroups": [{"GroupId": "sg-fixture"}],
            "NetworkInterfaces": [{"NetworkInterfaceId": "eni-fixture"}],
            "BlockDeviceMappings": [{"Ebs": {"VolumeId": "vol-fixture"}}],
        }

    def validate_ssm_request(self, request):
        operator.validate_ssm_request(request)

    def identity(self):
        account = self.config["expected_account_id"]
        arn = self.config["expected_principal_arn"]
        if self.scenario == "prestart_refusal":
            account = "".join(str((index + 2) % 10) for index in range(12))
        return {"Account": account, "Arn": arn}, "fake-sts-read"

    def describe_instance(self, _instance_id):
        row = copy.deepcopy(self.instance)
        row["State"] = {"Name": self.state}
        return row, "fake-instance-read"

    def describe_security_groups(self, _ids):
        return copy.deepcopy(self.baseline_rows["security_groups"]["SecurityGroups"]), "fake-sg-read"

    def describe_volumes(self, _ids):
        rows = copy.deepcopy(self.baseline_rows["volumes"]["Volumes"])
        rows[0]["CreateTime"] = datetime(2026, 10, 20, 1, 2, 3, tzinfo=timezone.utc)
        rows[0]["Attachments"][0]["AttachTime"] = datetime(
            2026, 10, 20, 1, 4, 5, tzinfo=timezone.utc)
        return rows, "fake-volume-read"

    def describe_addresses(self, _ids):
        return copy.deepcopy(self.baseline_rows["addresses"]["Addresses"]), "fake-address-read"

    def describe_subnets(self, _ids):
        return copy.deepcopy(self.baseline_rows["subnets"]["Subnets"]), "fake-subnet-read"

    def dry_run(self, action, _instance_id):
        self.dry_runs.append(action)
        return True

    def start_once(self, _instance_id):
        self.start_calls += 1
        self.state = "running"
        return {"synthetic": True}, "fake-start-request"

    def ssm_online(self, _instance_id):
        if self.scenario == "interrupt":
            raise KeyboardInterrupt("synthetic interruption after Start")
        return True, "fake-ssm-online"

    def send_once(self, request):
        self.validate_ssm_request(request)
        step = request["Comment"].split("-", 2)[2]
        command_id = f"fake-command-{len(self.sends) + 1}"
        self.sends.append((step, request))
        self.commands[command_id] = request["Parameters"]["commands"][0]
        self.steps[command_id] = step
        return command_id, f"fake-send-{len(self.sends)}"

    def _receipt_probe_output(self, command):
        tokens = shlex.split(command)
        if (tokens[:4] != ["sudo", "-u", "ssm-user", "--"]
                or tokens[4] != "/usr/bin/python3" or len(tokens) != 14
                or self.receipt_db is None):
            raise AssertionError("unexpected generated owner receipt command")
        # Execute the exact generated decoder and probe source/argv, replacing
        # only the remote database path with the local synthetic fixture path.
        args = [*tokens[5:10], str(self.receipt_db), *tokens[11:]]
        completed = subprocess.run([sys.executable, *args], check=True,
                                    capture_output=True, text=True)
        return completed.stdout, completed.stderr

    def invocation(self, command_id, _instance_id):
        self.invocation_reads += 1
        step = self.steps[command_id]
        command = self.commands[command_id]
        status, stdout, stderr = "Success", "", ""
        if self.scenario == "failure" and step == "stage_readback":
            status, stderr = "Failed", "synthetic fixed probe failure"
        elif self.scenario == "unknown_launch" and step == "launcher_start":
            status = "InProgress"
        elif step in {"stage_readback", "composed_state_readback",
                      "native_binding_readback", "ledger_readback"}:
            value = _probe_success(step)
            if self.scenario == "prior_row_refusal" and step == "ledger_readback":
                value = {"state": "PRIOR_RECORDS_RECONCILE", "code": None,
                    "prior_record_count": {"canaries": 1, "operations": 0,
                        "application_authority": 0, "native_owner_decisions": 0}}
            stdout = json.dumps(value, separators=(",", ":")) + "\n"
        elif step == "launcher_start":
            stdout = operator.READY_MARKER + "\n"
        elif step == "owner_reject_readback":
            stdout, stderr = self._receipt_probe_output(command)
        elif step == "launcher_stop":
            stdout = operator.STOP_MARKER + "\n"
        else:
            raise AssertionError(f"unexpected generated SSM step {step}")
        return {"Status": status, "ResponseCode": 0 if status == "Success" else 2,
            "StandardOutputContent": stdout, "StandardErrorContent": stderr}, "fake-invocation-read"

    def stop_once(self, _instance_id):
        self.stop_calls += 1
        self.state = "stopped"
        return {"synthetic": True}, "fake-stop-request"


class Issue90OperatorTests(unittest.TestCase):
    def test_target_property_readbacks_match_pinned_exact_baselines(self):
        original_lane = operator.PRIVATE_LANE
        with tempfile.TemporaryDirectory() as temp:
            try:
                lane = Path(temp)
                operator.PRIVATE_LANE = lane
                baseline_rows = {
                    "security_groups": {"SecurityGroups": [{
                        "GroupId": "sg-test", "IpPermissions": [{"FromPort": 4311,
                            "ToPort": 4311, "IpProtocol": "tcp", "IpRanges": []}],
                    }]},
                    "volumes": {"Volumes": [{"VolumeId": "vol-test", "State": "in-use",
                        "Encrypted": True, "CreateTime": "2026-10-20T01:02:03.000000Z",
                        "Attachments": [{"VolumeId": "vol-test", "AttachTime":
                                         "2026-10-20T01:04:05.000000Z"}]}]},
                    "addresses": {"Addresses": [{"AllocationId": "eipalloc-test",
                                                    "InstanceId": "i-test"}]},
                    "subnets": {"Subnets": [{"SubnetId": "subnet-test", "VpcId": "vpc-test",
                        "CidrBlock": "10.0.0.0/24", "State": "available",
                        "MapPublicIpOnLaunch": False, "AssignIpv6AddressOnCreation": False,
                        "Ipv6Native": False}]},
                }
                hashes = {}
                for name, value in baseline_rows.items():
                    path = lane / operator.TARGET_PROPERTY_FILES[name]
                    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")))
                    path.chmod(0o600)
                    hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()

                class PropertyProvider:
                    rows = baseline_rows

                    def __init__(self):
                        self.calls = []
                        self.rows = json.loads(json.dumps(baseline_rows))
                        volume = self.rows["volumes"]["Volumes"][0]
                        volume["CreateTime"] = datetime(2026, 10, 20, 1, 2, 3,
                                                        tzinfo=timezone.utc)
                        volume["Attachments"][0]["AttachTime"] = datetime(
                            2026, 10, 20, 1, 4, 5, tzinfo=timezone.utc)

                    def describe_security_groups(self, ids):
                        self.calls.append(("security_groups", ids))
                        return self.rows["security_groups"]["SecurityGroups"], "sg-read"

                    def describe_volumes(self, ids):
                        self.calls.append(("volumes", ids))
                        return self.rows["volumes"]["Volumes"], "volume-read"

                    def describe_addresses(self, ids):
                        self.calls.append(("addresses", ids))
                        return self.rows["addresses"]["Addresses"], "address-read"

                    def describe_subnets(self, ids):
                        self.calls.append(("subnets", ids))
                        return self.rows["subnets"]["Subnets"], "subnet-read"

                instance = {
                    "SubnetId": "subnet-test", "VpcId": "vpc-test",
                    "SecurityGroups": [{"GroupId": "sg-test"}],
                    "BlockDeviceMappings": [{"Ebs": {"VolumeId": "vol-test"}}],
                }
                config = {
                    "instance_id": "i-test",
                    "target_attachments": {"subnet_id": "subnet-test", "vpc_id": "vpc-test",
                        "security_group_ids": ["sg-test"], "volume_ids": ["vol-test"]},
                    "target_property_baselines": hashes,
                }
                provider = PropertyProvider()
                runtime = operator.RuntimeOperator(config, provider, None)
                request_ids = runtime._verify_target_properties(instance)
                self.assertEqual(set(request_ids), {"security_groups", "volumes", "addresses", "subnets"})
                self.assertEqual(len(provider.calls), 4)

                provider.rows = dict(baseline_rows)
                provider.rows["security_groups"] = {"SecurityGroups": [{
                    "GroupId": "sg-test", "IpPermissions": [{"FromPort": 0, "ToPort": 65535,
                        "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
                }]}
                with self.assertRaisesRegex(operator.RuntimeRefused,
                                            "TARGET_SECURITY_GROUP_PROPERTIES_CHANGED"):
                    runtime._verify_target_properties(instance)
            finally:
                operator.PRIVATE_LANE = original_lane

    def test_actual_generated_receipt_probe_checks_production_reject_fixture(self):
        with tempfile.TemporaryDirectory() as temp:
            now = int(__import__("time").time())
            principal_digest = canonical_digest({
                "principal_id": "test-owner", "tenant_id": "tenant:test-tenant"})
            app, fake_s3, _clock, _factory, _batch, authority, _packet, _ = make_case(
                temp, source_revision=operator.EXPECTED_TARGET_REVISION,
                mode="APPROVED_LAB_WRITE", principal_digest=principal_digest, clock=[now])
            native_db = Path(temp) / "native.sqlite"
            DecisionStore(native_db)
            binding_path = Path(temp) / "binding.private.json"
            binding_path.write_text(json.dumps({
                "account_id": app.binding.account_id, "bucket": app.binding.bucket}))
            binding_path.chmod(0o600)
            native_record = {
                "version": 1, "operation": "native_canary_reject",
                "batch_id": authority.batch_id, "authority_digest": authority.digest,
                "scope_digest": authority.scope_digest,
                "source_revision": authority.source_revision, "decision": "reject",
                "decided_at": now, "expires_at": authority.decision_expires_at,
                "binding": {"principal_id": "test-owner", "tenant_id": "tenant:test-tenant",
                    "conversation_id": "conversation-test", "action_id": "action-test",
                    "generation_id": str(now), "tool_call_id": "call-test",
                    "tool": "approve_s3_canary_once"},
            }
            source = r"""
const gate = require(process.argv[1]);
const config = {version:1, enabled:true, agent_id:'test-agent', python:process.argv[2],
  source_root:process.argv[3], database:process.argv[4], source_revision:process.argv[7],
  application_database:process.argv[5], application_binding:process.argv[6], source_version:'v1.0.0-mock'};
const record = JSON.parse(process.argv[8]);
(async () => {
  const first = await gate.dispatchNativeCanaryReject(config, record);
  const reopened = await gate.dispatchNativeCanaryReject(config, record);
  process.stdout.write(JSON.stringify({first, reopened}));
})().catch(() => { process.exitCode = 2; });
"""
            produced = subprocess.run([
                "node", "-e", source, str(ROOT / "integration/librechat/native_gate.cjs"),
                sys.executable, str(ROOT), str(native_db), str(app.path), str(binding_path),
                authority.source_revision, json.dumps(native_record, separators=(",", ":")),
            ], check=True, capture_output=True, text=True)
            generated = json.loads(produced.stdout)
            envelopes = generated["first"]["receipts"]
            self.assertEqual(generated["first"]["receipts"], generated["reopened"]["receipts"])
            self.assertEqual([item["kind"] for item in envelopes],
                             ["Batch", "Decision", "Run", "Evidence"])
            self.assertEqual(envelopes[2].get("schemaVersion"), "defence-factory/1")
            self.assertEqual(envelopes[2].get("kind"), "Run")
            self.assertEqual(envelopes[2]["record"]["status"], "REJECTED")
            self.assertEqual(envelopes[2]["record"]["realWrites"], 0)
            self.assertEqual(envelopes[2]["record"]["simulatedWrites"], 0)
            self.assertEqual(envelopes[3]["record"].get("provenance"), "TRUSTED_PROVIDER_READ")
            self.assertEqual(envelopes[3]["record"].get("limitation"), "FRESHNESS_NOT_VERIFIED")
            self.assertEqual(fake_s3.writes, [])
            with sqlite3.connect(app.path) as db:
                saved_auth = db.execute(
                    "SELECT assurance,verifier_id,choice FROM application_authority WHERE batch_id=?",
                    (authority.batch_id,)).fetchone()
            self.assertEqual(saved_auth, ("OWNER_AUTHENTICATED", "LIBRECHAT_NATIVE_CAS", "REJECT"))

            def execute_probe(database: Path, *, source_revision: str | None = None) -> str:
                saved_revision = operator.EXPECTED_TARGET_REVISION
                try:
                    if source_revision is not None:
                        operator.EXPECTED_TARGET_REVISION = source_revision
                    command = operator._receipt_probe({"remote": {
                        "application_database": str(database), "owner_uid": str(os.getuid())}},
                        now - 5)
                finally:
                    operator.EXPECTED_TARGET_REVISION = saved_revision
                argv = shlex.split(command)
                if argv[:4] != ["sudo", "-u", "ssm-user", "--"]:
                    self.fail("receipt probe lost its owner-scoped execution contract")
                result = subprocess.run(argv[4:], check=True, capture_output=True, text=True)
                return result.stdout

            self.assertEqual(execute_probe(app.path), "OWNER_REJECT_RECEIPT_VERIFIED\n")

            altered_packet_db = Path(temp) / "bad-packet.sqlite"
            shutil.copyfile(app.path, altered_packet_db)
            altered_packet_db.chmod(0o600)
            with sqlite3.connect(altered_packet_db) as db:
                db.execute("UPDATE application_authority SET packet_digest=? WHERE batch_id=?",
                           ("f" * 64, authority.batch_id))
            self.assertEqual(execute_probe(altered_packet_db), "RECEIPT_NOT_VERIFIED\n")
            self.assertEqual(execute_probe(app.path, source_revision="a" * 40),
                             "RECEIPT_NOT_VERIFIED\n")

    def test_run_full_fake_lifecycle_uses_production_steps_parser_and_cleanup(self):
        scenarios = ("success", "prestart_refusal", "prior_row_refusal",
                     "unknown_launch", "failure", "interrupt")
        for scenario in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temp:
                lane = Path(temp) / "private"
                repo = Path(temp) / "source"
                now = int(time.time())
                with (patch.object(operator, "PRIVATE_LANE", lane),
                      patch.object(operator, "RUNTIME_OWNER_UID", os.getuid()),
                      patch.object(operator, "RUNTIME_OWNER_GID", os.getgid())):
                    config, instance_id, baseline_rows = _make_runtime_case(
                        lane, repo, now=now)
                    receipt_db = None
                    if scenario == "success":
                        app, fake_s3, _authority, _generated = _make_production_reject_fixture(
                            Path(temp), now)
                        receipt_db = app.path
                    provider = FakeRuntimeProvider(
                        config, baseline_rows, scenario=scenario, receipt_db=receipt_db)
                    clock = FakeLifecycleClock()
                    notifications = []
                    runtime = operator.RuntimeOperator(
                        config, provider,
                        lambda run_id, _message: notifications.append(run_id) or "fake-native-receipt",
                        monotonic=clock.monotonic, sleep=clock.sleep, repo_root=repo)

                    if scenario == "prestart_refusal":
                        with self.assertRaisesRegex(operator.RuntimeRefused,
                                                    "RUNTIME_IDENTITY_MISMATCH"):
                            runtime.run()
                        self.assertEqual(provider.start_calls, 0)
                        self.assertEqual(provider.stop_calls, 0)
                        self.assertEqual(provider.sends, [])
                        continue

                    # Pin run's start timestamp to the synthetic decision time
                    # so this fixture cannot race a wall-clock second boundary.
                    with patch.object(operator.time, "time", return_value=now):
                        result = runtime.run()
                    self.assertEqual(provider.start_calls, 1)
                    self.assertEqual(provider.stop_calls, 1)
                    self.assertEqual(result["cleanup"]["final_state"], "stopped")
                    self.assertEqual(provider.state, "stopped")

                    if scenario == "success":
                        self.assertEqual(result["status"], "OWNER_REJECT_RECEIPT_VERIFIED")
                        self.assertEqual(len(notifications), 1)
                        self.assertEqual([name for name, _ in provider.sends],
                                         list(operator.EXPECTED_STEPS))
                        self.assertEqual(provider.invocation_reads, 7)
                        self.assertEqual(fake_s3.writes, [])
                        self.assertEqual(provider.dry_runs, ["start", "stop"])
                    elif scenario == "prior_row_refusal":
                        self.assertEqual(result["status"],
                                         "PRIOR_OR_AMBIGUOUS_RECORD_BLOCKS_LAUNCH")
                        self.assertNotIn("launcher_start", [name for name, _ in provider.sends])
                        self.assertEqual(len(provider.sends), 4)
                    elif scenario == "unknown_launch":
                        self.assertEqual(result["status"], "LAUNCH_UNKNOWN_NO_REPLAY")
                        names = [name for name, _ in provider.sends]
                        self.assertEqual(names.count("launcher_start"), 1)
                        self.assertEqual(names.count("launcher_stop"), 1)
                        self.assertNotIn("owner_reject_readback", names)
                    elif scenario == "failure":
                        self.assertEqual(result["status"],
                                         "SSM_STEP_REFUSED_NO_REPLAY_NO_LAUNCH")
                        self.assertEqual([name for name, _ in provider.sends],
                                         ["stage_readback"])
                    else:
                        self.assertEqual(result["status"], "INTERRUPTED_CLEANUP_REQUIRED")
                        self.assertEqual(provider.sends, [])
                    self.assertTrue((lane / "stop-claim.private.json").is_file())

    def test_parsed_probe_refusal_never_reaches_launcher(self):
        probe_names = ("stage_readback", "composed_state_readback",
                       "native_binding_readback")
        for refused_index, refused_name in enumerate(probe_names):
            with self.subTest(probe=refused_name), tempfile.TemporaryDirectory() as temp:
                responses = []
                for index, name in enumerate(probe_names + ("ledger_readback",)):
                    value = ({"state": "REFUSED", "code": "PINNED_READBACK_REFUSED"}
                             if index == refused_index else _probe_success(name))
                    responses.append(("Success", json.dumps(value, separators=(",", ":")) + "\n", ""))
                provider = FakeProvider(responses)
                runtime = operator.RuntimeOperator({}, provider, None)
                evidence = operator.PrivateEvidence(Path(temp) / "evidence")
                run_dir = evidence.create_run_dir("run-refusal")
                steps = tuple(operator.Step(name, "true", 30, json_state=expected)
                    for name, expected in (
                        ("stage_readback", "PRESERVED_STAGES_VALID"),
                        ("composed_state_readback", "COMPOSED_RUNTIME_READY"),
                        ("native_binding_readback", "NATIVE_BINDING_VALID"),
                        ("ledger_readback", "NO_PRIOR_RECORDS"))) + (
                            operator.Step("launcher_start", "true", 30,
                                          expected_stdout=operator.READY_MARKER + "\n"),
                            operator.Step("owner_reject_readback", "true", 10),
                            operator.Step("launcher_stop", "true", 30),
                        )
                result = runtime._inspect_and_launch(
                    evidence, run_dir, "run-refusal", "a" * 40, "i-0123456789abcdef0",
                    steps, 100, float("inf"), float("inf"))
                self.assertEqual(result, "SSM_PROBE_REFUSED_NO_REPLAY_NO_LAUNCH")
                self.assertEqual(len(provider.requests), refused_index + 1)
                self.assertEqual(provider.invocations, refused_index + 1)
                self.assertFalse(any("launcher" in request["Comment"]
                                     for request in provider.requests))
                parsed = json.loads((run_dir / f"ssm-output-{refused_index + 1:02d}.private.json").read_text())
                self.assertEqual(json.loads(parsed["stdout"]),
                                 {"state": "REFUSED", "code": "PINNED_READBACK_REFUSED"})

    def test_prior_ledger_rows_reach_reconciler_without_bypassing_launch_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            provider = FakeProvider([("Success", json.dumps({
                "state": "PRIOR_RECORDS_RECONCILE", "code": None,
                "prior_record_count": {"canaries": 1, "operations": 0,
                    "application_authority": 0, "native_owner_decisions": 0}},
                separators=(",", ":")) + "\n", "")])
            runtime = operator.RuntimeOperator({}, provider, None)
            evidence = operator.PrivateEvidence(Path(temp) / "evidence")
            run_dir = evidence.create_run_dir("run-state-mismatch")
            status, value = runtime._ssm_call(
                evidence, run_dir, "i-0123456789abcdef0", "run-state-mismatch", 1,
                operator.Step("ledger_readback", "true", 30,
                              json_state="NO_PRIOR_RECORDS"), 100)
            self.assertEqual(status, "Success")
            self.assertEqual(value["state"], "PRIOR_RECORDS_RECONCILE")
            self.assertEqual(len(provider.requests), 1)

    def test_invocation_does_not_exist_retries_only_the_readback(self):
        class InvocationMissing(Exception):
            response = {"Error": {"Code": "InvocationDoesNotExist"}}

        with tempfile.TemporaryDirectory() as temp:
            provider = FakeProvider([InvocationMissing(), ("Success", "ok\n", "")])
            runtime = operator.RuntimeOperator({}, provider, None, sleep=lambda _seconds: None)
            evidence = operator.PrivateEvidence(Path(temp) / "evidence")
            run_dir = evidence.create_run_dir("run-eventual-read")
            status, _ = runtime._ssm_call(
                evidence, run_dir, "i-0123456789abcdef0", "run-eventual-read", 1,
                operator.Step("launcher_stop", "true", 30, expected_stdout="ok\n"), 100)
            self.assertEqual(status, "Success")
            self.assertEqual(len(provider.requests), 1)
            self.assertEqual(provider.invocations, 2)

    def test_launcher_and_claim_write_failures_do_not_suppress_exact_stop(self):
        from unittest.mock import patch

        class Provider:
            def __init__(self):
                self.reads = 0
                self.stops = 0

            def describe_instance(self, _instance_id):
                self.reads += 1
                if self.reads == 1:
                    raise OSError("synthetic pre-stop read failure")
                return {"State": {"Name": "stopped"}}, "readback"

            def stop_once(self, _instance_id):
                self.stops += 1
                return {"StoppingInstances": []}, "stop-request"

        with tempfile.TemporaryDirectory() as temp, patch.object(
                operator, "build_steps", return_value=tuple(
                    operator.Step(f"step-{index}", "true", 30) for index in range(7))):
            provider = Provider()
            runtime = operator.RuntimeOperator({}, provider, None, monotonic=lambda: 1.0)
            runtime._ssm_call = lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("synthetic launcher cleanup failure"))
            evidence = operator.PrivateEvidence(Path(temp) / "evidence")
            run_dir = evidence.create_run_dir("run-cleanup")
            stop_claim = Path(temp) / "stop-claim.private.json"
            runtime.config = {"stop_claim_path": str(stop_claim)}
            write_once = evidence.write_once

            def fail_stop_claim(path, value):
                if path == stop_claim:
                    raise OSError("synthetic claim evidence write failure")
                return write_once(path, value)

            evidence.write_once = fail_stop_claim
            result = runtime._cleanup(evidence, run_dir, "run-cleanup",
                                      "i-0123456789abcdef0", True, True, 100.0)
            self.assertEqual(result["launcher_stop"], "RuntimeError")
            self.assertEqual(result["stop_intent"], "CLAIM_WRITE_FAILED_STOP_ONCE")
            self.assertEqual(provider.stops, 1)
            self.assertEqual(provider.reads, 2)
            self.assertEqual(result["final_state"], "stopped")

    def test_generated_python_decoder_shifts_probe_arguments(self):
        script = "import json,sys;print(json.dumps(sys.argv[1:]))"
        command = operator._compressed_python(script, ["first-probe-argument", "second"],
                                              as_root=False)
        completed = subprocess.run(shlex.split(command), check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(completed.stdout), ["first-probe-argument", "second"])

    def test_composed_probe_compiles_and_uses_accepted_installed_paths(self):
        old_stage = f"{operator.ISOLATED_ROOT}/.issue90-stage-d090c98-final-fixture"
        runtime_stage = f"{operator.ISOLATED_ROOT}/.issue90-config-resume-948e8bb6-fixture"
        command = operator._composed_probe({"remote": {
            "old_stage": old_stage, "runtime_stage": runtime_stage}})
        tokens = shlex.split(command)
        self.assertLessEqual(len(command.encode("utf-8")), 4096)
        script = lzma.decompress(base64.b85decode(tokens[6])).decode("utf-8")
        compile(script, "<generated-composed-probe>", "exec")
        self.assertIn("new_stage/'source-manifest.private.json'", script)
        self.assertNotIn("np/'source-manifest.private.json'", script)
        self.assertNotIn("old_rows[0].get('git_blob')", script)
        self.assertEqual(operator.ISOLATED_LAUNCHER,
                         "/opt/awsops-native-canary/awsops/integration/runtime/issue90-isolated-launcher.sh")

    def test_generated_node_probe_decodes_root_and_owner_arguments(self):
        original_root = operator.ISOLATED_ROOT
        original_uid, original_gid = operator.RUNTIME_OWNER_UID, operator.RUNTIME_OWNER_GID
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "isolated"
                root.mkdir(mode=0o700)
                state = root / "state"
                state.mkdir(mode=0o700)
                awsops = root / "awsops"
                awsops.mkdir(mode=0o700)
                marker = awsops / "SOURCE_REVISION"
                marker.write_text("wrong-revision\n")
                marker.chmod(0o644)
                operator.ISOLATED_ROOT = str(root)
                operator.RUNTIME_OWNER_UID = os.getuid()
                operator.RUNTIME_OWNER_GID = os.getgid()
                command = operator._native_probe({"remote": {
                    "root": str(root), "binding_sha256": "0" * 64}})
                tokens = shlex.split(command)
                self.assertEqual(tokens[0], "/usr/bin/node")
                node = shutil.which("node")
                self.assertIsNotNone(node)
                completed = subprocess.run([node, *tokens[1:]], check=True,
                                           capture_output=True, text=True)
                refusal = json.loads(completed.stdout)
                self.assertEqual(refusal, {"state": "REFUSED", "code": "NATIVE_SOURCE_MARKER"})
                decoded_source = zlib.decompress(base64.b64decode(tokens[3])).decode()
                self.assertIn("ownerUid", decoded_source)
                self.assertNotIn("process.getuid()", decoded_source)
                self.assertIn("path.join(awsops,'integration/runtime/issue90-isolated-launcher.sh')",
                              decoded_source)
                self.assertEqual(json.loads(completed.stdout), refusal)
        finally:
            operator.ISOLATED_ROOT = original_root
            operator.RUNTIME_OWNER_UID, operator.RUNTIME_OWNER_GID = original_uid, original_gid

    def test_ready_notifier_timeout_cannot_hold_stop_deadline(self):
        with tempfile.TemporaryDirectory() as temp:
            release = threading.Event()
            entered = threading.Event()

            def blocked_notifier(_run_id, _message):
                entered.set()
                release.wait(1)
                return "late-receipt"

            runtime = operator.RuntimeOperator({}, None, blocked_notifier,
                                               monotonic=lambda: 100.0)
            evidence = operator.PrivateEvidence(Path(temp) / "evidence")
            run_dir = evidence.create_run_dir("run-notifier-timeout")
            started = __import__("time").monotonic()
            result = runtime._notify_ready(evidence, run_dir, "run-notifier-timeout",
                                           "a" * 40, 100, 160.05)
            elapsed = __import__("time").monotonic() - started
            self.assertFalse(result)
            self.assertTrue(entered.wait(0.2))
            self.assertLess(elapsed, 0.5)
            saved = json.loads((run_dir / "READY-notification.private.json").read_text())
            self.assertEqual(saved["state"], "NOT_CONFIRMED_TIMEOUT_NO_RETRY")
            release.set()


if __name__ == "__main__":
    unittest.main()
