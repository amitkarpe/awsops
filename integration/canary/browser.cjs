'use strict';
// Normal UI authentication only. Never export cookies, tokens or storage state.
const fs = require('node:fs');
const path = require('node:path');
const BASE = 'http://127.0.0.1:4311';
const PURPOSE = 'awsops-issue11-isolated-auth-canary';

function privateFile(file) {
  const info = fs.lstatSync(file);
  if (!info.isFile() || (info.mode & 0o077) !== 0 || fs.realpathSync(file) !== file ||
      (process.getuid && info.uid !== process.getuid())) throw Error('PRIVATE_STATE_REQUIRED');
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}
function localRoute(url) {
  try { return new URL(url).origin === BASE; } catch { return false; }
}
async function run(root) {
  if (!path.isAbsolute(root) || fs.realpathSync(root) !== root) throw Error('CANARY_ROOT_REQUIRED');
  const manifest = privateFile(path.join(root, 'manifest.json'));
  if (manifest.purpose !== PURPOSE || manifest.root !== root || manifest.model !== 'DISABLED' ||
      !Array.isArray(manifest.tools) || manifest.tools.length !== 0) throw Error('AUTH_ONLY_CANARY_REQUIRED');
  const login = privateFile(path.join(root, 'state/login.json'));
  process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(root, 'state/browser');
  const {chromium} = require(path.join(root, 'app/node_modules/playwright'));
  let browser;
  let page;
  const pageErrors = [];
  let stage = 'launch';
  const observations = [];
  let authenticated = false;
  try {
    browser = await chromium.launch({headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage']});
    const context = await browser.newContext();
    // The disposable browser only loads this isolated native application's origin.
    await context.route('**/*', route => localRoute(route.request().url()) ? route.continue() : route.abort());
    page = await context.newPage();
    page.on('pageerror', error => { if (pageErrors.length < 8) pageErrors.push(error.name); });
    page.setDefaultTimeout(30000);
    page.on('response', response => {
      const pathname = new URL(response.url()).pathname;
      if (pathname === '/api/auth/login' && response.status() === 200) authenticated = true;
      if (authenticated && pathname.startsWith('/api/')) {
        if (observations.length < 64) observations.push({route: pathname.replace(/[a-f0-9]{24,}|[a-f0-9-]{36}/g, '[id]').slice(0,100), status: response.status()});
      }
    });
    stage = 'login_page';
    await page.goto(BASE + '/login', {waitUntil: 'domcontentloaded'});
    stage = 'normal_login';
    await page.getByLabel('Email', {exact: true}).fill(login.email);
    await page.getByLabel('Password', {exact: true}).fill(login.password);
    const accepted = page.waitForResponse(r => new URL(r.url()).pathname === '/api/auth/login' && r.status() === 200);
    await page.getByTestId('login-button').click();
    await accepted;
    stage = 'native_application';
    await page.waitForURL(BASE + '/c/new');
    await page.waitForTimeout(2500);
    const history = observations.some(r => r.route === '/api/convos' && r.status === 200);
    const unauthorized = observations.some(r => r.status === 401 || r.status === 403);
    if (!authenticated || !history || unauthorized) throw Error('NATIVE_API_AUTH_NOT_PROVEN');
    return {version: 1, outcome: 'AUTH_PASS', normal_login: true, same_origin_history: true,
      observed_routes: observations, browser_auth_exported: false,
      native_decision: 'NOT_RUN', provider_readback: 'NOT_RUN', model: 'DISABLED'};
  } catch {
    return {version: 1, outcome: 'AUTH_BLOCKED', stage, normal_login: authenticated,
      observed_routes: observations, page_error_types: pageErrors,
      page_path: page ? new URL(page.url()).pathname.replace(/[a-f0-9]{24,}|[a-f0-9-]{36}/g, '[id]') : null,
      browser_auth_exported: false, native_decision: 'NOT_RUN'};
  } finally {
    login.password = '';
    if (browser) await browser.close();
  }
}
if (require.main === module) {
  run(process.argv[2]).then(result => {
    console.log(JSON.stringify(result));
    if (result.outcome !== 'AUTH_PASS') process.exitCode = 2;
  }).catch(() => { console.log('{"outcome":"AUTH_BLOCKED","stage":"private_config"}'); process.exitCode = 2; });
}
module.exports = {localRoute, privateFile, BASE};
