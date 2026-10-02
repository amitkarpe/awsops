'use strict';
// Deterministic model transport ONLY. Native auth, pause, receipt and AWS reads are real.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const {randomUUID} = require('node:crypto');
const TOOL = 'decide_s3_ssl_reject_only_mcp_awsops';
function responseFor(body, candidate) {
  if (!body || !Array.isArray(body.messages) || body.model !== 'awsops-canary-fixed') throw Error('INVALID_FIXTURE_REQUEST');
  if (body.messages.some(m => m.role === 'tool')) return {role:'assistant', content:'Canary decision returned. No remediation was requested. Verify the independent receipt and readback evidence.'};
  if (!Array.isArray(body.tools) || !body.tools.some(t => t.function?.name === TOOL)) throw Error('EXACT_CANARY_TOOL_NOT_AVAILABLE');
  return {role:'assistant', content:null, tool_calls:[{id:'call_' + randomUUID().replaceAll('-',''), type:'function',
    function:{name:TOOL, arguments:JSON.stringify(candidate)}}]};
}
function start(root) {
  const manifest = JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
  if (manifest.purpose !== 'awsops-issue11-isolated-auth-canary' || manifest.model !== 'DETERMINISTIC_FIXTURE') throw Error('CANARY_REQUIRED');
  const candidate = JSON.parse(fs.readFileSync(path.join(root,'state/candidate.json'),'utf8'));
  let calls = 0;
  const server = http.createServer(async (req,res) => {
    if (req.method !== 'POST' || req.url !== '/v1/chat/completions' || ++calls > 8) {res.writeHead(400).end();return;}
    let raw='';
    try {
      for await(const chunk of req) {raw+=chunk;if(Buffer.byteLength(raw)>131072)throw Error('OVERSIZED');}
      const body=JSON.parse(raw), message=responseFor(body,candidate);
      fs.appendFileSync(path.join(root,'state/model-attempts.jsonl'),JSON.stringify({sequence:calls,tool_call:!!message.tool_calls})+'\n',{mode:0o600});
      const id='chatcmpl-'+randomUUID(),created=Math.floor(Date.now()/1000);
      if(body.stream) {
        res.writeHead(200,{'Content-Type':'text/event-stream','Cache-Control':'no-cache'});
        const send=(delta,finish_reason=null)=>res.write('data: '+JSON.stringify({id,object:'chat.completion.chunk',created,model:body.model,choices:[{index:0,delta,finish_reason}]})+'\n\n');
        send({role:'assistant',content:''});
        if(message.tool_calls)send({tool_calls:message.tool_calls.map((t,index)=>({...t,index}))});else send({content:message.content});
        send({},message.tool_calls?'tool_calls':'stop');res.end('data: [DONE]\n\n');
      } else {
        res.writeHead(200,{'Content-Type':'application/json'}).end(JSON.stringify({id,object:'chat.completion',created,model:body.model,
          choices:[{index:0,message,finish_reason:message.tool_calls?'tool_calls':'stop'}],usage:{prompt_tokens:0,completion_tokens:0,total_tokens:0}}));
      }
    } catch {res.writeHead(400,{'Content-Type':'application/json'}).end('{"error":{"message":"CANARY_FIXTURE_REFUSED"}}');}
  });
  server.listen(4312,'127.0.0.1');
  return server;
}
if(require.main===module)start(process.argv[2]);
module.exports={responseFor,TOOL};
