"""Local-only private review rendering. Never imports an AWS SDK or calls AWS."""
import hashlib,json,pathlib,re,sys,os
root=pathlib.Path(__file__).resolve().parent
binding=json.loads(pathlib.Path(sys.argv[1]).read_text()); out=pathlib.Path(sys.argv[2])
if not re.fullmatch(r'\d{12}',binding['accountId']): raise SystemExit('INVALID_ACCOUNT_BINDING')
if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',binding['bucketName']): raise SystemExit('INVALID_BUCKET_BINDING')
if binding['region']!='ap-southeast-1' or binding['accountAlias']!='amit': raise SystemExit('INVALID_TARGET_SCOPE')
if root.is_relative_to(out.resolve()) or out.resolve().is_relative_to(root.parents[2]): raise SystemExit('OUTPUT_MUST_BE_OUTSIDE_REPOSITORY')
out.mkdir(mode=0o700,parents=True,exist_ok=True)
text=(root/'proposal.json').read_text().replace('${LAB_ACCOUNT_ID}',binding['accountId']).replace('${EXACT_NEW_CANARY_BUCKET_NAME}',binding['bucketName'])
packet=json.loads(text)
# No JSON null/false literal is injected into Python source.
script=(root/'runbook-script.py').read_text().replace('__PRIVATE_BINDING__',repr(binding))
compile(script,'rendered-runbook','exec')
runbook={'schemaVersion':'0.3','description':'Issue90 single private canary; installation review only, admission currently blocked','assumeRole':f"arn:aws:iam::{binding['accountId']}:role/awsops-lab-s3-canary-execution",'parameters':{},'mainSteps':[{'name':'verifyAndTighten','action':'aws:executeScript','timeoutSeconds':120,'maxAttempts':1,'onFailure':'Abort','isEnd':True,'inputs':{'Runtime':'python3.12','Handler':'main','InputPayload':{},'Script':script},'outputs':[{'Name':'Receipt','Selector':'$.Payload','Type':'StringMap'}]}],'outputs':['verifyAndTighten.Receipt']}
# Payload includes numeric/null fields; do not misdeclare it as a StringMap.
runbook['mainSteps'][0]['outputs']=[{'Name':'State','Selector':'$.Payload.state','Type':'String'}]
runbook['outputs']=['verifyAndTighten.State']
files={'rendered-policies.json':packet,'fixed-runbook.json':runbook,'target-binding.json':binding}
manifest={'source':'PR93','status':'PRIVATE_CANDIDATE_RENDERED_NOT_PROVIDER_VERIFIED','files':{}}
for name,obj in files.items():
 data=(json.dumps(obj,indent=2)+'\n').encode(); f=out/name
 fd=os.open(f,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
 with os.fdopen(fd,'wb') as s:s.write(data)
 manifest['files'][name]=hashlib.sha256(data).hexdigest()
f=out/'manifest.json';fd=os.open(f,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as s:json.dump(manifest,s,indent=2);s.write('\n')
print('PRIVATE_RENDER=PASS; PROVIDER_BINDING=NOT_VERIFIED; LIVE_GATE=BLOCKED; identifiers and digests retained privately')
