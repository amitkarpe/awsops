"""One pinned Issue90 ledger read, with bounded EC2 start/finally-stop only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import time
import uuid
from datetime import datetime, timezone

from . import issue90_operator as runtime

COMMAND_SHA256 = "75c1290aae72a1ac4a7176aa96d9e75c4bc6da6391cb393a6201ce54709cd0ad"
REQUEST_SHA256 = "e0da9e03bd4551169e53c2679f89945f746e534c181735ca5d2710d7bf1467b3"
PREVIOUS_SHA256 = "469f8eeb197af35a46c8c775665140b622094f6ef006b36f22e54666c66fc207"
REQUEST_LABEL = "i90-ledger-diagnostic-b4f0198-offline"
REQUEST_BYTES = 2265
ACTIVE_SECONDS = 300
STOP_SECONDS = 600


class LedgerDiagnostic(runtime.RuntimeOperator):
    """Reuse validators/provider/cleanup, never the runtime launch sequence."""

    def prepare(self, request_path: Path) -> tuple[str, runtime.Step]:
        self._verify_common_config()
        head = self._verify_source()
        if self.config["previous_window"].get("result_sha256") != PREVIOUS_SHA256:
            raise runtime.RuntimeRefused("DIAGNOSTIC_PREDECESSOR_PIN")
        self._validate_previous()
        for key in ("start_claim_path", "stop_claim_path"):
            path = Path(self.config[key])
            if path.exists() or path.is_symlink():
                raise runtime.RuntimeRefused("ONE_USE_CLAIM_COLLISION")
        runtime._private_file(request_path, REQUEST_SHA256)
        request = runtime._load_private_json(request_path, expected_uid=os.getuid())
        command = runtime._ledger_probe(self.config)
        if hashlib.sha256(command.encode()).hexdigest() != COMMAND_SHA256:
            raise runtime.RuntimeRefused("DIAGNOSTIC_COMMAND_PIN")
        step = runtime.Step("ledger_readback", command, 30, json_state="NO_PRIOR_RECORDS")
        expected = runtime.build_ssm_request(self.config["instance_id"], REQUEST_LABEL, step)
        if request != expected or len(json.dumps(request, separators=(",", ":")).encode()) != REQUEST_BYTES:
            raise runtime.RuntimeRefused("DIAGNOSTIC_REQUEST_PIN")
        return head, step

    def run_diagnostic(self, request_path: Path) -> dict:
        head, step = self.prepare(request_path)
        instance_id = self.config["instance_id"]
        request = runtime.build_ssm_request(instance_id, REQUEST_LABEL, step)
        runtime._request_ok(self.provider, request)
        identity, identity_id = self.provider.identity()
        if (identity.get("Account") != self.config["expected_account_id"]
                or identity.get("Arn") != self.config["expected_principal_arn"]
                or ":root" in str(identity.get("Arn", ""))):
            raise runtime.RuntimeRefused("RUNTIME_IDENTITY_MISMATCH")
        row, read_id = self.provider.describe_instance(instance_id)
        if row is None:
            raise runtime.RuntimeRefused("TARGET_NOT_FOUND")
        self._verify_target(row, identity["Account"], identity["Arn"])
        property_ids = self._verify_target_properties(row)
        if not self.provider.dry_run("start", instance_id) or not self.provider.dry_run("stop", instance_id):
            raise runtime.RuntimeRefused("LIFECYCLE_PERMISSION_DRY_RUN_REFUSED")
        evidence = runtime.PrivateEvidence(Path(self.config["evidence_root"]))
        run_id = "i90-ledger-" + uuid.uuid4().hex
        directory = evidence.create_run_dir(run_id)
        evidence.write_once(directory / "preflight.private.json", {
            "source_head": head, "identity_request_id": identity_id,
            "target_read_request_id": read_id, "property_request_ids": property_ids,
            "request_sha256": REQUEST_SHA256, "command_sha256": COMMAND_SHA256,
            "active_seconds": ACTIVE_SECONDS, "stop_reserve_seconds": STOP_SECONDS,
            "operational_estimate_ceiling_usd": 1, "total_experiment_ceiling_usd": 100,
            "hard_billing_cap": False, "session_cleanup": "NOT_APPLICABLE"})
        # Cross-run exclusion: never reuse/reset either previous claim.
        if (Path(self.config["stop_claim_path"]).exists()
                or Path(self.config["stop_claim_path"]).is_symlink()):
            raise runtime.RuntimeRefused("ONE_USE_CLAIM_COLLISION")
        evidence.write_once(Path(self.config["start_claim_path"]), {
            "phase": "START_INTENT", "run_id": run_id, "instance_id": instance_id,
            "operator_source_head": head, "previous_result_sha256": PREVIOUS_SHA256,
            "issued_at_utc": datetime.now(timezone.utc).isoformat(), "request_count": 1})
        active_deadline = self.monotonic() + ACTIVE_SECONDS
        absolute_deadline = active_deadline + STOP_SECONDS
        result = {"run_id": run_id, "status": "START_NOT_SENT", "diagnostic": "UNKNOWN",
                  "session_cleanup": "NOT_APPLICABLE", "app_launch": "NOT_REQUESTED"}
        handlers = {}
        started = False

        def interrupt(_signum, _frame):
            raise KeyboardInterrupt

        try:
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                handlers[sig] = signal.signal(sig, interrupt)
            started = True  # An uncertain Start still requires independent Stop.
            response, request_id = self.provider.start_once(instance_id)
            result["start_request_id"] = request_id
            evidence.write_once(directory / "start-response.private.json", {
                "request_id": request_id, "response": response})
            online = False
            # Reserve 90s for the only command/readback; SDK calls are bounded.
            while self.monotonic() + 140 < active_deadline:
                current, _ = self.provider.describe_instance(instance_id)
                state = current.get("State", {}).get("Name") if current else None
                if state == "running":
                    online, _ = self.provider.ssm_online(instance_id)
                    if online:
                        break
                elif state != "pending":
                    break
                self.sleep(5)
            if not online or self.monotonic() + 90 >= active_deadline:
                result["status"] = "SSM_NOT_READY_NO_SEND"
            else:
                # Fixed label reproduces approved request bytes; actual run_id
                # remains in claims/result, never a regenerated Comment.
                status, value = self._ssm_call(evidence, directory, instance_id,
                    REQUEST_LABEL, 1, step, int(time.time()), active_deadline - 30)
                result["status"] = status
                if status in {"Success", "SSM_PROBE_REFUSED_NO_REPLAY"}:
                    result["diagnostic"] = value
        except KeyboardInterrupt:
            result["status"] = "INTERRUPTED_NO_REPLAY"
        except BaseException as exc:
            result["status"] = "ERROR_NO_REPLAY"
            result["error_code"] = runtime._safe_error_code(exc)
        finally:
            for sig in handlers:
                signal.signal(sig, signal.SIG_IGN)
            try:
                # No launcher cleanup, even on error. Leave 30s for the final
                # bounded SDK call before the absolute 15-minute deadline.
                result["cleanup"] = self._cleanup(evidence, directory, run_id,
                    instance_id, False, started, absolute_deadline - 30)
                if result["cleanup"].get("final_state") != "stopped":
                    result["status"] = "STOPPED_NOT_VERIFIED"
            except BaseException as exc:
                result["status"] = "STOPPED_NOT_VERIFIED"
                result["cleanup_error_code"] = runtime._safe_error_code(exc)
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)
            try:
                evidence.write_once(directory / "result.private.json", result)
            except BaseException:
                result["result_evidence"] = "WRITE_FAILED"
        return result


def main(argv=None, *, provider_factory=runtime.Boto3RuntimeProvider) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-ledger-diagnostic", action="store_true")
    parser.add_argument("--private-config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.execute_ledger_diagnostic:
        parser.error("requires --execute-ledger-diagnostic")
    try:
        runtime._private_file(args.private_config, args.config_sha256)
        config = runtime._load_private_json(args.private_config, expected_uid=os.getuid())
        diagnostic = LedgerDiagnostic(config, None, None)
        diagnostic.prepare(args.request)  # All local pins before SDK construction.
        diagnostic.provider = provider_factory()
        result = diagnostic.run_diagnostic(args.request)
    except runtime.RuntimeRefused as exc:
        print(f"DIAGNOSTIC_REFUSED={exc}")
        return 2
    print(f"DIAGNOSTIC_STATUS={result['status']}")
    return 0 if (isinstance(result["diagnostic"], dict)
                 and result.get("cleanup", {}).get("final_state") == "stopped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
