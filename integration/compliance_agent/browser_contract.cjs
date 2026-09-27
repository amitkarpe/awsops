'use strict';

const crypto = require('node:crypto');

const ALIASES = ['lab-dev', 'lab-poc', 'lab-qa', 'lab-sec'];
const CONTROLS = [
  's3-bucket-level-public-access-prohibited',
  'restricted-ssh',
];
const TOOL = 'ask_compliance_agent_mcp_awsops_compliance_agent';
const LOGICAL_TOOL = 'ask_compliance_agent';
const GUARDRAIL = '🛡️ **Read-only:** No AWS changes executed.';
const MAX_DIAGNOSTICS = 32;
const MODES = {
  status: 'Status',
  explain: 'Explain what needs attention',
  plan: 'Give me a remediation plan without making changes',
};
const STATUSES = new Set(['COMPLIANT', 'NON_COMPLIANT', 'INSUFFICIENT_DATA', 'NOT_APPLICABLE']);
const STATUS_MARKS = {
  COMPLIANT: '✅',
  NON_COMPLIANT: '🔴',
  INSUFFICIENT_DATA: '⚠️',
  NOT_APPLICABLE: '⚪',
};

function fail(code) { throw Error(code); }
function sha256(value) { return crypto.createHash('sha256').update(value).digest('hex'); }
function normalize(value) {
  if (typeof value !== 'string') fail('TEXT_REQUIRED');
  return value.replace(/\r\n/g, '\n').trim();
}

function validateEvidence(evidence) {
  if (!evidence || typeof evidence !== 'object' || evidence.identifiers_available !== false ||
      JSON.stringify(evidence.aliases) !== JSON.stringify(ALIASES) ||
      JSON.stringify(evidence.controls) !== JSON.stringify(CONTROLS) ||
      !Array.isArray(evidence.checks) || evidence.checks.length !== 8) fail('EVIDENCE_CONTRACT_REQUIRED');
  const expected = new Set(ALIASES.flatMap((alias) => CONTROLS.map((control) => `${alias}\0${control}`)));
  const checks = new Map();
  for (const row of evidence.checks) {
    const key = `${row?.account_alias}\0${row?.control}`;
    if (!expected.delete(key) || !STATUSES.has(row?.status)) fail('EVIDENCE_MATRIX_REQUIRED');
    if (row.status === 'COMPLIANT' && row.affected_resources !== 0) fail('EVIDENCE_COUNT_INVALID');
    if (row.status === 'NON_COMPLIANT' && (!Number.isSafeInteger(row.affected_resources) || row.affected_resources < 0))
      fail('EVIDENCE_COUNT_INVALID');
    if (row.affected_resources != null && (!Number.isSafeInteger(row.affected_resources) || row.affected_resources < 0))
      fail('EVIDENCE_COUNT_INVALID');
    checks.set(key, row);
  }
  if (expected.size) fail('EVIDENCE_MATRIX_REQUIRED');
  return checks;
}

function findToolResult(value, found = [], depth = 0) {
  if (depth > 8 || value == null) return found;
  if (typeof value === 'string') {
    try { findToolResult(JSON.parse(value), found, depth + 1); } catch {}
    return found;
  }
  if (Array.isArray(value)) {
    for (const item of value) findToolResult(item, found, depth + 1);
    return found;
  }
  if (typeof value !== 'object') return found;
  if (typeof value.answer === 'string' && value.mutation === false && value.evidence) found.push(value);
  for (const item of Object.values(value)) findToolResult(item, found, depth + 1);
  return found;
}

function collectToolCalls(messages) {
  if (!Array.isArray(messages)) fail('PERSISTED_MESSAGES_REQUIRED');
  const calls = [];
  const visit = (value) => {
    if (!value || typeof value !== 'object') return;
    if (Array.isArray(value)) { value.forEach(visit); return; }
    const call = value.tool_call ?? (value.type === 'tool_call' ? value : null);
    if (call && typeof call === 'object') {
      const name = call.function?.name ?? call.name ?? call.function_name ?? call.pluginKey;
      const id = call.id ?? call.tool_call_id ?? call.toolCallId;
      const output = call.output ?? call.result ?? value.output;
      if (name || id || output != null) calls.push({name, id, output});
    }
    Object.values(value).forEach(visit);
  };
  messages.forEach(visit);
  const unique = new Map();
  for (const call of calls) unique.set(`${call.id ?? ''}\0${call.name ?? ''}`, call);
  return [...unique.values()];
}

function persistedBinding(messages) {
  const calls = collectToolCalls(messages);
  if (calls.length !== 1 || ![TOOL, LOGICAL_TOOL].includes(calls[0].name) ||
      typeof calls[0].id !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(calls[0].id))
    fail('EXACT_TOOL_CALL_REQUIRED');

  const candidates = findToolResult(calls[0].output);
  let toolResult;
  let toolAnswer;
  if (candidates.length === 1) {
    toolResult = candidates[0];
    validateEvidence(toolResult.evidence);
    toolAnswer = normalize(toolResult.answer);
  } else if (candidates.length === 0 && typeof calls[0].output === 'string' && calls[0].output.trim()) {
    toolAnswer = normalize(calls[0].output);
    toolResult = {answer: toolAnswer, mutation: false, evidence: null, persistedOutput: true};
  } else {
    fail('EXACT_TOOL_OUTPUT_REQUIRED');
  }

  const messageText = (message) => {
    if (typeof message?.text === 'string' && message.text.trim()) return message.text;
    if (!Array.isArray(message?.content)) return '';
    return message.content.filter((part) => part?.type === 'text').map((part) =>
      typeof part.text === 'string' ? part.text : part.text?.value ?? '').join('\n').trim();
  };
  const assistant = [...messages].reverse().find((message) =>
    message?.isCreatedByUser === false && messageText(message));
  if (!assistant) fail('FINAL_ASSISTANT_REQUIRED');
  const assistantText = normalize(messageText(assistant));
  if (assistantText !== toolAnswer) fail('OUTER_AGENT_REWRITE_DETECTED');
  return {toolCallId: calls[0].id, toolResult, assistantText};
}

function markdownTables(text) {
  const lines = normalize(text).split('\n');
  const tables = [];
  for (let i = 0; i < lines.length;) {
    if (!/^\s*\|.*\|\s*$/.test(lines[i]) || i + 1 >= lines.length ||
        !/^\s*\|(?:\s*:?-+:?\s*\|)+\s*$/.test(lines[i + 1])) { i += 1; continue; }
    const cells = (line) => line.trim().slice(1, -1).split('|').map((cell) => cell.trim());
    const table = {header: cells(lines[i]), rows: []};
    i += 2;
    while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) table.rows.push(cells(lines[i++]));
    tables.push(table);
  }
  return tables;
}

function proseLines(text) {
  const lines = normalize(text).split('\n');
  const prose = [];
  for (let i = 0; i < lines.length;) {
    if (/^\s*\|.*\|\s*$/.test(lines[i]) && i + 1 < lines.length &&
        /^\s*\|(?:\s*:?-+:?\s*\|)+\s*$/.test(lines[i + 1])) {
      i += 2;
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) i += 1;
      continue;
    }
    const line = lines[i++].trim();
    if (line && line !== GUARDRAIL) prose.push(line);
  }
  return prose;
}

function assertGuardrail(answer) {
  const text = normalize(answer);
  const count = text.split(GUARDRAIL).length - 1;
  if (count !== 1 || !text.endsWith(GUARDRAIL)) fail('EXACT_FINAL_GUARDRAIL_REQUIRED');
  const line = text.split('\n').at(-1);
  if (line !== GUARDRAIL || /^\s*>/.test(line) || /["'“”‘’]/.test(line)) fail('PLAIN_GUARDRAIL_REQUIRED');
}

function expectedStatus(check) {
  const prefix = `${STATUS_MARKS[check.status]} ${check.status}`;
  if (check.status !== 'NON_COMPLIANT') return prefix;
  return `${prefix} (${check.affected_resources} affected)`;
}

function parseStatusCell(cell) {
  if (cell === '✅ COMPLIANT') return {status: 'COMPLIANT', affected_resources: 0};
  if (cell === '⚠️ INSUFFICIENT_DATA') return {status: 'INSUFFICIENT_DATA', affected_resources: null};
  if (cell === '⚪ NOT_APPLICABLE') return {status: 'NOT_APPLICABLE', affected_resources: null};
  const match = cell.match(/^🔴 NON_COMPLIANT \((\d+) affected\)$/);
  if (match) return {status: 'NON_COMPLIANT', affected_resources: Number(match[1])};
  fail('STATUS_CELL_INVALID');
}

function matrixChecks(table) {
  if (!table || JSON.stringify(table.header) !== JSON.stringify(['Account', '🪣 S3 BPA', '🔐 Restricted SSH']) ||
      table.rows.length !== 4) fail('STATUS_MATRIX_REQUIRED');
  const checks = new Map();
  table.rows.forEach((row, index) => {
    const alias = ALIASES[index];
    if (row.length !== 3 || row[0] !== alias) fail('STATUS_MATRIX_REQUIRED');
    CONTROLS.forEach((control, controlIndex) => {
      checks.set(`${alias}\0${control}`, {
        account_alias: alias,
        control,
        ...parseStatusCell(row[controlIndex + 1]),
      });
    });
  });
  return checks;
}

function assertMatrixEvidence(tableChecks, evidenceChecks) {
  for (const [key, expected] of evidenceChecks.entries()) {
    const actual = tableChecks.get(key);
    if (!actual || actual.status !== expected.status) fail('STATUS_EVIDENCE_MISMATCH');
    if (expected.status === 'NON_COMPLIANT' &&
        actual.affected_resources !== expected.affected_resources) fail('STATUS_EVIDENCE_MISMATCH');
  }
}

function assertNoInvention(answer, checks) {
  const text = normalize(answer);
  const forbidden = [
    /\barn:[a-z0-9-]+:/i, /\b\d{12}\b/, /\b(?:\d{1,3}\.){3}\d{1,3}(?:\/\d{1,2})?\b/,
    /\b(?:i|sg|subnet|vpc|eni|vol|snap|ami)-[0-9a-f]{8,}\b/i, /\bport\s+\d{1,5}\b/i,
    /\b(?:access[_ -]?key|secret[_ -]?key|password|credential|token)\s*[:=]/i,
    /\b(?:exploitable|exploitation|breach|attacker|sensitive data|publicly exposed)\b/i,
    /"(?:Action|Resource|Effect|Statement)"\s*:/,
  ];
  if (forbidden.some((pattern) => pattern.test(text))) fail('INVENTED_PRIVATE_OR_RISK_CLAIM');
  const aliases = text.match(/\blab-[a-z0-9-]+\b/g) ?? [];
  if (aliases.some((alias) => !ALIASES.includes(alias))) fail('EXTRA_ALIAS');
  const attentionCount = [...checks.values()].filter((row) =>
    row.status === 'NON_COMPLIANT' || row.status === 'INSUFFICIENT_DATA').length;
  const allowedNumbers = new Set([4, 8, attentionCount,
    ...[...checks.values()].map((row) => row.affected_resources).filter(Number.isSafeInteger)]);
  const numbers = text.match(/\b\d+\b/g) ?? [];
  if (numbers.some((value) => !allowedNumbers.has(Number(value)))) fail('INVENTED_NUMBER');
}

function assertAttention(table, checks) {
  const attention = [...checks.values()].filter((row) =>
    row.status === 'NON_COMPLIANT' || row.status === 'INSUFFICIENT_DATA');
  if (!table || JSON.stringify(table.header) !== JSON.stringify(['Needs attention', 'Why', 'Affected']) ||
      table.rows.length !== attention.length) fail('EXPLAIN_TABLE_REQUIRED');
  for (const check of attention) {
    const row = table.rows.find((item) => item[0].includes(check.account_alias) &&
      (item[0].includes(check.control) || item[0].includes(check.control === CONTROLS[0] ? 'S3 BPA' : 'Restricted SSH')));
    if (!row || row.length !== 3) fail('EXPLAIN_EVIDENCE_MISMATCH');
    const label = check.control === CONTROLS[0] ? 'S3 BPA' : 'Restricted SSH';
    const why = check.status === 'INSUFFICIENT_DATA' ? 'evidence is insufficient.'
      : check.control === CONTROLS[0]
        ? 'bucket-level Block Public Access is not in the compliant configuration.'
        : 'unrestricted SSH ingress is present.';
    const affected = check.status === 'INSUFFICIENT_DATA' ? 'Unknown' : String(check.affected_resources);
    if (row[0] !== `${check.account_alias} — ${label}` || row[1] !== why || row[2] !== affected)
      fail('EXPLAIN_EVIDENCE_MISMATCH');
  }
}

function assertPlan(table, checks) {
  const attention = [...checks.values()].filter((row) => row.status === 'NON_COMPLIANT');
  if (!table || JSON.stringify(table.header) !== JSON.stringify(['Alias', 'Control', 'Evidence', 'Suggested change', 'Execution']) ||
      table.rows.length !== attention.length) fail('PLAN_TABLE_REQUIRED');
  for (const check of attention) {
    const label = check.control === CONTROLS[0] ? 'S3 BPA' : 'Restricted SSH';
    const row = table.rows.find((item) => item[0] === check.account_alias && item[1] === label);
    if (!row || row.length !== 5 || row[2] !== expectedStatus(check) || row[4] !== '🚫 Not executed')
      fail('PLAN_EVIDENCE_MISMATCH');
    const allowed = check.control === CONTROLS[0]
      ? 'Bring bucket-level Block Public Access into the compliant configuration.'
      : 'Remove unrestricted SSH ingress; if access is required, replace it with an approved source.';
    if (row[3] !== allowed) fail('PLAN_GUIDANCE_MISMATCH');
  }
}

function assertAnswer(mode, toolResult, rendered) {
  if (!Object.hasOwn(MODES, mode) || typeof toolResult?.answer !== 'string' ||
      toolResult?.mutation !== false) fail('READ_ONLY_RESULT_REQUIRED');
  const answer = normalize(toolResult.answer);
  const evidenceChecks = toolResult.evidence ? validateEvidence(toolResult.evidence) : null;
  assertGuardrail(answer);
  const tables = markdownTables(answer);
  const checks = matrixChecks(tables[0]);
  if (evidenceChecks) assertMatrixEvidence(checks, evidenceChecks);
  assertNoInvention(answer, checks);
  const withoutTables = proseLines(answer);
  const attentionCount = [...checks.values()].filter((row) =>
    row.status === 'NON_COMPLIANT' || row.status === 'INSUFFICIENT_DATA').length;
  if (mode === 'status') {
    const summary = attentionCount ? `${attentionCount} of 8 checks need attention.`
      : 'All 8 checks are compliant or not applicable.';
    if (tables.length !== 1 || JSON.stringify(withoutTables) !== JSON.stringify([summary]))
      fail('STATUS_LAYOUT_MISMATCH');
  }
  if (mode === 'explain') {
    if (tables.length !== 2 || withoutTables.length) fail('EXPLAIN_LAYOUT_MISMATCH');
    assertAttention(tables[1], checks);
  }
  if (mode === 'plan') {
    if (tables.length !== 2 || withoutTables.length) fail('PLAN_LAYOUT_MISMATCH');
    assertPlan(tables[1], checks);
  }
  if (!rendered || rendered.guardrailCount !== 1 || rendered.trailingText !== '' ||
      rendered.guardrailText !== '🛡️ Read-only: No AWS changes executed.' ||
      JSON.stringify(rendered.tables) !== JSON.stringify(tables.map((table) => [table.header, ...table.rows])))
    fail('RENDERED_OUTPUT_MISMATCH');
  const proof = {mode, checks: 8, tables: tables.length, attention: tables[1]?.rows.length ?? 0,
    toolOutputDigest: sha256(answer)};
  if (toolResult.evidence) proof.evidenceDigest = sha256(JSON.stringify(toolResult.evidence));
  return proof;
}

async function waitForSettledSnapshot(read, {attempts = 120, stableSamples = 3, pause = defaultPause} = {}) {
  let previous; let stable = 0;
  for (let i = 0; i < attempts; i++) {
    const value = await read(); const encoded = JSON.stringify(value);
    stable = encoded && encoded === previous ? stable + 1 : 1;
    if (stable >= stableSamples) return value;
    previous = encoded; await pause(250);
  }
  fail('RENDERED_TURN_NOT_SETTLED');
}
function defaultPause(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

function archiveRequest(conversationId) {
  if (typeof conversationId !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(conversationId)) fail('ARCHIVE_ID_REQUIRED');
  return {path: '/api/convos/archive', method: 'POST', body: {arg: {conversationId, isArchived: true}}};
}
function assertArchived(result, conversationId) {
  if (result?.status !== 200 || result?.json?.conversationId !== conversationId || result?.json?.isArchived !== true)
    fail('EXACT_CONVERSATION_ARCHIVE_FAILED');
  return true;
}

function routeClass(url, base) {
  let parsed; try { parsed = new URL(url); } catch { return 'unknown'; }
  if (parsed.origin !== new URL(base).origin) return 'external';
  if (parsed.pathname === '/api/auth/login' || parsed.pathname === '/api/auth/refresh') return 'auth';
  if (parsed.pathname === '/api/agents/chat') return 'agents_chat';
  if (parsed.pathname === '/api/messages' || parsed.pathname.startsWith('/api/messages/')) return 'messages';
  if (parsed.pathname === '/api/convos/archive') return 'convo_archive';
  if (parsed.pathname.startsWith('/api/convos/')) return 'convo_item';
  if (parsed.pathname.startsWith('/api/')) return 'api_other';
  return 'page';
}
function safeDiagnostic({stage, method, url, status, headerNames = [], base}) {
  const names = new Set(headerNames.map((name) => String(name).toLowerCase()));
  return {stage: /^[a-z_]{1,40}$/.test(stage) ? stage : 'other', route: routeClass(url, base),
    method: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'].includes(method) ? method : 'OTHER',
    status: Number.isInteger(status) && status >= 100 && status <= 599 ? status : null,
    authorization_present: names.has('authorization'), cookie_present: names.has('cookie'),
    content_type_present: names.has('content-type')};
}
function recordDiagnostic(rows, row) { if (rows.length < MAX_DIAGNOSTICS) rows.push(row); }

module.exports = {ALIASES, CONTROLS, GUARDRAIL, LOGICAL_TOOL, MAX_DIAGNOSTICS, MODES, TOOL, archiveRequest,
  assertAnswer, assertArchived, collectToolCalls, findToolResult, markdownTables, matrixChecks, normalize,
  persistedBinding, proseLines, recordDiagnostic, routeClass, safeDiagnostic, sha256, validateEvidence,
  waitForSettledSnapshot};
