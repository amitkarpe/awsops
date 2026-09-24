'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const gate = require('../integration/librechat/native_gate.cjs');
const patch = require('../integration/librechat/rehearse_patch.cjs');
const root = path.resolve(__dirname, '..');
const python = process.env.AWSOPS_TEST_PYTHON || 'python3';
const fixture = path.join(root, 'artifacts/native-upstream/resume.js');
const hasUpstream = fs.existsSync(fixture);
if (process.env.AWSOPS_REQUIRE_NATIVE_FIXTURE === '1' && !hasUpstream) throw Error('Pinned upstream fixture is required');

function setup(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'awsops-native-'));
  t.after(() => fs.rmSync(dir, {recursive: true, force: true}));
  const database = path.join(dir, 'receipt.sqlite3');
  const frozen = JSON.parse(execFileSync(python, ['-I', '-B', path.join(__dirname, 'native_seed.py'), database]));
  const config = {version: 1, enabled: true, agent_id: 'awsops-canary', python: fs.realpathSync(python), source_root: root, database};
  const user = {id: 'native-user', tenantId: 'tenant-1'};
  const streamId = 'conversation-1';
  const job = {
    status: 'requires_action', createdAt: Date.now(), abortController: new AbortController(),
    metadata: {userId: user.id, tenantId: user.tenantId, agent_id: config.agent_id, endpoint: 'agents',
      checkpointNamespace: 'isolated-checkpoint', responseMessageId: 'response-1',
      userMessage: {messageId: 'message-1', parentMessageId: 'parent-1'},
      pendingAction: {actionId: 'action-1', expiresAt: Date.now()+120000, payload: {type: 'tool_approval',
        action_requests: [{name: gate.WIRE_TOOL, tool_call_id: 'call-1', arguments: {
          control: 's3_ssl', batch_id: frozen.batch_id, scope_hash: frozen.scope_hash}}],
        review_configs: [{tool_call_id: 'call-1', allowed_decisions: ['reject', 'approve']}],
      }},
    },
  };
  const req = {user, body: {conversationId: streamId, actionId: 'action-1', generationCreatedAt: job.createdAt,
    agent_id: config.agent_id, endpoint: 'agents', decisions: [{tool_call_id: 'call-1', decision: 'reject'}]}, config: {}};
  return {dir, database, frozen, config, user, job, req, streamId,
    context: () => ({req, job, pendingAction: job.metadata.pendingAction, streamId})};
}
async function register(f) { return gate.registerPrepared(f, f.config); }
async function record(f) { return gate.persistNativeDecision(gate.prepareNativeRequest(f.context(), f.config)); }

for (const choice of ['reject', 'approve']) test('real private process commits ' + choice + ' before returning only reject', async t => {
  const f = setup(t); await register(f); f.req.body.decisions[0].decision = choice;
  const result = await record(f);
  assert.equal(result.resumeValue['call-1'].type, 'reject');
  assert.equal(result.receipt.outcome, choice === 'reject' ? 'REJECTED' : 'APPROVE_BLOCKED');
  const envelope = gate.prepareNativeRequest(f.context(), f.config);
  const audit = await gate.pipe(f.config, {version: 1, operation: 'inspect', binding: envelope.message.binding, batch_id: f.frozen.batch_id});
  assert.equal(audit.events.length, 2); assert.equal(audit.events[1].event_hash, result.receipt.event_hash);
  assert.equal(audit.resume_value, undefined);
  await assert.rejects(record(f));
});
test('registration requires exact server-owned scope and cannot silently rebind', async t => {
  const f = setup(t);
  await assert.rejects(gate.registerPrepared({...f, frozen: {...f.frozen, scope_hash: 'd'.repeat(64)}}, f.config));
  await register(f); await assert.rejects(register(f));
});
test('missing registration never creates a continuation', async t => { const f = setup(t); await assert.rejects(record(f)); });

test('request snapshot rejects bad ownership, tenant, generation, scope and mixed actions', async t => {
  const mutations = [
    f => {f.req.user = {id: 'other-user', tenantId: 'tenant-1'};},
    f => {f.req.user = {...f.user, tenantId: 'other-tenant'};},
    f => {delete f.req.body.generationCreatedAt;},
    f => {f.req.body.generationCreatedAt++;},
    f => {f.req.body.actionId = 'other-action';},
    f => {f.req.body.agent_id = 'other-agent';},
    f => {f.job.metadata.pendingAction.expiresAt = 1;},
    f => {f.req.body.decisions.push({...f.req.body.decisions[0]});},
    f => {f.req.body.decisions[0].decision = 'edit';},
    f => {f.req.body.decisions[0].editedArguments = {};},
    f => {f.req.body.decisions[0].tool_call_id = '__proto__';},
    f => {f.job.metadata.pendingAction.payload.action_requests.push({name: 'legacy-execute'});},
    f => {f.job.metadata.pendingAction.payload.action_requests[0].name = gate.LOGICAL_TOOL+'_other';},
    f => {f.job.metadata.pendingAction.payload.action_requests[0].arguments = JSON.stringify(f.job.metadata.pendingAction.payload.action_requests[0].arguments);},
    f => {f.job.metadata.pendingAction.payload.action_requests[0].arguments.scope_hash = 'bad';},
    f => {f.job.metadata.pendingAction.payload.action_requests[0].arguments.operation = 'execute';},
  ];
  for (const change of mutations) { const f = setup(t); change(f); assert.throws(() => gate.prepareNativeRequest(f.context(), f.config)); }
});
test('default-off config never routes the reserved tool to a legacy path', t => {
  const f = setup(t); assert.throws(() => gate.prepareNativeRequest(f.context(), {...f.config, enabled: false}));
  const before = process.env.AWSOPS_NATIVE_CONFIG; delete process.env.AWSOPS_NATIVE_CONFIG;
  try { assert.throws(() => gate.prepareNativeRequest(f.context())); } finally {
    if (before !== undefined) process.env.AWSOPS_NATIVE_CONFIG = before;
  }
});
test('private config is not a secret and refuses group-readable files', t => {
  const f = setup(t); const configPath = path.join(f.dir, 'native.json');
  fs.writeFileSync(configPath, JSON.stringify(f.config), {mode: 0o600});
  const before = process.env.AWSOPS_NATIVE_CONFIG; process.env.AWSOPS_NATIVE_CONFIG = configPath;
  try { assert.equal(gate.configFromEnvironment().enabled, true); fs.chmodSync(configPath, 0o644); assert.throws(gate.configFromEnvironment); }
  finally { if (before === undefined) delete process.env.AWSOPS_NATIVE_CONFIG; else process.env.AWSOPS_NATIVE_CONFIG = before; }
});
test('validated snapshot does not retain mutable request context', t => {
  const f = setup(t); const env = gate.prepareNativeRequest(f.context(), f.config);
  f.req.body.decisions[0].decision = 'approve'; f.req.user.id = 'changed';
  assert.equal(env.message.decision, 'reject'); assert.equal(env.message.binding.principal_id, 'native-user');
});
test('malicious receipt cannot return an approve resolution', async t => {
  const f = setup(t); await register(f); const envelope = gate.prepareNativeRequest(f.context(), f.config);
  const valid = await gate.pipe(f.config, envelope.message);
  for (const change of [r => {r.dispatch_allowed = true;}, r => {r.receipt.scope_hash = 'd'.repeat(64);},
    r => {r.receipt.outcome = 'APPROVED';}, r => {r.resume_value['call-1'].type = 'approve';}]) {
    const bad = JSON.parse(JSON.stringify(valid)); change(bad);
    await assert.rejects(gate.persistNativeDecision(envelope, async () => bad));
  }
});
test('pipe does not retry a failed process or leak its diagnostics', async t => {
  const f = setup(t); const fake = path.join(f.dir, 'fake-python');
  fs.writeFileSync(fake, '#!/bin/sh\necho do-not-leak-native-state >&2\nexit 2\n', {mode: 0o700});
  await assert.rejects(gate.pipe({...f.config, python: fake}, {version: 1, operation: 'inspect'}), {message: 'AWSOPS_PIPE_FAILED'});
});
test('pipe kills only its own timed-out child and denies continuation', {timeout: 7000}, async t => {
  const f = setup(t); const fake = path.join(f.dir, 'slow-python');
  fs.writeFileSync(fake, '#!/bin/sh\nexec sleep 10\n', {mode: 0o700});
  const before = Date.now();
  await assert.rejects(gate.pipe({...f.config, python: fake}, {version: 1, operation: 'inspect'}));
  assert.ok(Date.now() - before >= gate.TIMEOUT_MS - 100);
});

function harness(f, options = {}) {
  let current = {...f.job, metadata: f.job.metadata};
  const calls = {claim: 0, receipt: 0, initialize: 0, resume: 0, decrement: 0, terminal: 0, checkpoint: 0, finished: 0, errors: []};
  let saved;
  const manager = {
    getJob: async () => current ? {...current, metadata: current.metadata} : null,
    getJobStore: () => ({getJob: async () => current}),
    getResumeState: async () => ({aggregatedContent: [], runSteps: []}),
    setContentParts: () => {}, rearmQueuedPreempts: async () => 0,
    approvals: {resolve: async (_id, _action, _metadata, createdAt) => {
      calls.claim++; if (options.claimFails) throw Error('store unavailable');
      if (options.loseClaim || current.status !== 'requires_action' || current.createdAt !== createdAt) return false;
      current = {...current, status: 'running'}; return true;
    }},
    completeJob: async (_id, _error, createdAt) => {
      calls.terminal++; calls.terminalGeneration = createdAt;
      if (options.terminalFails) throw Error('private-store-error');
      if (options.replaceJob) current = {...current, createdAt: current.createdAt + 1};
      if (current.createdAt !== createdAt) return false;
      current = {...current, status: 'error'}; return true;
    },
    claimTerminalJob: async (_id, _kind, _error, createdAt) => current.createdAt === createdAt ? {drainedSteers: []} : null,
    publishTerminalClaim: async () => {}, finishTerminalJob: async () => { calls.finished++; },
    expireApproval: async () => {},
  };
  const api = {
    GenerationJobManager: manager,
    isPendingActionStale: ({pendingAction}) => pendingAction.expiresAt <= Date.now(),
    findUndecidedToolCalls: (payload, rows) => payload.action_requests.filter(a => !rows.some(r => r.tool_call_id === a.tool_call_id)),
    findDisallowedDecisions: () => [], findIncompleteDecisions: () => [],
    mapToolApprovalResolutions: rows => Object.fromEntries(rows.map(r => [r.tool_call_id, {type: r.decision}])),
    buildResolvedAskUserQuestion: () => null, appendResolvedAskUserQuestion: () => undefined,
    computeAgentRequestFingerprint: () => 'test', isSteerPreemptSupported: () => false,
    checkAndIncrementPendingRequest: async () => ({allowed: !options.concurrencyBlocked}),
    decrementPendingRequest: async () => { calls.decrement++; if (options.slotFails) throw Error('slot'); },
    captureAgentCheckpointGeneration: async () => ({checkpointIds: []}),
    deleteAgentCheckpoint: async (...args) => { calls.checkpoint++; calls.checkpointArgs = args; if (options.checkpointFails) throw Error('checkpoint'); },
    buildAbortedResponseMetadata: () => null, filterMalformedContentParts: value => value,
    sanitizeMessageForTransmit: value => value, toPendingSteer: value => value,
  };
  const native = {
    prepareNativeRequest: context => gate.prepareNativeRequest(context, f.config),
    persistNativeDecision: async envelope => {
      calls.receipt++;
      if (options.receiptFails) throw Error('private-receipt-error');
      const result = await gate.persistNativeDecision(envelope);
      if (options.lostAck) throw Error('lost acknowledgement');
      return result;
    },
  };
  const modules = {
    '@librechat/data-schemas': {logger: {warn: () => {}, debug: () => {}, error: message => calls.errors.push(message)}},
    'librechat-data-provider': {Constants: {NO_PARENT: 'none'}, EModelEndpoint: {agents: 'agents'}},
    '@librechat/api': api,
    '~/server/cleanup': {disposeClient: () => {}},
    '~/server/services/MCPRequestContext': {getMCPRequestContext: () => {}, cleanupMCPRequestContextForReq: async () => {}},
    '~/models': {saveMessage: async (_context, value) => { saved = value; return value; }, getConvo: async () => null, getMessages: async () => []},
    './protocol': {GENERATION_PROTOCOL_HEADER: 'test-protocol', negotiateNewGenerationProtocol: () => 1, negotiateExistingGenerationProtocol: () => 1},
    './awsops-native-gate.cjs': native,
  };
  const module = {exports: {}};
  vm.runInNewContext(patch.render(fs.readFileSync(fixture)).toString('utf8'), {
    module, require: name => { if (!(name in modules)) throw Error('Unexpected import '+name); return modules[name]; },
    setTimeout, clearTimeout, console,
  }, {filename: 'pinned-resume.js'});
  const res = {set: () => {}, status: n => { res.code = n; return res; }, json: body => { res.body = body; return res; }};
  const initialize = async () => { calls.initialize++; return {client: {
    contentParts: [], artifactPromises: [], buildResponseMetadata: () => null,
    resumeCompletion: async args => { calls.resume++; calls.resolution = args.resumeValue; },
  }}; };
  return {calls, res, state: () => current, saved: () => saved,
    run: () => module.exports(f.req, res, () => {}, initialize, null)};
}

test('pinned upstream controller + real SQLite process bridge', {skip: !hasUpstream}, async t => {
  for (const decision of ['reject', 'approve']) await t.test('successful '+decision, async t => {
    const f = setup(t); await register(f); f.req.body.decisions[0].decision = decision;
    const h = harness(f); await h.run();
    assert.equal(h.res.code, 200); assert.equal(h.calls.claim, 1); assert.equal(h.calls.receipt, 1);
    assert.equal(h.calls.resume, 1); assert.equal(h.calls.resolution['call-1'].type, 'reject');
    assert.equal(h.calls.finished, 1); assert.equal(h.calls.decrement, 1); assert.equal(h.calls.checkpoint, 1);
    assert.equal(h.calls.terminal, 0); assert.ok(h.saved());
  });
  for (const fault of ['receiptFails', 'lostAck']) await t.test(fault+' terminalizes before continuation', async t => {
    const f = setup(t); await register(f); const h = harness(f, {[fault]: true}); await h.run();
    assert.equal(h.res.code, 503); assert.equal(h.res.body.terminalization, 'FINALIZED');
    assert.equal(h.calls.resume, 0); assert.equal(h.calls.initialize, 0);
    assert.equal(h.calls.terminalGeneration, f.job.createdAt); assert.equal(h.calls.checkpoint, 1); assert.equal(h.calls.decrement, 1);
    if (fault === 'lostAck') await assert.rejects(record(f));
  });
  for (const fault of ['replaceJob', 'terminalFails', 'slotFails', 'checkpointFails']) await t.test(fault+' reports reconciliation, not success', async t => {
    const f = setup(t); const h = harness(f, {receiptFails: true, [fault]: true}); await h.run();
    assert.equal(h.res.code, 503); assert.equal(h.res.body.terminalization, 'RECONCILE_REQUIRED');
    assert.equal(h.calls.resume, 0); assert.equal(h.calls.decrement, 1);
    if (['replaceJob', 'terminalFails'].includes(fault)) assert.equal(h.calls.checkpoint, 0);
  });
  for (const fault of ['loseClaim', 'claimFails', 'concurrencyBlocked']) await t.test(fault+' never records or resumes', async t => {
    const f = setup(t); const h = harness(f, {[fault]: true}); await h.run();
    assert.equal(h.calls.receipt, 0); assert.equal(h.calls.resume, 0);
    assert.notEqual(h.res.code, 200);
  });
  await t.test('native ownership guard runs before receipt or claim', async t => {
    const f = setup(t); f.req.user = {id: 'wrong-user'};
    const h = harness(f); await h.run(); assert.equal(h.res.code, 403); assert.equal(h.calls.claim, 0); assert.equal(h.calls.receipt, 0);
  });
  await t.test('unconfigured/wrong canary fails before claim', async t => {
    const f = setup(t); f.config.enabled = false;
    const h = harness(f); await h.run(); assert.equal(h.res.code, 403); assert.equal(h.calls.claim, 0);
  });
  await t.test('unrelated legacy tool bypasses new receipt unchanged', async t => {
    const f = setup(t); f.job.metadata.pendingAction.payload.action_requests[0].name = 'legacy_bpa';
    f.req.body.decisions[0].decision = 'approve';
    const h = harness(f); await h.run(); assert.equal(h.res.code, 200); assert.equal(h.calls.receipt, 0);
    assert.equal(h.calls.resolution['call-1'].type, 'approve');
  });
});

test('isolated candidate apply/check/reapply/rollback and drift refusal', {skip: !hasUpstream}, t => {
  const f = setup(t); const candidate = path.join(f.dir, 'candidate'); fs.mkdirSync(candidate);
  fs.mkdirSync(path.join(candidate, 'api/server/controllers/agents'), {recursive: true});
  const target = path.join(candidate, patch.pin.controller);
  fs.copyFileSync(fixture, target); fs.writeFileSync(path.join(candidate, 'package.json'), JSON.stringify({version: patch.pin.version}));
  fs.writeFileSync(path.join(candidate, '.awsops-offline-candidate.json'), JSON.stringify({purpose: 'offline-rehearsal', root: candidate, upstream_commit: patch.pin.commit, live: false}));
  const original = fs.readFileSync(target);
  assert.equal(patch.check(candidate).state, 'ORIGINAL');
  assert.equal(patch.change(candidate, 'apply').state, 'PATCHED');
  const patched = fs.readFileSync(target);
  assert.equal(patch.change(candidate, 'apply').state, 'PATCHED');
  fs.appendFileSync(target, '\n// foreign drift');
  assert.throws(() => patch.change(candidate, 'rollback')); assert.ok(fs.readFileSync(target).includes(Buffer.from('foreign drift')));
  fs.writeFileSync(target, patched);
  const helper = path.join(path.dirname(target), 'awsops-native-gate.cjs');
  fs.appendFileSync(helper, '\n// foreign helper');
  assert.throws(() => patch.change(candidate, 'rollback')); assert.deepEqual(fs.readFileSync(target), patched);
  fs.copyFileSync(path.join(root, 'integration/librechat/native_gate.cjs'), helper);
  assert.equal(patch.change(candidate, 'rollback').state, 'ORIGINAL'); assert.deepEqual(fs.readFileSync(target), original);
  assert.equal(patch.change(candidate, 'rollback').state, 'ORIGINAL'); assert.equal(fs.existsSync(helper), false);
  fs.unlinkSync(path.join(candidate, '.awsops-offline-candidate.json'));
  assert.throws(() => patch.change(candidate, 'apply'));
  assert.throws(() => patch.render(Buffer.concat([original, Buffer.from('\n')])));
});
