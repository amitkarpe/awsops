'use strict';
// Configure ONLY the isolated Issue #11 canary. No existing service/runtime path.
const fs=require('node:fs');
const path=require('node:path');
const {isDeepStrictEqual}=require('node:util');
const {createHash}=require('node:crypto');

const PURPOSE='awsops-issue11-isolated-auth-canary';
const SERVER='awsops';
const TOOL='decide_s3_ssl_reject_only_mcp_awsops';
const MODEL_ENDPOINT='awsops_canary_fixture';
const MODEL='awsops-canary-fixed';
// Previous deployed helper from accepted M3C main. Deployment renames the native helper,
// so the deployed pause helper has a distinct blob from the repository source file.
const PREVIOUS_PAUSE_BLOB='853eeea8dc3e9c8ccc6dfc7c080ad868fbeadda8';
function deployedPauseHelper(data){
  const marker="require('./native_gate.cjs')";
  const source=data.toString('utf8');
  if(source.split(marker).length!==2)fail('PAUSE_HELPER_SEAM_DRIFT');
  return Buffer.from(source.replace(marker,"require('./awsops-native-gate.cjs')"));
}
function gitBlob(data){return createHash('sha1').update(Buffer.concat([Buffer.from('blob '+data.length+'\\0'),data])).digest('hex');}

function fail(message){throw Error(message);}
function atomic(file,data,mode){
  const staged=file+'.awsops-stage';
  let fd;
  try{
    fd=fs.openSync(staged,'wx',mode);
    fs.writeFileSync(fd,data);fs.fsyncSync(fd);fs.closeSync(fd);fd=undefined;
    fs.renameSync(staged,file);
  }catch(error){
    if(fd!==undefined){fs.closeSync(fd);try{fs.unlinkSync(staged)}catch{}}
    throw error;
  }
}
function exactOrEmpty(value,name){
  if(value==null)return;
  if(typeof value!=='object'||Array.isArray(value))fail('UNSAFE_EXISTING_'+name);
}
function configure(root,sourceRoot=path.resolve(__dirname,'../..')){
  if(!path.isAbsolute(root)||fs.realpathSync(root)!==root)fail('CANARY_ROOT_REQUIRED');
  const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
  if(manifest.purpose!==PURPOSE||manifest.root!==root||manifest.model!=='DETERMINISTIC_FIXTURE'||
     JSON.stringify(manifest.tools)!==JSON.stringify([TOOL]))fail('CANARY_MANIFEST_REQUIRED');
  const app=path.join(root,'app');
  const yaml=require(path.join(app,'node_modules/js-yaml'));
  const file=path.join(app,'librechat.yaml');
  const raw=fs.readFileSync(file,'utf8');
  const cfg=yaml.load(raw)||{};
  exactOrEmpty(cfg.endpoints,'ENDPOINTS'); exactOrEmpty(cfg.mcpServers,'MCP');
  cfg.endpoints??={};
  const existingCustom=cfg.endpoints.custom??[];
  if(!Array.isArray(existingCustom))fail('UNSAFE_EXISTING_CUSTOM');
  const custom={
    name:MODEL_ENDPOINT,
    apiKey:'fixture-only',
    baseURL:'http://127.0.0.1:4312/v1',
    models:{default:[MODEL],fetch:false},
    titleConvo:false,
  };
  if(existingCustom.length && !isDeepStrictEqual(existingCustom,[custom]))fail('CUSTOM_ENDPOINT_DRIFT');
  cfg.endpoints.custom=[custom];

  const addresses=cfg.endpoints.allowedAddresses??[];
  if(!Array.isArray(addresses)||addresses.some(x=>x!=='127.0.0.1'))fail('ALLOWED_ADDRESS_DRIFT');
  cfg.endpoints.allowedAddresses=['127.0.0.1'];

  cfg.endpoints.agents??={};
  const hook=path.join(sourceRoot,'integration/canary/approval_hook.cjs');
  const approval={
    enabled:true, mode:'default', allow:[], ask:[TOOL], deny:[],
    reason:'Reject-only isolated S3 TLS canary. No remediation execution is authorized.',
    hooks:[{matcher:'^'+TOOL+'$',module:hook}],
  };
  if(cfg.endpoints.agents.toolApproval && !isDeepStrictEqual(cfg.endpoints.agents.toolApproval,approval))
    fail('TOOL_APPROVAL_DRIFT');
  cfg.endpoints.agents.toolApproval=approval;

  const mcp={
    type:'stdio',command:'/usr/bin/node',
    args:[path.join(sourceRoot,'integration/canary/mcp_guard.cjs'),root],
    timeout:15000,initTimeout:10000,chatMenu:false,serverInstructions:true,
  };
  const names=Object.keys(cfg.mcpServers||{});
  if(names.some(name=>name!==SERVER))fail('UNEXPECTED_MCP_SERVER');
  if(cfg.mcpServers?.[SERVER] && !isDeepStrictEqual(cfg.mcpServers[SERVER],mcp))fail('MCP_DRIFT');
  cfg.mcpServers={[SERVER]:mcp};

  const controllers=path.join(app,'api/server/controllers/agents');
  for(const [source,target,previousBlob] of [
    [path.join(sourceRoot,'integration/librechat/native_gate.cjs'),path.join(controllers,'awsops-native-gate.cjs'),null],
    [path.join(sourceRoot,'integration/librechat/pause_gate.cjs'),path.join(controllers,'awsops-pause-gate.cjs'),PREVIOUS_PAUSE_BLOB],
  ]){
    const rawExpected=fs.readFileSync(source);
    const expected=target.endsWith('awsops-pause-gate.cjs')?deployedPauseHelper(rawExpected):rawExpected;
    if(fs.existsSync(target)){
      const info=fs.lstatSync(target);
      if(!info.isFile()||fs.realpathSync(target)!==target)fail('HELPER_DRIFT');
      const current=fs.readFileSync(target);
      if(!current.equals(expected)){
        if(previousBlob==null||gitBlob(current)!==previousBlob)fail('HELPER_DRIFT');
        atomic(target,expected,info.mode&0o777);
      }
    }else atomic(target,expected,0o644);
  }

  const rendered=yaml.dump(cfg,{lineWidth:-1,noRefs:true});
  if(!isDeepStrictEqual(yaml.load(rendered),cfg))fail('YAML_ROUNDTRIP_FAILED');
  if(rendered!==raw){
    const backup=file+'.before-awsops-native-canary';
    if(!fs.existsSync(backup))fs.writeFileSync(backup,raw,{mode:0o600,flag:'wx'});
    atomic(file,rendered,fs.statSync(file).mode&0o777);
  }
  return {configured:true,endpoint:MODEL_ENDPOINT,model:MODEL,mcp:SERVER,tool:TOOL,live_execution_authorized:false};
}

function rollback(root){
  if(!path.isAbsolute(root)||fs.realpathSync(root)!==root)fail('CANARY_ROOT_REQUIRED');
  const app=path.join(root,'app'),file=path.join(app,'librechat.yaml'),backup=file+'.before-awsops-native-canary';
  if(!fs.existsSync(backup))return {rolled_back:false};
  atomic(file,fs.readFileSync(backup),fs.statSync(file).mode&0o777);
  return {rolled_back:true};
}

if(require.main===module){
  try{
    const [action,root,...extra]=process.argv.slice(2);
    if(extra.length||!['apply','rollback'].includes(action))fail('INVALID_ARGS');
    console.log(JSON.stringify(action==='apply'?configure(root):rollback(root)));
  }catch{console.error('AWSOPS_CANARY_CONFIG_REFUSED');process.exitCode=2;}
}
module.exports={configure,rollback,gitBlob,deployedPauseHelper,PREVIOUS_PAUSE_BLOB,PURPOSE,SERVER,TOOL,MODEL_ENDPOINT,MODEL};
