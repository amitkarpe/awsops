'use strict';
// Authenticated NEW sec2 browser acceptance for Issue #49.
// Reuses the proven PR #13/old PR #192 mechanics: normal login, same-origin
// browser activity, settled rendered state, exact conversation binding and Archive cleanup.
// Never export cookies, bearer tokens or browser storage state.

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const contract = require('./browser_contract.cjs');

const ORIGIN = (process.env.AWSOPS_SEC2_ORIGIN || 'https://sec2.astromedicomp.org').replace(/\/$/, '');
const AGENT_NAME = 'AWS Ops Compliance Agent';
const TOOL_FRAGMENT = 'ask_compliance_agent';

function privateJson(file) {
  const info = fs.lstatSync(file);
  if (!info.isFile() || (info.mode & 0o077) !== 0 || fs.realpathSync(file) !== file ||
      (process.getuid && info.uid !== process.getuid())) throw Error('PRIVATE_STATE_REQUIRED');
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function privateRoot(root) {
  if (!path.isAbsolute(root) || fs.realpathSync(root) !== root) throw Error('PRIVATE_ROOT_REQUIRED');
  const info = fs.statSync(root);
  if (!info.isDirectory() || (info.mode & 0o077) !== 0 ||
      (process.getuid && info.uid !== process.getuid())) throw Error('PRIVATE_ROOT_REQUIRED');
  return root;
}

function localRoute(url) {
  try { return new URL(url).origin === ORIGIN; } catch { return false; }
}

function sha256File(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function writePrivateJson(file, value) {
  const staged = file + '.stage';
  fs.writeFileSync(staged, JSON.stringify(value, null, 2) + '\n', {mode: 0o600, flag: 'wx'});
  fs.renameSync(staged, file);
}

async function api(page, urlPath, method = 'GET', body) {
  return page.evaluate(async ({urlPath, method, body}) => {
    const refresh = await fetch('/api/auth/refresh', {
      method: 'POST',
      credentials: 'include',
      headers: {'Content-Type': 'application/json'},
      body: '{}',
    });
    if (!refresh.ok) throw Error('AUTH_REFRESH_FAILED');
    const auth = await refresh.json();
    if (typeof auth?.token !== 'string' || auth.token.length < 16) throw Error('AUTH_TOKEN_MISSING');
    const headers = {Authorization: 'Bearer ' + auth.token};
    const init = {method, credentials: 'include', headers};
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
    const response = await fetch(urlPath, init);
    const text = await response.text();
    let json = null;
    try { json = text ? JSON.parse(text) : null; } catch {}
    return {ok: response.ok, status: response.status, json};
  }, {urlPath, method, body});
}

async function openAgentBuilder(page, mark = () => {}) {
  mark('agent_page');
  await page.goto(ORIGIN + '/c/new', {waitUntil: 'domcontentloaded'});
  mark('agent_form_probe');
  const form = page.getByRole('form', {name: 'Agent configuration form'});
  const visible = await form.waitFor({state: 'visible', timeout: 1500}).then(() => true).catch(() => false);
  if (!visible) {
    mark('agent_builder_button');
    const button = page.getByRole('button', {name: 'Agent Builder', exact: true});
    await button.waitFor({state: 'visible', timeout: 15000});
    if (!(await button.isEnabled())) throw Error('AGENT_BUILDER_DISABLED');
    if (await button.getAttribute('aria-pressed') !== 'true') await button.click();
  }
  mark('agent_form_wait');
  await form.waitFor({state: 'visible', timeout: 30000});
  return form;
}

async function selectAgent(page, mark = () => {}) {
  const form = await openAgentBuilder(page, mark);
  mark('agent_combobox');
  const agentSelect = form.getByRole('combobox', {name: 'Agent', exact: true});
  await agentSelect.waitFor({state: 'visible', timeout: 30000});
  await agentSelect.click();
  mark('agent_option');
  const option = page.getByRole('option', {name: AGENT_NAME, exact: true});
  await option.waitFor({state: 'visible', timeout: 30000});
  await option.click();

  mark('agent_name');
  const nameField = form.getByLabel('Agent name');
  await nameField.waitFor({state: 'visible', timeout: 30000});
  let selected = '';
  for (let attempt = 0; attempt < 120; attempt += 1) {
    selected = await nameField.inputValue();
    if (selected === AGENT_NAME) break;
    await page.waitForTimeout(250);
  }
  if (selected !== AGENT_NAME) throw Error('AGENT_SELECTION_MISMATCH');

  mark('agent_builder_back');
  await form.getByRole('button', {name: 'Back to builder', exact: true}).click();
  mark('agent_submit');
  await form.getByRole('button', {name: 'Select Agent', exact: true}).click();
}

async function waitForConversation(page) {
  await page.waitForURL(/\/c\/(?!new)[A-Za-z0-9_-]+$/, {timeout: 60000});
  const id = new URL(page.url()).pathname.replace('/c/', '');
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(id)) throw Error('CONVERSATION_ID_REQUIRED');
  return id;
}

async function settledTurn(page) {
  return contract.waitForSettledSnapshot(async () => {
    const messages = await page.getByTestId('message-body').allInnerTexts();
    const stopVisible = await page.locator('button[aria-label*="Stop generating" i]:visible').count() > 0;
    const toolCalls = page.locator('[data-testid="tool-call"]');
    const toolCount = await toolCalls.count();
    let outputCount = 0;
    let toolCallId = null;
    let toolText = '';
    let outputText = '';
    if (toolCount === 1) {
      toolCallId = await toolCalls.first().getAttribute('data-tool-call-id');
      toolText = await toolCalls.first().innerText().catch(() => '');
      if (toolCallId) {
        const output = page.locator('[data-tool-call-output-id="' + toolCallId + '"]');
        outputCount = await output.count();
        if (outputCount === 1) outputText = (await output.first().textContent()) || '';
      }
    }
    return {
      messageCount: messages.length,
      lastMessage: messages.at(-1) || '',
      stopVisible,
      toolCount,
      outputCount,
      toolCallId,
      toolText,
      outputText,
    };
  }, {
    pause: (ms) => page.waitForTimeout(ms),
    isReady: (value) => !value.stopVisible && value.messageCount >= 2 &&
      value.toolCount === 1 && value.outputCount === 1 &&
      typeof value.outputText === 'string' && value.outputText.includes(contract.GUARDRAIL),
  });
}

async function archiveConversation(page, conversationId) {
  const request = contract.archiveRequest(conversationId);
  const archived = await api(page, request.path, request.method, request.body);
  contract.assertArchived(archived, conversationId);
  const readback = await api(page, '/api/convos/' + encodeURIComponent(conversationId));
  contract.assertArchived(readback, conversationId);
  return true;
}

async function runPrompt(page, root, mode, diagnostics, pageErrors, mark = () => {}) {
  const prompt = contract.PROMPTS[mode];
  if (!prompt) throw Error('MODE_REQUIRED');
  mark(mode + '_agent_select');
  await selectAgent(page, (step) => mark(mode + '_' + step));

  mark(mode + '_composer');
  const input = page.getByRole('textbox', {name: 'Message input'});
  await input.waitFor({state: 'visible', timeout: 30000});
  await input.fill(prompt);
  const admitted = page.waitForResponse((response) => {
    const request = response.request();
    return request.method() === 'POST' && new URL(response.url()).pathname === '/api/agents/chat' &&
      [200, 201].includes(response.status());
  }, {timeout: 60000});
  mark(mode + '_send');
  await input.press('Enter');
  await admitted;

  mark(mode + '_conversation');
  const conversationId = await waitForConversation(page);
  let archived = false;
  try {
    mark(mode + '_settle');
    const settled = await settledTurn(page);
    if (settled.stopVisible || settled.toolCount !== 1 || settled.outputCount !== 1 ||
        typeof settled.toolCallId !== 'string' || !settled.toolText.includes(TOOL_FRAGMENT)) {
      throw Error('SINGLE_TOOL_BINDING_REQUIRED');
    }

    mark(mode + '_history');
    const historyResult = await api(page, '/api/messages/' + encodeURIComponent(conversationId));
    if (!historyResult.ok || !Array.isArray(historyResult.json)) throw Error('MESSAGE_READBACK_FAILED');
    const binding = contract.assertToolToAssistantBinding(mode, settled.outputText, historyResult.json);
    const counts = contract.structuralCounts(mode, binding.answer);

    mark(mode + '_evidence');
    const evidenceDir = path.join(root, 'evidence');
    fs.mkdirSync(evidenceDir, {recursive: true, mode: 0o700});
    fs.chmodSync(evidenceDir, 0o700);
    const screenshot = path.join(evidenceDir, 'issue49-' + mode + '.png');
    await page.screenshot({path: screenshot, fullPage: true});
    fs.chmodSync(screenshot, 0o600);

    mark(mode + '_archive');
    archived = await archiveConversation(page, conversationId);
    const manifest = {
      version: 1,
      mode,
      reviewed_head: process.env.AWSOPS_REVIEWED_HEAD || 'UNSET',
      prompt_digest: contract.digest(prompt),
      conversation_digest: contract.digest(conversationId),
      answer_digest: binding.digest,
      screenshot_sha256: sha256File(screenshot),
      structure: counts,
      page_error_types: [...new Set(pageErrors)].slice(0, 8),
      diagnostic_count: diagnostics.length,
      conversation_archived: archived,
      browser_auth_exported: false,
    };
    const manifestFile = path.join(evidenceDir, 'issue49-' + mode + '.json');
    writePrivateJson(manifestFile, manifest);
    return manifest;
  } finally {
    if (!archived) {
      try { await archiveConversation(page, conversationId); } catch {}
    }
  }
}

async function run(rootValue) {
  const root = privateRoot(rootValue);
  const login = privateJson(path.join(root, 'state', 'login.json'));
  if (typeof login.email !== 'string' || typeof login.password !== 'string' ||
      !login.email || !login.password) throw Error('LOGIN_REQUIRED');

  const modulePath = process.env.AWSOPS_PLAYWRIGHT_MODULE;
  if (typeof modulePath !== 'string' || !path.isAbsolute(modulePath)) throw Error('PLAYWRIGHT_MODULE_REQUIRED');
  if (process.env.AWSOPS_PLAYWRIGHT_BROWSERS_PATH) {
    process.env.PLAYWRIGHT_BROWSERS_PATH = process.env.AWSOPS_PLAYWRIGHT_BROWSERS_PATH;
  }
  const {chromium} = require(modulePath);
  const diagnostics = [];
  const pageErrors = [];
  let browser;
  let page;
  let stage = 'launch';
  try {
    const args = ['--no-sandbox', '--disable-dev-shm-usage'];
    if (process.env.AWSOPS_SEC2_RESOLVE_LOCAL === '1') {
      args.push('--host-resolver-rules=MAP ' + new URL(ORIGIN).hostname + ' 127.0.0.1');
    }
    browser = await chromium.launch({headless: true, args});
    const context = await browser.newContext();
    await context.route('**/*', (route) => localRoute(route.request().url()) ? route.continue() : route.abort());
    page = await context.newPage();
    page.setDefaultTimeout(30000);
    page.on('pageerror', (error) => { if (pageErrors.length < 8) pageErrors.push(error.name); });
    page.on('request', (request) => contract.recordDiagnostic(diagnostics, contract.safeDiagnostic({
      stage,
      method: request.method(),
      url: request.url(),
      status: null,
      headerNames: Object.keys(request.headers()),
    })));
    page.on('response', (response) => {
      const item = diagnostics.at(-1);
      if (item && item.route === contract.safeDiagnostic({
        stage, method: response.request().method(), url: response.url(), status: response.status(),
        headerNames: Object.keys(response.request().headers()),
      }).route && item.status === null) item.status = response.status();
    });

    stage = 'login';
    await page.goto(ORIGIN + '/login', {waitUntil: 'domcontentloaded'});
    await page.getByLabel('Email', {exact: true}).fill(login.email);
    await page.getByLabel('Password', {exact: true}).fill(login.password);
    const accepted = page.waitForResponse((response) => new URL(response.url()).pathname === '/api/auth/login' &&
      response.status() === 200, {timeout: 60000});
    await page.getByTestId('login-button').click();
    await accepted;
    await page.waitForURL(ORIGIN + '/c/new', {timeout: 60000});

    const outcomes = [];
    for (const mode of ['status', 'explain', 'plan']) {
      stage = mode;
      outcomes.push(await runPrompt(page, root, mode, diagnostics, pageErrors, (value) => { stage = value; }));
    }
    return {
      version: 1,
      outcome: 'PASS',
      modes: outcomes.map((item) => ({
        mode: item.mode,
        answer_digest: item.answer_digest,
        screenshot_sha256: item.screenshot_sha256,
        structure: item.structure,
        conversation_archived: item.conversation_archived,
      })),
      one_read_only_tool: true,
      browser_auth_exported: false,
    };
  } catch (error) {
    return {
      version: 1,
      outcome: 'BLOCKED',
      stage,
      error_type: error?.name || 'Error',
      error_code: /^[A-Z0-9_]+$/.test(String(error?.message || '')) ? error.message : 'BROWSER_ACCEPTANCE_FAILED',
      browser_auth_exported: false,
    };
  } finally {
    login.password = '';
    if (browser) await browser.close();
  }
}

if (require.main === module) {
  run(process.argv[2]).then((result) => {
    console.log(JSON.stringify(result));
    if (result.outcome !== 'PASS') process.exitCode = 2;
  }).catch(() => {
    console.log('{"outcome":"BLOCKED","stage":"private_config","browser_auth_exported":false}');
    process.exitCode = 2;
  });
}

module.exports = {api, localRoute, privateJson, run};
