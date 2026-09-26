'use strict';
// Real native-browser Reject-only canary. Auth tokens never leave page.evaluate.
const fs=require('node:fs');
const path=require('node:path');
const contract=require('./browser_contract.cjs');
const BASE='http://127.0.0.1:4311';
const PURPOSE='awsops-issue11-isolated-auth-canary';
const TOOL='decide_s3_ssl_reject_only_mcp_awsops';
const LOGICAL_TOOL='decide_s3_ssl_reject_only';
const SERVER_TOOL='sys__server__sys_mcp_awsops';
const PROVIDER='awsops_canary_fixture';
const MODEL='awsops-canary-fixed';
const MCP_READY_ATTEMPTS=120;

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
async function openAgentBuilder(page,mark=()=>{},navigate=true){
  if(navigate){
    mark('agent_builder_navigation');
    await page.goto(BASE+'/c/new',{waitUntil:'domcontentloaded'});
  }else{
    mark('agent_builder_current_page');
    const url=new URL(page.url());
    if(url.origin!==BASE||url.pathname!=='/c/new')throw Error('AGENT_BUILDER_PAGE_REQUIRED');
  }
  const form=page.getByRole('form',{name:'Agent configuration form'});
  mark('agent_builder_form_probe');
  const visible=await form.waitFor({state:'visible',timeout:1500}).then(()=>true).catch(()=>false);
  if(!visible){
    mark('agent_builder_button_wait');
    const button=page.getByRole('button',{name:'Agent Builder',exact:true});
    if(await button.count()!==1)throw Error('AGENT_BUILDER_TRIGGER_REQUIRED');
    await button.waitFor({state:'visible',timeout:15000});
    if(!(await button.isEnabled()))throw Error('AGENT_BUILDER_TRIGGER_DISABLED');
    mark('agent_builder_button_click');
    if(await button.getAttribute('aria-pressed')!=='true')await button.click();
  }
  mark('agent_builder_form_wait');
  await form.waitFor({state:'visible',timeout:30000});
  mark('agent_builder_ready');
  return form;
}
async function run(root){
  if(!path.isAbsolute(root)||fs.realpathSync(root)!==root)throw Error('CANARY_ROOT_REQUIRED');
  const manifest=privateJson(path.join(root,'manifest.json'));
  if(manifest.purpose!==PURPOSE||manifest.model!=='DETERMINISTIC_FIXTURE'||
     JSON.stringify(manifest.tools)!==JSON.stringify([TOOL]))throw Error('CANARY_MANIFEST_REQUIRED');
  const login=privateJson(path.join(root,'state/login.json'));
  const candidate=contract.validateCandidate(privateJson(path.join(root,'state/candidate.json')));
  const python=process.env.AWSOPS_CANARY_PYTHON;
  if(typeof python!=='string'||!path.isAbsolute(python))throw Error('CANARY_PYTHON_REQUIRED');
  const pythonLink=fs.lstatSync(python), pythonTarget=fs.statSync(fs.realpathSync(python));
  const pythonParent=fs.statSync(path.dirname(python));
  if(!(pythonLink.isFile()||pythonLink.isSymbolicLink())||!pythonTarget.isFile()||
     (pythonTarget.mode&0o111)===0||(pythonTarget.mode&0o022)!==0||(pythonParent.mode&0o022)!==0)
    throw Error('CANARY_PYTHON_REQUIRED');
  process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(root,'state/browser');
  const {chromium}=require(path.join(root,'app/node_modules/playwright'));
  let browser,page,agentId,conversationId,agentName;
  const option_state={count:0,visible:false,enabled:false,box:false,center_hit:false,search_visible:false,form_visible:false,select_completed:false};
  let stage='launch';
  const diagnostics=[];
  const resumeRequests=[];
  const diagnosticByRequest=new WeakMap();
  const resumeStatusByRequest=new WeakMap();
  try{
    browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
    const context=await browser.newContext();
    await context.route('**/*',route=>localRoute(route.request().url())?route.continue():route.abort());
    page=await context.newPage();page.setDefaultTimeout(30000);
    page.on('request',request=>{
      const route=contract.routeClass(request.url());
      const entry=contract.safeDiagnostic({stage,method:request.method(),url:request.url(),status:null,
        headerNames:Object.keys(request.headers())});
      contract.recordDiagnostic(diagnostics,entry);
      diagnosticByRequest.set(request,entry);
      if(request.method()==='POST'&&route==='agents_resume')resumeRequests.push(request);
    });
    page.on('response',response=>{
      const status=response.status();
      const diagnostic=diagnosticByRequest.get(response.request());
      if(diagnostic){
        diagnostic.status=status;
        diagnostic.auth_state=status===401||status===403?'rejected':'response';
      }
      if(contract.routeClass(response.url())==='agents_resume')resumeStatusByRequest.set(response.request(),status);
    });
    stage='login';
    await page.goto(BASE+'/login',{waitUntil:'domcontentloaded'});
    await page.getByLabel('Email',{exact:true}).fill(login.email);
    await page.getByLabel('Password',{exact:true}).fill(login.password);
    const accepted=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/auth/login'&&r.status()===200);
    await page.getByTestId('login-button').click();await accepted;
    await page.waitForURL(BASE+'/c/new');
    const nativePath=path.join(root,'state/native.json');
    if(fs.existsSync(nativePath)){
      const stale=privateJson(nativePath);
      if(stale?.version!==1||typeof stale.agent_id!=='string')throw Error('STALE_NATIVE_CONFIG_INVALID');
      const retired=await api(page,'/api/agents/'+encodeURIComponent(stale.agent_id),'DELETE');
      if(!retired.ok&&retired.status!==404)throw Error('STALE_AGENT_CLEANUP_FAILED');
      fs.unlinkSync(nativePath);
    }
    stage='tool_ready';
    let tools;
    for(let i=0;i<MCP_READY_ATTEMPTS;i++){
      const r=await api(page,'/api/mcp/tools');
      if(r.ok && r.json?.servers?.awsops?.tools?.some(t=>t.pluginKey===TOOL)){tools=r.json;break}
      await page.waitForTimeout(500);
    }
    if(!tools)throw Error('MCP_TOOL_NOT_READY');

    stage='agent_create';
    agentName='AWS Ops Reject Canary '+Date.now();
    const name=agentName;
    const created=await api(page,'/api/agents','POST',{
      name,description:'Disposable Reject-only native acceptance agent.',
      instructions:'Call the provided S3 TLS decision tool exactly once. Never request or perform remediation.',
      provider:PROVIDER,model:MODEL,tools:[SERVER_TOOL,TOOL],
    });
    if(!created.ok||typeof created.json?.id!=='string')throw Error('AGENT_CREATE_FAILED');
    agentId=created.json.id;

    stage='agent_visibility';
    let listedAgent=null;
    for(let i=0;i<20;i++){
      const listed=await api(page,'/api/agents?search='+encodeURIComponent(name)+'&limit=10&requiredPermission=2');
      listedAgent=listed.ok&&Array.isArray(listed.json?.data)
        ? listed.json.data.find(agent=>agent?.id===agentId&&agent?.name===name)
        : null;
      if(listedAgent)break;
      await page.waitForTimeout(500);
    }
    if(!listedAgent)throw Error('AGENT_NOT_PERSISTED');

    const native={
      version:1,enabled:true,agent_id:agentId,python,
      source_root:path.join(root,'awsops'),database:path.join(root,'state/receipt.sqlite3'),
    };
    writePrivate(path.join(root,'state/native.json'),native);

    let agentSelected=false;
    for(let attempt=0;attempt<3;attempt++){
      try{
        Object.assign(option_state,{count:0,visible:false,enabled:false,box:false,center_hit:false,
          search_visible:false,form_visible:false,select_completed:false});
        stage='agent_builder_open';
        const form=await openAgentBuilder(page,value=>{stage=value},attempt>0);
        stage='agent_builder_root';
        const backToBuilder=form.getByRole('button',{name:'Back to builder',exact:true});
        const agentSelect=form.getByRole('combobox',{name:'Agent',exact:true});
        let builderRootReady=false;
        for(let i=0;i<120;i++){
          if(await agentSelect.isVisible().catch(()=>false)){builderRootReady=true;break}
          if(await backToBuilder.isVisible().catch(()=>false)){
            if(!(await backToBuilder.isEnabled()))throw Error('AGENT_BUILDER_BACK_DISABLED');
            await backToBuilder.click();
          }
          await page.waitForTimeout(250);
        }
        if(!builderRootReady)throw Error('AGENT_BUILDER_ROOT_REQUIRED');
        stage='agent_combobox_click';
        if(!(await agentSelect.isEnabled()))throw Error('AGENT_COMBOBOX_DISABLED');
        await agentSelect.click();
        stage='agent_search_wait';
        const search=page.getByPlaceholder('Search agents by name',{exact:true});
        await search.waitFor({state:'visible',timeout:30000});
        stage='agent_search';
        await search.fill(name);
        const option=page.getByRole('option',{name,exact:true});
        stage='agent_option_wait';
        await option.waitFor({state:'visible',timeout:30000});
        option_state.count=await option.count();
        option_state.visible=await option.isVisible().catch(()=>false);
        option_state.enabled=await option.isEnabled().catch(()=>false);
        option_state.search_visible=await search.isVisible().catch(()=>false);
        option_state.form_visible=await form.isVisible().catch(()=>false);
        option_state.box=await option.boundingBox().then(box=>!!(box&&box.width>0&&box.height>0)).catch(()=>false);
        option_state.center_hit=await option.evaluate(element=>{
          const rect=element.getBoundingClientRect();
          if(!rect.width||!rect.height)return false;
          const hit=document.elementFromPoint(rect.left+rect.width/2,rect.top+rect.height/2);
          return !!(hit&&(hit===element||element.contains(hit)));
        }).catch(()=>false);
        stage='agent_option_enter';
        await search.press('Enter');
        option_state.select_completed=true;
        stage='agent_select_submit';
        const selectAgent=form.getByRole('button',{name:'Select Agent',exact:true});
        await selectAgent.click();
        agentSelected=true;
        break;
      }catch(error){
        if(attempt===2)throw error;
        stage='agent_selection_retry';
        await page.waitForTimeout(250);
      }
    }
    if(!agentSelected)throw Error('AGENT_SELECTION_UI_BLOCKED');

    stage='send';
    const input=page.getByRole('textbox',{name:'Message input'});
    await input.fill('Run the isolated s3_ssl Reject-only canary now.');
    const admission=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/agents/chat'&&r.status()===200);
    await input.press('Enter');await admission;
    await page.waitForURL(/\/c\/(?!new)/,{timeout:15000});
    conversationId=new URL(page.url()).pathname.replace('/c/','');

    stage='approval_card';
    const cards=page.getByTestId('tool-approval');
    await cards.first().waitFor({state:'visible',timeout:30000});
    if(await cards.count()!==1)throw Error('AMBIGUOUS_APPROVAL_CARD');
    const card=cards.first();
    const cardToolCallId=await card.getAttribute('data-tool-call-id');
    if(typeof cardToolCallId!=='string'||!/^[A-Za-z0-9_-]{1,128}$/.test(cardToolCallId))
      throw Error('APPROVAL_CARD_ID_REQUIRED');
    const toolCall=page.locator(`[data-testid="tool-call"][data-tool-call-id="${cardToolCallId}"]`);
    const toolOutput=page.locator(`[data-tool-call-output-id="${cardToolCallId}"]`);
    if(await toolCall.count()!==1||await toolOutput.count()!==1)throw Error('APPROVAL_TOOL_BINDING_MISSING');
    const parameters=toolOutput.getByRole('button',{name:'Parameters',exact:true});
    await parameters.waitFor({state:'visible'});await parameters.click();
    const snapshot=await contract.waitForSettledSnapshot(async()=>{
      const cardCount=await cards.count();
      if(cardCount!==1)return {cardCount};
      return {
        cardCount,visible:await card.isVisible(),toolCallId:await card.getAttribute('data-tool-call-id'),
        toolCallCount:await page.locator(`[data-testid="tool-call"][data-tool-call-id="${cardToolCallId}"]`).count(),
        outputCount:await page.locator(`[data-tool-call-output-id="${cardToolCallId}"]`).count(),
        toolText:await toolCall.innerText(),scopeText:await toolOutput.innerText(),
        buttons:{
          reject:await card.getByRole('button',{name:'Reject',exact:true}).count(),
          approve:await card.getByRole('button',{name:'Approve',exact:true}).count(),
          edit:await card.getByRole('button',{name:'Edit',exact:true}).count(),
          respond:await card.getByRole('button',{name:'Respond',exact:true}).count(),
          submit:await card.getByRole('button',{name:'Submit',exact:true}).count(),
        },
      };
    },{pause:ms=>page.waitForTimeout(ms)});
    const boundToolCallId=contract.assertApprovalSnapshot(snapshot,{toolName:LOGICAL_TOOL,candidate});
    const submit=card.getByRole('button',{name:'Submit',exact:true});
    if(await submit.isDisabled())throw Error('REJECT_SUBMIT_NOT_READY');
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
       choice?.decision!=='reject'||choice?.tool_call_id!==boundToolCallId||!Number.isSafeInteger(body?.generationCreatedAt))
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
    await page.waitForTimeout(300);
    const submissions=resumeRequests.map(item=>({
      method:item.method(),route:contract.routeClass(item.url()),status:resumeStatusByRequest.get(item)??null,
      body:item.postDataJSON(),
    }));
    const submissionProof=contract.assertSingleRejectSubmission(submissions,{agentId,conversationId,toolCallId:boundToolCallId});

    stage='cleanup';
    const agentDelete=await api(page,'/api/agents/'+encodeURIComponent(agentId),'DELETE');
    if(!agentDelete.ok)throw Error('AGENT_CLEANUP_FAILED');
    const archive=contract.archiveRequest(conversationId);
    const archived=await api(page,archive.path,archive.method,archive.body);
    contract.assertArchived(archived,conversationId);
    const archiveReadback=await api(page,'/api/convos/'+encodeURIComponent(conversationId));
    contract.assertArchived(archiveReadback,conversationId);
    return {version:1,outcome:'REJECT_UI_PASS',normal_login:true,reject_only:true,resume_status:200,
      resume_submissions:submissionProof.count,dispatch_attempts:0,agent_cleanup:true,conversation_archived:true,
      browser_auth_exported:false,provider_readback:'PENDING',diagnostics};
  }catch{
    let agentCleanup=false,conversationCleanup=false;
    const ui_state={select_agent_count:0,select_agent_visible:false,select_agent_enabled:false,
      agent_name_count:0,agent_name_matches:false,agent_combobox_count:0,agent_combobox_matches:false};
    if(page){
      try{
        const failedForm=page.getByRole('form',{name:'Agent configuration form'});
        const failedSelect=failedForm.getByRole('button',{name:'Select Agent',exact:true});
        const failedName=failedForm.getByLabel('Agent name');
        const failedCombo=failedForm.getByRole('combobox',{name:'Agent',exact:true});
        ui_state.select_agent_count=await failedSelect.count();
        ui_state.select_agent_visible=await failedSelect.isVisible().catch(()=>false);
        ui_state.select_agent_enabled=await failedSelect.isEnabled().catch(()=>false);
        ui_state.agent_name_count=await failedName.count();
        ui_state.agent_name_matches=typeof agentName==='string'
          ?await failedName.inputValue().then(value=>value===agentName).catch(()=>false):false;
        ui_state.agent_combobox_count=await failedCombo.count();
        ui_state.agent_combobox_matches=typeof agentName==='string'
          ?await failedCombo.innerText().then(value=>value.includes(agentName)).catch(()=>false):false;
      }catch{}
    }
    if(page&&agentId){
      try{const removed=await api(page,'/api/agents/'+encodeURIComponent(agentId),'DELETE');
        agentCleanup=removed.ok||removed.status===404;}catch{}
    }
    if(page&&conversationId){
      try{const archive=contract.archiveRequest(conversationId);
        const archived=await api(page,archive.path,archive.method,archive.body);
        conversationCleanup=contract.assertArchived(archived,conversationId)===true;}catch{}
    }
    return {version:1,outcome:'REJECT_UI_BLOCKED',stage,browser_auth_exported:false,
      agent_created:!!agentId,conversation_created:!!conversationId,resume_submissions:resumeRequests.length,
      agent_cleanup:agentCleanup,conversation_archived:conversationCleanup,ui_state,option_state,diagnostics};
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
