import hashlib
import io
import json
import os
from pathlib import Path
import pwd
import grp
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from integration.librechat import isolated_migration as migration


class IsolatedMigrationTests(unittest.TestCase):
    def test_inspect_reports_partial_state_without_paths_or_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bundle, root = base / "bundle", base / "isolated"
            bundle.mkdir(); root.mkdir(); root.chmod(0o700)
            targets = {"awsops/one.py": b"private-payload-sentinel-one",
                       "awsops/two.py": b"private-payload-sentinel-two"}
            prior_data = b"private-known-legacy-sentinel"
            for rel, data in targets.items():
                path = bundle / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            controllers = bundle / "app/api/server/controllers/agents"
            controllers.mkdir(parents=True)
            resume, producer = b"pinned resume\n", b"pinned producer\n"
            (controllers / "resume.js").write_bytes(resume)
            (controllers / "client.js").write_bytes(producer)
            (bundle / "awsops/SOURCE_REVISION").write_text("a" * 40 + "\n")
            archive = base / "bundle.tar.gz"
            archive.write_bytes(b"archive fixture")
            files = []
            for index, (rel, data) in enumerate(targets.items()):
                item = {"target": rel, "sha256": hashlib.sha256(data).hexdigest(),
                    "mode": "0644", "owner": "ssm-user", "group": "ssm-user",
                    "legacy_presence_policy": ("absent_or_exact_known_legacy" if index == 0
                                                else "absent_only")}
                if index == 0:
                    item.update({"legacy_owner": "ssm-user", "legacy_group": "ssm-user",
                        "legacy_mode": "0644", "legacy_git_blobs": [migration.git_blob(prior_data)]})
                files.append(item)
            manifest = {"version": 1, "build_template": False,
                "isolated_root": str(root), "migration_id": "test-inspect-v1",
                "target": {"owner": "ssm-user", "group": "ssm-user",
                    "source_revision": "a" * 40,
                    "upstream_commit": "cdfe54c3498818b21b33fb609fee02f2742b37ea",
                    "bundle_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                    "resume_git_blob": migration.git_blob(resume),
                    "producer_git_blob": migration.git_blob(producer)},
                "files": files}
            manifest_path = base / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))

            installed = root / "awsops/one.py"
            installed.parent.mkdir(parents=True)
            installed.write_bytes(targets["awsops/one.py"])
            installed.chmod(0o644)
            backup = root / migration.BACKUP
            backup.mkdir(mode=0o700)
            prior_name = hashlib.sha256(b"awsops/one.py").hexdigest()
            prior_path = backup / prior_name
            prior_path.write_bytes(prior_data)
            prior_path.chmod(0o600)
            journal_path = backup / "journal.json"
            journal_path.write_text(json.dumps({"version": 1,
                "migration_id": "test-inspect-v1", "files": [
                    {"target": "awsops/one.py", "prior": prior_name,
                     "prior_sha256": hashlib.sha256(prior_data).hexdigest(),
                     "installed_sha256": files[0]["sha256"]},
                    {"target": "awsops/two.py", "prior": None, "prior_sha256": None,
                     "installed_sha256": files[1]["sha256"]}]}))
            journal_path.chmod(0o600)
            backup.chmod(0o700)
            isolated_inode = root.stat().st_ino
            backup_inode, journal_inode, prior_inode = (backup.stat().st_ino,
                journal_path.stat().st_ino, prior_path.stat().st_ino)
            installed_inode = installed.stat().st_ino
            prior_root = migration.EXPECTED_ROOT
            migration.EXPECTED_ROOT = str(root)
            def fixture_owner(info):
                if info.st_ino in (backup_inode, journal_inode, prior_inode):
                    return "root", "root"
                if info.st_ino == isolated_inode:
                    return "ssm-user", "ssm-user"
                if info.st_ino == installed_inode:
                    return "ssm-user", "ssm-user"
                return pwd.getpwuid(info.st_uid).pw_name, grp.getgrgid(info.st_gid).gr_name
            try:
                with patch.object(migration, "_owner_group", side_effect=fixture_owner):
                    result = migration.inspect_migration(bundle, manifest_path, archive, root)
                rendered = json.dumps(result, sort_keys=True)
                self.assertEqual(result["state"], "PARTIAL_RECONCILE_REQUIRED")
                self.assertEqual(result["phase"], "APPLY_OR_ROLLBACK_DIRECTION_UNKNOWN")
                self.assertEqual(result["journal"], "VALID")
                self.assertEqual([row["state"] for row in result["targets"]],
                                 ["INSTALLED_EXACT", "ABSENT_ALLOWED"])
                self.assertNotIn("awsops/one.py", rendered)
                self.assertNotIn("private-payload-sentinel", rendered)

                argv = ["isolated_migration.py", "apply", "--bundle", str(bundle),
                        "--manifest", str(manifest_path), "--archive", str(archive),
                        "--root", str(root)]
                stderr = io.StringIO()
                with patch.object(sys, "argv", argv), \
                     patch.object(migration, "apply", side_effect=ValueError("LEGACY_TARGET_DRIFT")), \
                     redirect_stderr(stderr):
                    self.assertEqual(migration.main(), 2)
                self.assertEqual(stderr.getvalue().strip(),
                                 "ISOLATED_MIGRATION_REFUSED:LEGACY_TARGET_DRIFT")
                stderr = io.StringIO()
                with patch.object(sys, "argv", argv), \
                     patch.object(migration, "apply", side_effect=ValueError("private details")), \
                     redirect_stderr(stderr):
                    self.assertEqual(migration.main(), 2)
                self.assertEqual(stderr.getvalue().strip(), "ISOLATED_MIGRATION_REFUSED")
            finally:
                migration.EXPECTED_ROOT = prior_root

    def test_exact_absent_file_apply_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bundle = base / "bundle"
            root = base / "isolated"
            bundle.mkdir()
            root.mkdir()
            target = "awsops/src/awsops/example.py"
            data = b"fixed reviewed source\n"
            source = bundle / target
            source.parent.mkdir(parents=True)
            source.write_bytes(data)
            legacy_target = "awsops/src/awsops/legacy.py"
            legacy_data = b"known legacy source\n"
            legacy_source = bundle / legacy_target
            legacy_source.parent.mkdir(parents=True, exist_ok=True)
            legacy_source.write_bytes(b"replacement source\n")
            nested_target = "awsops/integration/canary/example.cjs"
            nested_data = b"nested fixed source\n"
            nested_source = bundle / nested_target
            nested_source.parent.mkdir(parents=True)
            nested_source.write_bytes(nested_data)
            controllers = bundle / "app/api/server/controllers/agents"
            controllers.mkdir(parents=True)
            resume = b"pinned resume\n"
            producer = b"pinned producer\n"
            (controllers / "resume.js").write_bytes(resume)
            (controllers / "client.js").write_bytes(producer)
            (bundle / "awsops").mkdir(exist_ok=True)
            (bundle / "awsops/SOURCE_REVISION").write_text("a"*40 + "\n")
            live_legacy = root / legacy_target
            live_legacy.parent.mkdir(parents=True)
            live_legacy.write_bytes(legacy_data)
            live_legacy.chmod(0o644)
            archive = base / "bundle.tar.gz"
            archive.write_bytes(b"archive fixture")
            manifest = {
                "version": 1,
                "build_template": False,
                "isolated_root": str(root),
                "migration_id": "test-v1",
                "target": {"owner": "ssm-user", "group": "ssm-user",
                    "source_revision":"a"*40,"upstream_commit":"cdfe54c3498818b21b33fb609fee02f2742b37ea",
                    "bundle_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
                    "resume_git_blob":migration.git_blob(resume),
                    "producer_git_blob":migration.git_blob(producer)},
                "files": [
                    {"target": legacy_target, "sha256": hashlib.sha256(b"replacement source\n").hexdigest(),
                     "mode": "0644", "owner": "ssm-user", "group": "ssm-user",
                     "legacy_presence_policy": "absent_or_exact_known_legacy",
                     "legacy_owner":pwd.getpwuid(os.getuid()).pw_name,
                     "legacy_group":grp.getgrgid(os.getgid()).gr_name,"legacy_mode":"0644",
                     "legacy_git_blobs":[migration.git_blob(legacy_data)]},
                    {"target": target, "sha256": hashlib.sha256(data).hexdigest(),
                     "mode": "0644", "owner": "ssm-user", "group": "ssm-user",
                     "legacy_presence_policy": "absent_only"},
                    {"target": nested_target, "sha256": hashlib.sha256(nested_data).hexdigest(),
                     "mode": "0644", "owner": "ssm-user", "group": "ssm-user",
                     "legacy_presence_policy": "absent_only"},
                ],
            }
            manifest_path = base / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            prior_root, prior_identity = migration.EXPECTED_ROOT, migration._identity
            migration.EXPECTED_ROOT = str(root)
            migration._identity = lambda: (os.getuid(), os.getgid())
            try:
                result = migration.apply(bundle, manifest_path, archive, root)
                self.assertEqual(result["state"], "INSTALLED")
                self.assertEqual((root / target).read_bytes(), data)
                self.assertEqual((root / nested_target).read_bytes(), nested_data)
                backup_name = hashlib.sha256(legacy_target.encode()).hexdigest()
                backup_file = root / migration.BACKUP / backup_name
                backup_file.write_bytes(b"corrupt backup")
                with patch.object(migration, "_owner_group", return_value=("root", "root")):
                    with self.assertRaisesRegex(ValueError, "MIGRATION_JOURNAL_MISMATCH"):
                        migration.rollback(bundle, manifest_path, archive, root)
                self.assertEqual((root / target).read_bytes(), data)
                self.assertEqual((root / nested_target).read_bytes(), nested_data)
                self.assertEqual(live_legacy.read_bytes(), b"replacement source\n")
                backup_file.write_bytes(legacy_data)
                (root / target).unlink()  # Simulate interruption before this new-only path was installed.
                backup_dir = root / migration.BACKUP
                root_owned_inodes = {backup_dir.stat().st_ino, backup_file.stat().st_ino,
                    (backup_dir / "journal.json").stat().st_ino}
                target_inodes = {live_legacy.stat().st_ino,
                                 (root / nested_target).stat().st_ino}
                def fixture_owner(info):
                    if info.st_ino in target_inodes:
                        return "ssm-user", "ssm-user"
                    if info.st_ino in root_owned_inodes:
                        return "root", "root"
                    return pwd.getpwuid(info.st_uid).pw_name, grp.getgrgid(info.st_gid).gr_name
                with patch.object(migration, "_owner_group", side_effect=fixture_owner):
                    restored = migration.rollback(bundle, manifest_path, archive, root)
                self.assertEqual(restored["state"], "ROLLED_BACK")
                self.assertFalse((root / target).exists())
                self.assertEqual(live_legacy.read_bytes(), legacy_data)
            finally:
                migration.EXPECTED_ROOT, migration._identity = prior_root, prior_identity

    def test_rejects_foreign_target_before_mutating_any_file(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bundle, root = base / "bundle", base / "isolated"
            bundle.mkdir(); root.mkdir()
            target = "awsops/src/awsops/example.py"
            data = b"fixed reviewed source\n"
            (bundle / target).parent.mkdir(parents=True)
            (bundle / target).write_bytes(data)
            controllers = bundle / "app/api/server/controllers/agents"
            controllers.mkdir(parents=True)
            resume, producer = b"pinned resume\n", b"pinned producer\n"
            (controllers / "resume.js").write_bytes(resume)
            (controllers / "client.js").write_bytes(producer)
            (bundle / "awsops").mkdir(exist_ok=True)
            (bundle / "awsops/SOURCE_REVISION").write_text("a"*40 + "\n")
            archive = base / "bundle.tar.gz"
            archive.write_bytes(b"archive fixture")
            live = root / target
            live.parent.mkdir(parents=True)
            live.write_bytes(b"foreign\n")
            manifest = {"version":1,"build_template":False,"isolated_root":str(root),"migration_id":"test-v1",
                "target":{"owner":"ssm-user","group":"ssm-user","source_revision":"a"*40,
                    "upstream_commit":"cdfe54c3498818b21b33fb609fee02f2742b37ea",
                    "bundle_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
                    "resume_git_blob":migration.git_blob(resume),"producer_git_blob":migration.git_blob(producer)},"files":[{
                    "target":target,"sha256":hashlib.sha256(data).hexdigest(),"mode":"0644",
                    "owner":"ssm-user","group":"ssm-user","legacy_presence_policy":"absent_only"}]}
            manifest_path = base / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            prior_root = migration.EXPECTED_ROOT
            prior_identity = migration._identity
            migration.EXPECTED_ROOT = str(root)
            migration._identity = lambda: (os.getuid(), os.getgid())
            try:
                with self.assertRaisesRegex(ValueError, "LEGACY_TARGET_DRIFT"):
                    migration.apply(bundle, manifest_path, archive, root)
                self.assertEqual(live.read_bytes(), b"foreign\n")
            finally:
                migration.EXPECTED_ROOT, migration._identity = prior_root, prior_identity

    def test_versioned_recovery_restores_exact_legacy_metadata_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bundle, root = base / "bundle", base / "isolated"
            bundle.mkdir(); root.mkdir(mode=0o700)
            target = "integration/canary/mcp_guard.cjs"
            replacement, legacy = b"reviewed replacement\n", b"known non-executing legacy guard\n"
            source = bundle / target
            source.parent.mkdir(parents=True)
            source.write_bytes(replacement)
            absent_target = "new/nested/canary/new_guard.cjs"
            absent_replacement = b"new reviewed guard\n"
            absent_source = bundle / absent_target
            absent_source.parent.mkdir(parents=True)
            absent_source.write_bytes(absent_replacement)
            controllers = bundle / "app/api/server/controllers/agents"
            controllers.mkdir(parents=True)
            resume, producer = b"pinned resume\n", b"pinned producer\n"
            (controllers / "resume.js").write_bytes(resume)
            (controllers / "client.js").write_bytes(producer)
            (bundle / "awsops/SOURCE_REVISION").parent.mkdir(parents=True)
            (bundle / "awsops/SOURCE_REVISION").write_text("a" * 40 + "\n")
            live = root / target
            live.parent.mkdir(parents=True)
            live.write_bytes(legacy)
            live.chmod(0o600)
            prior_tuple = {"sha256": hashlib.sha256(legacy).hexdigest(),
                           "git_blob": migration.git_blob(legacy), "uid": os.getuid(),
                           "gid": os.getgid(), "mode": "0600"}
            archive = base / "bundle.tar.gz"
            archive.write_bytes(b"archive fixture")
            manifest = {"version": 2, "recovery_policy": {"version": 1,
                "kind": "exact-prestate-tuples"}, "build_template": False,
                "isolated_root": str(root), "migration_id": "test-recovery-v1",
                "target": {"owner": "ssm-user", "group": "ssm-user",
                    "source_revision": "a" * 40,
                    "upstream_commit": "cdfe54c3498818b21b33fb609fee02f2742b37ea",
                    "bundle_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                    "resume_git_blob": migration.git_blob(resume),
                    "producer_git_blob": migration.git_blob(producer)},
                "files": [{"target": target, "sha256": hashlib.sha256(replacement).hexdigest(),
                    "mode": "0644", "owner": "ssm-user", "group": "ssm-user",
                    "legacy_presence_policy": "absent_only",
                    "recovery_preconditions": [prior_tuple]},
                    {"target": absent_target,
                     "sha256": hashlib.sha256(absent_replacement).hexdigest(),
                     "mode": "0644", "owner": "ssm-user", "group": "ssm-user",
                     "legacy_presence_policy": "absent_only",
                     "recovery_preconditions": [{"state": "ABSENT"}]}]}
            manifest_path = base / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            prior_root, prior_identity = migration.EXPECTED_ROOT, migration._identity
            migration.EXPECTED_ROOT = str(root)
            migration._identity = lambda: (os.getuid(), os.getgid())
            try:
                write_exclusive = migration._write_exclusive
                def corrupt_backup_after_journal(path, data, mode, uid, gid):
                    write_exclusive(path, data, mode, uid, gid)
                    if path.name == "journal.json":
                        backup_file = path.parent / hashlib.sha256(target.encode()).hexdigest()
                        with backup_file.open("r+b") as stream:
                            stream.write(b"late corruption")
                            stream.flush()
                            os.fsync(stream.fileno())
                with patch.object(migration, "_write_exclusive",
                                  side_effect=corrupt_backup_after_journal):
                    with self.assertRaisesRegex(ValueError, "MIGRATION_BACKUP_VERIFY_FAILED"):
                        migration.apply(bundle, manifest_path, archive, root)
                self.assertEqual((live.read_bytes(), live.stat().st_uid, live.stat().st_gid,
                                  format(live.stat().st_mode & 0o777, "04o")),
                                 (legacy, prior_tuple["uid"], prior_tuple["gid"], "0600"))
                self.assertFalse((root / absent_target).exists())
                self.assertFalse((root / "new").exists())
                shutil.rmtree(root / migration.BACKUP)

                def change_target_after_journal(path, data, mode, uid, gid):
                    write_exclusive(path, data, mode, uid, gid)
                    if path.name == "journal.json":
                        live.write_bytes(b"changed during backup")
                        live.chmod(0o600)
                with patch.object(migration, "_write_exclusive",
                                  side_effect=change_target_after_journal):
                    with self.assertRaisesRegex(ValueError,
                                                "MIGRATION_TARGET_CHANGED_DURING_BACKUP"):
                        migration.apply(bundle, manifest_path, archive, root)
                self.assertEqual(live.read_bytes(), b"changed during backup")
                self.assertFalse((root / absent_target).exists())
                self.assertFalse((root / "new").exists())
                shutil.rmtree(root / migration.BACKUP)
                live.write_bytes(legacy)
                live.chmod(0o600)

                result = migration.apply(bundle, manifest_path, archive, root)
                self.assertEqual(result["state"], "INSTALLED")
                self.assertEqual((live.read_bytes(), live.stat().st_uid, live.stat().st_gid,
                                  format(live.stat().st_mode & 0o777, "04o")),
                                 (replacement, os.getuid(), os.getgid(), "0644"))
                installed_new = root / absent_target
                self.assertEqual(installed_new.read_bytes(), absent_replacement)
                backup_dir = root / migration.BACKUP
                root_owned_inodes = {backup_dir.stat().st_ino,
                    (backup_dir / "journal.json").stat().st_ino,
                    (backup_dir / hashlib.sha256(target.encode()).hexdigest()).stat().st_ino}
                target_inode = live.stat().st_ino
                installed_new_inode = installed_new.stat().st_ino
                def fixture_owner(info):
                    if info.st_ino in (target_inode, installed_new_inode):
                        return "ssm-user", "ssm-user"
                    if info.st_ino in root_owned_inodes:
                        return "root", "root"
                    return pwd.getpwuid(info.st_uid).pw_name, grp.getgrgid(info.st_gid).gr_name
                with patch.object(migration, "_owner_group", side_effect=fixture_owner):
                    self.assertEqual(migration.apply(bundle, manifest_path, archive, root)["state"],
                                     "ALREADY_INSTALLED")
                journal = json.loads((root / migration.BACKUP / "journal.json").read_text())
                row = journal["files"][0]
                self.assertEqual((journal["version"], row["prior_git_blob"], row["prior_uid"],
                                  row["prior_gid"], row["prior_mode"]),
                                 (2, migration.git_blob(legacy), os.getuid(), os.getgid(), "0600"))
                with patch.object(migration, "_owner_group", side_effect=fixture_owner):
                    result = migration.rollback(bundle, manifest_path, archive, root)
                self.assertEqual(result["state"], "ROLLED_BACK")
                self.assertEqual((live.read_bytes(), live.stat().st_uid, live.stat().st_gid,
                                  format(live.stat().st_mode & 0o777, "04o")),
                                 (legacy, os.getuid(), os.getgid(), "0600"))
                self.assertFalse(installed_new.exists())
                live.chmod(0o640)
                with self.assertRaisesRegex(ValueError, "LEGACY_TARGET_DRIFT"):
                    migration.apply(bundle, manifest_path, archive, root)
                self.assertFalse((root / migration.BACKUP).exists())
            finally:
                migration.EXPECTED_ROOT, migration._identity = prior_root, prior_identity


if __name__ == "__main__":
    unittest.main()
