#!/usr/bin/env python3
"""Apply/rollback the exact reviewed Issue 90 bundle inside its isolated root."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import grp
import shutil
import stat
import sys
import tempfile

EXPECTED_ROOT = "/opt/awsops-native-canary"
BACKUP = ".awsops-issue90-migration-v1"
SAFE_ERROR_CODES = {
    "MIGRATION_PATH_UNSAFE", "MIGRATION_PATH_ESCAPE", "MIGRATION_DIRECTORY_DRIFT",
    "MIGRATION_FILE_SYMLINK", "ISOLATED_ROOT_REQUIRED", "BUNDLE_PATH_UNSAFE",
    "MIGRATION_MANIFEST_UNSUPPORTED", "MIGRATION_SOURCE_PIN_INVALID",
    "MIGRATION_MANIFEST_EMPTY", "MIGRATION_MANIFEST_INVALID",
    "BUNDLE_FILE_DIGEST_MISMATCH", "RENDERED_CONTROLLER_PIN_MISMATCH",
    "SOURCE_REVISION_MISMATCH", "BUNDLE_ARCHIVE_REQUIRED",
    "BUNDLE_ARCHIVE_DIGEST_MISMATCH", "ROOT_INSTALLER_REQUIRED",
    "LEGACY_TARGET_DRIFT", "MIGRATION_ALREADY_STARTED_RECONCILE",
    "MIGRATION_DIRECTORY_UNAVAILABLE",
    "MIGRATION_JOURNAL_MISSING", "MIGRATION_JOURNAL_MISMATCH",
    "MIGRATION_INSTALLED_FILE_DRIFT",
}


def fail(code: str) -> None:
    raise ValueError(code)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def checked_path(root: Path, rel: str) -> Path:
    value = PurePosixPath(rel)
    if value.is_absolute() or not value.parts or any(p in ("", ".", "..") for p in value.parts):
        fail("MIGRATION_PATH_UNSAFE")
    result = root.joinpath(*value.parts)
    if not result.resolve(strict=False).is_relative_to(root):
        fail("MIGRATION_PATH_ESCAPE")
    current = root
    for part in value.parts[:-1]:
        current = current / part
        if current.exists() and (current.is_symlink() or not current.is_dir()):
            fail("MIGRATION_DIRECTORY_DRIFT")
    if result.is_symlink():
        fail("MIGRATION_FILE_SYMLINK")
    return result


def load_manifest(bundle: Path, manifest_path: Path, root: Path) -> tuple[dict, list[dict]]:
    if root != Path(EXPECTED_ROOT) or not root.is_absolute() or root.resolve(strict=True) != root:
        fail("ISOLATED_ROOT_REQUIRED")
    if bundle.resolve(strict=True) != bundle or manifest_path.resolve(strict=True) != manifest_path:
        fail("BUNDLE_PATH_UNSAFE")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("version") != 1 or manifest.get("build_template") is not False
            or manifest.get("isolated_root") != EXPECTED_ROOT
            or manifest.get("target", {}).get("owner") != "ssm-user"
            or manifest.get("target", {}).get("group") != "ssm-user"):
        fail("MIGRATION_MANIFEST_UNSUPPORTED")
    target_meta = manifest.get("target", {})
    if (not isinstance(target_meta.get("source_revision"), str)
            or len(target_meta["source_revision"]) != 40
            or target_meta.get("upstream_commit") != "cdfe54c3498818b21b33fb609fee02f2742b37ea"
            or not isinstance(target_meta.get("bundle_sha256"), str)
            or len(target_meta["bundle_sha256"]) != 64):
        fail("MIGRATION_SOURCE_PIN_INVALID")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        fail("MIGRATION_MANIFEST_EMPTY")
    seen = set()
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("target"), str):
            fail("MIGRATION_MANIFEST_INVALID")
        target = item["target"]
        if target in seen or item.get("legacy_presence_policy") not in ("absent_only", "absent_or_exact_known_legacy"):
            fail("MIGRATION_MANIFEST_INVALID")
        seen.add(target)
        data_path = checked_path(bundle, target)
        data = data_path.read_bytes()
        if (sha(data) != item.get("sha256") or item.get("mode") != "0644"
                or item.get("owner") != "ssm-user" or item.get("group") != "ssm-user"):
            fail("BUNDLE_FILE_DIGEST_MISMATCH")
    for rel, expected in (("app/api/server/controllers/agents/resume.js",
                           target_meta.get("resume_git_blob")),
                          ("app/api/server/controllers/agents/client.js",
                           target_meta.get("producer_git_blob"))):
        if not isinstance(expected, str) or git_blob(checked_path(bundle, rel).read_bytes()) != expected:
            fail("RENDERED_CONTROLLER_PIN_MISMATCH")
    revision = checked_path(bundle, "awsops/SOURCE_REVISION").read_text(encoding="ascii").strip()
    if revision != target_meta["source_revision"]:
        fail("SOURCE_REVISION_MISMATCH")
    return manifest, files


def verify_archive(manifest: dict, archive: Path) -> None:
    if archive.resolve(strict=True) != archive or not archive.is_file():
        fail("BUNDLE_ARCHIVE_REQUIRED")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != manifest["target"]["bundle_sha256"]:
        fail("BUNDLE_ARCHIVE_DIGEST_MISMATCH")


def _identity() -> tuple[int, int]:
    if os.geteuid() != 0:
        fail("ROOT_INSTALLER_REQUIRED")
    return pwd.getpwnam("ssm-user").pw_uid, grp.getgrnam("ssm-user").gr_gid


def _legacy_ok(target: Path, item: dict) -> bool:
    if not target.exists():
        return item["legacy_presence_policy"] in ("absent_only", "absent_or_exact_known_legacy")
    if item["legacy_presence_policy"] == "absent_only":
        return False
    info = target.lstat()
    if not stat.S_ISREG(info.st_mode) or target.resolve(strict=True) != target:
        return False
    user, group = pwd.getpwuid(info.st_uid).pw_name, grp.getgrgid(info.st_gid).gr_name
    if (user, group, format(stat.S_IMODE(info.st_mode), "04o")) != (
            item.get("legacy_owner"), item.get("legacy_group"), item.get("legacy_mode")):
        return False
    allowed = set(item.get("legacy_git_blobs", [])) | set(item.get("legacy_git_blob_alternates", []))
    return git_blob(target.read_bytes()) in allowed


def _atomic(path: Path, data: bytes, mode: int, uid: int, gid: int) -> None:
    fd, name = tempfile.mkstemp(prefix=".awsops-stage-", dir=path.parent)
    temp = Path(name)
    try:
        os.fchmod(fd, mode)
        os.fchown(fd, uid, gid)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        dir_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if temp.exists():
            temp.unlink()


def apply(bundle: Path, manifest_path: Path, archive: Path, root: Path) -> dict:
    manifest, files = load_manifest(bundle, manifest_path, root)
    verify_archive(manifest, archive)
    uid, gid = _identity()
    backup = root / BACKUP
    if backup.exists() or backup.is_symlink():
        fail("MIGRATION_ALREADY_STARTED_RECONCILE")
    states = []
    for item in files:
        target = checked_path(root, item["target"])
        if not _legacy_ok(target, item):
            fail("LEGACY_TARGET_DRIFT")
        states.append((item, target, target.read_bytes() if target.exists() else None))
    backup.mkdir(mode=0o700)
    os.chown(backup, os.geteuid(), os.getegid())
    journal = {"version": 1, "migration_id": manifest["migration_id"], "files": []}
    try:
        for item, target, prior in states:
            if not target.parent.exists():
                missing = []
                parent = target.parent
                while parent != root and not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                if (parent.is_symlink() or not parent.is_dir()
                        or not parent.resolve(strict=True).is_relative_to(root)):
                    fail("MIGRATION_DIRECTORY_UNAVAILABLE")
                for directory in reversed(missing):
                    directory.mkdir(mode=0o755)
                    os.chown(directory, uid, gid)
            prior_name = hashlib.sha256(item["target"].encode()).hexdigest()
            if prior is not None:
                prior_path = backup / prior_name
                prior_path.write_bytes(prior)
                prior_path.chmod(0o600)
                journal["files"].append({"target": item["target"], "prior": prior_name,
                                         "prior_sha256": sha(prior), "installed_sha256": item["sha256"]})
            else:
                journal["files"].append({"target": item["target"], "prior": None,
                                         "prior_sha256": None, "installed_sha256": item["sha256"]})
        journal_path = backup / "journal.json"
        journal_path.write_text(json.dumps(journal, sort_keys=True, separators=(",", ":")) + "\n")
        journal_path.chmod(0o600)
        for item, target, _prior in states:
            _atomic(target, checked_path(bundle, item["target"]).read_bytes(), 0o644, uid, gid)
    except Exception:
        # Do not auto-restore after an uncertain rename; journal plus per-file
        # hashes give the explicit rollback command exact reconciliation data.
        raise
    return {"state": "INSTALLED", "migration_id": manifest["migration_id"], "files": len(files)}


def _owner_group(info: os.stat_result) -> tuple[str, str]:
    return pwd.getpwuid(info.st_uid).pw_name, grp.getgrgid(info.st_gid).gr_name


def _inspect_root(root: Path) -> str:
    if root != Path(EXPECTED_ROOT) or not root.is_absolute():
        return "ROOT_PATH_REFUSED"
    try:
        info = root.lstat()
        owner, group = _owner_group(info)
    except (OSError, KeyError):
        return "ROOT_READ_REFUSED"
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        return "ROOT_NOT_REAL_DIRECTORY"
    if (owner, group, stat.S_IMODE(info.st_mode)) != ("ssm-user", "ssm-user", 0o700):
        return "ROOT_METADATA_DRIFT"
    return "SSM_USER_0700"


def _inspect_target(root: Path, item: dict) -> str:
    try:
        target = checked_path(root, item["target"])
        info = target.lstat()
    except FileNotFoundError:
        return "ABSENT_ALLOWED" if _legacy_ok(root / item["target"], item) else "ABSENT_NOT_ALLOWED"
    except (OSError, ValueError):
        return "TARGET_PATH_REFUSED"
    if stat.S_ISLNK(info.st_mode):
        return "TARGET_SYMLINK"
    if not stat.S_ISREG(info.st_mode):
        return "TARGET_NOT_REGULAR"
    try:
        data = target.read_bytes()
        owner, group = _owner_group(info)
    except (OSError, KeyError):
        return "TARGET_READ_REFUSED"
    mode = format(stat.S_IMODE(info.st_mode), "04o")
    if (sha(data) == item["sha256"] and mode == item["mode"]
            and owner == item["owner"] and group == item["group"]):
        return "INSTALLED_EXACT"
    if _legacy_ok(target, item):
        return "LEGACY_EXACT"
    if sha(data) == item["sha256"]:
        return "INSTALLED_METADATA_DRIFT"
    return "TARGET_DRIFT"


def _inspect_journal(root: Path, manifest: dict, files: list[dict]) -> tuple[str, str]:
    backup = root / BACKUP
    try:
        backup_info = backup.lstat()
    except FileNotFoundError:
        return "ABSENT", "ABSENT"
    except OSError:
        return "UNREADABLE", "UNREADABLE"
    if stat.S_ISLNK(backup_info.st_mode):
        return "UNSAFE", "BACKUP_SYMLINK"
    if not stat.S_ISDIR(backup_info.st_mode):
        return "UNSAFE", "BACKUP_NOT_DIRECTORY"
    owner, group = _owner_group(backup_info)
    backup_status = ("ROOT_0700" if (owner, group, stat.S_IMODE(backup_info.st_mode))
                     == ("root", "root", 0o700) else "BACKUP_METADATA_DRIFT")
    journal_path = backup / "journal.json"
    try:
        info = journal_path.lstat()
    except FileNotFoundError:
        return "MISSING", backup_status
    except OSError:
        return "UNREADABLE", backup_status
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return "UNSAFE", backup_status
    if (_owner_group(info) != ("root", "root")
            or stat.S_IMODE(info.st_mode) != 0o600):
        return "JOURNAL_METADATA_DRIFT", backup_status
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return "INVALID", backup_status
    rows = journal.get("files") if isinstance(journal, dict) else None
    expected = {item["target"]: item for item in files}
    if (not isinstance(journal, dict)
            or journal.get("version") != 1
            or journal.get("migration_id") != manifest["migration_id"]
            or not isinstance(rows, list) or len(rows) != len(files)):
        return "INVALID", backup_status
    actual = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("target") not in expected:
            return "INVALID", backup_status
        target = row["target"]
        if target in actual or row.get("installed_sha256") != expected[target]["sha256"]:
            return "INVALID", backup_status
        prior = row.get("prior")
        if prior is None:
            if row.get("prior_sha256") is not None:
                return "INVALID", backup_status
            target_state = _inspect_target(root, expected[target])
            if target_state not in ("ABSENT_ALLOWED", "INSTALLED_EXACT"):
                return "INVALID", backup_status
        else:
            expected_name = hashlib.sha256(target.encode()).hexdigest()
            if prior != expected_name or not isinstance(row.get("prior_sha256"), str):
                return "INVALID", backup_status
            prior_path = backup / prior
            try:
                prior_info = prior_path.lstat()
                if (stat.S_ISLNK(prior_info.st_mode) or not stat.S_ISREG(prior_info.st_mode)
                        or _owner_group(prior_info) != ("root", "root")
                        or stat.S_IMODE(prior_info.st_mode) != 0o600
                        or sha(prior_path.read_bytes()) != row["prior_sha256"]):
                    return "INVALID", backup_status
                prior_data = prior_path.read_bytes()
                allowed = (set(expected[target].get("legacy_git_blobs", []))
                           | set(expected[target].get("legacy_git_blob_alternates", [])))
                if git_blob(prior_data) not in allowed:
                    return "INVALID", backup_status
                target_state = _inspect_target(root, expected[target])
                if target_state == "LEGACY_EXACT":
                    current_target = checked_path(root, target)
                    if sha(current_target.read_bytes()) != row["prior_sha256"]:
                        return "INVALID", backup_status
                elif target_state != "INSTALLED_EXACT":
                    return "INVALID", backup_status
            except (OSError, KeyError):
                return "INVALID", backup_status
        actual[target] = row
    if set(actual) != set(expected):
        return "INVALID", backup_status
    expected_entries = {"journal.json"} | {
        row["prior"] for row in actual.values() if row["prior"] is not None
    }
    try:
        actual_entries = {entry.name for entry in backup.iterdir()}
    except OSError:
        return "UNREADABLE", backup_status
    if actual_entries != expected_entries:
        return "UNEXPECTED_BACKUP_ENTRIES", backup_status
    return "VALID", backup_status


def inspect_migration(bundle: Path, manifest_path: Path, archive: Path, root: Path) -> dict:
    """Read-only, path-free summary for reconciling an interrupted migration."""
    manifest, files = load_manifest(bundle, manifest_path, root)
    verify_archive(manifest, archive)
    root_status = _inspect_root(root)
    journal_status, backup_status = _inspect_journal(root, manifest, files)
    targets = [{"key": f"T{index:02d}", "state": _inspect_target(root, item)}
               for index, item in enumerate(files, 1)]
    states = [row["state"] for row in targets]
    pre_states = {"ABSENT_ALLOWED", "LEGACY_EXACT"}
    if root_status != "SSM_USER_0700":
        overall = "ROOT_RECONCILE_REQUIRED"
        phase = "UNKNOWN_ROOT_METADATA"
    elif journal_status == "VALID" and backup_status == "ROOT_0700":
        if all(state == "INSTALLED_EXACT" for state in states):
            overall = "INSTALLED"
            phase = "APPLY_COMPLETE"
        elif all(state in pre_states for state in states):
            overall = "JOURNAL_PRESENT_NO_INSTALLED_FILES"
            phase = "NO_TARGET_WRITES_OR_ROLLBACK_RESTORED_ALL"
        else:
            overall = "PARTIAL_RECONCILE_REQUIRED"
            phase = "APPLY_OR_ROLLBACK_DIRECTION_UNKNOWN"
    elif journal_status == "ABSENT" and backup_status == "ABSENT":
        if all(state in pre_states for state in states):
            overall = "PRE_MIGRATION_OR_ROLLED_BACK"
            phase = "NO_JOURNAL_ALL_TARGETS_PRESTATE"
        elif all(state == "INSTALLED_EXACT" for state in states):
            overall = "INSTALLED_WITHOUT_JOURNAL"
            phase = "UNKNOWN_WITHOUT_JOURNAL"
        elif all(state in pre_states | {"INSTALLED_EXACT"} for state in states):
            overall = "PARTIAL_WITHOUT_JOURNAL"
            phase = "UNKNOWN_WITHOUT_JOURNAL"
        else:
            overall = "TARGET_DRIFT_WITHOUT_VALID_JOURNAL"
            phase = "UNKNOWN_WITHOUT_VALID_JOURNAL"
    else:
        overall = "JOURNAL_RECONCILE_REQUIRED"
        phase = "UNKNOWN_WITHOUT_VALID_JOURNAL"
    return {"state": overall, "phase": phase, "root": root_status,
            "journal": journal_status,
            "backup": backup_status, "targets": targets}


def rollback(bundle: Path, manifest_path: Path, archive: Path, root: Path) -> dict:
    manifest, files = load_manifest(bundle, manifest_path, root)
    verify_archive(manifest, archive)
    uid, gid = _identity()
    backup = root / BACKUP
    if backup.is_symlink() or not backup.is_dir():
        fail("MIGRATION_JOURNAL_MISSING")
    journal = json.loads((backup / "journal.json").read_text(encoding="utf-8"))
    if journal.get("migration_id") != manifest["migration_id"] or len(journal.get("files", [])) != len(files):
        fail("MIGRATION_JOURNAL_MISMATCH")
    by_target = {item["target"]: item for item in journal["files"]}
    installed = set()
    restore_data = {}
    for item in files:
        state = by_target.get(item["target"])
        target = checked_path(root, item["target"])
        if not state or state.get("installed_sha256") != item["sha256"]:
            fail("MIGRATION_INSTALLED_FILE_DRIFT")
        if target.is_file() and sha(target.read_bytes()) == item["sha256"]:
            installed.add(item["target"])
        elif state["prior"] is None:
            if target.exists():
                fail("MIGRATION_INSTALLED_FILE_DRIFT")
        else:
            prior = backup / state["prior"]
            if not target.is_file() or sha(target.read_bytes()) != state["prior_sha256"]:
                fail("MIGRATION_INSTALLED_FILE_DRIFT")
        if state["prior"] is not None:
            prior = backup / state["prior"]
            if (prior.is_symlink() or not prior.is_file()
                    or sha(prior.read_bytes()) != state["prior_sha256"]):
                fail("MIGRATION_INSTALLED_FILE_DRIFT")
            restore_data[item["target"]] = prior.read_bytes()
    for item in reversed(files):
        state = by_target[item["target"]]
        target = checked_path(root, item["target"])
        if item["target"] not in installed:
            continue
        if state["prior"] is None:
            target.unlink()
        else:
            data = restore_data[item["target"]]
            _atomic(target, data, int(item["legacy_mode"], 8), uid, gid)
    shutil.rmtree(backup)
    return {"state": "ROLLED_BACK", "migration_id": manifest["migration_id"], "files": len(files)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("apply", "rollback", "inspect"))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(EXPECTED_ROOT))
    args = parser.parse_args()
    try:
        if args.action == "inspect":
            result = inspect_migration(args.bundle, args.manifest, args.archive, args.root)
        elif args.action == "apply":
            result = apply(args.bundle, args.manifest, args.archive, args.root)
        else:
            result = rollback(args.bundle, args.manifest, args.archive, args.root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except ValueError as exc:
        code = str(exc)
        if code in SAFE_ERROR_CODES:
            print(f"ISOLATED_MIGRATION_REFUSED:{code}", file=sys.stderr)
        else:
            print("ISOLATED_MIGRATION_REFUSED", file=sys.stderr)
        return 2
    except Exception:
        print("ISOLATED_MIGRATION_REFUSED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
