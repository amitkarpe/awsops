'use strict';

const BASE = 'http://127.0.0.1:4311';
const MAX_DIAGNOSTICS = 24;
const SCOPE_FIELDS = ['account_alias', 'control', 'expected_evidence_digest', 'resource_ref'];
const STAGES = new Set([
  'launch', 'login', 'tool_ready', 'agent_create', 'agent_select', 'send',
  'approval_card', 'reject_resume', 'binding', 'completion', 'cleanup',
]);
const METHODS = new Set(['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']);

function fail(code) { throw Error(code); }

function validateCandidate(candidate) {
  if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate) ||
      Object.keys(candidate).sort().join(',') !== SCOPE_FIELDS.join(',')) fail('CANARY_SCOPE_REQUIRED');
  if (candidate.control !== 's3_ssl' ||
      !['lab-dev', 'lab-poc', 'lab-qa', 'lab-sec'].includes(candidate.account_alias) ||
      typeof candidate.resource_ref !== 'string' || !/^bucket-ref-[a-f0-9]{20}$/.test(candidate.resource_ref) ||
      typeof candidate.expected_evidence_digest !== 'string' || !/^[a-f0-9]{64}$/.test(candidate.expected_evidence_digest))
    fail('CANARY_SCOPE_REQUIRED');
  return candidate;
}

function assertApprovalSnapshot(snapshot, expected) {
  validateCandidate(expected.candidate);
  if (snapshot.cardCount !== 1 || snapshot.visible !== true || snapshot.toolCallCount !== 1 ||
      snapshot.outputCount !== 1) fail('AMBIGUOUS_APPROVAL_CARD');
  if (typeof snapshot.toolCallId !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(snapshot.toolCallId))
    fail('APPROVAL_CARD_ID_REQUIRED');
  if (typeof snapshot.toolText !== 'string' ||
      !snapshot.toolText.split(/[^A-Za-z0-9_-]+/).includes(expected.toolName))
    fail('APPROVAL_TOOL_MISMATCH');
  const scopeTokens = typeof snapshot.scopeText === 'string'
    ? new Set(snapshot.scopeText.split(/[^A-Za-z0-9_-]+/)) : new Set();
  if (SCOPE_FIELDS.some((key) => !scopeTokens.has(key) ||
      !scopeTokens.has(String(expected.candidate[key])))) fail('APPROVAL_SCOPE_MISMATCH');
  const buttons = snapshot.buttons;
  if (!buttons || buttons.reject !== 1 || buttons.approve !== 0 || buttons.edit !== 0 ||
      buttons.respond !== 0 || buttons.submit !== 1) fail('NOT_REJECT_ONLY');
  return snapshot.toolCallId;
}

async function waitForSettledSnapshot(read, {attempts = 30, stableSamples = 3, pause = defaultPause} = {}) {
  let previous;
  let stable = 0;
  for (let i = 0; i < attempts; i++) {
    const value = await read();
    const encoded = JSON.stringify(value);
    if (encoded && encoded === previous) stable += 1;
    else stable = 1;
    if (stable >= stableSamples) return value;
    previous = encoded;
    await pause(100);
  }
  fail('APPROVAL_CARD_NOT_SETTLED');
}

function defaultPause(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

function assertSingleRejectSubmission(submissions, expected) {
  if (!Array.isArray(submissions) || submissions.length !== 1) fail('REJECT_SUBMISSION_COUNT');
  const item = submissions[0];
  const body = item.body;
  const decision = body?.decisions?.[0];
  if (item.method !== 'POST' || item.route !== 'agents_resume' || item.status !== 200 ||
      body?.agent_id !== expected.agentId || body?.conversationId !== expected.conversationId ||
      body?.endpoint !== 'agents' || !Number.isSafeInteger(body?.generationCreatedAt) ||
      typeof body?.actionId !== 'string' || body.actionId.length === 0 ||
      body?.decisions?.length !== 1 || decision?.decision !== 'reject' ||
      decision?.tool_call_id !== expected.toolCallId) fail('REJECT_SUBMISSION_MISMATCH');
  return {count: 1, status: 200};
}

function archiveRequest(conversationId) {
  if (typeof conversationId !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(conversationId))
    fail('ARCHIVE_CONVERSATION_ID_REQUIRED');
  return {
    path: '/api/convos/archive',
    method: 'POST',
    body: {arg: {conversationId, isArchived: true}},
  };
}

function assertArchived(result, conversationId) {
  if (result?.status !== 200 || result?.json?.conversationId !== conversationId ||
      result?.json?.isArchived !== true) fail('EXACT_CONVERSATION_ARCHIVE_FAILED');
  return true;
}

function routeClass(url) {
  let parsed;
  try { parsed = new URL(url); } catch { return 'unknown'; }
  if (parsed.origin !== BASE) return 'external';
  const pathname = parsed.pathname;
  if (pathname === '/api/auth/login' || pathname === '/api/auth/refresh') return 'auth';
  if (pathname === '/api/agents/chat') return 'agents_chat';
  if (pathname === '/api/agents/chat/resume') return 'agents_resume';
  if (pathname === '/api/mcp/tools') return 'mcp_tools';
  if (pathname === '/api/agents') return 'agents';
  if (pathname === '/api/user') return 'user';
  if (pathname === '/api/convos/archive') return 'convo_archive';
  if (/^\/api\/convos\/[A-Za-z0-9_-]{1,128}$/.test(pathname)) return 'convo_item';
  if (pathname.startsWith('/api/')) return 'api_other';
  return 'page';
}

function safeDiagnostic({stage, method, url, status, headerNames = []}) {
  const names = new Set(Array.isArray(headerNames) ? headerNames.map((name) => String(name).toLowerCase()) : []);
  const code = Number.isInteger(status) && status >= 100 && status <= 599 ? status : null;
  return {
    stage: STAGES.has(stage) ? stage : 'other',
    route: routeClass(url),
    method: METHODS.has(method) ? method : 'OTHER',
    status: code,
    authorization_present: names.has('authorization'),
    cookie_present: names.has('cookie'),
    content_type_present: names.has('content-type'),
    auth_state: code === 401 || code === 403 ? 'rejected' : code === null ? 'pending' : 'response',
  };
}

function recordDiagnostic(diagnostics, entry) {
  if (Array.isArray(diagnostics) && diagnostics.length < MAX_DIAGNOSTICS) diagnostics.push(entry);
}

module.exports = {
  MAX_DIAGNOSTICS,
  assertApprovalSnapshot,
  assertArchived,
  assertSingleRejectSubmission,
  archiveRequest,
  recordDiagnostic,
  routeClass,
  safeDiagnostic,
  validateCandidate,
  waitForSettledSnapshot,
};
