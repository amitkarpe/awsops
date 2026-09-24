'use strict';
// Offline candidate only. This tool never starts/restarts/deploys a service.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const pin = require('./upstream.json');
const PRE_MARKER = '  let resolvedAskContentIndex;';
const POST_MARKER = '  /**\n   * An interrupt steer enqueued just before the pause survives durably with';
const PRE = `  // awsops: capture only the native server-owned context before the CAS.
  let awsopsNativeEnvelope = null;
  if (Array.isArray(pendingAction?.payload?.action_requests) &&
      pendingAction.payload.action_requests.some(a =>
        typeof a?.name === 'string' && a.name.startsWith('decide_s3_ssl_reject_only'))) {
    try {
      awsopsNativeEnvelope = require('./awsops-native-gate.cjs')
        .prepareNativeRequest({ req, job, pendingAction, streamId });
    } catch {
      return sendGenerationJson(res, 403, { code: 'AWSOPS_NATIVE_NOT_READY' }, generationProtocolVersion);
    }
  }

`;
const POST = `  // awsops: the native single-winner CAS has succeeded. Commit before ACK/resume.
  if (awsopsNativeEnvelope) {
    try {
      const decision = await require('./awsops-native-gate.cjs')
        .persistNativeDecision(awsopsNativeEnvelope);
      mapped.resumeValue = decision.resumeValue;
    } catch {
      // Terminal operations are exact-generation fenced. A timeout/false result
      // is reconciliation-required, never a fabricated terminal success.
      const bounded = async (operation) => {
        let timer;
        try {
          return await Promise.race([
            operation(),
            new Promise((_, reject) => { timer = setTimeout(() => reject(Error('timeout')), 2500); }),
          ]);
        } finally { clearTimeout(timer); }
      };
      let finalized = false;
      let checkpointCleaned = false;
      let slotReleased = false;
      try {
        finalized = (await bounded(() => GenerationJobManager.completeJob(
          streamId, 'AWSOPS_DECISION_UNAVAILABLE', job.createdAt))) === true;
        if (finalized) {
          await bounded(() => deleteResumedGenerationCheckpoint({
            conversationId, checkpointerCfg, job, checkpointGeneration,
          }));
          checkpointCleaned = true;
        }
      } catch { logger.error('[awsops] Exact native terminalization needs reconciliation'); }
      try {
        await bounded(() => decrementPendingRequest(userId));
        slotReleased = true;
      } catch { logger.error('[awsops] Native concurrency slot needs reconciliation'); }
      return sendGenerationJson(res, 503, {
        code: 'AWSOPS_DECISION_UNAVAILABLE', dispatch_allowed: false,
        terminalization: finalized && checkpointCleaned && slotReleased ? 'FINALIZED' : 'RECONCILE_REQUIRED',
      }, generationProtocolVersion);
    }
  }

`;
const PAUSE_MARKER = '    const paused = await GenerationJobManager.approvals.pause(streamId, pendingAction, {';
const PAUSE = `    // awsops: bind fresh provider evidence BEFORE publishing any native pause.
    if (Array.isArray(pendingAction?.payload?.action_requests) &&
        pendingAction.payload.action_requests.some(a =>
          typeof a?.name === 'string' && a.name.startsWith('decide_s3_ssl_reject_only'))) {
      await require('./awsops-pause-gate.cjs').beforePause({
        client: this, manager: GenerationJobManager, pendingAction, streamId,
      });
    }

`;
function sha(raw) { return crypto.createHash('sha256').update(raw).digest('hex'); }
function blob(raw) {
  const data = Buffer.isBuffer(raw) ? raw : Buffer.from(raw);
  return crypto.createHash('sha1').update(Buffer.from(`blob ${data.length}\0`)).update(data).digest('hex');
}
function componentSpec(component) {
  if(component === 'resume') return {source:pin.controller, blob:pin.controller_blob, helper:'native_gate.cjs', installed:'awsops-native-gate.cjs', backup:'resume.original', suffix:'native'};
  if(component === 'pause') return {source:pin.producer, blob:pin.producer_blob, helper:'pause_gate.cjs', installed:'awsops-pause-gate.cjs', backup:'client.original', suffix:'pause'};
  throw Error('UNSUPPORTED_COMPONENT');
}
function render(raw, component='resume') {
  const spec=componentSpec(component);
  if (blob(raw) !== spec.blob) throw Error('UPSTREAM_SOURCE_DRIFT');
  let source = raw.toString('utf8');
  const insertions=component === 'pause' ? [[PAUSE_MARKER,PAUSE]] : [[PRE_MARKER,PRE],[POST_MARKER,POST]];
  for (const [marker, insertion] of insertions) {
    if (source.split(marker).length !== 2) throw Error('UPSTREAM_SEAM_DRIFT');
    source = source.replace(marker, insertion + marker);
  }
  return Buffer.from(source);
}
function file(p, limit = pin.fixture_max_bytes) {
  const st = fs.lstatSync(p);
  if (!st.isFile() || fs.realpathSync(p) !== p || st.size > limit) throw Error('UNSAFE_CANDIDATE_PATH');
  return fs.readFileSync(p);
}
function candidate(root, component) {
  if (!path.isAbsolute(root) || fs.realpathSync(root) !== root) throw Error('ISOLATED_COPY_REQUIRED');
  const marker = JSON.parse(file(path.join(root, '.awsops-offline-candidate.json'), 4096));
  if (marker.purpose !== 'offline-rehearsal' || marker.root !== root || marker.upstream_commit !== pin.commit || marker.live !== false) throw Error('ISOLATED_COPY_REQUIRED');
  const pkg = JSON.parse(file(path.join(root, 'package.json')));
  if (pkg.version !== pin.version) throw Error('UPSTREAM_VERSION_DRIFT');
  const spec=componentSpec(component);
  return {
    root, component, spec, target:path.join(root,spec.source), helper:path.join(root,path.dirname(spec.source),spec.installed),
    backupDir:path.join(root,`.awsops-${spec.suffix}-backup`), lock:path.join(root,'.awsops-native-lock'),
  };
}
function state(c) {
  const originalFile = path.join(c.backupDir,c.spec.backup);
  const current = file(c.target);
  const hasBackup = fs.existsSync(c.backupDir);
  if (hasBackup && (fs.realpathSync(c.backupDir) !== c.backupDir || !fs.lstatSync(c.backupDir).isDirectory())) throw Error('UNSAFE_BACKUP');
  const original = hasBackup ? file(originalFile) : current;
  const patched = render(original,c.component);
  let helper = fs.readFileSync(path.join(__dirname,c.spec.helper));
  if(c.component === 'pause') helper=Buffer.from(helper.toString().replace("require('./native_gate.cjs')","require('./awsops-native-gate.cjs')"));
  if (!current.equals(original) && !current.equals(patched)) throw Error('CANDIDATE_SOURCE_DRIFT');
  const hasHelper = fs.existsSync(c.helper);
  if (hasHelper && !file(c.helper).equals(helper)) throw Error('CANDIDATE_HELPER_DRIFT');
  if (current.equals(patched) && !hasHelper) throw Error('CANDIDATE_HELPER_MISSING');
  return {original, patched, helper, hasBackup, hasHelper, patchedNow: current.equals(patched)};
}
function atomic(fileName, data, mode) {
  const staged = fileName + '.awsops-staged';
  let fd;
  try {
    fd = fs.openSync(staged, 'wx', mode);
    fs.writeFileSync(fd, data); fs.fsyncSync(fd); fs.closeSync(fd); fd = undefined;
    fs.renameSync(staged, fileName);
  } catch (error) {
    if (fd !== undefined) { fs.closeSync(fd); fs.unlinkSync(staged); }
    throw error;
  }
}
function check(root, component='resume') {
  const c=candidate(root,component), s=state(c);
  return {state:s.patchedNow ? 'PATCHED' : 'ORIGINAL',original_blob:c.spec.blob,
    patched_sha256:sha(s.patched),helper_sha256:sha(s.helper),deployed:false};
}
function change(root, action, component='resume') {
  const c = candidate(root,component);
  const lock = fs.openSync(c.lock, 'wx', 0o600);
  try {
    const s = state(c);
    if (action === 'apply') {
      if (!s.hasBackup) {
        fs.mkdirSync(c.backupDir, {mode: 0o700});
        fs.writeFileSync(path.join(c.backupDir,c.spec.backup),s.original,{mode:0o600,flag:'wx'});
      }
      if (!s.hasHelper) atomic(c.helper, s.helper, 0o644);
      if (!s.patchedNow) atomic(c.target, s.patched, fs.statSync(c.target).mode & 0o777);
    } else if (action === 'rollback') {
      if (s.patchedNow) atomic(c.target, s.original, fs.statSync(c.target).mode & 0o777);
      if (s.hasHelper) fs.unlinkSync(c.helper);
    } else throw Error('UNSUPPORTED_ACTION');
    return check(root,component);
  } finally { fs.closeSync(lock); fs.unlinkSync(c.lock); }
}
if (require.main === module) {
  try {
    const [action,root,component='resume',...extra]=process.argv.slice(2);
    if(extra.length || !['check','apply','rollback'].includes(action))throw Error('INVALID_ARGUMENTS');
    console.log(JSON.stringify(action==='check' ? check(root,component) : change(root,action,component)));
  } catch {console.error('OFFLINE_NATIVE_REHEARSAL_REFUSED');process.exitCode=2;}
}
module.exports={pin,PRE,POST,PRE_MARKER,POST_MARKER,PAUSE,PAUSE_MARKER,render,blob,sha,check,change};
