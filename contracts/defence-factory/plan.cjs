'use strict';
// Offline planning only. Existing native live Approve remains disabled.
const {intake}=require('./intake.cjs');const {digest}=require('./scope.cjs');
const capabilities=Object.freeze({'s3-ssl-requests-only':['s3-require-tls','DENY_INSECURE_TRANSPORT','AWS::S3::Bucket'],'s3-bucket-public-read-prohibited':['s3-block-public-access','ENABLE_BUCKET_PUBLIC_ACCESS_BLOCK','AWS::S3::Bucket'],'s3-bucket-public-write-prohibited':['s3-block-public-access','ENABLE_BUCKET_PUBLIC_ACCESS_BLOCK','AWS::S3::Bucket'],'restricted-ssh':['sg-restrict-ssh','REMOVE_EXACT_WORLD_OPEN_SSH','AWS::EC2::SecurityGroup']});
function freeze(text,format,controlId,now=new Date().toISOString()){
 const imported=intake(text,format),cap=capabilities[controlId];if(!cap)throw Error('NO_REGISTERED_MOCK_CAPABILITY');const t=Date.parse(now);if(!Number.isFinite(t))throw Error('INVALID_TIME');
 const selected=imported.findings.map(x=>x.record).filter(x=>x.controlId===controlId&&x.compliance==='NON_COMPLIANT');if(!selected.length||selected.some(x=>x.resource.resourceType!==cap[2]))throw Error('INVALID_EXACT_SCOPE');
 const targets=selected.map(x=>({findingId:x.findingId,resource:x.resource,controlId:x.controlId,revision:x.revision,evidenceDigest:digest(x),capabilityId:cap[0],expectedChange:cap[1]})).sort((a,b)=>{const ka=[a.resource.accountAlias,a.resource.resourceAlias,a.controlId,a.findingId].join('|'),kb=[b.resource.accountAlias,b.resource.resourceAlias,b.controlId,b.findingId].join('|');return ka<kb?-1:ka>kb?1:0;});
 const scope={batchId:'batch-synthetic-'+digest({imported,controlId,now}).slice(0,24),datasetId:'dataset-import-a',registryVersion:1,mode:'MOCK',frozenAt:new Date(t).toISOString(),expiresAt:new Date(t+300000).toISOString(),targets};return {schemaVersion:'defence-factory/1',kind:'Batch',record:{...scope,scopeDigest:digest(scope)}};
}
function admission(batch,choice,now){
 const r=batch?.record;if(batch?.schemaVersion!=='defence-factory/1'||batch?.kind!=='Batch'||!r)throw Error('INVALID_BATCH');const {scopeDigest,...scope}=r;
 if(digest(scope)!==scopeDigest||r.mode!=='MOCK'||!Number.isFinite(Date.parse(now))||Date.parse(now)<Date.parse(r.frozenAt)||Date.parse(now)>=Date.parse(r.expiresAt))return {state:'BLOCKED',realWrites:0,dispatch:false};
 if(choice==='REJECT')return {state:'REJECTED',realWrites:0,dispatch:false};
 return {state:'APPROVE_BLOCKED',realWrites:0,dispatch:false,reason:'No live executor, trusted principal or durable approval authority in an imported offline plan'};
}
module.exports={freeze,admission};
