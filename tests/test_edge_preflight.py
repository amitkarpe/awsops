"""Fixture-only checks for the read-only M2 collector's safety boundaries."""

from pathlib import Path
import json
import stat
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.edge.preflight import (  # noqa: E402
    CommandResult, FixedHostReads, PreflightError, collect, validate_inputs,
)


def config():
    return {
        "aws_profile": "verified-lab",
        "hosted_zone_id": "Z12345678",
        "dns_target_fqdn": "retained-edge.example.net",
        "units": {
            "old_ops": "old-ops.service", "old_sec": "old-sec.service",
            "new_ops": "new-ops.service", "new_sec": "new-sec.service",
        },
        "candidate_ports": {"ops": 18441, "sec": 18442},
        "nginx_config_file": "/etc/nginx/nginx.conf",
        "certbot_config_dir": "/etc/letsencrypt",
        "dns01_role_name": "verified-dns01-role",
    }


def record(name, kind="A", value="192.0.2.10", ttl=60):
    return {"Name": name, "Type": kind, "TTL": ttl, "ResourceRecords": [{"Value": value}]}


class FakeAws:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else [
            record("retained-edge.example.net."),
            record("ops.astromedicomp.org."),
            record("sec.astromedicomp.org."),
            record("ops2.astromedicomp.org.", "CNAME", "retained-edge.example.net."),
            record("sec2.astromedicomp.org.", "CNAME", "retained-edge.example.net."),
        ]
        self.calls = []

    def identity(self):
        self.calls.append("identity")
        return {"Account": "000000000000", "Arn": "private-identity"}

    def zone(self, zone_id):
        self.calls.append("zone")
        return {
            "HostedZone": {"Name": "astromedicomp.org.", "Config": {"PrivateZone": False}},
            "DelegationSet": {"NameServers": ["ns1.example.net", "ns2.example.net"]},
        }

    def records(self, zone_id):
        self.calls.append("records")
        return {"ResourceRecordSets": self.rows + [record("unrelated.example.net.")]}

    def policies(self, role):
        self.calls.append("policies")
        return {"documents": [{"private_policy": "private"}]}


class FakeHost:
    def __init__(self, shared=False, jq_fail=False):
        self.calls = []
        self.shared = shared
        self.jq_fail = jq_fail

    def run(self, argv):
        self.calls.append(argv)
        if argv[0] == "jq":
            return CommandResult(1, "false\n") if self.jq_fail else CommandResult(0, "true\n")
        if argv[0] == "dig":
            return CommandResult(0, "ns1.example.net.\nns2.example.net.\n")
        if argv[0] == "nginx":
            return CommandResult(0, "server_name ops.astromedicomp.org sec.astromedicomp.org;\nserver_name ops2.astromedicomp.org sec2.astromedicomp.org;\n")
        if argv[0] == "ss":
            return CommandResult(0, "LISTEN 0 128 127.0.0.1:3333 0.0.0.0:* users:((\"old\",pid=10,fd=3))\n")
        if argv[0] == "certbot":
            if "certificates" in argv:
                return CommandResult(0, "Certificate Name: awsops-ops2-sec2\nDomains: ops2.astromedicomp.org sec2.astromedicomp.org\n")
            return CommandResult(0, "dns-route53")
        if argv[:2] == ("systemctl", "list-units"):
            return CommandResult(0, "four confirmed units")
        if argv[:2] == ("systemctl", "show"):
            unit = argv[2]
            old = unit.startswith("old-")
            role = unit.removesuffix(".service")
            root = "/srv/old" if old else "/srv/new"
            state = "/var/lib/old" if old else "/var/lib/new"
            if self.shared and unit == "new-sec.service":
                state = "/var/lib/old/old-sec"
            else:
                state = f"{state}/{role}"
            return CommandResult(0, f"Id={unit}\nActiveState=active\nWorkingDirectory={root}/{role}\nStateDirectory={state}\nMainPID=123\n")
        raise AssertionError("unexpected host command")


class PreflightTests(unittest.TestCase):
    def test_private_planner_input_and_sanitized_fail_closed_summary(self):
        with tempfile.TemporaryDirectory() as parent:
            output = Path(parent) / "evidence"
            aws, host = FakeAws(), FakeHost()
            summary = collect(config(), output, aws, host)
            planner = json.loads((output / "PRIVATE_ROUTE53_PLANNER_JSON").read_text())
            self.assertEqual(
                {row["Name"] for row in planner["ResourceRecordSets"]},
                {"retained-edge.example.net.", "ops.astromedicomp.org.", "sec.astromedicomp.org.",
                 "ops2.astromedicomp.org.", "sec2.astromedicomp.org."},
            )
            self.assertTrue(summary["dns"]["owner_zone_verified"])
            self.assertTrue(summary["dns"]["target_a_verified"])
            self.assertEqual(summary["listeners"]["candidate_free_at_snapshot"], {"ops": 18441, "sec": 18442})
            self.assertFalse(summary["activation_ready"])
            self.assertEqual(summary["status"], "NOT_READY")
            self.assertIn("AUTH_SESSION_SEPARATION_UNVERIFIED", summary["reasons"])
            self.assertNotIn("private-identity", json.dumps(summary))
            self.assertNotIn("/srv/old", json.dumps(summary))
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
            self.assertTrue(all(stat.S_IMODE(file.stat().st_mode) == 0o600 for file in output.iterdir() if file.is_file()))
            self.assertEqual(aws.calls, ["identity", "zone", "records", "policies"])
            self.assertTrue(any(argv[:2] == ("jq", "-e") for argv in host.calls))
            self.assertFalse(any(word in argv for argv in host.calls for word in ("start", "stop", "restart", "reload", "apply")))

    def test_missing_target_and_new_dns_conflict_fail_closed(self):
        rows = [record("ops.astromedicomp.org."), record("sec.astromedicomp.org."),
                record("ops2.astromedicomp.org.", "A")]
        with tempfile.TemporaryDirectory() as parent:
            output = Path(parent) / "evidence"
            summary = collect(config(), output, FakeAws(rows), FakeHost())
            self.assertFalse((output / "PRIVATE_ROUTE53_PLANNER_JSON").exists())
        self.assertFalse(summary["dns"]["target_a_verified"])
        self.assertEqual(summary["dns"]["records"]["ops2.astromedicomp.org"], "CONFLICT")
        self.assertEqual(summary["collision"], "CONFLICT")
        self.assertIn("TARGET_A_UNVERIFIED", summary["reasons"])
        self.assertFalse(summary["activation_ready"])

    def test_shared_state_blocks_readiness(self):
        with tempfile.TemporaryDirectory() as parent:
            summary = collect(config(), Path(parent) / "evidence", FakeAws(), FakeHost(shared=True))
        self.assertEqual(summary["separation"]["runtime_state"], "SHARED")
        self.assertEqual(summary["collision"], "CONFLICT")
        self.assertFalse(summary["activation_ready"])

    def test_target_assertion_failure_is_not_ready(self):
        with tempfile.TemporaryDirectory() as parent:
            summary = collect(config(), Path(parent) / "evidence", FakeAws(), FakeHost(jq_fail=True))
        self.assertFalse(summary["dns"]["target_a_verified"])
        self.assertIn("TARGET_A_UNVERIFIED", summary["reasons"])

    def test_occupied_candidate_port_is_a_collision(self):
        values = config()
        values["candidate_ports"]["sec"] = 3333
        with tempfile.TemporaryDirectory() as parent:
            summary = collect(values, Path(parent) / "evidence", FakeAws(), FakeHost())
        self.assertEqual(summary["collision"], "CONFLICT")
        self.assertEqual(summary["listeners"]["candidate_free_at_snapshot"], {"ops": 18441})
        self.assertIn("CANDIDATE_PORT_OCCUPIED", summary["reasons"])

    def test_host_runner_rejects_service_mutation_argv(self):
        with tempfile.TemporaryDirectory() as parent:
            reader = FixedHostReads(Path(parent))
            with self.assertRaises(PreflightError):
                reader.run(("systemctl", "restart", "old-sec.service"))

    def test_explicit_inputs_and_private_output_are_required(self):
        values = config()
        values["candidate_ports"]["ops"] = values["candidate_ports"]["sec"]
        with self.assertRaises(PreflightError):
            validate_inputs(values)
        with tempfile.TemporaryDirectory() as parent:
            output = Path(parent) / "evidence"
            output.mkdir(mode=0o755)
            with self.assertRaises(PreflightError):
                collect(config(), output, FakeAws(), FakeHost())


if __name__ == "__main__":
    unittest.main()
