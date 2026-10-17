'use strict';
// stdio registration only. The native controller owns the Reject card and
// intercepts it before execution; this process has no provider or credentials.
const readline = require('node:readline');
const LEGACY = 'decide_s3_ssl_reject_only';
const CANARY = 'approve_s3_canary_once';
const schemas = [
  {name:LEGACY,description:'Legacy S3 TLS Reject review. Native approval handling only; never execute directly.',inputSchema:{
    type:'object',additionalProperties:false,required:['control','account_alias','resource_ref','expected_evidence_digest'],properties:{
      control:{type:'string',enum:['s3_ssl']},account_alias:{type:'string',enum:['lab-dev','lab-poc','lab-qa','lab-sec']},
      resource_ref:{type:'string',pattern:'^bucket-ref-[a-f0-9]{20}$'},expected_evidence_digest:{type:'string',pattern:'^[a-f0-9]{64}$'}}}},
  {name:CANARY,description:'Request the fixed Issue 90 native Reject card; resource and authority are server-owned.',inputSchema:{
    type:'object',additionalProperties:false,required:['control'],properties:{control:{type:'string',enum:['s3_canary']}}}},
];
function answer(message) {
  if(message.method==='initialize')return {protocolVersion:'2024-11-05',capabilities:{tools:{}},serverInfo:{name:'awsops-native-review',version:'1.0.0'}};
  if(message.method==='tools/list')return {tools:schemas};
  if(message.method==='ping')return {};
  if(message.method==='tools/call')return {isError:true,content:[{type:'text',text:'NATIVE_DECISION_REQUIRED'}]};
  return null;
}
if(require.main===module){
  readline.createInterface({input:process.stdin}).on('line',line=>{
    if(Buffer.byteLength(line)>65536)return process.exit(2);
    try{
      const request=JSON.parse(line);if(request.id==null)return;
      const result=answer(request);
      const reply=result===null?{jsonrpc:'2.0',id:request.id,error:{code:-32601,message:'Unsupported method'}}:
        {jsonrpc:'2.0',id:request.id,result};
      process.stdout.write(JSON.stringify(reply)+'\n');
    }catch{process.exit(2);}
  });
}
module.exports={answer,schemas};
