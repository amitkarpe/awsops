'use strict';
// Shared, narrow filesystem contract for the native DecisionStore.
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {createHash} = require('node:crypto');

const SYSTEM_PYTHON = '/usr/bin/python3';
const DATABASE_NAMES = new Set(['native.sqlite', 'receipt.sqlite3']);
const VERIFY_SOURCE = `import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[2]) / 'src'))
from awsops.approval.decisions import DecisionStore
DecisionStore.validate_existing(Path(sys.argv[1]))
print('VALID')
`;

function fail(code) { throw new Error(code); }
function canonicalSystemPython() {
  let resolved, st;
  try {
    resolved = fs.realpathSync(SYSTEM_PYTHON);
    st = fs.statSync(resolved);
  } catch { fail('NATIVE_SYSTEM_PYTHON_UNAVAILABLE'); }
  if (!st.isFile() || st.uid !== 0 || (st.mode & 0o022) !== 0 || (st.mode & 0o111) === 0)
    fail('NATIVE_SYSTEM_PYTHON_UNSAFE');
  return resolved;
}
function validateLegacyPython(configured) {
  const system = canonicalSystemPython();
  if (configured === SYSTEM_PYTHON) return SYSTEM_PYTHON;
  if (typeof configured !== 'string' || !path.isAbsolute(configured)) fail('NATIVE_LEGACY_PYTHON_UNSUPPORTED');
  try {
    if (!fs.lstatSync(configured).isSymbolicLink() || fs.realpathSync(configured) !== system)
      fail('NATIVE_LEGACY_PYTHON_UNSUPPORTED');
  } catch { fail('NATIVE_LEGACY_PYTHON_UNSUPPORTED'); }
  // The configured alias is inspected only. Child processes always receive the
  // reviewed system path above, never the legacy path.
  return SYSTEM_PYTHON;
}
function assertSystemPython() {
  canonicalSystemPython();
  return SYSTEM_PYTHON;
}
function databaseLocation(database, root) {
  if (typeof database !== 'string' || !path.isAbsolute(database)) fail('NATIVE_DATABASE_PATH_UNSUPPORTED');
  const leaf = path.basename(database);
  if (!DATABASE_NAMES.has(leaf)) fail('NATIVE_DATABASE_PATH_UNSUPPORTED');
  const state = root ? path.join(root, 'state') : path.dirname(database);
  if (path.dirname(database) !== state || path.basename(state) !== 'state') fail('NATIVE_DATABASE_PATH_UNSUPPORTED');
  return {state, database};
}
function validateDatabaseMetadata(database, {root, uid, gid} = {}) {
  const target = databaseLocation(database, root);
  let stateStat, databaseStat;
  try {
    stateStat = fs.lstatSync(target.state);
    if (!stateStat.isDirectory() || stateStat.isSymbolicLink() || fs.realpathSync(target.state) !== target.state ||
        (uid !== undefined && stateStat.uid !== uid) || (gid !== undefined && stateStat.gid !== gid) ||
        (stateStat.mode & 0o777) !== 0o700) fail('NATIVE_DATABASE_STATE_UNSAFE');
    databaseStat = fs.lstatSync(target.database);
    if (!databaseStat.isFile() || databaseStat.isSymbolicLink() ||
        fs.realpathSync(target.database) !== target.database ||
        (uid !== undefined && databaseStat.uid !== uid) || (gid !== undefined && databaseStat.gid !== gid) ||
        (databaseStat.mode & 0o777) !== 0o600) fail('NATIVE_DATABASE_FILE_UNSAFE');
    for (const suffix of ['-journal', '-wal', '-shm']) {
      try { fs.lstatSync(target.database + suffix); fail('NATIVE_DATABASE_SIDECAR_PRESENT'); }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
    }
  } catch (error) {
    if (error?.message?.startsWith('NATIVE_')) throw error;
    fail('NATIVE_DATABASE_UNAVAILABLE');
  }
  return {state:target.state, database:target.database, stateStat, databaseStat};
}
function hashFile(file, expected) {
  const fd = fs.openSync(file, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
  try {
    const opened = fs.fstatSync(fd);
    if (!opened.isFile() || (expected && !sameFileSnapshot(expected,opened)))
      fail('NATIVE_DATABASE_FILE_UNSAFE');
    return cryptoHashFd(fd);
  } finally { fs.closeSync(fd); }
}
function cryptoHashFd(fd) {
  const hash = createHash('sha256');
  const buffer = Buffer.allocUnsafe(64 * 1024);
  let position = 0;
  for (;;) {
    const count = fs.readSync(fd, buffer, 0, buffer.length, position);
    if (count === 0) break;
    hash.update(buffer.subarray(0, count)); position += count;
  }
  return hash.digest('hex');
}
function sameFileSnapshot(before, after) {
  return before.dev === after.dev && before.ino === after.ino && before.size === after.size &&
    before.uid === after.uid && before.gid === after.gid && before.mode === after.mode &&
    before.mtimeMs === after.mtimeMs;
}
function validateDecisionDatabase(database, {root, uid, gid} = {}) {
  const before = validateDatabaseMetadata(database, {root, uid, gid});
  const digest = hashFile(database,before.databaseStat);
  const python = assertSystemPython();
  const sourceRoot = path.resolve(__dirname, '../..');
  try {
    const result = execFileSync(python, ['-I', '-B', '-c', VERIFY_SOURCE, database, sourceRoot], {
      cwd: sourceRoot, env: {LANG:'C.UTF-8', PATH:'/usr/bin:/bin', PYTHONNOUSERSITE:'1'},
      encoding:'utf8', timeout:10000, maxBuffer:1024,
    });
    if (result !== 'VALID\n') fail('NATIVE_DATABASE_SCHEMA_UNSUPPORTED');
  } catch { fail('NATIVE_DATABASE_SCHEMA_UNSUPPORTED'); }
  const after = validateDatabaseMetadata(database, {root, uid, gid});
  if (!sameFileSnapshot(before.databaseStat, after.databaseStat) || hashFile(database,after.databaseStat) !== digest)
    fail('NATIVE_DATABASE_READONLY_VERIFY_DRIFT');
  return {database, sha256:digest};
}

module.exports = {SYSTEM_PYTHON, DATABASE_NAMES, canonicalSystemPython, validateLegacyPython,
  assertSystemPython, validateDatabaseMetadata, validateDecisionDatabase};
