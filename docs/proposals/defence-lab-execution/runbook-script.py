"""Review source for one embedded SSM step. No CLI entrypoint or live dispatch."""
import datetime
import hashlib
import json
import re

# Replaced only by the local review renderer; never supplied as Automation inputs.
BINDING = __PRIVATE_BINDING__
FLAGS = ('BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets')

def result(state, writes=0):
    return {'resourceAlias': 'canary-1', 'state': state, 'realWrites': writes,
            'configFreshness': 'NOT_VERIFIED', 'viewerAcceptance': 'NOT_RUN'}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def main(events, context):
    # Input cannot select target, code, flags, identity, expiry or approval.
    if events not in ({}, None):
        return result('BLOCKED_UNEXPECTED_INPUT')
    if BINDING.get('targetState') != 'PROVIDER_VERIFIED' or BINDING.get('liveDecision') != 'APPROVED_EXACT_BATCH':
        return result('BLOCKED_UNVERIFIED_BINDING_OR_APPROVAL')
    if not re.fullmatch(r'[0-9a-f]{64}', BINDING.get('baselineDigest', '')):
        return result('BLOCKED_BASELINE')
    try:
        expires = datetime.datetime.fromisoformat(BINDING['expiresAt'].replace('Z', '+00:00'))
        now = datetime.datetime.now(datetime.timezone.utc)
        if not (now < expires <= now + datetime.timedelta(minutes=5)):
            return result('BLOCKED_EXPIRED_OR_UNBOUNDED')
    except (KeyError, ValueError, TypeError):
        return result('BLOCKED_EXPIRY')

    # Imports are intentionally after all no-call gates; review checks inject fakes.
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
    cfg = Config(region_name='ap-southeast-1', retries={'total_max_attempts': 1, 'mode': 'standard'},
                 connect_timeout=3, read_timeout=7, ignore_configured_endpoint_urls=True)
    wrote = False
    attempted = False
    try:
        # Only the exact service-role session may reach S3; root is never accepted.
        identity = boto3.client('sts', config=cfg).get_caller_identity()
        prefix = 'arn:aws:sts::' + BINDING['accountId'] + ':assumed-role/awsops-lab-s3-canary-execution/'
        if identity.get('Account') != BINDING['accountId'] or not identity.get('Arn', '').startswith(prefix):
            return result('BLOCKED_IDENTITY')
        if identity.get('UserId', '').split(':', 1)[0] != BINDING['executionRoleId']:
            return result('BLOCKED_ROLE_ID')
        s3 = boto3.client('s3', config=cfg)
        args = {'Bucket': BINDING['bucketName'], 'ExpectedBucketOwner': BINDING['accountId']}
        if s3.get_bucket_location(**args).get('LocationConstraint') != 'ap-southeast-1':
            return result('BLOCKED_REGION')
        tags = s3.get_bucket_tagging(**args).get('TagSet', [])
        if len({x.get('Key') for x in tags}) != len(tags):
            return result('BLOCKED_TAGS')
        if {x.get('Key'): x.get('Value') for x in tags} != BINDING['tags']:
            return result('BLOCKED_TAGS')
        listing = s3.list_objects_v2(**args, MaxKeys=1)
        if listing.get('KeyCount') != 0 or listing.get('IsTruncated') is not False or listing.get('Contents') or listing.get('NextContinuationToken'):
            return result('BLOCKED_NOT_PROVEN_EMPTY')
        def posture():
            try:
                raw = s3.get_public_access_block(**args)['PublicAccessBlockConfiguration']
                if set(raw) != set(FLAGS) or any(type(raw[k]) is not bool for k in FLAGS):
                    raise ValueError('INVALID_POSTURE')
                return raw
            except ClientError as exc:
                if exc.response.get('Error', {}).get('Code') == 'NoSuchPublicAccessBlockConfiguration':
                    return None
                raise
        before = posture()
        if digest(before) != BINDING['baselineDigest']:
            return result('BLOCKED_DRIFT')
        if before is not None and all(before[k] for k in FLAGS):
            return result('NO_CHANGE')
        if datetime.datetime.now(datetime.timezone.utc) >= expires:
            return result('BLOCKED_EXPIRED')
        attempted = True
        s3.put_public_access_block(**args, PublicAccessBlockConfiguration={k: True for k in FLAGS})
        wrote = True
        after = posture()
        return result('PROVIDER_MATCH_CONFIG_NOT_VERIFIED' if after and all(after[k] for k in FLAGS) else 'NEEDS_REVIEW', 1)
    except Exception:
        # Never print raw exception/response or claim no write after an uncertain call.
        return result('UNKNOWN_WRITE_OUTCOME' if attempted and not wrote else 'READBACK_UNKNOWN' if wrote else 'BLOCKED_PROVIDER_READ', 1 if wrote else None if attempted else 0)
