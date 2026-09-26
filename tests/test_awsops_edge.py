from copy import deepcopy
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.edge.awsops_edge import (  # noqa: E402
    EdgeConfigError,
    OPS_HOST,
    SEC_HOST,
    plan_dns,
    render_nginx,
)


def config():
    return {
        "dns_target_fqdn": "retained-edge.example.net",
        "ops": {
            "service_unit": "awsops-ops.service",
            "runtime_root": "/srv/awsops/ops/runtime",
            "state_root": "/var/lib/awsops/ops",
            "loopback_port": 18441,
        },
        "sec": {
            "service_unit": "awsops-sec.service",
            "runtime_root": "/srv/awsops/sec/runtime",
            "state_root": "/var/lib/awsops/sec",
            "loopback_port": 18442,
        },
        "tls": {
            "identity": "awsops-ops2-sec2",
            "certificate_file": "/etc/letsencrypt/live/awsops-ops2-sec2/fullchain.pem",
            "private_key_file": "/etc/letsencrypt/live/awsops-ops2-sec2/privkey.pem",
        },
    }


def record_sets():
    return {
        "ResourceRecordSets": [
            {
                "Name": "retained-edge.example.net.",
                "Type": "A",
                "TTL": 60,
                "ResourceRecords": [{"Value": "192.0.2.10"}],
            },
            {
                "Name": "ops.astromedicomp.org.",
                "Type": "A",
                "TTL": 300,
                "ResourceRecords": [{"Value": "192.0.2.20"}],
            },
            {
                "Name": "sec.astromedicomp.org.",
                "Type": "A",
                "TTL": 300,
                "ResourceRecords": [{"Value": "192.0.2.21"}],
            },
        ]
    }


class AwsopsEdgeTests(unittest.TestCase):
    def test_dns_plan_creates_only_new_aliases_and_preserves_inputs(self):
        source = record_sets()
        before = deepcopy(source)
        plan = plan_dns(config(), source)

        self.assertEqual(source, before)
        self.assertEqual([change["Action"] for change in plan["Changes"]], ["CREATE", "CREATE"])
        records = [change["ResourceRecordSet"] for change in plan["Changes"]]
        self.assertEqual({record["Name"] for record in records}, {OPS_HOST, SEC_HOST})
        self.assertTrue(all(record["Type"] == "CNAME" for record in records))
        self.assertTrue(all(record["TTL"] == 60 for record in records))
        self.assertTrue(all(record["ResourceRecords"] == [{"Value": "retained-edge.example.net."}] for record in records))

    def test_exact_dns_match_is_noop(self):
        source = record_sets()
        first = plan_dns(config(), source)
        source["ResourceRecordSets"].extend(change["ResourceRecordSet"] for change in first["Changes"])

        self.assertEqual(plan_dns(config(), source)["Changes"], [])

    def test_dns_conflicts_and_missing_target_fail_closed(self):
        conflicting = record_sets()
        conflicting["ResourceRecordSets"].append({
            "Name": OPS_HOST,
            "Type": "A",
            "TTL": 60,
            "ResourceRecords": [{"Value": "192.0.2.30"}],
        })
        with self.assertRaises(EdgeConfigError):
            plan_dns(config(), conflicting)

        missing_target = record_sets()
        missing_target["ResourceRecordSets"] = [
            row for row in missing_target["ResourceRecordSets"]
            if row["Name"] != "retained-edge.example.net."
        ]
        with self.assertRaises(EdgeConfigError):
            plan_dns(config(), missing_target)

    def test_unavailable_ops_backend_emits_sec_only_and_no_ui(self):
        values = config()
        values["ops"] = None

        nginx = render_nginx(values)
        self.assertIn("server_name sec2.astromedicomp.org;", nginx)
        self.assertNotIn("ops2.astromedicomp.org", nginx)
        self.assertNotIn("admin", nginx.lower())

        plan = plan_dns(values, record_sets())
        self.assertEqual([item["ResourceRecordSet"]["Name"] for item in plan["Changes"]], [SEC_HOST])

        source = record_sets()
        source["ResourceRecordSets"].append({
            "Name": OPS_HOST,
            "Type": "CNAME",
            "TTL": 60,
            "ResourceRecords": [{"Value": "retained-edge.example.net."}],
        })
        with self.assertRaises(EdgeConfigError):
            plan_dns(values, source)

    def test_nginx_is_additive_new_only_and_loopback_websocket_safe(self):
        nginx = render_nginx(config())
        self.assertNotIn("ops.astromedicomp.org", nginx)
        self.assertNotIn("sec.astromedicomp.org", nginx)
        self.assertIn("server_name ops2.astromedicomp.org sec2.astromedicomp.org;", nginx)
        self.assertIn("proxy_pass http://127.0.0.1:18441;", nginx)
        self.assertIn("proxy_pass http://127.0.0.1:18442;", nginx)
        self.assertIn("proxy_set_header Upgrade $http_upgrade;", nginx)
        self.assertIn('proxy_set_header Connection "upgrade";', nginx)
        self.assertNotIn("default_server", nginx)

    def test_duplicate_ports_or_shared_roots_are_rejected(self):
        values = config()
        values["sec"]["loopback_port"] = values["ops"]["loopback_port"]
        with self.assertRaises(EdgeConfigError):
            render_nginx(values)

    def test_old_service_path_and_non_dedicated_tls_identity_are_rejected(self):
        values = config()
        values["ops"]["service_unit"] = "aws-secops-librechat.service"
        with self.assertRaises(EdgeConfigError):
            render_nginx(values)

        values = config()
        values["tls"]["certificate_file"] = "/etc/letsencrypt/live/legacy/fullchain.pem"
        values["tls"]["private_key_file"] = "/etc/letsencrypt/live/legacy/privkey.pem"
        with self.assertRaises(EdgeConfigError):
            render_nginx(values)

        values = config()
        values["upstream_host"] = "0.0.0.0"
        with self.assertRaises(EdgeConfigError):
            render_nginx(values)

        values = config()
        values["sec"]["state_root"] = values["ops"]["state_root"]
        with self.assertRaises(EdgeConfigError):
            render_nginx(values)


if __name__ == "__main__":
    unittest.main()
