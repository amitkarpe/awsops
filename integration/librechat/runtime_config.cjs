'use strict';
// Narrow YAML update for the already isolated LibreChat application.
const fs = require('node:fs');
const path = require('node:path');
const {isDeepStrictEqual} = require('node:util');

const TOOL = 'approve_s3_canary_once_mcp_awsops';
const BACKUP = '.awsops-issue90-runtime-config.original';
function fail(code) { throw Error(code); }
function privatePath(file) {
  if (!path.isAbsolute(file) || fs.realpathSync(file) !== file) fail('CONFIG_PATH_UNSAFE');
  const st = fs.lstatSync(file);
  if (!st.isFile() || (st.mode & 0o077) !== 0) fail('CONFIG_FILE_UNSAFE');
  return st;
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
    if (backupStat.isSymbolicLink() || !backupStat.isFile()) fail('CONFIG_BACKUP_DRIFT');
    const original = fs.readFileSync(backup);
    const expected = transform(original,yaml,appRoot,sourceRoot);
    if (!fs.readFileSync(file).equals(expected)) fail('CONFIG_BACKUP_DRIFT');
    atomic(file,expected,st,'.awsops-staged');
    return {state:'CONFIGURED', tool:TOOL, backup:BACKUP};
  } else {
    const original = fs.readFileSync(file);
    const updated = transform(original,yaml,appRoot,sourceRoot);
    const fd = fs.openSync(backup,'wx',0o600);
    try { fs.writeFileSync(fd,original); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
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
    if (!['apply','rollback'].includes(action) || extra.length || !root) fail('INVALID_ARGS');
    process.stdout.write(JSON.stringify(action === 'apply' ? configure(root,root) : rollback(root)) + '\n');
  } catch {
    process.stderr.write('ISOLATED_RUNTIME_CONFIG_REFUSED\n');
    process.exitCode = 2;
  }
}
module.exports={configure,rollback,transform,desiredMcp,atomic,TOOL,BACKUP};
