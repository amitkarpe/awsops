'use strict';
// Authenticated NEW sec2 UI acceptance. Tokens and browser state never leave page.evaluate.
const fs = require('node:fs');
const path = require('node:path');
const contract = require('./browser_contract.cjs');

const PURPOSE = 'awsops-issue49-compliance-agent-browser';
const BASE = 'https://sec2.astromedicomp.org';
const AGENT = 'AWS Ops Compliance Agent';

function privateJson(file) {
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || (stat.mode & 0o077) !== 0 || fs.realpathSync(file) !== file ||
      (process.getuid && stat.uid !== process.getuid())) throw Error('PRIVATE_STATE_REQUIRED');
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}
function privateRoot(root) {
  if (!path.isAbsolute(root) || fs.realpathSync(root) !== root) throw Error('PRIVATE_ROOT_REQUIRED');
  const stat = fs.statSync(root);
  if (!stat.isDirectory() || (stat.mode & 0o077) !== 0 || (process.getuid && stat.uid !== process.getuid()))
    throw Error('PRIVATE_ROOT_REQUIRED');
  return root;
}
function localRoute(url) { try { return new URL(url).origin === BASE; } catch { return false; } }
function writePrivate(file, value) {
  const staged = `${file}.stage`;
  fs.writeFileSync(staged, JSON.stringify(value, null, 2) + '\n', {mode: 0o600, flag: 'wx'});
  fs.renameSync(staged, file);
}
function ensurePrivateDir(directory) {
  if (!fs.existsSync(directory)) fs.mkdirSync(directory, {mode: 0o700});
  const stat = fs.statSync(directory);
  if (!stat.isDirectory() || (stat.mode & 0o077) !== 0 || (process.getuid && stat.uid !== process.getuid()))
    throw Error('PRIVATE_EVIDENCE_DIR_REQUIRED');
}

async function requireVisible(locator, code, timeout = 30000) {
  try {
    await locator.waitFor({state: 'visible', timeout});
  } catch (error) {
    if (error?.name === 'TimeoutError') throw Error(code);
    throw error;
  }
}
async function api(page, urlPath, method = 'GET', body) {
  return page.evaluate(async ({urlPath, method, body}) => {
    const refresh = await fetch('/api/auth/refresh', {method: 'POST', credentials: 'include',
      headers: {'Content-Type': 'application/json'}, body: '{}'});
    if (!refresh.ok) throw Error('AUTH_REFRESH_FAILED');
    const auth = await refresh.json();
    if (typeof auth?.token !== 'string' || auth.token.length < 16) throw Error('AUTH_TOKEN_MISSING');
    const headers = {Authorization: `Bearer ${auth.token}`};
    const init = {method, credentials: 'include', headers};
    if (body !== undefined) { headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(body); }
    const response = await fetch(urlPath, init);
    const text = await response.text();
    let json = null; try { json = text ? JSON.parse(text) : null; } catch {}
    return {ok: response.ok, status: response.status, json};
  }, {urlPath, method, body});
}

async function authenticate(page, root, mode) {
  if (mode === 'cdp') {
    await page.goto(`${BASE}/c/new`, {waitUntil: 'domcontentloaded'});
  } else {
    const login = privateJson(path.join(root, 'state/login.json'));
    try {
      await page.goto(`${BASE}/login`, {waitUntil: 'domcontentloaded'});
      await page.getByLabel('Email', {exact: true}).fill(login.email);
      await page.getByLabel('Password', {exact: true}).fill(login.password);
      const accepted = page.waitForResponse((response) =>
        new URL(response.url()).pathname === '/api/auth/login' && response.status() === 200);
      await page.getByTestId('login-button').click();
      await accepted;
      await page.waitForURL(`${BASE}/c/new`);
    } finally { login.password = ''; }
  }
  const user = await api(page, '/api/user');
  if (!user.ok || typeof user.json?.id !== 'string') throw Error('NORMAL_AUTH_REQUIRED');
}

async function exactAgent(page) {
  const listed = await api(page, `/api/agents?search=${encodeURIComponent(AGENT)}&limit=10&requiredPermission=2`);
  const matches = listed.ok && Array.isArray(listed.json?.data)
    ? listed.json.data.filter((agent) => agent?.name === AGENT) : [];
  if (matches.length !== 1) throw Error('EXACT_AGENT_REQUIRED');
  const agentId = matches[0].id ?? matches[0]._id;
  if (typeof agentId !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(agentId))
    throw Error('EXACT_AGENT_ID_REQUIRED');
  const detail = await api(page, `/api/agents/${encodeURIComponent(agentId)}/expanded`);
  const agent = detail.ok ? (detail.json?.agent ?? detail.json) : null;
  if (!agent || agent.name !== AGENT) throw Error('EXACT_AGENT_DETAIL_REQUIRED');
  const tools = agent.tools;
  if (!Array.isArray(tools) || JSON.stringify(tools) !== JSON.stringify([contract.TOOL]))
    throw Error('ONE_READ_ONLY_TOOL_REQUIRED');
  for (const field of ['actions', 'action_ids', 'agentActions']) {
    if (Array.isArray(agent[field]) && agent[field].length) throw Error('ZERO_ACTIONS_REQUIRED');
  }
  return agent;
}

async function selectAgent(page) {
  if (new URL(page.url()).pathname !== '/c/new') {
    await page.goto(`${BASE}/c/new`, {waitUntil: 'domcontentloaded'});
  }
  const selector = page.getByTestId('model-selector-button');
  await requireVisible(selector, 'MODEL_SELECTOR_REQUIRED');
  if ((await selector.innerText()).trim() === AGENT) return;
  await selector.click();
  const search = page.locator('#model-search');
  await requireVisible(search, 'MODEL_SEARCH_REQUIRED', 15000);
  await search.fill(AGENT);
  await page.waitForTimeout(800);
  const option = page.getByRole('option').filter({hasText: AGENT});
  if (await option.count() !== 1) throw Error('EXACT_AGENT_OPTION_REQUIRED');
  await requireVisible(option, 'AGENT_OPTION_VISIBLE_REQUIRED', 15000);
  try {
    await option.click({timeout: 15000});
  } catch (error) {
    if (error?.name === 'TimeoutError') throw Error('AGENT_OPTION_CLICK_TIMEOUT');
    throw error;
  }
  const deadline = Date.now() + 30000;
  while ((await selector.innerText()).trim() !== AGENT && Date.now() < deadline) {
    await page.waitForTimeout(250);
  }
  if ((await selector.innerText()).trim() !== AGENT) throw Error('AGENT_SELECTION_MISMATCH');
}

async function renderedSnapshot(page) {
  const messages = page.locator('.message-content');
  if (await messages.count() < 1) return {ready: false};
  const assistant = messages.last();
  const text = (await assistant.innerText()).trim();
  const tables = await assistant.locator('table').evaluateAll((items) => items.map((table) =>
    [...table.querySelectorAll('tr')].map((row) => [...row.querySelectorAll('th,td')].map((cell) =>
      (cell.textContent ?? '').trim()))));
  const plainGuardrail = '🛡️ Read-only: No AWS changes executed.';
  const guardrailCount = text.split(plainGuardrail).length - 1;
  const offset = text.lastIndexOf(plainGuardrail);
  return {ready: true, text, tables, guardrailText: offset < 0 ? '' : plainGuardrail,
    guardrailCount, trailingText: offset < 0 ? text : text.slice(offset + plainGuardrail.length).trim(),
    streaming: await assistant.locator('.result-streaming').count()};
}

async function acceptPrompt(page, mode, evidenceDir, gitHead, registerConversation) {
  await selectAgent(page);
  const input = page.getByRole('textbox', {name: 'Message input'});
  await requireVisible(input, 'MESSAGE_INPUT_REQUIRED');
  await input.fill(contract.MODES[mode]);
  const admission = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname;
    const isAgentsChat = pathname === '/api/agents/chat' || pathname.startsWith('/api/agents/chat/');
    return response.request().method() === 'POST' && isAgentsChat &&
      !pathname.endsWith('/abort') && response.status() === 200;
  }, {timeout: 45000}).catch((error) => {
    if (error?.name === 'TimeoutError') throw Error('AGENT_CHAT_ADMISSION_TIMEOUT');
    throw error;
  });
  await input.press('Enter');
  const admitted = await admission;
  let start;
  try {
    start = await admitted.json();
  } catch {
    throw Error('AGENT_CHAT_ADMISSION_JSON_REQUIRED');
  }
  const conversationId = start?.conversationId;
  if (typeof conversationId !== 'string' || conversationId === 'new' ||
      !/^[A-Za-z0-9_-]{1,128}$/.test(conversationId)) {
    throw Error('PERSISTED_CONVERSATION_REQUIRED');
  }
  registerConversation(conversationId);
  const snapshot = await contract.waitForSettledSnapshot(async () => {
    const persisted = await api(page, `/api/messages/${encodeURIComponent(conversationId)}`);
    if (!persisted.ok || !Array.isArray(persisted.json)) return {ready: false};
    let binding; try { binding = contract.persistedBinding(persisted.json); } catch { return {ready: false}; }
    const rendered = await renderedSnapshot(page);
    if (!rendered.ready || rendered.streaming) return {ready: false};
    return {ready: true, assistantText: binding.assistantText, toolCallId: binding.toolCallId,
      toolResult: binding.toolResult, rendered};
  }, {attempts: 240, pause: (ms) => page.waitForTimeout(ms)});
  if (!snapshot.ready) throw Error('SETTLED_OUTPUT_REQUIRED');
  const toolCall = page.locator(`[data-testid="tool-call"][data-tool-call-id="${snapshot.toolCallId}"]`);
  const toolOutput = page.locator(`[data-tool-call-output-id="${snapshot.toolCallId}"]`);
  if (await toolCall.count() !== 1 || await toolOutput.count() !== 1 ||
      !(await toolCall.innerText()).includes(contract.LOGICAL_TOOL)) throw Error('TOOL_DOM_BINDING_REQUIRED');
  const proof = contract.assertAnswer(mode, snapshot.toolResult, snapshot.rendered);
  const screenshot = path.join(evidenceDir, `${mode}.png`);
  await page.locator('.message-content').last().screenshot({path: screenshot}); fs.chmodSync(screenshot, 0o600);
  const screenshotSha = contract.sha256(fs.readFileSync(screenshot));
  const archive = contract.archiveRequest(conversationId);
  contract.assertArchived(await api(page, archive.path, archive.method, archive.body), conversationId);
  contract.assertArchived(await api(page, `/api/convos/${encodeURIComponent(conversationId)}`), conversationId);
  return {...proof, prompt: contract.MODES[mode], conversationDigest: contract.sha256(conversationId),
    toolCallDigest: contract.sha256(snapshot.toolCallId), screenshot: `${mode}.png`, screenshotSha,
    archived: true, gitHead};
}

async function run(root) {
  root = privateRoot(root);
  const manifest = privateJson(path.join(root, 'manifest.json'));
  if (manifest.purpose !== PURPOSE || manifest.base_url !== BASE || manifest.agent_name !== AGENT ||
      typeof manifest.git_head !== 'string' || !/^[a-f0-9]{40}$/.test(manifest.git_head) ||
      !['launch', 'cdp'].includes(manifest.browser_mode) ||
      ![undefined, true, false].includes(manifest.loopback_origin)) throw Error('BROWSER_MANIFEST_REQUIRED');
  const playwright = require(path.join(root, 'app/node_modules/playwright'));
  const evidenceRoot = path.join(root, 'evidence'); ensurePrivateDir(evidenceRoot);
  const runDir = path.join(evidenceRoot, `issue49-${Date.now()}`);
  fs.mkdirSync(runDir, {recursive: false, mode: 0o700});
  let browser; let context; let page; let attached = false; let stage = 'launch';
  const diagnostics = []; const diagnosticByRequest = new WeakMap(); const conversations = [];
  const consoleTypes = []; const pageErrorTypes = [];
  try {
    if (manifest.browser_mode === 'cdp') {
      if (typeof manifest.cdp_endpoint !== 'string' || !/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(manifest.cdp_endpoint))
        throw Error('LOOPBACK_CDP_REQUIRED');
      browser = await playwright.chromium.connectOverCDP(manifest.cdp_endpoint); attached = true;
      context = browser.contexts()[0]; if (!context) throw Error('CDP_CONTEXT_REQUIRED');
    } else {
      const launchArgs = ['--no-sandbox', '--disable-dev-shm-usage'];
      if (manifest.loopback_origin === true) launchArgs.push('--host-resolver-rules=MAP sec2.astromedicomp.org 127.0.0.1');
      browser = await playwright.chromium.launch({headless: true, args: launchArgs});
      context = await browser.newContext();
    }
    page = await context.newPage(); page.setDefaultTimeout(30000);
    await page.route('**/*', (route) => localRoute(route.request().url()) ? route.continue() : route.abort());
    page.on('console', (message) => {
      if (consoleTypes.length < 16 && ['warning', 'error'].includes(message.type())) consoleTypes.push(message.type());
    });
    page.on('pageerror', (error) => {
      if (pageErrorTypes.length < 16) pageErrorTypes.push(error?.name === 'Error' ? 'Error' : 'BrowserError');
    });
    page.on('request', (request) => {
      const row = contract.safeDiagnostic({stage, method: request.method(), url: request.url(), status: null,
        headerNames: Object.keys(request.headers()), base: BASE});
      contract.recordDiagnostic(diagnostics, row); diagnosticByRequest.set(request, row);
    });
    page.on('response', (response) => {
      const row = diagnosticByRequest.get(response.request()); if (row) row.status = response.status();
    });
    stage = 'authenticate'; await authenticate(page, root, manifest.browser_mode);
    stage = 'agent_contract'; await exactAgent(page);
    const results = [];
    for (const mode of Object.keys(contract.MODES)) {
      stage = mode; const result = await acceptPrompt(page, mode, runDir, manifest.git_head,
        (conversationId) => conversations.push(conversationId));
      results.push(result);
    }
    const evidence = {version: 1, outcome: 'COMPLIANCE_UI_PASS', git_head: manifest.git_head,
      agent: AGENT, tool_count: 1, action_count: 0, browser_auth_exported: false,
      storage_state_exported: false, results, console_types: consoleTypes,
      page_error_types: pageErrorTypes, diagnostics};
    writePrivate(path.join(runDir, 'manifest.json'), evidence);
    return evidence;
  } catch (error) {
    if (page) {
      for (const conversationId of conversations) {
        try { const archive = contract.archiveRequest(conversationId);
          await api(page, archive.path, archive.method, archive.body); } catch {}
      }
    }
    const reason = typeof error?.message === 'string' && /^[A-Z0-9_]{3,80}$/.test(error.message)
      ? error.message : error?.name === 'TimeoutError' ? 'BROWSER_TIMEOUT' : 'BROWSER_RUNTIME_BLOCKED';
    return {version: 1, outcome: 'COMPLIANCE_UI_BLOCKED', stage, reason,
      browser_auth_exported: false, storage_state_exported: false,
      conversations_created: conversations.length, console_types: consoleTypes,
      page_error_types: pageErrorTypes, diagnostics};
  } finally {
    if (page) await page.close().catch(() => {});
    if (browser && !attached) await browser.close().catch(() => {});
  }
}

if (require.main === module) {
  run(process.argv[2]).then((result) => { console.log(JSON.stringify(result));
    if (result.outcome !== 'COMPLIANCE_UI_PASS') process.exitCode = 2; })
    .catch(() => { console.log('{"outcome":"COMPLIANCE_UI_BLOCKED","stage":"private_config"}'); process.exitCode = 2; });
}
module.exports = {AGENT, BASE, PURPOSE, api, localRoute, privateJson, run};
