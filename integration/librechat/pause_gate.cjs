'use strict';
// Trusted producer only. Candidate nominations are not evidence or authority.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {spawn} = require('node:child_process');
const {createHash} = require('node:crypto');
const gate = require('./native_gate.cjs');
const ID = /^[A-Za-z0-9_.:-]{1,128}$/;
const HEX64 = /^[a-f0-9]{64}$/;
const PREPARE_TIMEOUT_MS = 30000;
function fail() { throw Error('AWSOPS_PAUSE_NOT_READY'); }
function text(v, re=ID) { if (typeof v !== 'string' || !re.test(v)) fail(); return v; }
function keys(v, names) {
  if (!v || typeof v !== 'object' || Array.isArray(v) ||
      Object.keys(v).sort().join(',') !== names.slice().sort().join(',')) fail();
}
function snapshot({client, job, pendingAction, streamId}, config) {
  config = gate.validateConfig(config);
  const req = client?.options?.req;
  if (streamId !== client?.conversationId || !req?.user ||
      job?.status !== 'running' || job.createdAt !== client.jobCreatedAt ||
      !Number.isSafeInteger(job.createdAt) || job.createdAt < 0 ||
      job.metadata?.userId !== req.user.id ||
      (job.metadata.tenantId ?? null) !== (req.user.tenantId ?? null) ||
      job.metadata.agent_id !== config.agent_id || job.metadata.endpoint !== 'agents' ||
      !Number.isSafeInteger(pendingAction?.expiresAt) || pendingAction.expiresAt <= Date.now() ||
      pendingAction.payload?.type !== 'tool_approval') fail();
  text(streamId); text(req.user.id); text(pendingAction.actionId);
  const actions = pendingAction.payload.action_requests;
  const reviews = pendingAction.payload.review_configs;
  if (!Array.isArray(actions) || actions.length !== 1 || actions[0]?.name !== gate.WIRE_TOOL ||
      !Array.isArray(reviews) || reviews.length !== 1 || reviews[0]?.tool_call_id !== actions[0].tool_call_id ||
      JSON.stringify(reviews[0].allowed_decisions) !== '["reject"]') fail();
  const action = actions[0]; text(action.tool_call_id);
  keys(action.arguments, ['control','account_alias','resource_ref','expected_evidence_digest']);
  const candidate = action.arguments;
  if (candidate.control !== 's3_ssl') fail();
  text(candidate.account_alias, /^lab-(dev|poc|qa|sec)$/);
  text(candidate.resource_ref, /^bucket-ref-[a-f0-9]{20}$/);
  text(candidate.expected_evidence_digest, HEX64);
  const tenant = req.user.tenantId == null ? 'system:single-tenant' : 'tenant:' + text(req.user.tenantId);
  text(tenant);
  const binding = Object.freeze({principal_id:req.user.id, tenant_id:tenant, conversation_id:streamId,
    action_id:pendingAction.actionId, generation_id:String(job.createdAt), tool_call_id:action.tool_call_id,
    tool:gate.LOGICAL_TOOL});
  return Object.freeze({version:1, operation:'prepare_pause', binding,
    candidate:Object.freeze({...candidate}), pause_expires_at:Math.floor(pendingAction.expiresAt/1000)});
}
function bindingDigest(binding) {
  const ordered = Object.fromEntries(Object.keys(binding).sort().map(k => [k,binding[k]]));
  return createHash('sha256').update(JSON.stringify(ordered)).digest('hex');
}
function providerPipe(config, message) {
  const readConfig = process.env.AWSOPS_READ_CONFIG;
  if (typeof readConfig !== 'string' || !path.isAbsolute(readConfig) || fs.realpathSync(readConfig) !== readConfig) fail();
  const stat = fs.lstatSync(readConfig);
  if (!stat.isFile() || stat.size > 8192 || (stat.mode & 0o077) ||
      (process.getuid && stat.uid !== process.getuid())) fail();
  const input = Buffer.from(JSON.stringify(message));
  if (input.length > gate.MAX_BYTES) fail();
  return new Promise((resolve,reject) => {
    let child, timer, done=false, size=0; const output=[];
    const stop = () => {
      if (done) return; done=true; clearTimeout(timer);
      if (child && child.exitCode === null) child.kill('SIGKILL');
      reject(Error('AWSOPS_PAUSE_NOT_READY'));
    };
    try {
      child=spawn(config.python,['-I','-B',path.join(config.source_root,'integration/librechat/prepare_entry.py'),
        '--database',config.database,'--read-config',readConfig],{
        shell:false,cwd:config.source_root,stdio:['pipe','pipe','pipe'],
        // Only the existing SDK's named local profile is used. No native auth or
        // temporary credentials are copied from the parent environment.
        env:{LANG:'C.UTF-8',HOME:os.homedir(),AWS_EC2_METADATA_DISABLED:'true'},
      });
      timer=setTimeout(stop,PREPARE_TIMEOUT_MS);
      child.on('error',stop); child.stdin.on('error',stop); child.stderr.on('data',stop);
      child.stdout.on('data',data => {size+=data.length;if(size>gate.MAX_BYTES)stop();else output.push(data);});
      child.on('close',code => {
        if(done)return;
        if(code!==0)return stop();
        try {const value=JSON.parse(Buffer.concat(output).toString('utf8'));
          done=true;clearTimeout(timer);resolve(value);
        } catch {stop();}
      });
      child.stdin.end(input);
    } catch {stop();}
  });
}
async function beforePause({client,manager,pendingAction,streamId}, config=gate.configFromEnvironment(), transport=providerPipe) {
  config=gate.validateConfig(config);
  // Only immutable snapshots cross the await. A replaced run cannot acquire a
  // newer generation's pending action from an old provider response.
  const job=await manager.getJobStore().getJob(streamId);
  const context={client,job,pendingAction,streamId};
  const message=snapshot(context,config);
  const saved=JSON.stringify(message);
  const result=await transport(config,message);
  keys(result,['version','ok','operation','dispatch_allowed','batch_id','scope_hash','expires_at','event_hash','candidate','binding_digest']);
  if(result.version!==1 || result.ok!==true || result.operation!=='prepare_pause' || result.dispatch_allowed!==false ||
      result.binding_digest!==bindingDigest(message.binding) ||
      Object.keys(message.candidate).some(k=>result.candidate?.[k]!==message.candidate[k]) ||
      !Number.isSafeInteger(result.expires_at) || result.expires_at<=Math.floor(Date.now()/1000) ||
      result.expires_at>message.pause_expires_at) fail();
  keys(result.candidate,Object.keys(message.candidate));
  text(result.batch_id,/^[a-f0-9]{32}$/);text(result.scope_hash,HEX64);text(result.event_hash,HEX64);
  const live=await manager.getJobStore().getJob(streamId);
  if(JSON.stringify(snapshot({...context,job:live},config))!==saved)fail();
  // The native card and the later resume both receive ONLY the committed scope.
  pendingAction.payload.action_requests[0].arguments={control:'s3_ssl',batch_id:result.batch_id,scope_hash:result.scope_hash};
  pendingAction.expiresAt=Math.min(pendingAction.expiresAt,result.expires_at*1000);
}
module.exports={beforePause,snapshot,providerPipe,bindingDigest,PREPARE_TIMEOUT_MS};

// Compatible with the pinned native pre-tool hook factory. This requests review;
// it does not register evidence, authenticate a user or authorize execution.
module.exports.approvalHook = () => context => async input => {
  try {
    text(context?.userId);
    const c=input?.toolInput;
    keys(c,['control','account_alias','resource_ref','expected_evidence_digest']);
    if(c.control!=='s3_ssl')fail();
    text(c.account_alias,/^lab-(dev|poc|qa|sec)$/);
    text(c.resource_ref,/^bucket-ref-[a-f0-9]{20}$/);
    text(c.expected_evidence_digest,HEX64);
    return {decision:'ask',allowedDecisions:['reject'],reason:'Read-only S3 TLS validation. Reject only; no remediation.'};
  } catch {return {decision:'deny',reason:'AWSOPS_PAUSE_NOT_READY'};}
};
