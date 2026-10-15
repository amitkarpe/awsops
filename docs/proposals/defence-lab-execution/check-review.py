"""Offline focused security checks. NOT the AWS IAM simulator/effective policy proof."""
import copy,datetime,fnmatch,hashlib,json,pathlib,sys,types
root=pathlib.Path(__file__).resolve().parent
proposal=json.loads((root/'proposal.json').read_text())
# Deliberately synthetic bindings; never the private render or AWS credentials.
account='0'*12;bucket='synthetic-canary-only'
p=json.loads(json.dumps(proposal).replace('${LAB_ACCOUNT_ID}',account).replace('${EXACT_NEW_CANARY_BUCKET_NAME}',bucket))
def array(v):return v if isinstance(v,list) else [v]
def match(value,patterns):return any(fnmatch.fnmatchcase(value,x) for x in array(patterns))
def statement(s,action,resource,ctx):
 if 'Action' in s and not match(action,s['Action']):return False
 if 'NotAction' in s and match(action,s['NotAction']):return False
 if 'Resource' in s and not match(resource,s['Resource']):return False
 if 'NotResource' in s and match(resource,s['NotResource']):return False
 for op,items in s.get('Condition',{}).items():
  for key,value in items.items():
   actual=ctx.get(key)
   if op=='StringEquals' and actual not in array(value):return False
   if op=='StringNotEquals' and actual in array(value):return False
   if op=='NumericEquals' and (actual is None or float(actual)!=float(value)):return False
   if op=='Bool' and (actual is None or str(actual).lower()!=str(value).lower()):return False
   if op not in ('StringEquals','StringNotEquals','NumericEquals','Bool'):raise AssertionError('unsupported local condition')
 return True
def decision(role,action,resource,ctx):
 r=p[role]; policies=[r['permissions'],r['permissionsBoundary']]
 if any(s['Effect']=='Deny' and statement(s,action,resource,ctx) for pol in policies for s in pol['Statement']):return 'DENY'
 return 'ALLOW' if all(any(s['Effect']=='Allow' and statement(s,action,resource,ctx) for s in pol['Statement']) for pol in policies) else 'DENY'
ctx={'aws:RequestedRegion':'ap-southeast-1','s3:ResourceAccount':account,'aws:SecureTransport':'true','s3:max-keys':'1'}
arn='arn:aws:s3:::'+bucket
checks=[]
def check(name,actual,expected):assert actual==expected,(name,actual,expected);checks.append(name)
for action in ['s3:GetBucketLocation','s3:GetBucketTagging','s3:ListBucket','s3:GetBucketPublicAccessBlock','s3:PutBucketPublicAccessBlock']:
 check(action,decision('serviceExecutor',action,arn,ctx),'ALLOW')
 for key,value in [('aws:RequestedRegion','us-east-1'),('s3:ResourceAccount','1'*12),('aws:SecureTransport','false')]:
  check('deny-'+action+key,decision('serviceExecutor',action,arn,{**ctx,key:value}),'DENY')
 check('other-resource-'+action,decision('serviceExecutor',action,arn+'-other',ctx),'DENY')
for action in ['s3:GetObject','s3:PutObject','s3:DeleteObject','s3:CreateBucket','s3:DeleteBucket','s3:PutBucketPolicy','iam:PutRolePolicy','iam:PassRole','sts:AssumeRole','ec2:RevokeSecurityGroupIngress','config:StartConfigRulesEvaluation','ssm:SendCommand']:
 check('negative-'+action,decision('serviceExecutor',action,arn,ctx),'DENY')
check('list-too-many',decision('serviceExecutor','s3:ListBucket',arn,{**ctx,'s3:max-keys':'2'}),'DENY')
doc=f'arn:aws:ssm:ap-southeast-1:{account}:automation-definition/AWSOPS-Issue90-S3BpaCanary:1'
cctx={'aws:RequestedRegion':'ap-southeast-1','ssm:DocumentVersion':'1'}
check('start-exact',decision('oidcController','ssm:StartAutomationExecution',doc,cctx),'ALLOW')
for resource,context in [(doc[:-1]+'2',cctx),(doc,{**cctx,'ssm:DocumentVersion':'$DEFAULT'}),(doc.replace('ap-southeast-1','us-east-1'),cctx),(doc,cctx|{'aws:RequestedRegion':'us-east-1'})]:
 check('start-negative',decision('oidcController','ssm:StartAutomationExecution',resource,context),'DENY')
rolearn=f'arn:aws:iam::{account}:role/awsops-lab-s3-canary-execution'
check('pass-exact',decision('oidcController','iam:PassRole',rolearn,{'iam:PassedToService':'ssm.amazonaws.com'}),'ALLOW')
check('pass-other',decision('oidcController','iam:PassRole',rolearn+'-other',{'iam:PassedToService':'ssm.amazonaws.com'}),'DENY')
check('pass-wrong-service',decision('oidcController','iam:PassRole',rolearn,{'iam:PassedToService':'ec2.amazonaws.com'}),'DENY')
check('controller-no-direct-write',decision('oidcController','s3:PutBucketPublicAccessBlock',arn,ctx),'DENY')

script=(root/'runbook-script.py').read_text()
ns={};exec(script.replace('__PRIVATE_BINDING__',repr({'targetState':'RESERVED_NOT_CREATED','liveDecision':'NOT_AUTHORIZED'})),ns)
check('unbound-zero-SDK',ns['main']({},None)['state'],'BLOCKED_UNVERIFIED_BINDING_OR_APPROVAL')
flags={k:True for k in ns['FLAGS']};baseline={k:False for k in flags}
base={'targetState':'PROVIDER_VERIFIED','liveDecision':'APPROVED_EXACT_BATCH','baselineDigest':ns['digest'](baseline),'expiresAt':(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=4)).isoformat(),'accountId':account,'bucketName':bucket,'executionRoleId':'SYNTHETIC_ROLE_ID','tags':{'Disposable':'true'}}
class Error(Exception):
 def __init__(self,code):self.response={'Error':{'Code':code}}
class Fake:
 def __init__(self):self.calls=[];self.posture=baseline.copy();self.failwrite=False;self.region='ap-southeast-1';self.empty=True;self.root=False
 def get_caller_identity(self):
  self.calls.append('sts');return {'Account':account,'Arn':f'arn:aws:iam::{account}:root' if self.root else f'arn:aws:sts::{account}:assumed-role/awsops-lab-s3-canary-execution/test','UserId':'SYNTHETIC_ROLE_ID:test'}
 def guard(self,kwargs):assert kwargs['Bucket']==bucket and kwargs['ExpectedBucketOwner']==account
 def get_bucket_location(self,**kw):self.guard(kw);self.calls.append('location');return {'LocationConstraint':self.region}
 def get_bucket_tagging(self,**kw):self.guard(kw);self.calls.append('tags');return {'TagSet':[{'Key':'Disposable','Value':'true'}]}
 def list_objects_v2(self,**kw):self.guard(kw);assert kw['MaxKeys']==1;self.calls.append('list');return {'KeyCount':0 if self.empty else 1,'IsTruncated':False}
 def get_public_access_block(self,**kw):self.guard(kw);self.calls.append('read');return {'PublicAccessBlockConfiguration':self.posture.copy()}
 def put_public_access_block(self,**kw):
  self.guard(kw);assert kw['PublicAccessBlockConfiguration']==flags;self.calls.append('put')
  if self.failwrite:raise TimeoutError('private error must not escape')
  self.posture=flags.copy()
def execute(fake,binding=None):
 def config(**kw):assert kw['retries']['total_max_attempts']==1;return kw
 sys.modules['boto3']=types.SimpleNamespace(client=lambda service,**kw:fake)
 sys.modules['botocore']=types.ModuleType('botocore')
 sys.modules['botocore.config']=types.SimpleNamespace(Config=config)
 sys.modules['botocore.exceptions']=types.SimpleNamespace(ClientError=Error)
 n={};exec(script.replace('__PRIVATE_BINDING__',repr(binding or base)),n);return n['main']({},None)
f=Fake();r=execute(f);check('one-fixed-write',r['state'],'PROVIDER_MATCH_CONFIG_NOT_VERIFIED');check('put-count',f.calls.count('put'),1)
r=execute(f);check('repeat-drift',r['state'],'BLOCKED_DRIFT');check('no-replay-write',f.calls.count('put'),1)
f=Fake();f.failwrite=True;r=execute(f);check('unknown-no-retry',r['state'],'UNKNOWN_WRITE_OUTCOME');check('unknown-write-count',r['realWrites'],None);check('one-attempt',f.calls.count('put'),1)
for attr,value,state in [('root',True,'BLOCKED_IDENTITY'),('empty',False,'BLOCKED_NOT_PROVEN_EMPTY'),('region','us-east-1','BLOCKED_REGION')]:
 f=Fake();setattr(f,attr,value);r=execute(f);check(attr,r['state'],state);assert 'put' not in f.calls
f=Fake();f.posture=flags.copy();r=execute(f,base|{'baselineDigest':ns['digest'](flags)});check('secure-default-no-change',r['state'],'NO_CHANGE');assert 'put' not in f.calls
f=Fake();r=execute(f,base|{'expiresAt':'2000-01-01T00:00:00+00:00'});check('expired-no-call',r['state'],'BLOCKED_EXPIRED_OR_UNBOUNDED');assert not f.calls
print(json.dumps({'offlineChecks':len(checks),'result':'PASS','providerCalls':0,'scope':'local policy subset + injected fake runbook clients only','awsIamSimulation':'NOT_RUN','effectiveInstalledPolicies':'NOT_VERIFIED','realCanary':'NOT_CREATED','realWrites':0},indent=2))
