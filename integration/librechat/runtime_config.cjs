'use strict';
// Narrow YAML update for the already isolated LibreChat application.
const fs = require('node:fs');
const path = require('node:path');
const {isDeepStrictEqual} = require('node:util');
const crypto = require('node:crypto');

const TOOL = 'approve_s3_canary_once_mcp_awsops';
const FIXTURE_ENDPOINT = 'awsops_canary_fixture';
const FIXTURE_MODEL = 'awsops-canary-fixed';
const FIXTURE_URL = 'http://127.0.0.1:4312/v1';
const BACKUP = '.awsops-issue90-runtime-config.original';
const NATIVE_SOURCE_BACKUP = '.awsops-issue90-native-source-revision.original';
const LEGACY_SOURCE_REVISION = 'd9545f7cd3aca485a137c5b8e8b8d55f02a004c8';
function fail(code) { throw Error(code); }
function privatePath(file) {
  if (!path.isAbsolute(file) || fs.realpathSync(file) !== file) fail('CONFIG_PATH_UNSAFE');
  const st = fs.lstatSync(file);
  if (!st.isFile() || (st.mode & 0o077) !== 0) fail('CONFIG_FILE_UNSAFE');
  return st;
}
function readPrivateBackup(file, uid, gid) {
  const pathStat = fs.lstatSync(file);
  if (!pathStat.isFile() || pathStat.isSymbolicLink() || pathStat.uid !== uid ||
      pathStat.gid !== gid || (pathStat.mode & 0o777) !== 0o600) fail('CONFIG_BACKUP_DRIFT');
  const fd = fs.openSync(file, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
  try {
    const opened = fs.fstatSync(fd);
    if (!opened.isFile() || opened.dev !== pathStat.dev || opened.ino !== pathStat.ino ||
        opened.uid !== uid || opened.gid !== gid || (opened.mode & 0o777) !== 0o600)
      fail('CONFIG_BACKUP_DRIFT');
    const data = fs.readFileSync(fd);
    return {data, sha256:crypto.createHash('sha256').update(data).digest('hex')};
  } finally { fs.closeSync(fd); }
}
function validateNativeConfig(value, root) {
  const expectedKeys = ['agent_id','application_binding','application_database','database','enabled',
    'python','source_revision','source_root','source_version','version'];
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).sort().join(',') !== expectedKeys.sort().join(',') ||
      value.version !== 1 || value.enabled !== true || typeof value.agent_id !== 'string' ||
      !/^[A-Za-z0-9_.:-]{1,128}$/.test(value.agent_id) || value.python !== '/usr/bin/python3' ||
      value.source_root !== path.join(root,'awsops') ||
      value.database !== path.join(root,'state/native.sqlite') ||
      value.application_database !== path.join(root,'state/canary.sqlite') ||
      typeof value.application_binding !== 'string' || !path.isAbsolute(value.application_binding) ||
      !value.application_binding.startsWith(path.join(root,'state') + path.sep) ||
      typeof value.source_revision !== 'string' || !/^[a-f0-9]{40}$/.test(value.source_revision) ||
      typeof value.source_version !== 'string' || !/^v[0-9]+\.[0-9]+\.[0-9]+-mock$/.test(value.source_version))
    fail('NATIVE_CONFIG_SCHEMA_DRIFT');
  return value;
}
function nativeTarget(root) {
  const file = path.join(root,'state/native.json');
  const st = privatePath(file);
  if (st.uid !== process.getuid() || (st.mode & 0o777) !== 0o600) fail('NATIVE_CONFIG_METADATA_DRIFT');
  return {file, st};
}
function readNativeBytes(file) {
  const fd = fs.openSync(file,fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
  try { return fs.readFileSync(fd); } finally { fs.closeSync(fd); }
}
function nativeSnapshotMatches(file, priorStat, priorBytes) {
  const currentStat = fs.lstatSync(file);
  return currentStat.isFile() && !currentStat.isSymbolicLink() &&
    currentStat.dev === priorStat.dev && currentStat.ino === priorStat.ino &&
    currentStat.uid === priorStat.uid && currentStat.gid === priorStat.gid &&
    (currentStat.mode & 0o777) === (priorStat.mode & 0o777) && readNativeBytes(file).equals(priorBytes);
}
function migrateNativeSourceRevision(root) {
  if (!path.isAbsolute(root) || fs.realpathSync(root) !== root) fail('ISOLATED_ROOT_REQUIRED');
  const marker = path.join(root,'awsops/SOURCE_REVISION');
  const markerStat = fs.lstatSync(marker);
  if (!markerStat.isFile() || markerStat.isSymbolicLink()) fail('SOURCE_REVISION_FILE_UNSAFE');
  const revision = fs.readFileSync(marker,'ascii').trim();
  if (!/^[a-f0-9]{40}$/.test(revision) || revision === LEGACY_SOURCE_REVISION)
    fail('SOURCE_REVISION_MISMATCH');
  const {file,st} = nativeTarget(root);
  const backup = path.join(root,'state',NATIVE_SOURCE_BACKUP);
  const original = readNativeBytes(file);
  const current = validateNativeConfig(JSON.parse(original.toString('utf8')),root);
  if (current.source_revision === revision) {
    let backupStat;
    try { backupStat = fs.lstatSync(backup); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (!backupStat) return {state:'ALREADY_CURRENT'};
  } else if (current.source_revision !== LEGACY_SOURCE_REVISION) {
    fail('NATIVE_SOURCE_REVISION_UNEXPECTED');
  }
  const transformed = {...current,source_revision:revision};
  const updated = Buffer.from(JSON.stringify(transformed,null,2) + '\n');
  let backupStat;
  try { backupStat = fs.lstatSync(backup); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (backupStat) {
    const {data:saved} = readPrivateBackup(backup,st.uid,st.gid);
    const prior = validateNativeConfig(JSON.parse(saved.toString('utf8')),root);
    if (prior.source_revision !== LEGACY_SOURCE_REVISION) fail('NATIVE_CONFIG_BACKUP_DRIFT');
    const expected = Buffer.from(JSON.stringify({...prior,source_revision:revision},null,2) + '\n');
    if (!saved.equals(original) && !expected.equals(original)) fail('NATIVE_CONFIG_BACKUP_DRIFT');
    if (!expected.equals(original)) {
      if (!nativeSnapshotMatches(file,st,original)) fail('NATIVE_CONFIG_READBACK_DRIFT');
      atomic(file,expected,st,'.awsops-source-staged');
    }
  } else {
    if (current.source_revision !== LEGACY_SOURCE_REVISION) fail('NATIVE_CONFIG_BACKUP_REQUIRED');
    const fd = fs.openSync(backup,'wx',0o600);
    try {
      fs.fchownSync(fd,st.uid,st.gid); fs.fchmodSync(fd,0o600);
      fs.writeFileSync(fd,original); fs.fsyncSync(fd);
    } finally { fs.closeSync(fd); }
    const dir = fs.openSync(path.dirname(backup),fs.constants.O_RDONLY);
    try { fs.fsyncSync(dir); } finally { fs.closeSync(dir); }
    const {data:saved,sha256} = readPrivateBackup(backup,st.uid,st.gid);
    if (sha256 !== crypto.createHash('sha256').update(original).digest('hex') ||
        !saved.equals(original) || !nativeSnapshotMatches(file,st,original)) fail('NATIVE_CONFIG_BACKUP_DRIFT');
    atomic(file,updated,st,'.awsops-source-staged');
  }
  const verifyStat = fs.lstatSync(file);
  const verifiedBytes = readNativeBytes(file);
  const verified = validateNativeConfig(JSON.parse(verifiedBytes.toString('utf8')),root);
  if (!verifiedBytes.equals(updated) || verified.source_revision !== revision || verifyStat.uid !== st.uid || verifyStat.gid !== st.gid ||
      (verifyStat.mode & 0o777) !== (st.mode & 0o777)) fail('NATIVE_CONFIG_READBACK_DRIFT');
  return {state:'UPDATED'};
}
function rollbackNativeSourceRevision(root) {
  if (!path.isAbsolute(root) || fs.realpathSync(root) !== root) fail('ISOLATED_ROOT_REQUIRED');
  const {file,st} = nativeTarget(root);
  const backup = path.join(root,'state',NATIVE_SOURCE_BACKUP);
  let backupStat;
  try { backupStat = fs.lstatSync(backup); } catch (error) { if (error.code === 'ENOENT') return {state:'NO_CHANGE'}; throw error; }
  const {data:saved} = readPrivateBackup(backup,st.uid,st.gid);
  const prior = validateNativeConfig(JSON.parse(saved.toString('utf8')),root);
  if (prior.source_revision !== LEGACY_SOURCE_REVISION) fail('NATIVE_CONFIG_BACKUP_DRIFT');
  const marker = path.join(root,'awsops/SOURCE_REVISION');
  const revision = fs.readFileSync(marker,'ascii').trim();
  const expected = Buffer.from(JSON.stringify({...prior,source_revision:revision},null,2) + '\n');
  if (!readNativeBytes(file).equals(expected)) fail('NATIVE_CONFIG_ROLLBACK_DRIFT');
  atomic(file,saved,st,'.awsops-source-rollback');
  if (!readNativeBytes(file).equals(saved)) fail('NATIVE_CONFIG_ROLLBACK_DRIFT');
  fs.unlinkSync(backup);
  const dir = fs.openSync(path.dirname(backup),fs.constants.O_RDONLY);
  try { fs.fsyncSync(dir); } finally { fs.closeSync(dir); }
  return {state:'ROLLED_BACK'};
}
function ownObject(value, name) {
  if (value == null) return {};
  if (typeof value !== 'object' || Array.isArray(value)) fail('CONFIG_' + name + '_UNSAFE');
  return value;
}
function desiredMcp(root) {
  return {type:'stdio', command:'/usr/bin/node',
    args:[path.join(root,'awsops/integration/canary/mcp_guard.cjs')],
    timeout:15000, initTimeout:10000, chatMenu:false, serverInstructions:true};
}
function atomic(file, data, priorStat, suffix) {
  const temp = file + suffix;
  const fd = fs.openSync(temp,'wx',priorStat.mode & 0o777);
  try {
    fs.fchownSync(fd,priorStat.uid,priorStat.gid);
    fs.fchmodSync(fd,priorStat.mode & 0o777);
    fs.writeFileSync(fd,data);
    fs.fsyncSync(fd);
  } catch (error) {
    fs.closeSync(fd);
    try { fs.unlinkSync(temp); } catch {}
    throw error;
  }
  fs.closeSync(fd);
  fs.renameSync(temp,file);
  const dir = fs.openSync(path.dirname(file),fs.constants.O_RDONLY);
  try { fs.fsyncSync(dir); } finally { fs.closeSync(dir); }
}
function transform(raw, yaml, appRoot, sourceRoot) {
  const config = yaml.load(raw.toString('utf8')) || {};
  ownObject(config.endpoints, 'ENDPOINTS'); ownObject(config.mcpServers, 'MCP');
  config.endpoints ??= {}; config.mcpServers ??= {};
  const fixture = {name:FIXTURE_ENDPOINT,apiKey:'fixture-only',baseURL:FIXTURE_URL,
    models:{default:[FIXTURE_MODEL],fetch:false},titleConvo:false};
  const previousFixture = {...fixture,baseURL:'http://localhost:4312/v1'};
  const custom = config.endpoints.custom ?? [];
  if (!isDeepStrictEqual(custom,[fixture]) && !isDeepStrictEqual(custom,[previousFixture]))
    fail('FIXTURE_ENDPOINT_DRIFT');
  config.endpoints.custom = [fixture];
  const addresses = config.endpoints.allowedAddresses ?? [];
  if (!isDeepStrictEqual(addresses,[]) && !isDeepStrictEqual(addresses,['localhost:4312']) &&
      !isDeepStrictEqual(addresses,['127.0.0.1:4312'])) fail('FIXTURE_ADDRESS_DRIFT');
  config.endpoints.allowedAddresses = ['127.0.0.1:4312'];
  const mcp = desiredMcp(appRoot);
  const existing = config.mcpServers.awsops;
  const legacyMcp = {...mcp, args:[mcp.args[0],appRoot]};
  if (existing && !isDeepStrictEqual(existing,mcp) && !isDeepStrictEqual(existing,legacyMcp))
    fail('MCP_AWSOPS_DRIFT');
  config.mcpServers.awsops = mcp;

  const agents = ownObject(config.endpoints.agents, 'AGENTS');
  config.endpoints.agents = agents;
  const approval = ownObject(agents.toolApproval, 'TOOL_APPROVAL');
  agents.toolApproval = approval;
  if (approval.enabled === false || (approval.mode && approval.mode !== 'default')) fail('APPROVAL_MODE_DRIFT');
  approval.enabled = true; approval.mode = 'default';
  for (const field of ['allow','ask','deny']) {
    const value = approval[field] ?? [];
    if (!Array.isArray(value) || value.some(x => typeof x !== 'string')) fail('APPROVAL_LIST_DRIFT');
    if (field !== 'ask' && value.includes(TOOL)) fail('CANARY_APPROVAL_POLICY_DRIFT');
    approval[field] = field === 'ask' ? [...new Set([...value, TOOL])].sort() : value;
  }
  const hookPath = path.join(sourceRoot,'app/api/server/controllers/agents/awsops-pause-gate.cjs');
  const matcher = '^' + TOOL + '$';
  const hooks = approval.hooks ?? [];
  if (!Array.isArray(hooks)) fail('APPROVAL_HOOKS_DRIFT');
  const exact = hooks.filter(h => h?.matcher === matcher);
  if (exact.length > 1 || (exact.length === 1 && exact[0].module !== hookPath)) fail('APPROVAL_HOOK_DRIFT');
  if (!exact.length) hooks.push({matcher, module:hookPath});
  const legacyMatcher = '^decide_s3_ssl_reject_only_mcp_awsops$';
  for (const hook of hooks.filter(h => h?.matcher === legacyMatcher)) {
    if (hook.module !== hookPath && !(typeof hook.module === 'string' &&
        hook.module.endsWith('/integration/canary/approval_hook.cjs'))) fail('LEGACY_APPROVAL_HOOK_DRIFT');
    hook.module = hookPath;
  }
  approval.hooks = hooks;
  const rendered = yaml.dump(config, {lineWidth:-1, noRefs:true});
  if (!isDeepStrictEqual(yaml.load(rendered), config)) fail('CONFIG_ROUNDTRIP_FAILED');
  return Buffer.from(rendered);
}
function configure(appRoot, sourceRoot=path.resolve(__dirname,'../..')) {
  if (!path.isAbsolute(appRoot) || fs.realpathSync(appRoot) !== appRoot ||
      !path.isAbsolute(sourceRoot) || fs.realpathSync(sourceRoot) !== sourceRoot) fail('ISOLATED_ROOT_REQUIRED');
  const file = path.join(appRoot,'app/librechat.yaml');
  const st = privatePath(file);
  const backup = path.join(appRoot,BACKUP);
  const yaml = require(path.join(appRoot,'app/node_modules/js-yaml'));
  let backupStat;
  try { backupStat = fs.lstatSync(backup); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (backupStat) {
    const {data:original} = readPrivateBackup(backup,st.uid,st.gid);
    const expected = transform(original,yaml,appRoot,sourceRoot);
    if (!fs.readFileSync(file).equals(expected)) fail('CONFIG_BACKUP_DRIFT');
    atomic(file,expected,st,'.awsops-staged');
    return {state:'CONFIGURED', tool:TOOL, backup:BACKUP};
  } else {
    const original = fs.readFileSync(file);
    const updated = transform(original,yaml,appRoot,sourceRoot);
    const fd = fs.openSync(backup,'wx',0o600);
    try {
      fs.fchownSync(fd,st.uid,st.gid);
      fs.fchmodSync(fd,0o600);
      fs.writeFileSync(fd,original);
      fs.fsyncSync(fd);
    } finally { fs.closeSync(fd); }
    const backupDirectory = fs.openSync(path.dirname(backup),fs.constants.O_RDONLY);
    try { fs.fsyncSync(backupDirectory); } finally { fs.closeSync(backupDirectory); }
    const {data:verified,sha256} = readPrivateBackup(backup,st.uid,st.gid);
    const expectedHash = crypto.createHash('sha256').update(original).digest('hex');
    if (sha256 !== expectedHash || !verified.equals(original) ||
        !fs.readFileSync(file).equals(original)) fail('CONFIG_BACKUP_DRIFT');
    atomic(file,updated,st,'.awsops-staged');
    return {state:'CONFIGURED', tool:TOOL, backup:BACKUP};
  }
}
function rollback(appRoot) {
  if (!path.isAbsolute(appRoot) || fs.realpathSync(appRoot) !== appRoot) fail('ISOLATED_ROOT_REQUIRED');
  const file = path.join(appRoot,'app/librechat.yaml');
  const st = privatePath(file);
  const backup = path.join(appRoot,BACKUP);
  if (!fs.existsSync(backup)) return {state:'NO_CHANGE'};
  const yaml = require(path.join(appRoot,'app/node_modules/js-yaml'));
  const sourceRoot = path.join(appRoot,'awsops');
  const expected = transform(fs.readFileSync(backup),yaml,appRoot,appRoot);
  if (!fs.readFileSync(file).equals(expected)) fail('CONFIG_ROLLBACK_DRIFT');
  atomic(file,fs.readFileSync(backup),st,'.awsops-rollback');
  fs.unlinkSync(backup);
  return {state:'ROLLED_BACK'};
}
if (require.main === module) {
  try {
    const [action,root,...extra] = process.argv.slice(2);
    if (!['apply','rollback','migrate-source-revision','rollback-source-revision'].includes(action) || extra.length || !root) fail('INVALID_ARGS');
    const result = action === 'apply' ? configure(root,root) : action === 'rollback' ? rollback(root) :
      action === 'migrate-source-revision' ? migrateNativeSourceRevision(root) : rollbackNativeSourceRevision(root);
    process.stdout.write(JSON.stringify(result) + '\n');
  } catch {
    process.stderr.write('ISOLATED_RUNTIME_CONFIG_REFUSED\n');
    process.exitCode = 2;
  }
}
module.exports={configure,rollback,transform,desiredMcp,atomic,readPrivateBackup,migrateNativeSourceRevision,
  rollbackNativeSourceRevision,validateNativeConfig,TOOL,FIXTURE_ENDPOINT,FIXTURE_MODEL,FIXTURE_URL,BACKUP,NATIVE_SOURCE_BACKUP};
