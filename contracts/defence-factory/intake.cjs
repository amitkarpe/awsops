/* Defence Factory bounded synthetic intake. No IO, credentials or execution. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.DefenceIntake=api;})(typeof globalThis==='object'?globalThis:this,function(){
'use strict';
const MAX_BYTES=262144,MAX_ROWS=500;
const CATALOG=Object.freeze(['s3-ssl-requests-only','s3-bucket-public-read-prohibited','s3-bucket-public-write-prohibited','restricted-ssh','s3-bucket-logging-enabled','s3-bucket-versioning-enabled','s3-bucket-server-side-encryption-enabled','s3-default-encryption-kms','s3-bucket-level-public-access-prohibited','s3-account-level-public-access-blocks-periodic','ec2-imdsv2-check','ec2-ebs-encryption-by-default','encrypted-volumes','ec2-volume-inuse-check','ec2-instance-no-public-ip','incoming-ssh-disabled','vpc-default-security-group-closed','restricted-common-ports','rds-storage-encrypted','rds-instance-public-access-check','rds-snapshots-public-prohibited','cloudtrail-enabled','cloud-trail-encryption-enabled','iam-root-access-key-check']);
const COLUMNS=Object.freeze(['findingId','accountAlias','resourceAlias','resourceType','region','controlId','severity','compliance','observedAt']);
const bad=()=>{throw new Error('INVALID_SYNTHETIC_INPUT');};
const obj=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
function keys(x,allowed){if(!obj(x)||Object.keys(x).length!==allowed.length||Object.keys(x).some(k=>!allowed.includes(k)))bad();}
function parseJSON(text){let i=0;const ws=()=>{while(/[\t\r\n ]/.test(text[i]||'x'))i++;};
 function str(){const start=i++;while(i<text.length){const c=text[i++];if(c==='"'){try{return JSON.parse(text.slice(start,i));}catch{bad();}}if(c==='\\')i++;}bad();}
 function value(depth){if(depth>8)bad();ws();const c=text[i];if(c==='"')return str();if(c==='{'){i++;const o=Object.create(null),seen=new Set();ws();if(text[i]==='}'){i++;return o;}while(i<text.length){ws();if(text[i]!=='"')bad();const k=str();if(seen.has(k)||['__proto__','constructor','prototype'].includes(k))bad();seen.add(k);ws();if(text[i++]!==':')bad();o[k]=value(depth+1);ws();const end=text[i++];if(end==='}')return o;if(end!==',')bad();}bad();}
 if(c==='['){i++;const a=[];ws();if(text[i]===']'){i++;return a;}while(i<text.length){a.push(value(depth+1));if(a.length>MAX_ROWS)bad();ws();const end=text[i++];if(end===']')return a;if(end!==',')bad();}bad();}
 const m=/^(true|false|null|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)/.exec(text.slice(i));if(!m)bad();i+=m[0].length;const v=JSON.parse(m[0]);if(typeof v==='number'&&!Number.isSafeInteger(v))bad();return v;
 }const result=value(0);ws();if(i!==text.length)bad();return result;}
function parseCSV(text){let rows=[],row=[],cell='',quoted=false,closed=false;
 const field=()=>{row.push(cell);cell='';closed=false;if(row.length>COLUMNS.length)bad();};
 const line=()=>{field();rows.push(row);row=[];if(rows.length>MAX_ROWS+1)bad();};
 for(let i=0;i<text.length;i++){const c=text[i];if(quoted){if(c==='"'){if(text[i+1]==='"'){cell+='"';i++;}else{quoted=false;closed=true;}}else cell+=c;continue;}
 if(closed&&c!==','&&c!=='\r'&&c!=='\n')bad();
 if(c==='"'){if(cell||closed)bad();quoted=true;}else if(c===',')field();else if(c==='\n')line();else if(c==='\r'){if(text[i+1]!=='\n')bad();i++;line();}else cell+=c;
 }if(quoted)bad();if(cell||row.length||closed)line();if(!rows.length||JSON.stringify(rows.shift())!==JSON.stringify(COLUMNS))bad();return rows.map(r=>{if(r.length!==COLUMNS.length)bad();return Object.fromEntries(COLUMNS.map((k,i)=>[k,r[i]]));});}
function intake(input,format){try{
 let text;if(typeof input==='string'){text=input;if(new TextEncoder().encode(text).length>MAX_BYTES)bad();}else if(input instanceof Uint8Array){if(input.byteLength>MAX_BYTES)bad();text=new TextDecoder('utf-8',{fatal:true}).decode(input);}else bad();
 if(!text.length||text.charCodeAt(0)===0xfeff||/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\uffff]/.test(text))bad();
 // Only printable ASCII schema values are supported. Reject sensitive shapes before display.
 if(/\d{12}|arn:|AKIA[A-Z0-9]{16}|ASIA[A-Z0-9]{16}|-----BEGIN|https?:|@|secret|password|token|credential/i.test(text))bad();
 let rows;if(format==='json'){const p=parseJSON(text);keys(p,['schemaVersion','findings']);if(p.schemaVersion!=='defence-intake/1')bad();rows=p.findings;}else if(format==='csv')rows=parseCSV(text);else bad();
 if(!Array.isArray(rows)||rows.length<1||rows.length>MAX_ROWS)bad();const ids=new Set(),resources=new Set();
 const findings=rows.map(r=>{keys(r,COLUMNS);if(COLUMNS.some(k=>typeof r[k]!=='string'))bad();if(Object.values(r).some(v=>/\d{12}|arn:|AKIA[A-Z0-9]{16}|ASIA[A-Z0-9]{16}|-----BEGIN|https?:|@|secret|password|token|credential/i.test(v)))bad();
 if(!/^finding-[a-z][a-z0-9-]{0,47}$/.test(r.findingId)||!/^resource-[a-z][a-z0-9-]{0,47}$/.test(r.resourceAlias))bad();
 if(!['mock-a','mock-b'].includes(r.accountAlias)||!['AWS::S3::Bucket','AWS::EC2::SecurityGroup','UNKNOWN'].includes(r.resourceType)||r.region!=='ap-southeast-1')bad();
 if(!/^[a-z][a-z0-9-]{0,63}$/.test(r.controlId)||!['CRITICAL','HIGH','MEDIUM','LOW','INFORMATIONAL'].includes(r.severity)||!['COMPLIANT','NON_COMPLIANT','INSUFFICIENT_DATA','NOT_APPLICABLE','UNKNOWN'].includes(r.compliance))bad();
 if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(r.observedAt)||!Number.isFinite(Date.parse(r.observedAt))||new Date(r.observedAt).toISOString().replace('.000Z','Z')!==r.observedAt)bad();
 const key=[r.accountAlias,r.resourceAlias,r.controlId].join('|');if(ids.has(r.findingId)||resources.has(key))bad();ids.add(r.findingId);resources.add(key);
 return Object.freeze({schemaVersion:'defence-factory/1',kind:'Finding',record:Object.freeze({findingId:r.findingId,datasetId:'dataset-import-a',revision:1,resource:Object.freeze({accountAlias:r.accountAlias,resourceAlias:r.resourceAlias,resourceType:r.resourceType,region:r.region}),controlId:CATALOG.includes(r.controlId)?r.controlId:'unknown-control',severity:r.severity,compliance:r.compliance,observedAt:r.observedAt,evaluatedAt:null,freshness:'NOT_VERIFIED',provenance:'IMPORTED_ASSERTION',evidenceId:'evidence-import-a'})});});
 const groups=new Map();for(const f of findings){const k=f.record.controlId;groups.set(k,(groups.get(k)||0)+1);}
 return Object.freeze({schemaVersion:'defence-intake-result/1',mode:'MOCK_IMPORT',realWrites:0,liveCoverage:'UNKNOWN',catalogCandidates:CATALOG.length,findings:Object.freeze(findings),groups:Object.freeze([...groups].sort(([a],[b])=>a.localeCompare(b)).map(([controlId,count])=>Object.freeze({controlId,count}))) });
}catch{bad();}}
return Object.freeze({intake,CATALOG,COLUMNS,MAX_BYTES,MAX_ROWS});
});
