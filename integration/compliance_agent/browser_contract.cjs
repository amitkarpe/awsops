'use strict';

const crypto = require('node:crypto');

const ALIASES = ['lab-dev', 'lab-poc', 'lab-qa', 'lab-sec'];
const GUARDRAIL = '🛡️ **Read-only:** No AWS changes executed.';
const PROMPTS = Object.freeze({
  status: 'Status',
  explain: 'Explain what needs attention',
  plan: 'Give me a remediation plan without making changes',
});
const MODES = new Set(Object.keys(PROMPTS));
const MAX_DIAGNOSTICS = 32;

function fail(code) { throw Error(code); }

function normalizeMarkdown(value) {
  if (typeof value !== 'string') fail('MARKDOWN_REQUIRED');
  return value.replace(/\r\n/g, '\n').split('\n').map((line) => line.trimEnd()).join('\n').trim();
}

function digest(value) {
  return crypto.createHash('sha256').update(String(value)).digest('hex');
}

function extractToolAnswer(text) {
  if (typeof text !== 'string') fail('TOOL_OUTPUT_REQUIRED');
  const source = text.replace(/\r\n/g, '\n');
  const start = source.indexOf('| Account |');
  const guard = source.indexOf(GUARDRAIL, start);
  if (start < 0 || guard < 0) fail('TOOL_ANSWER_NOT_FOUND');
  return normalizeMarkdown(source.slice(start, guard + GUARDRAIL.length));
}

function strings(value) {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(strings);
  if (value && typeof value === 'object') return Object.values(value).flatMap(strings);
  return [];
}

function persistedAssistantText(history) {
  if (!Array.isArray(history)) fail('MESSAGE_HISTORY_REQUIRED');
  for (let index = history.length - 1; index >= 0; index -= 1) {
    const message = history[index];
    if (!message || typeof message !== 'object' || message.isCreatedByUser === true || message.unfinished === true) continue;
    if (typeof message.text === 'string' && message.text.trim()) return normalizeMarkdown(message.text);
    const candidates = strings(message.content).filter((item) => item.trim());
    if (candidates.length) return normalizeMarkdown(candidates.join('\n'));
  }
  fail('PERSISTED_ASSISTANT_REQUIRED');
}

function count(source, pattern) {
  return [...source.matchAll(pattern)].length;
}

function assertNoInventedDetails(answer) {
  const forbidden = [
    /\barn:aws(?::[A-Za-z0-9_./+=,@-]*)?/i,
    /\b\d{12}\b/,
    /\bi-[0-9a-f]{8,17}\b/i,
    /\bsg-[0-9a-f]{8,17}\b/i,
    /\bvpc-[0-9a-f]{8,17}\b/i,
    /\bsubnet-[0-9a-f]{8,17}\b/i,
    /\b(?:\d{1,3}\.){3}\d{1,3}(?:\/\d{1,2})?\b/,
    /\b::\/0\b/i,
    /\bCIDR\b/i,
    /\bport\s*22\b/i,
    /\bbastion\b/i,
    /\bsensitive data\b/i,
    /\bpublic internet\b/i,
    /\bexploit(?:able|ability|ation)?\b/i,
  ];
  if (forbidden.some((pattern) => pattern.test(answer))) fail('INVENTED_DETAIL');
  const aliases = answer.match(/\blab-[a-z0-9-]+\b/g) || [];
  if (aliases.some((alias) => !ALIASES.includes(alias))) fail('UNKNOWN_ALIAS');
}

function matrixRows(answer) {
  const rows = answer.split('\n').filter((line) => /^\| lab-(?:dev|poc|qa|sec) \|/.test(line));
  if (rows.length !== 4) fail('MATRIX_ROW_COUNT');
  for (const alias of ALIASES) {
    if (rows.filter((line) => line.startsWith('| ' + alias + ' |')).length !== 1) fail('MATRIX_ALIAS_COUNT');
  }
  return rows;
}

function assertAnswerContract(mode, answerValue) {
  if (!MODES.has(mode)) fail('MODE_REQUIRED');
  const answer = normalizeMarkdown(answerValue);
  if (!answer.startsWith('| Account | 🪣 S3 BPA | 🔐 Restricted SSH |')) fail('MATRIX_FIRST');
  matrixRows(answer);
  assertNoInventedDetails(answer);

  const guardCount = answer.split(GUARDRAIL).length - 1;
  if (guardCount !== 1 || !answer.endsWith(GUARDRAIL)) fail('GUARDRAIL_EXACT');
  if (/^\s*>\s*🛡️/m.test(answer) || /[“”"]\s*🛡️ \*\*Read-only:\*\*/.test(answer)) fail('GUARDRAIL_QUOTED');

  const attention = count(answer, /^\| Needs attention \| Why \| Affected \|$/gm);
  const plan = count(answer, /^\| Priority \| Control \| Suggested change \| Execution \|$/gm);
  if (mode === 'status' && (attention !== 0 || plan !== 0)) fail('STATUS_MODE_MIXED');
  if (mode === 'explain' && (attention !== 1 || plan !== 0)) fail('EXPLAIN_MODE_MIXED');
  if (mode === 'plan' && (attention !== 0 || plan !== 1)) fail('PLAN_MODE_MIXED');

  if (mode === 'plan') {
    const executionRows = answer.split('\n').filter((line) => /^\| (?:P\d+|[🔴🟠🟡🟢]|High|Medium|Low)/i.test(line));
    if (executionRows.some((line) => !line.includes('🚫 Not executed'))) fail('PLAN_EXECUTION_BOUNDARY');
  }
  return answer;
}

function assertToolToAssistantBinding(mode, toolOutputText, history) {
  const toolAnswer = assertAnswerContract(mode, extractToolAnswer(toolOutputText));
  const persisted = persistedAssistantText(history);
  if (persisted !== toolAnswer) fail('OUTER_AGENT_REWRITE');
  return {answer: persisted, digest: digest(persisted)};
}

function safeDiagnostic({stage, method, url, status, headerNames = []}) {
  let parsed;
  try { parsed = new URL(url); } catch { parsed = null; }
  const route = parsed ? parsed.pathname
    .replace(/[0-9a-f]{24,}|[0-9a-f-]{36}/gi, ':id')
    .replace(/\/api\/messages\/[^/]+$/, '/api/messages/:id')
    .replace(/\/api\/convos\/[^/]+$/, '/api/convos/:id')
    .slice(0, 120) : 'unknown';
  const names = new Set(headerNames.map((name) => String(name).toLowerCase()));
  return {
    stage: typeof stage === 'string' ? stage.slice(0, 40) : 'unknown',
    method: typeof method === 'string' ? method.slice(0, 12) : 'UNKNOWN',
    route,
    status: Number.isInteger(status) ? status : null,
    authorization_present: names.has('authorization'),
    cookie_present: names.has('cookie'),
  };
}

function recordDiagnostic(rows, entry) {
  if (Array.isArray(rows) && rows.length < MAX_DIAGNOSTICS) rows.push(entry);
}

async function waitForSettledSnapshot(read, {attempts = 120, stableSamples = 3, pause = defaultPause} = {}) {
  let previous;
  let stable = 0;
  for (let index = 0; index < attempts; index += 1) {
    const value = await read();
    const encoded = JSON.stringify(value);
    if (encoded && encoded === previous) stable += 1;
    else stable = 1;
    if (stable >= stableSamples) return value;
    previous = encoded;
    await pause(500);
  }
  fail('ASSISTANT_NOT_SETTLED');
}

function defaultPause(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

function archiveRequest(conversationId) {
  if (typeof conversationId !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(conversationId)) fail('CONVERSATION_ID_REQUIRED');
  return {path: '/api/convos/archive', method: 'POST', body: {arg: {conversationId, isArchived: true}}};
}

function assertArchived(result, conversationId) {
  if (result?.status !== 200 || result?.json?.conversationId !== conversationId || result?.json?.isArchived !== true) {
    fail('ARCHIVE_READBACK_FAILED');
  }
  return true;
}

function structuralCounts(mode, answerValue) {
  const answer = normalizeMarkdown(answerValue);
  return {
    mode,
    matrix_rows: matrixRows(answer).length,
    attention_tables: count(answer, /^\| Needs attention \| Why \| Affected \|$/gm),
    plan_tables: count(answer, /^\| Priority \| Control \| Suggested change \| Execution \|$/gm),
    guardrails: answer.split(GUARDRAIL).length - 1,
  };
}

module.exports = {
  ALIASES,
  GUARDRAIL,
  MAX_DIAGNOSTICS,
  PROMPTS,
  archiveRequest,
  assertAnswerContract,
  assertArchived,
  assertNoInventedDetails,
  assertToolToAssistantBinding,
  digest,
  extractToolAnswer,
  normalizeMarkdown,
  persistedAssistantText,
  recordDiagnostic,
  safeDiagnostic,
  structuralCounts,
  waitForSettledSnapshot,
};
