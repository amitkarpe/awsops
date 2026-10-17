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
    parser.add_argument("action", choices=("apply", "rollback"))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(EXPECTED_ROOT))
    args = parser.parse_args()
    try:
        result = apply(args.bundle, args.manifest, args.archive, args.root) if args.action == "apply" else rollback(
            args.bundle, args.manifest, args.archive, args.root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        print("ISOLATED_MIGRATION_REFUSED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
