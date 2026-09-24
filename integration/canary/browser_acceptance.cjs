'use strict';
// Real native-browser Reject-only canary. Auth tokens never leave page.evaluate.
const fs=require('node:fs');
const path=require('node:path');
const BASE='http://127.0.0.1:4311';
const PURPOSE='awsops-issue11-isolated-auth-canary';
const TOOL='decide_s3_ssl_reject_only_mcp_awsops';
const LOGICAL_TOOL='decide_s3_ssl_reject_only';
const SERVER_TOOL='sys__server__sys_mcp_awsops';
const PROVIDER='awsops_canary_fixture';
const MODEL='awsops-canary-fixed';

function privateJson(file){
  const st=fs.lstatSync(file);
  if(!st.isFile()||(st.mode&0o077)!==0||fs.realpathSync(file)!==file||
     (process.getuid&&st.uid!==process.getuid()))throw Error('PRIVATE_STATE_REQUIRED');
  return JSON.parse(fs.readFileSync(file,'utf8'));
}
function localRoute(url){try{return new URL(url).origin===BASE}catch{return false}}
function writePrivate(file,value){
  const staged=file+'.stage';
  fs.writeFileSync(staged,JSON.stringify(value),{mode:0o600,flag:'wx'});
  fs.renameSync(staged,file);
}
async function api(page,urlPath,method='GET',body){
  return page.evaluate(async ({urlPath,method,body})=>{
    const refresh=await fetch('/api/auth/refresh',{method:'POST',credentials:'include',
      headers:{'Content-Type':'application/json'},body:'{}'});
    if(!refresh.ok)throw Error('AUTH_REFRESH_FAILED');
    const auth=await refresh.json();
    if(typeof auth?.token!=='string'||auth.token.length<16)throw Error('AUTH_TOKEN_MISSING');
    const headers={Authorization:'Bearer '+auth.token};
    const init={method,credentials:'include',headers};
    if(body!==undefined){headers['Content-Type']='application/json';init.body=JSON.stringify(body)}
    const response=await fetch(urlPath,init);
    const text=await response.text();
    let json=null;try{json=text?JSON.parse(text):null}catch{}
    return {ok:response.ok,status:response.status,json};
  },{urlPath,method,body});
}
async function openAgentBuilder(page){
  await page.goto(BASE+'/c/new',{waitUntil:'domcontentloaded'});
  const form=page.getByRole('form',{name:'Agent configuration form'});
  const visible=await form.waitFor({state:'visible',timeout:1500}).then(()=>true).catch(()=>false);
  if(!visible){
    const button=page.getByRole('button',{name:'Agent Builder'});
    await button.waitFor({state:'visible'});
    if(await button.getAttribute('aria-pressed')!=='true')await button.click();
  }
  await form.waitFor({state:'visible'});return form;
}
async function run(root){
  if(!path.isAbsolute(root)||fs.realpathSync(root)!==root)throw Error('CANARY_ROOT_REQUIRED');
  const manifest=privateJson(path.join(root,'manifest.json'));
  if(manifest.purpose!==PURPOSE||manifest.model!=='DETERMINISTIC_FIXTURE'||
     JSON.stringify(manifest.tools)!==JSON.stringify([TOOL]))throw Error('CANARY_MANIFEST_REQUIRED');
  const login=privateJson(path.join(root,'state/login.json'));
  const python=process.env.AWSOPS_CANARY_PYTHON;
  if(typeof python!=='string'||!path.isAbsolute(python))throw Error('CANARY_PYTHON_REQUIRED');
  const pythonLink=fs.lstatSync(python), pythonTarget=fs.statSync(fs.realpathSync(python));
  const pythonParent=fs.statSync(path.dirname(python));
  if(!(pythonLink.isFile()||pythonLink.isSymbolicLink())||!pythonTarget.isFile()||
     (pythonTarget.mode&0o111)===0||(pythonTarget.mode&0o022)!==0||(pythonParent.mode&0o022)!==0)
    throw Error('CANARY_PYTHON_REQUIRED');
  process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(root,'state/browser');
  const {chromium}=require(path.join(root,'app/node_modules/playwright'));
  let browser,page,agentId,conversationId;
  let stage='launch';
  try{
    browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
    const context=await browser.newContext();
    await context.route('**/*',route=>localRoute(route.request().url())?route.continue():route.abort());
    page=await context.newPage();page.setDefaultTimeout(30000);
    stage='login';
    await page.goto(BASE+'/login',{waitUntil:'domcontentloaded'});
    await page.getByLabel('Email',{exact:true}).fill(login.email);
    await page.getByLabel('Password',{exact:true}).fill(login.password);
    const accepted=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/auth/login'&&r.status()===200);
    await page.getByTestId('login-button').click();await accepted;
    await page.waitForURL(BASE+'/c/new');
    stage='tool_ready';
    let tools;
    for(let i=0;i<20;i++){
      const r=await api(page,'/api/mcp/tools');
      if(r.ok && r.json?.servers?.awsops?.tools?.some(t=>t.pluginKey===TOOL)){tools=r.json;break}
      await page.waitForTimeout(500);
    }
    if(!tools)throw Error('MCP_TOOL_NOT_READY');

    stage='agent_create';
    const name='AWS Ops Reject Canary '+Date.now();
    const created=await api(page,'/api/agents','POST',{
      name,description:'Disposable Reject-only native acceptance agent.',
      instructions:'Call the provided S3 TLS decision tool exactly once. Never request or perform remediation.',
      provider:PROVIDER,model:MODEL,tools:[SERVER_TOOL,TOOL],
    });
    if(!created.ok||typeof created.json?.id!=='string')throw Error('AGENT_CREATE_FAILED');
    agentId=created.json.id;

    const native={
      version:1,enabled:true,agent_id:agentId,python,
      source_root:path.join(root,'awsops'),database:path.join(root,'state/receipt.sqlite3'),
    };
    writePrivate(path.join(root,'state/native.json'),native);

    stage='agent_select';
    const form=await openAgentBuilder(page);
    await form.getByRole('combobox',{name:'Agent',exact:true}).click();
    await page.getByRole('option',{name}).click();
    await form.getByLabel('Agent name').waitFor({state:'visible'});
    await form.getByRole('button',{name:'Select Agent'}).click();

    stage='send';
    const input=page.getByRole('textbox',{name:'Message input'});
    await input.fill('Run the isolated s3_ssl Reject-only canary now.');
    const admission=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/agents/chat'&&r.status()===200);
    await input.press('Enter');await admission;
    await page.waitForURL(/\/c\/(?!new)/,{timeout:15000});
    conversationId=new URL(page.url()).pathname.replace('/c/','');

    stage='approval_card';
    const card=page.getByTestId('tool-approval').first();
    await card.waitFor({state:'visible',timeout:30000});
    const buttons={
      reject:await card.getByRole('button',{name:'Reject',exact:true}).count(),
      approve:await card.getByRole('button',{name:'Approve',exact:true}).count(),
      edit:await card.getByRole('button',{name:'Edit',exact:true}).count(),
      respond:await card.getByRole('button',{name:'Respond',exact:true}).count(),
    };
    if(buttons.reject!==1||buttons.approve||buttons.edit||buttons.respond)throw Error('NOT_REJECT_ONLY');
    const submit=card.getByRole('button',{name:'Submit',exact:true});
    await card.getByRole('button',{name:'Reject',exact:true}).click();
    const reason=card.getByRole('textbox',{name:'Reject'});
    if(await reason.count())await reason.fill('isolated canary reject');
    await submit.waitFor({state:'visible'});

    stage='reject_resume';
    const reqWait=page.waitForRequest(r=>r.method()==='POST'&&new URL(r.url()).pathname==='/api/agents/chat/resume');
    const resWait=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/agents/chat/resume');
    await submit.click();
    const [request,response]=await Promise.all([reqWait,resWait]);
    if(response.status()!==200)throw Error('RESUME_FAILED');
    const body=request.postDataJSON();
    const choice=body?.decisions?.[0];
    if(body?.agent_id!==agentId||body?.conversationId!==conversationId||body?.endpoint!=='agents'||
       choice?.decision!=='reject'||typeof choice?.tool_call_id!=='string'||!Number.isSafeInteger(body?.generationCreatedAt))
      throw Error('UNEXPECTED_REJECT_BODY');

    stage='binding';
    const u=await api(page,'/api/user');
    if(!u.ok||typeof u.json?.id!=='string')throw Error('USER_ID_UNAVAILABLE');
    const tenant=u.json.tenantId==null?'system:single-tenant':'tenant:'+u.json.tenantId;
    writePrivate(path.join(root,'state/decision-binding.json'),{
      principal_id:u.json.id,tenant_id:tenant,conversation_id:conversationId,
      action_id:body.actionId,generation_id:String(body.generationCreatedAt),
      tool_call_id:choice.tool_call_id,tool:LOGICAL_TOOL,
    });

    stage='completion';
    await page.getByText('Canary decision returned. No remediation was requested. Verify the independent receipt and readback evidence.',
      {exact:true}).waitFor({state:'visible',timeout:30000});
    const dispatchFile=path.join(root,'state/dispatch-attempts.jsonl');
    const dispatchAttempts=fs.existsSync(dispatchFile)?fs.readFileSync(dispatchFile,'utf8').split('\n').filter(Boolean).length:0;
    if(dispatchAttempts!==0)throw Error('DISPATCH_ATTEMPTED');

    stage='cleanup';
    const agentDelete=await api(page,'/api/agents/'+encodeURIComponent(agentId),'DELETE');
    const convoDelete=await api(page,'/api/convos/'+encodeURIComponent(conversationId),'DELETE');
    return {version:1,outcome:'REJECT_UI_PASS',normal_login:true,reject_only:true,resume_status:200,
      dispatch_attempts:0,agent_cleanup:agentDelete.ok,conversation_cleanup:convoDelete.ok,
      browser_auth_exported:false,provider_readback:'PENDING'};
  }catch{
    return {version:1,outcome:'REJECT_UI_BLOCKED',stage,browser_auth_exported:false,
      agent_created:!!agentId,conversation_created:!!conversationId};
  }finally{
    login.password='';
    if(browser)await browser.close();
  }
}
if(require.main===module){
  run(process.argv[2]).then(r=>{console.log(JSON.stringify(r));if(r.outcome!=='REJECT_UI_PASS')process.exitCode=2})
    .catch(()=>{console.log('{"outcome":"REJECT_UI_BLOCKED","stage":"private_config"}');process.exitCode=2});
}
module.exports={run,api,localRoute,BASE};
