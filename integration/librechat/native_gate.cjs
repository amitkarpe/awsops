'use strict';
// Private OS pipe only. The platform supplies authenticated server context.
// No credential handling, network listener, AWS client or executor exists here.
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');

const LOGICAL_TOOL = 'decide_s3_ssl_reject_only';
const WIRE_TOOL = 'decide_s3_ssl_reject_only_mcp_awsops';
const MAX_BYTES = 16384;
const TIMEOUT_MS = 4000;
const ID = /^[A-Za-z0-9_.:-]{1,128}$/;
const HEX32 = /^[a-f0-9]{32}$/;
const HEX64 = /^[a-f0-9]{64}$/;
function fail() { throw new Error('AWSOPS_NATIVE_CONTRACT_REJECTED'); }
function text(value, re = ID) { if (typeof value !== 'string' || !re.test(value)) fail(); return value; }
function keys(value, expected) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).sort().join(',') !== [...expected].sort().join(',')) fail();
}
function privateFile(file) {
  if (typeof file !== 'string' || !path.isAbsolute(file) || fs.realpathSync(file) !== file) fail();
  const st = fs.lstatSync(file);
  if (!st.isFile() || st.size > MAX_BYTES || (st.mode & 0o077) !== 0 ||
      (process.getuid && st.uid !== process.getuid())) fail();
}
function validateConfig(config) {
  keys(config, ['version', 'enabled', 'agent_id', 'python', 'source_root', 'database']);
  if (config.version !== 1 || config.enabled !== true) fail();
  text(config.agent_id);
  for (const value of [config.python, config.source_root, config.database]) {
    if (typeof value !== 'string' || !path.isAbsolute(value)) fail();
  }
  return Object.freeze({...config});
}
function configFromEnvironment() {
  const file = process.env.AWSOPS_NATIVE_CONFIG;
  privateFile(file);
  return validateConfig(JSON.parse(fs.readFileSync(file, 'utf8')));
}
function reserved(pendingAction) {
  const actions = pendingAction?.payload?.action_requests;
  return Array.isArray(actions) && actions.some(a => typeof a?.name === 'string' && a.name.startsWith(LOGICAL_TOOL));
}
function nativeEnvelope({user, job, streamId}, config) {
  text(streamId);
  if (!user || job?.metadata?.userId !== user.id || job.status !== 'requires_action' ||
      job.metadata.agent_id !== config.agent_id || job.metadata.endpoint !== 'agents') fail();
  text(user.id);
  if ((job.metadata.tenantId ?? null) !== (user.tenantId ?? null)) fail();
  const tenant = user.tenantId == null ? 'system:single-tenant' : 'tenant:' + text(user.tenantId);
  text(tenant);
  if (!Number.isSafeInteger(job.createdAt) || job.createdAt < 0) fail();
  const pending = job.metadata.pendingAction;
  if (pending?.payload?.type !== 'tool_approval' || !Number.isSafeInteger(pending.expiresAt) ||
      pending.expiresAt <= Date.now()) fail();
  text(pending.actionId);
  const actions = pending.payload.action_requests;
  if (!Array.isArray(actions) || actions.length !== 1 || actions[0]?.name !== WIRE_TOOL) fail();
  const action = actions[0];
  text(action.tool_call_id);
  // Exact object contract. Strings/nested input/extra fields fail closed.
  keys(action.arguments, ['control', 'batch_id', 'scope_hash']);
  const args = action.arguments;
  if (args.control !== 's3_ssl') fail();
  text(args.batch_id, HEX32); text(args.scope_hash, HEX64);
  return {batch_id: args.batch_id, scope_hash: args.scope_hash, binding: {
    principal_id: user.id, tenant_id: tenant, conversation_id: streamId,
    action_id: pending.actionId, generation_id: String(job.createdAt),
    tool_call_id: action.tool_call_id, tool: LOGICAL_TOOL,
  }};
}
function prepareNativeRequest({req, job, pendingAction, streamId}, config = configFromEnvironment()) {
  config = validateConfig(config);
  if (pendingAction !== job?.metadata?.pendingAction || req?.body?.conversationId !== streamId ||
      req.body.actionId !== pendingAction.actionId || req.body.generationCreatedAt !== job.createdAt ||
      req.body.agent_id !== config.agent_id || req.body.endpoint !== 'agents') fail();
  const base = nativeEnvelope({user: req.user, job, streamId}, config);
  const decisions = req.body.decisions;
  if (!Array.isArray(decisions) || decisions.length !== 1) fail();
  const choice = decisions[0];
  if (!choice || Object.keys(choice).some(key => !['tool_call_id', 'decision', 'reason'].includes(key)) ||
      choice.tool_call_id !== base.binding.tool_call_id || !['reject', 'approve'].includes(choice.decision)) fail();
  const message = {version: 1, operation: 'record', ...base, decision: choice.decision};
  // No reference to mutable req.body or job metadata survives asynchronous work.
  return Object.freeze({config, message: Object.freeze({...message, binding: Object.freeze({...base.binding})})});
}
function pipe(config, message) {
  const encoded = Buffer.from(JSON.stringify(message));
  if (encoded.length > MAX_BYTES) return Promise.reject(new Error('AWSOPS_PIPE_FAILED'));
  const entry = path.join(config.source_root, 'integration/librechat/receipt_entry.py');
  return new Promise((resolve, reject) => {
    let child; let timer; let settled = false; let output = []; let bytes = 0;
    const stop = () => {
      if (settled) return;
      settled = true; clearTimeout(timer);
      if (child && child.exitCode === null) child.kill('SIGKILL');
      reject(new Error('AWSOPS_PIPE_FAILED'));
    };
    try {
      child = spawn(config.python, ['-I', '-B', entry, '--database', config.database], {
        shell: false, stdio: ['pipe', 'pipe', 'pipe'], cwd: config.source_root,
        // Do not export platform auth or AWS credentials into the receipt process.
        env: {LANG: 'C.UTF-8'},
      });
      timer = setTimeout(stop, TIMEOUT_MS);
      child.on('error', stop); child.stdin.on('error', stop);
      child.stderr.on('data', stop); // No raw child diagnostics returned to the platform.
      child.stdout.on('data', data => { bytes += data.length; if (bytes > MAX_BYTES) stop(); else output.push(data); });
      child.on('close', code => {
        if (settled) return;
        if (code !== 0) return stop();
        try {
          const value = JSON.parse(Buffer.concat(output).toString('utf8'));
          if (value?.version !== 1 || value.ok !== true || value.dispatch_allowed !== false || value.operation !== message.operation) return stop();
          settled = true; clearTimeout(timer); resolve(value);
        } catch { stop(); }
      });
      child.stdin.end(encoded);
    } catch { stop(); }
  });
}
async function persistNativeDecision(envelope, transport = pipe) {
  const {config, message} = envelope;
  const result = await transport(config, message);
  const outcome = message.decision === 'reject' ? 'REJECTED' : 'APPROVE_BLOCKED';
  const reason = message.decision === 'reject' ? 'REJECTED' : 'LIVE_EXECUTION_NOT_AUTHORIZED';
  const receipt = result?.receipt;
  if (result?.version !== 1 || result.ok !== true || result.operation !== 'record' || result.dispatch_allowed !== false ||
      receipt?.version !== 1 || receipt.dispatch_allowed !== false || receipt.outcome !== outcome ||
      receipt.batch_id !== message.batch_id || receipt.scope_hash !== message.scope_hash ||
      !Number.isSafeInteger(receipt.recorded_at) || receipt.recorded_at < 0) fail();
  text(receipt.event_hash, HEX64);
  // Ignore arbitrary child resume data: independently construct ONLY reject.
  const expected = {[message.binding.tool_call_id]: {type: 'reject', reason}};
  if (JSON.stringify(result.resume_value) !== JSON.stringify(expected)) fail();
  return {resumeValue: expected, receipt};
}
async function registerPrepared({user, job, streamId, frozen}, config, transport = pipe) {
  // Call from the trusted pause producer with the actual provider-backed scope,
  // never from /resume request JSON or model arguments. Not installed by M3B.
  config = validateConfig(config);
  const base = nativeEnvelope({user, job, streamId}, config);
  if (frozen?.batch_id !== base.batch_id || frozen.scope_hash !== base.scope_hash || frozen.live_execution_authorized !== false) fail();
  const result = await transport(config, {version: 1, operation: 'register', binding: base.binding, frozen});
  if (result?.version !== 1 || result.ok !== true || result.operation !== 'register' ||
      result.dispatch_allowed !== false || result.batch_id !== base.batch_id || result.scope_hash !== base.scope_hash) fail();
  text(result.event_hash, HEX64);
  return result;
}

module.exports = {WIRE_TOOL, LOGICAL_TOOL, TIMEOUT_MS, MAX_BYTES, reserved,
  prepareNativeRequest, persistNativeDecision, registerPrepared, pipe, validateConfig, configFromEnvironment};
