'use strict';
const test=require('node:test'), assert=require('node:assert/strict');
const fs=require('node:fs'), path=require('node:path'), os=require('node:os'), vm=require('node:vm');
const {execFileSync}=require('node:child_process');
const gate=require('../integration/librechat/native_gate.cjs');
const pause=require('../integration/librechat/pause_gate.cjs');
const patch=require('../integration/librechat/rehearse_patch.cjs');
const root=path.resolve(__dirname,'..');
const python=process.env.AWSOPS_TEST_PYTHON || '/usr/bin/python3';
const fixture=path.join(root,'artifacts/native-upstream/client.js');
const hasFixture=fs.existsSync(fixture);
if(process.env.AWSOPS_REQUIRE_NATIVE_FIXTURE==='1' && !hasFixture)throw Error('Pinned producer required');
function setup(t){
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'awsops-pause-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const database=path.join(dir,'ledger.sqlite3');
  const seed=path.join(root,'tests/pause_seed.py');
  const candidate=JSON.parse(execFileSync(python,['-I','-B',seed,database,'candidate']));
  const config={version:1,enabled:true,agent_id:'canary',python,source_root:root,database};
  const user={id:'native-user',tenantId:'tenant-1'};
  const job={status:'running',createdAt:Date.now(),metadata:{userId:user.id,tenantId:user.tenantId,agent_id:'canary',endpoint:'agents'}};
  const pendingAction={actionId:'action-1',expiresAt:Date.now()+120000,payload:{type:'tool_approval',
    action_requests:[{name:gate.WIRE_TOOL,tool_call_id:'call-1',arguments:candidate}],
    review_configs:[{tool_call_id:'call-1',allowed_decisions:['reject']}],}};
  const client={conversationId:'conversation-1',jobCreatedAt:job.createdAt,options:{req:{user,body:{},config:{}}}};
  const f={dir,database,config,user,job,pendingAction,client,streamId:client.conversationId,reads:0};
  f.manager={getJobStore:()=>({getJob:async()=>f.job})};
  f.transport=async(_config,message)=>{f.reads++;return JSON.parse(execFileSync(python,['-I','-B',seed,database],{input:JSON.stringify(message)}));};
  return f;
}
async function prepare(f){return pause.beforePause(f,f.config,f.transport);}
async function inspect(f){
  const args=f.pendingAction.payload.action_requests[0].arguments;
  return gate.pipe(f.config,{version:1,operation:'inspect',batch_id:args.batch_id,binding:{principal_id:f.user.id,
    tenant_id:'tenant:'+f.user.tenantId,conversation_id:f.streamId,action_id:'action-1',generation_id:String(f.client.jobCreatedAt),tool_call_id:'call-1',tool:gate.LOGICAL_TOOL}});
}
test('fresh private preparation replaces only candidate input with committed scope',async t=>{
  const f=setup(t);await prepare(f);const args=f.pendingAction.payload.action_requests[0].arguments;
  assert.deepEqual(Object.keys(args),['control','batch_id','scope_hash']);assert.equal(f.reads,1);
  const audit=await inspect(f);assert.equal(audit.events.length,1);assert.equal(audit.events[0].kind,'PREPARE_FROZEN');
});
test('ownership, generation, tenant, agent, mixed actions and unsafe choice sets fail before provider reads',async t=>{
  const changes=[f=>f.job.metadata.userId='wrong',f=>f.job.metadata.tenantId='wrong',f=>f.client.jobCreatedAt++,
    f=>f.job.status='requires_action',f=>f.job.metadata.agent_id='wrong',f=>f.client.conversationId='wrong',
    f=>f.pendingAction.payload.action_requests.push({name:'legacy'}),
    f=>f.pendingAction.payload.action_requests[0].name=gate.LOGICAL_TOOL+'_wrong',
    f=>f.pendingAction.payload.review_configs[0].allowed_decisions=['approve','reject'],
    f=>f.pendingAction.payload.action_requests[0].arguments={control:'s3_ssl',batch_id:'a'.repeat(32),scope_hash:'b'.repeat(64)},
    f=>f.pendingAction.expiresAt=0];
  for(const change of changes){const f=setup(t);change(f);await assert.rejects(prepare(f));assert.equal(f.reads,0);}
});
test('default off blocks preparation',async t=>{
  const f=setup(t);const previous=process.env.AWSOPS_NATIVE_CONFIG;delete process.env.AWSOPS_NATIVE_CONFIG;
  try{await assert.rejects(pause.beforePause(f));assert.equal(f.reads,0);}
  finally{if(previous!==undefined)process.env.AWSOPS_NATIVE_CONFIG=previous;}
});
test('replaced generation or mutated candidate while provider reads never gains readiness',async t=>{
  for(const change of [f=>f.job={...f.job,createdAt:f.job.createdAt+1},f=>f.pendingAction.payload.action_requests[0].arguments.resource_ref='bucket-ref-'+'f'.repeat(20)]){
    const f=setup(t), original=f.transport;f.transport=async(c,m)=>{const r=await original(c,m);change(f);return r;};
    await assert.rejects(prepare(f));assert.equal(f.pendingAction.payload.action_requests[0].arguments.batch_id,undefined);
  }
});
test('forged receipt or candidate reply cannot publish a frozen action',async t=>{
  for(const change of [r=>r.dispatch_allowed=true,r=>r.binding_digest='0'.repeat(64),r=>r.candidate.account_alias='lab-sec',r=>r.expires_at=1,r=>r.batch_id='bad']){
    const f=setup(t),original=f.transport;f.transport=async(c,m)=>{const r=await original(c,m);change(r);return r;};
    await assert.rejects(prepare(f));assert.equal(f.pendingAction.payload.action_requests[0].arguments.batch_id,undefined);
  }
});
test('supported pre-tool factory offers Reject only and does not register',async()=>{
  const hook=pause.approvalHook()({userId:'native-user'});
  const c={control:'s3_ssl',account_alias:'lab-dev',resource_ref:'bucket-ref-'+'a'.repeat(20),expected_evidence_digest:'b'.repeat(64)};
  assert.deepEqual((await hook({toolInput:c})).allowedDecisions,['reject']);
  assert.equal((await hook({toolInput:{...c,account_id:'forbidden'}})).decision,'deny');
});
function actualMethod(f,options={}){
  const raw=fs.readFileSync(fixture);assert.equal(patch.blob(raw),patch.pin.producer_blob);
  const source=patch.render(raw,'pause').toString();
  const start=source.indexOf('  async handleRunInterrupt(run, streamId) {');
  const end=source.indexOf('\n  async chatCompletion(',start);
  assert.ok(start>0 && end>start);
  const calls={paused:0,emitted:0,released:0};
  f.manager.approvals={pause:async(_id,pending,opts)=>{
    calls.paused++;assert.equal(opts.persistencePending,true);
    if(options.loseClaim)return false;
    f.job={...f.job,status:'requires_action',metadata:{...f.job.metadata,pendingAction:pending}};return true;
  }};
  f.manager.emitChunk=async()=>{calls.emitted++;if(!options.unrelated){const audit=await inspect(f);assert.equal(audit.events[0].kind,'PREPARE_FROZEN');}};
  const context={GenerationJobManager:f.manager,EModelEndpoint:{agents:'agents'},
    pickResumeContext:()=>({}),captureResumeModelParameters:()=>null,getApprovalTtlMs:()=>120000,
    computeAgentRequestFingerprint:()=> 'fixture',getRunDiscoveredTools:()=>[],
    buildPendingAction:()=>f.pendingAction,logger:{debug(){},warn(){},error(){}},
    decrementPendingRequest:async()=>{calls.released++;},ApprovalEvents:{ON_PENDING_ACTION:'pending'},toClientPendingAction:p=>p,
    require:name=>{assert.equal(name,'./awsops-pause-gate.cjs');return {beforePause:args=>pause.beforePause(args,f.config,f.transport)};},
  };
  const method=vm.runInNewContext('(class {\n'+source.slice(start,end)+'\n}).prototype.handleRunInterrupt',context);
  return {calls,run:()=>method.call(f.client,{getInterrupt:()=>({payload:f.pendingAction.payload})},f.streamId)};
}
test('actual pinned producer commits before pause/card; native receipt then rejects', {skip:!hasFixture},async t=>{
  const f=setup(t),m=actualMethod(f);await m.run();assert.equal(m.calls.paused,1);assert.equal(m.calls.emitted,1);
  const req={user:f.user,body:{conversationId:f.streamId,actionId:'action-1',generationCreatedAt:f.job.createdAt,
    agent_id:'canary',endpoint:'agents',decisions:[{tool_call_id:'call-1',decision:'reject'}]}};
  const env=gate.prepareNativeRequest({req,job:f.job,pendingAction:f.pendingAction,streamId:f.streamId},f.config);
  const result=await gate.persistNativeDecision(env);assert.equal(result.receipt.outcome,'REJECTED');
  assert.equal(result.resumeValue['call-1'].type,'reject');assert.equal((await inspect(f)).events.length,2);
  const readback=await pause.readbackRejected(env,f.transport);
  assert.equal(readback.unchanged,true);assert.equal(readback.resume_value,undefined);
  assert.equal((await inspect(f)).events.length,2);
  await assert.rejects(gate.persistNativeDecision(env));
});
test('actual producer storage failure withholds both pause and card', {skip:!hasFixture},async t=>{
  const f=setup(t);f.transport=async()=>{throw Error('unavailable');};const m=actualMethod(f);
  await assert.rejects(m.run());assert.equal(m.calls.paused,0);assert.equal(m.calls.emitted,0);
});
test('actual producer lost registration ack never publishes readiness', {skip:!hasFixture},async t=>{
  const f=setup(t),original=f.transport;f.transport=async(c,m)=>{await original(c,m);throw Error('lost ack');};
  const m=actualMethod(f);await assert.rejects(m.run());assert.equal(m.calls.paused,0);assert.equal(m.calls.emitted,0);
});
test('actual producer losing pause CAS emits no card', {skip:!hasFixture},async t=>{
  const f=setup(t),m=actualMethod(f,{loseClaim:true});await m.run();assert.equal(m.calls.emitted,0);
});
test('actual unrelated producer path bypasses provider registration', {skip:!hasFixture},async t=>{
  const f=setup(t);f.pendingAction.payload.action_requests[0].name='legacy-tool';
  const m=actualMethod(f,{unrelated:true});await m.run();assert.equal(f.reads,0);assert.equal(m.calls.emitted,1);
});
test('producer apply/reapply/rollback preserves exact original and refuses drift', {skip:!hasFixture},t=>{
  const f=setup(t),candidate=path.join(f.dir,'candidate');fs.mkdirSync(candidate);
  const target=path.join(candidate,patch.pin.producer);fs.mkdirSync(path.dirname(target),{recursive:true});
  const raw=fs.readFileSync(fixture);fs.writeFileSync(target,raw);
  fs.writeFileSync(path.join(candidate,'package.json'),JSON.stringify({version:patch.pin.version}));
  fs.writeFileSync(path.join(candidate,'.awsops-offline-candidate.json'),JSON.stringify({purpose:'offline-rehearsal',root:candidate,upstream_commit:patch.pin.commit,live:false}));
  assert.equal(patch.change(candidate,'apply','pause').state,'PATCHED');
  assert.equal(patch.change(candidate,'apply','pause').state,'PATCHED');
  const originalPatched=fs.readFileSync(target);fs.appendFileSync(target,'\n// drift');
  assert.throws(()=>patch.change(candidate,'rollback','pause'));fs.writeFileSync(target,originalPatched);
  assert.equal(patch.change(candidate,'rollback','pause').state,'ORIGINAL');assert.deepEqual(fs.readFileSync(target),raw);
});

test('provider pipe uses an explicit existing SDK home and excludes ambient credentials',async t=>{
  const f=setup(t),configPath=path.join(f.dir,'read.json'),fake=path.join(f.dir,'env-python'),sdk=path.join(f.dir,'sdk-home');
  fs.writeFileSync(configPath,'{}',{mode:0o600});fs.mkdirSync(sdk,{mode:0o700});
  fs.writeFileSync(fake,`#!/bin/sh
if [ -n "$AUTH_TOKEN$AWS_SECRET_ACCESS_KEY$AWS_SESSION_TOKEN" ]; then exit 2; fi
[ "$AWS_EC2_METADATA_DISABLED" = true ] || exit 2
[ "$HOME" = "${sdk}" ] || exit 2
echo '{"isolated":true}'
`,{mode:0o700});
  const names=['AWSOPS_READ_CONFIG','AWSOPS_SDK_HOME','AUTH_TOKEN','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN'];
  const before=Object.fromEntries(names.map(k=>[k,process.env[k]]));
  Object.assign(process.env,{AWSOPS_READ_CONFIG:configPath,AWSOPS_SDK_HOME:sdk,
    AUTH_TOKEN:'test-only',AWS_SECRET_ACCESS_KEY:'test-only',AWS_SESSION_TOKEN:'test-only'});
  try{
    assert.equal(pause.sdkHome(),sdk);
    assert.deepEqual(await pause.providerPipe({...f.config,python:fake},{operation:'test'}),{isolated:true});
    delete process.env.AWSOPS_SDK_HOME;
    await assert.rejects(pause.providerPipe({...f.config,python:fake},{operation:'test'}));
  } finally {for(const key of names){if(before[key]===undefined)delete process.env[key];else process.env[key]=before[key];}}
});
