'use strict';
// Narrow YAML update for the already isolated LibreChat application.
const fs = require('node:fs');
const path = require('node:path');
const {isDeepStrictEqual} = require('node:util');
const crypto = require('node:crypto');
const nativeStore = require('./native_store.cjs');

const TOOL = 'approve_s3_canary_once_mcp_awsops';
const FIXTURE_ENDPOINT = 'awsops_canary_fixture';
const FIXTURE_MODEL = 'awsops-canary-fixed';
const FIXTURE_URL = 'http://127.0.0.1:4312/v1';
const BACKUP = '.awsops-issue90-runtime-config.original';
const NATIVE_SOURCE_BACKUP = '.awsops-issue90-native-source-revision.original';
const CONFIG_RESUME_YAML_BACKUP = '.awsops-issue90-config-resume-runtime.original';
const CONFIG_RESUME_NATIVE_BACKUP = '.awsops-issue90-config-resume-native.original';
const CONFIG_RESUME_NATIVE_JOURNAL = '.awsops-issue90-config-resume-native.json';
const LEGACY_SOURCE_REVISION = 'd9545f7cd3aca485a137c5b8e8b8d55f02a004c8';
const D090_SOURCE_REVISION = 'd090c98561e87e4be1ad234891f3f78bc665aa6f';
const LEGACY_NATIVE_GATE_COMMIT = '1ee21e15017a066413bf705c96749ab7bf9cffd2';
const LEGACY_NATIVE_KEYS = ['version','enabled','agent_id','python','source_root','database'];
const CURRENT_NATIVE_KEYS = ['agent_id','application_binding','application_database','database','enabled',
  'python','source_revision','source_root','source_version','version'];
const LAB_ALIASES = ['lab-dev','lab-poc','lab-qa','lab-sec'];
const CANARY_SOURCE_VERSION = 'v1.0.0-mock';
const REGION = 'ap-southeast-1';
const FIXTURE_KEYS = ['apiKey','baseURL','models','name','titleConvo'];
const FIXTURE_MODEL_KEYS = ['default','fetch'];
function fail(code) { throw Error(code); }
function privatePath(file) {
  if (!path.isAbsolute(file) || fs.realpathSync(file) !== file) fail('CONFIG_PATH_UNSAFE');
  const st = fs.lstatSync(file);
  if (!st.isFile() || (st.mode & 0o077) !== 0) fail('CONFIG_FILE_UNSAFE');
  return st;
}
function readPrivateBackup(file, uid, gid) {
  const pathStat = fs.lstatSync(file);
  if (!pathStat.isFile() || pathStat.isSymbolicLink() || pathStat.uid !== uid ||
      pathStat.gid !== gid || (pathStat.mode & 0o777) !== 0o600) fail('CONFIG_BACKUP_DRIFT');
  const fd = fs.openSync(file, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
  try {
    const opened = fs.fstatSync(fd);
    if (!opened.isFile() || opened.dev !== pathStat.dev || opened.ino !== pathStat.ino ||
        opened.uid !== uid || opened.gid !== gid || (opened.mode & 0o777) !== 0o600)
      fail('CONFIG_BACKUP_DRIFT');
    const data = fs.readFileSync(fd);
    return {data, sha256:crypto.createHash('sha256').update(data).digest('hex')};
  } finally { fs.closeSync(fd); }
}
function record(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function keysetCode(value, expected) {
  if (!record(value)) return 'NOT_OBJECT';
  const keys=Object.keys(value).sort(), wanted=[...expected].sort();
  if (isDeepStrictEqual(keys,wanted)) return 'EXACT';
  if (keys.every(key=>wanted.includes(key))) return 'MISSING_FIELDS';
  if (wanted.every(key=>keys.includes(key))) return 'EXTRA_FIELDS';
  return 'OTHER_FIELDS';
}
function projectFixtureShape(raw, yaml) {
  const result=(config,endpoints,custom,address)=>({v:1,complete:true,config,endpoints,custom,allowed_addresses:address});
  const unknownAddress={state:'UNKNOWN',container_type:'UNKNOWN',count:null};
  let config;
  try { config=yaml.load(raw.toString('utf8')) ?? {}; }
  catch { return result('PARSE_REFUSED','UNKNOWN',{state:'UNKNOWN',container_type:'UNKNOWN',count:null},unknownAddress); }
  if (!record(config)) return result('ROOT_NOT_OBJECT','UNKNOWN',{state:'UNKNOWN',container_type:'UNKNOWN',count:null},unknownAddress);
  const endpoints=config.endpoints;
  if (endpoints == null) return result('OBJECT','ABSENT',
    {state:'EMPTY_UNCONFIGURED',container_type:endpoints===null?'NULL':'ABSENT',count:0},
    {state:'ABSENT',container_type:'ABSENT',count:0});
  if (!record(endpoints)) return result('OBJECT','NOT_OBJECT',
    {state:'UNKNOWN',container_type:'UNKNOWN',count:null},unknownAddress);
  const value=endpoints.custom;
  const customType=value === undefined ? 'ABSENT' : value === null ? 'NULL' : Array.isArray(value) ? 'ARRAY' : 'OTHER';
  const count=Array.isArray(value) ? value.length : customType === 'ABSENT' || customType === 'NULL' ? 0 : null;
  const fixture={name:FIXTURE_ENDPOINT,apiKey:'fixture-only',baseURL:FIXTURE_URL,
    models:{default:[FIXTURE_MODEL],fetch:false},titleConvo:false};
  const previousFixture={...fixture,baseURL:'http://localhost:4312/v1'};
  let state='UNKNOWN_NONEMPTY',entryType='NONE',entryKeyset='NOT_APPLICABLE',modelsKeyset='NOT_APPLICABLE';
  if (customType === 'ABSENT' || customType === 'NULL' || (customType === 'ARRAY' && count === 0)) {
    state='EMPTY_UNCONFIGURED';
  } else if (customType !== 'ARRAY') {
    state='CUSTOM_NOT_ARRAY';
  } else if (count !== 1) {
    state='UNKNOWN_NONEMPTY';
  } else {
    const entry=value[0]; entryType=Array.isArray(entry) ? 'ARRAY' : entry === null ? 'NULL' : typeof entry;
    entryKeyset=keysetCode(entry,FIXTURE_KEYS);
    modelsKeyset=record(entry) ? keysetCode(entry.models,FIXTURE_MODEL_KEYS) : 'NOT_APPLICABLE';
    if (isDeepStrictEqual(entry,previousFixture)) state='KNOWN_LEGACY_FIXTURE';
    else if (isDeepStrictEqual(entry,fixture)) state='KNOWN_CURRENT_FIXTURE';
    else state='UNKNOWN_NONEMPTY';
  }
  const addresses=endpoints.allowedAddresses;
  let addressState='ABSENT';
  if (addresses !== undefined && addresses !== null) {
    if (!Array.isArray(addresses)) addressState='NOT_ARRAY';
    else if (isDeepStrictEqual(addresses,[])) addressState='EMPTY';
    else if (isDeepStrictEqual(addresses,['localhost:4312'])) addressState='KNOWN_LEGACY';
    else if (isDeepStrictEqual(addresses,['127.0.0.1:4312'])) addressState='KNOWN_CURRENT';
    else addressState='UNKNOWN';
  }
  return result('OBJECT','OBJECT',
    {state,container_type:customType,count,entry_type:entryType,entry_keyset:entryKeyset,
      models_keyset:modelsKeyset},{state:addressState,
      container_type:addresses === undefined ? 'ABSENT' : addresses === null ? 'NULL' : Array.isArray(addresses) ? 'ARRAY' : 'OTHER',
      count:Array.isArray(addresses) ? addresses.length : null});
}
function validateNativeConfig(value, root, ownerStat, sourceRoot=path.resolve(__dirname,'../..')) {
  const owner = ownerStat || fs.lstatSync(path.join(root,'state/native.json'));
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).sort().join(',') !== [...CURRENT_NATIVE_KEYS].sort().join(',') ||
      value.version !== 1 || value.enabled !== true || typeof value.agent_id !== 'string' ||
      !/^[A-Za-z0-9_.:-]{1,128}$/.test(value.agent_id) || value.python !== nativeStore.SYSTEM_PYTHON ||
      value.source_root !== path.join(root,'awsops') ||
      ![path.join(root,'state/native.sqlite'),path.join(root,'state/receipt.sqlite3')].includes(value.database) ||
      value.application_database !== path.join(root,'state/canary.sqlite') ||
      typeof value.application_binding !== 'string' || !path.isAbsolute(value.application_binding) ||
      !value.application_binding.startsWith(path.join(root,'state') + path.sep) ||
      typeof value.source_revision !== 'string' || !/^[a-f0-9]{40}$/.test(value.source_revision) ||
      typeof value.source_version !== 'string' || !/^v[0-9]+\.[0-9]+\.[0-9]+-mock$/.test(value.source_version))
    fail('NATIVE_CONFIG_SCHEMA_DRIFT');
  try { nativeStore.validateDecisionDatabase(value.database,{root,uid:owner.uid,gid:owner.gid,
    sourceRoot}); }
  catch { fail('NATIVE_CONFIG_DATABASE_UNSAFE'); }
  return value;
}
function readPrivateJson(file, code, maxBytes=8192, expectedUid=process.getuid()) {
  let st;
  try { st=privatePath(file); } catch { fail(code); }
  if (st.uid !== expectedUid || (st.mode & 0o777) !== 0o600 || st.size > maxBytes)
    fail(code);
  const fd = fs.openSync(file,fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
  try {
    const opened = fs.fstatSync(fd);
    if (!opened.isFile() || opened.dev !== st.dev || opened.ino !== st.ino ||
        opened.uid !== st.uid || (opened.mode & 0o777) !== 0o600) fail(code);
    return JSON.parse(fs.readFileSync(fd,'utf8'));
  } finally { fs.closeSync(fd); }
}
function validateLegacyNativeConfig(value, root, ownerStat, sourceRoot=path.resolve(__dirname,'../..')) {
  const owner = ownerStat || fs.lstatSync(path.join(root,'state/native.json'));
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).sort().join(',') !== [...LEGACY_NATIVE_KEYS].sort().join(',') ||
      value.version !== 1 || value.enabled !== true || typeof value.agent_id !== 'string' ||
      !/^[A-Za-z0-9_.:-]{1,128}$/.test(value.agent_id) ||
      value.source_root !== path.join(root,'awsops') ||
      ![path.join(root,'state/native.sqlite'),path.join(root,'state/receipt.sqlite3')].includes(value.database))
    fail('NATIVE_LEGACY_SCHEMA_UNSUPPORTED');
  try {
    nativeStore.validateLegacyPython(value.python);
    nativeStore.validateDecisionDatabase(value.database,{root,uid:owner.uid,gid:owner.gid,
      sourceRoot});
  } catch { fail('NATIVE_LEGACY_RUNTIME_UNSUPPORTED'); }
  return value;
}
function validateReadConfig(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).sort().join(',') !== 'accounts,profile,region,source_account_id' ||
      value.profile !== 'amit' || value.region !== REGION ||
      typeof value.source_account_id !== 'string' || !/^[0-9]{12}$/.test(value.source_account_id) ||
      !Array.isArray(value.accounts) || value.accounts.length !== LAB_ALIASES.length) fail('NATIVE_READ_CONFIG_UNSUPPORTED');
  const aliases=[]; const ids=[];
  for (const row of value.accounts) {
    if (!row || typeof row !== 'object' || Array.isArray(row) ||
        Object.keys(row).sort().join(',') !== 'account_id,alias' ||
        typeof row.alias !== 'string' || !LAB_ALIASES.includes(row.alias) ||
        typeof row.account_id !== 'string' || !/^[0-9]{12}$/.test(row.account_id))
      fail('NATIVE_READ_CONFIG_UNSUPPORTED');
    aliases.push(row.alias); ids.push(row.account_id);
  }
  if (aliases.sort().join(',') !== [...LAB_ALIASES].sort().join(',') || new Set(ids).size !== ids.length)
    fail('NATIVE_READ_CONFIG_UNSUPPORTED');
  return value;
}
function prepareNativeCanaryBinding(root, bucket) {
  if (!path.isAbsolute(root) || fs.realpathSync(root) !== root) fail('ISOLATED_ROOT_REQUIRED');
  if (typeof bucket !== 'string' || !/^awsops-dev-issue90-s3-canary-[a-z0-9]{12}$/.test(bucket))
    fail('NATIVE_TARGET_SCOPE_UNSUPPORTED');
  const state=path.join(root,'state');
  const stateStat=fs.lstatSync(state);
  if (!stateStat.isDirectory() || stateStat.isSymbolicLink() || stateStat.uid !== process.getuid() ||
      (stateStat.mode & 0o777) !== 0o700) fail('NATIVE_STATE_DIRECTORY_UNSAFE');
  const {file:nativeFile,st:nativeStat}=nativeTarget(root);
  const native=JSON.parse(readNativeBytes(nativeFile).toString('utf8'));
  const nativeKeys=native && typeof native==='object' && !Array.isArray(native) ? Object.keys(native).sort().join(',') : '';
  if (nativeKeys === [...LEGACY_NATIVE_KEYS].sort().join(',')) validateLegacyNativeConfig(native,root,nativeStat);
  else validateNativeConfig(native,root,nativeStat);
  const read=validateReadConfig(readPrivateJson(path.join(state,'read.json'),'NATIVE_READ_CONFIG_UNAVAILABLE'));
  const bindingPath=path.join(state,'binding.private.json');
  const expected={account_id:read.source_account_id,bucket};
  let bindingStat;
  try { bindingStat=fs.lstatSync(bindingPath); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (bindingStat) {
    const existing=readPrivateJson(bindingPath,'NATIVE_TARGET_BINDING_MISMATCH',4096);
    if (!existing || typeof existing !== 'object' || Array.isArray(existing) ||
        Object.keys(existing).sort().join(',') !== 'account_id,bucket' ||
        existing.account_id !== expected.account_id || existing.bucket !== expected.bucket)
      fail('NATIVE_TARGET_BINDING_MISMATCH');
    return {state:'ALREADY_BOUND'};
  }
  const data=Buffer.from(JSON.stringify(expected,null,2)+'\n');
  const temp=path.join(state,`.binding.private.${process.pid}.${crypto.randomBytes(8).toString('hex')}.tmp`);
  const fd=fs.openSync(temp,'wx',0o600);
  try { fs.fchmodSync(fd,0o600); fs.writeFileSync(fd,data); fs.fsyncSync(fd); }
  finally { fs.closeSync(fd); }
  try {
    fs.linkSync(temp,bindingPath);
    const dirfd=fs.openSync(state,fs.constants.O_RDONLY);
    try { fs.fsyncSync(dirfd); } finally { fs.closeSync(dirfd); }
  } catch (error) {
    if (error.code === 'EEXIST') fail('NATIVE_TARGET_BINDING_RACE');
    throw error;
  } finally { fs.unlinkSync(temp); }
  const written=readPrivateJson(bindingPath,'NATIVE_TARGET_BINDING_READBACK',4096);
  if (!isDeepStrictEqual(written,expected)) fail('NATIVE_TARGET_BINDING_READBACK');
  return {state:'BOUND'};
}
function expandedLegacyNativeConfig(value, root, revision, ownerStat, sourceRoot) {
  const legacy=validateLegacyNativeConfig(value,root,ownerStat,sourceRoot);
  return {...legacy,python:nativeStore.SYSTEM_PYTHON,source_revision:revision,
    application_database:path.join(root,'state/canary.sqlite'),
    application_binding:path.join(root,'state/binding.private.json'),
    source_version:CANARY_SOURCE_VERSION};
}
function normalizeNativeConfig(value, root, revision, ownerStat, sourceRoot) {
  const keysValue = value && typeof value === 'object' && !Array.isArray(value) ? Object.keys(value) : [];
  if (keysValue.sort().join(',') === [...LEGACY_NATIVE_KEYS].sort().join(',')) {
    const upgraded=expandedLegacyNativeConfig(value,root,revision,ownerStat,sourceRoot);
    const state=path.join(root,'state');
    const read=validateReadConfig(readPrivateJson(path.join(state,'read.json'),'NATIVE_READ_CONFIG_UNAVAILABLE'));
    const bindingPath=path.join(state,'binding.private.json');
    const binding=readPrivateJson(bindingPath,'NATIVE_TARGET_BINDING_UNAVAILABLE',4096);
    if (!binding || typeof binding !== 'object' || Array.isArray(binding) ||
        Object.keys(binding).sort().join(',') !== 'account_id,bucket' ||
        binding.account_id !== read.source_account_id ||
        typeof binding.bucket !== 'string' ||
        !/^awsops-dev-issue90-s3-canary-[a-z0-9]{12}$/.test(binding.bucket))
      fail('NATIVE_TARGET_BINDING_MISMATCH');
    return upgraded;
  }
  if (keysValue.sort().join(',') !== [...CURRENT_NATIVE_KEYS].sort().join(','))
    fail('NATIVE_CONFIG_SCHEMA_UNSUPPORTED');
  const current=validateNativeConfig(value,root,ownerStat,sourceRoot);
  if (current.source_revision === revision) return current;
  if (current.source_revision !== LEGACY_SOURCE_REVISION) fail('NATIVE_SOURCE_REVISION_UNEXPECTED');
  return {...current,source_revision:revision};
}
function inspectNativeConfig(root) {
  if (!path.isAbsolute(root) || fs.realpathSync(root) !== root) fail('ISOLATED_ROOT_REQUIRED');
  const {file,st}=nativeTarget(root,{rootReadOnly:true});
  const value=JSON.parse(readNativeBytes(file).toString('utf8'));
  const valueKeys=value && typeof value==='object' && !Array.isArray(value) ? Object.keys(value).sort().join(',') : '';
  if (valueKeys === [...LEGACY_NATIVE_KEYS].sort().join(',')) validateLegacyNativeConfig(value,root,st);
  else if (valueKeys === [...CURRENT_NATIVE_KEYS].sort().join(',')) {
    validateNativeConfig(value,root,st);
    if (value.source_revision !== LEGACY_SOURCE_REVISION) fail('NATIVE_SOURCE_REVISION_UNSUPPORTED');
  } else fail('NATIVE_CONFIG_SCHEMA_UNSUPPORTED');
  validateReadConfig(readPrivateJson(path.join(root,'state/read.json'),'NATIVE_READ_CONFIG_UNAVAILABLE',8192,st.uid));
  const marker=path.join(root,'awsops/SOURCE_REVISION');
  try { fs.lstatSync(marker); fail('SOURCE_REVISION_ALREADY_PRESENT'); }
  catch (error) { if (error?.message?.startsWith('SOURCE_REVISION_')) throw error; if (error.code !== 'ENOENT') throw error; }
  const packageFile=path.join(root,'app/package.json');
  const packageStat=fs.lstatSync(packageFile);
  if (!packageStat.isFile() || packageStat.isSymbolicLink() || fs.realpathSync(packageFile) !== packageFile)
    fail('APP_PACKAGE_UNSAFE');
  const app=JSON.parse(fs.readFileSync(packageFile,'utf8'));
  if (app.name !== 'LibreChat' || app.version !== 'v0.8.8-rc1') fail('APP_PACKAGE_UNSUPPORTED');
  return {state:'PREWRITE_COMPATIBLE',ledger:'READONLY_VALIDATED',application:'PINNED_PACKAGE_VERSION'};
}
function nativeTarget(root, {rootReadOnly=false}={}) {
  const file = path.join(root,'state/native.json');
  const st = privatePath(file);
  if ((st.mode & 0o777) !== 0o600) fail('NATIVE_CONFIG_METADATA_DRIFT');
  if (process.getuid() === 0) {
    if (!rootReadOnly || root !== '/opt/awsops-native-canary' || st.uid === 0)
      fail('NATIVE_CONFIG_METADATA_DRIFT');
    const rootStat=fs.lstatSync(root),stateStat=fs.lstatSync(path.join(root,'state'));
    if (!rootStat.isDirectory() || rootStat.isSymbolicLink() || !stateStat.isDirectory() || stateStat.isSymbolicLink() ||
        rootStat.uid !== st.uid || rootStat.gid !== st.gid || stateStat.uid !== st.uid || stateStat.gid !== st.gid ||
        (rootStat.mode & 0o777) !== 0o700 || (stateStat.mode & 0o777) !== 0o700)
      fail('NATIVE_CONFIG_METADATA_DRIFT');
  } else if (st.uid !== process.getuid()) fail('NATIVE_CONFIG_METADATA_DRIFT');
  return {file, st};
}
function readNativeBytes(file) {
  const fd = fs.openSync(file,fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
  try { return fs.readFileSync(fd); } finally { fs.closeSync(fd); }
}
function nativeSnapshotMatches(file, priorStat, priorBytes) {
  const currentStat = fs.lstatSync(file);
  return currentStat.isFile() && !currentStat.isSymbolicLink() &&
    currentStat.dev === priorStat.dev && currentStat.ino === priorStat.ino &&
    currentStat.uid === priorStat.uid && currentStat.gid === priorStat.gid &&
    (currentStat.mode & 0o777) === (priorStat.mode & 0o777) && readNativeBytes(file).equals(priorBytes);
}
function migrateNativeSourceRevision(root) {
  if (!path.isAbsolute(root) || fs.realpathSync(root) !== root) fail('ISOLATED_ROOT_REQUIRED');
  const marker = path.join(root,'awsops/SOURCE_REVISION');
  const markerStat = fs.lstatSync(marker);
  if (!markerStat.isFile() || markerStat.isSymbolicLink()) fail('SOURCE_REVISION_FILE_UNSAFE');
  const revision = fs.readFileSync(marker,'ascii').trim();
  if (!/^[a-f0-9]{40}$/.test(revision) || revision === LEGACY_SOURCE_REVISION)
    fail('SOURCE_REVISION_MISMATCH');
  const {file,st} = nativeTarget(root);
  const backup = path.join(root,'state',NATIVE_SOURCE_BACKUP);
  const original = readNativeBytes(file);
  const parsed=JSON.parse(original.toString('utf8'));
  const updated = Buffer.from(JSON.stringify(normalizeNativeConfig(parsed,root,revision,st),null,2) + '\n');
  let backupStat;
  try { backupStat = fs.lstatSync(backup); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (!backupStat && Object.keys(parsed).sort().join(',') === [...CURRENT_NATIVE_KEYS].sort().join(',') &&
      parsed.source_revision === revision) return {state:'ALREADY_CURRENT'};
  if (backupStat) {
    const {data:saved} = readPrivateBackup(backup,st.uid,st.gid);
    let expected;
    try {
      const prior=JSON.parse(saved.toString('utf8'));
      const priorKeys=prior && typeof prior==='object' && !Array.isArray(prior) ? Object.keys(prior).sort().join(',') : '';
      const normalized=priorKeys === [...LEGACY_NATIVE_KEYS].sort().join(',')
        ? expandedLegacyNativeConfig(prior,root,revision,st)
        : normalizeNativeConfig(prior,root,revision,st);
      expected=Buffer.from(JSON.stringify(normalized,null,2)+'\n');
    }
    catch { fail('NATIVE_CONFIG_BACKUP_DRIFT'); }
    if (!saved.equals(original) && !expected.equals(original)) fail('NATIVE_CONFIG_BACKUP_DRIFT');
    if (!expected.equals(original)) {
      if (!nativeSnapshotMatches(file,st,original)) fail('NATIVE_CONFIG_READBACK_DRIFT');
      atomic(file,expected,st,'.awsops-source-staged');
    }
  } else {
    const fd = fs.openSync(backup,'wx',0o600);
    try {
      fs.fchownSync(fd,st.uid,st.gid); fs.fchmodSync(fd,0o600);
      fs.writeFileSync(fd,original); fs.fsyncSync(fd);
    } finally { fs.closeSync(fd); }
    const dir = fs.openSync(path.dirname(backup),fs.constants.O_RDONLY);
    try { fs.fsyncSync(dir); } finally { fs.closeSync(dir); }
    const {data:saved,sha256} = readPrivateBackup(backup,st.uid,st.gid);
    if (sha256 !== crypto.createHash('sha256').update(original).digest('hex') ||
        !saved.equals(original) || !nativeSnapshotMatches(file,st,original)) fail('NATIVE_CONFIG_BACKUP_DRIFT');
    atomic(file,updated,st,'.awsops-source-staged');
  }
  const verifyStat = fs.lstatSync(file);
  const verifiedBytes = readNativeBytes(file);
  const verified = validateNativeConfig(JSON.parse(verifiedBytes.toString('utf8')),root,st);
  if (!verifiedBytes.equals(updated) || verified.source_revision !== revision || verifyStat.uid !== st.uid || verifyStat.gid !== st.gid ||
      (verifyStat.mode & 0o777) !== (st.mode & 0o777)) fail('NATIVE_CONFIG_READBACK_DRIFT');
  return {state:'UPDATED'};
}
function rollbackNativeSourceRevision(root) {
  if (!path.isAbsolute(root) || fs.realpathSync(root) !== root) fail('ISOLATED_ROOT_REQUIRED');
  const {file,st} = nativeTarget(root);
  const backup = path.join(root,'state',NATIVE_SOURCE_BACKUP);
  let backupStat;
  try { backupStat = fs.lstatSync(backup); } catch (error) { if (error.code === 'ENOENT') return {state:'NO_CHANGE'}; throw error; }
  const {data:saved} = readPrivateBackup(backup,st.uid,st.gid);
  const marker = path.join(root,'awsops/SOURCE_REVISION');
  const revision = fs.readFileSync(marker,'ascii').trim();
  let expected;
  try {
    const prior=JSON.parse(saved.toString('utf8'));
    const priorKeys=prior && typeof prior==='object' && !Array.isArray(prior) ? Object.keys(prior).sort().join(',') : '';
    const normalized=priorKeys === [...LEGACY_NATIVE_KEYS].sort().join(',')
      ? expandedLegacyNativeConfig(prior,root,revision,st)
      : normalizeNativeConfig(prior,root,revision,st);
    expected=Buffer.from(JSON.stringify(normalized,null,2)+'\n');
  }
  catch { fail('NATIVE_CONFIG_BACKUP_DRIFT'); }
  if (!readNativeBytes(file).equals(expected)) fail('NATIVE_CONFIG_ROLLBACK_DRIFT');
  atomic(file,saved,st,'.awsops-source-rollback');
  if (!readNativeBytes(file).equals(saved)) fail('NATIVE_CONFIG_ROLLBACK_DRIFT');
  fs.unlinkSync(backup);
  const dir = fs.openSync(path.dirname(backup),fs.constants.O_RDONLY);
  try { fs.fsyncSync(dir); } finally { fs.closeSync(dir); }
  return {state:'ROLLED_BACK'};
}
function privateDigest(file, uid, gid) {
  const st=fs.lstatSync(file);
  if (!st.isFile() || st.isSymbolicLink() || st.uid !== uid || st.gid !== gid || (st.mode & 0o777) !== 0o600)
    fail('CONFIG_RESUME_PRIVATE_FILE_DRIFT');
  const fd=fs.openSync(file,fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
  try {
    const opened=fs.fstatSync(fd);
    if (!opened.isFile() || opened.dev !== st.dev || opened.ino !== st.ino || opened.uid !== uid ||
        opened.gid !== gid || (opened.mode & 0o777) !== 0o600) fail('CONFIG_RESUME_PRIVATE_FILE_DRIFT');
    return crypto.createHash('sha256').update(fs.readFileSync(fd)).digest('hex');
  } finally { fs.closeSync(fd); }
}
function preflightConfigResume(root, targetRevision, expectedBindingSha256, expectedDatabaseSha256) {
  if (!path.isAbsolute(root) || fs.realpathSync(root)!==root) fail('ISOLATED_ROOT_REQUIRED');
  if (typeof targetRevision!=='string' || !/^[a-f0-9]{40}$/.test(targetRevision) ||
      targetRevision===D090_SOURCE_REVISION) fail('CONFIG_RESUME_SOURCE_PIN_MISMATCH');
  for (const digest of [expectedBindingSha256,expectedDatabaseSha256])
    if (typeof digest!=='string' || !/^[a-f0-9]{64}$/.test(digest)) fail('CONFIG_RESUME_BASELINE_INVALID');
  const marker=path.join(root,'awsops/SOURCE_REVISION');
  const markerStat=fs.lstatSync(marker);
  if (!markerStat.isFile() || markerStat.isSymbolicLink() || (markerStat.mode&0o777)!==0o644 ||
      fs.readFileSync(marker,'ascii').trim()!==D090_SOURCE_REVISION)
    fail('CONFIG_RESUME_SOURCE_PIN_MISMATCH');
  const {file,st}=nativeTarget(root,{rootReadOnly:process.getuid()===0});
  const currentBytes=readNativeBytes(file),current=JSON.parse(currentBytes.toString('utf8'));
  if (keysetCode(current,CURRENT_NATIVE_KEYS)!=='EXACT' || current.source_revision!==D090_SOURCE_REVISION)
    fail('CONFIG_RESUME_NATIVE_PRESTATE_DRIFT');
  validateNativeConfig(current,root,st,path.join(root,'awsops'));
  const read=validateReadConfig(readPrivateJson(path.join(root,'state/read.json'),
    'NATIVE_READ_CONFIG_UNAVAILABLE',8192,st.uid));
  const bindingPath=path.join(root,'state/binding.private.json');
  const binding=readPrivateJson(bindingPath,'NATIVE_TARGET_BINDING_MISMATCH',4096,st.uid);
  if (!binding || typeof binding!=='object' || Array.isArray(binding) ||
      Object.keys(binding).sort().join(',')!=='account_id,bucket' ||
      binding.account_id!==read.source_account_id ||
      !/^awsops-dev-issue90-s3-canary-[a-z0-9]{12}$/.test(binding.bucket))
    fail('NATIVE_TARGET_BINDING_MISMATCH');
  if (privateDigest(bindingPath,st.uid,st.gid)!==expectedBindingSha256 ||
      privateDigest(current.database,st.uid,st.gid)!==expectedDatabaseSha256)
    fail('CONFIG_RESUME_BASELINE_DRIFT');
  const firstBackup=path.join(root,'state',NATIVE_SOURCE_BACKUP);
  const {data:firstOriginal}=readPrivateBackup(firstBackup,st.uid,st.gid);
  let derived;
  try {
    derived=Buffer.from(JSON.stringify(normalizeNativeConfig(JSON.parse(firstOriginal.toString('utf8')),
      root,D090_SOURCE_REVISION,st,path.join(root,'awsops')),null,2)+'\n');
  } catch { fail('CONFIG_RESUME_PRIOR_BACKUP_DRIFT'); }
  if (!derived.equals(currentBytes)) fail('CONFIG_RESUME_PRIOR_BACKUP_DRIFT');
  for (const filePath of [path.join(root,'state',CONFIG_RESUME_NATIVE_BACKUP),
    path.join(root,'state',CONFIG_RESUME_NATIVE_JOURNAL),path.join(root,CONFIG_RESUME_YAML_BACKUP)]) {
    try { fs.lstatSync(filePath); fail('CONFIG_RESUME_RECONCILE_REQUIRED'); }
    catch (error) { if (error?.message==='CONFIG_RESUME_RECONCILE_REQUIRED') throw error;
      if (error.code!=='ENOENT') fail('CONFIG_RESUME_RECONCILE_REQUIRED'); }
  }
  const yamlPath=path.join(root,'app/librechat.yaml');
  privatePath(yamlPath);
  const yaml=require(path.join(root,'app/node_modules/js-yaml'));
  const raw=fs.readFileSync(yamlPath),projection=projectFixtureShape(raw,yaml);
  if (!['EMPTY_UNCONFIGURED','KNOWN_LEGACY_FIXTURE','KNOWN_CURRENT_FIXTURE'].includes(projection.custom.state) ||
      !['ABSENT','EMPTY','KNOWN_LEGACY','KNOWN_CURRENT'].includes(projection.allowed_addresses.state))
    fail('CONFIG_RESUME_FIXTURE_DRIFT');
  transform(raw,yaml,root,root);
  return {state:'PREWRITE_COMPATIBLE',native:'D090_PINNED',binding:'BASELINE_MATCH',database:'BASELINE_MATCH',
    fixture:projection.custom.state};
}
function writePrivateExclusive(file, data, uid, gid) {
  const fd=fs.openSync(file,'wx',0o600);
  try {
    fs.fchownSync(fd,uid,gid); fs.fchmodSync(fd,0o600); fs.writeFileSync(fd,data); fs.fsyncSync(fd);
  } finally { fs.closeSync(fd); }
  const dir=fs.openSync(path.dirname(file),fs.constants.O_RDONLY);
  try { fs.fsyncSync(dir); } finally { fs.closeSync(dir); }
  const {data:readback,sha256}=readPrivateBackup(file,uid,gid);
  if (!readback.equals(data) || sha256 !== crypto.createHash('sha256').update(data).digest('hex'))
    fail('CONFIG_RESUME_BACKUP_DRIFT');
}
function resumeNativeSourcePin(root, expectedTargetRevision, expectedBindingSha256, expectedDatabaseSha256, yamlSnapshot) {
  if (!path.isAbsolute(root) || fs.realpathSync(root) !== root) fail('ISOLATED_ROOT_REQUIRED');
  if (typeof expectedTargetRevision!=='string' || !/^[a-f0-9]{40}$/.test(expectedTargetRevision))
    fail('CONFIG_RESUME_SOURCE_PIN_MISMATCH');
  for (const digest of [expectedBindingSha256,expectedDatabaseSha256])
    if (typeof digest !== 'string' || !/^[a-f0-9]{64}$/.test(digest)) fail('CONFIG_RESUME_BASELINE_INVALID');
  const marker=path.join(root,'awsops/SOURCE_REVISION');
  const markerStat=fs.lstatSync(marker);
  if (!markerStat.isFile() || markerStat.isSymbolicLink() || (markerStat.mode & 0o777) !== 0o644)
    fail('CONFIG_RESUME_SOURCE_MARKER_UNSAFE');
  const revision=fs.readFileSync(marker,'ascii').trim();
  if (!/^[a-f0-9]{40}$/.test(revision) || revision===D090_SOURCE_REVISION || revision!==expectedTargetRevision)
    fail('CONFIG_RESUME_SOURCE_PIN_MISMATCH');
  const {file,st}=nativeTarget(root);
  const currentBytes=readNativeBytes(file), current=JSON.parse(currentBytes.toString('utf8'));
  if (keysetCode(current,CURRENT_NATIVE_KEYS)!=='EXACT' ||
      ![D090_SOURCE_REVISION,revision].includes(current.source_revision))
    fail('CONFIG_RESUME_NATIVE_PRESTATE_DRIFT');
  validateNativeConfig(current,root,st);
  const read=validateReadConfig(readPrivateJson(path.join(root,'state/read.json'),'NATIVE_READ_CONFIG_UNAVAILABLE',8192,st.uid));
  const bindingPath=path.join(root,'state/binding.private.json');
  const binding=readPrivateJson(bindingPath,'NATIVE_TARGET_BINDING_MISMATCH',4096,st.uid);
  if (!binding || typeof binding!=='object' || Array.isArray(binding) ||
      Object.keys(binding).sort().join(',')!=='account_id,bucket' ||
      binding.account_id!==read.source_account_id ||
      !/^awsops-dev-issue90-s3-canary-[a-z0-9]{12}$/.test(binding.bucket))
    fail('NATIVE_TARGET_BINDING_MISMATCH');
  const databasePath=current.database;
  const bindingDigest=privateDigest(bindingPath,st.uid,st.gid);
  const databaseDigest=privateDigest(databasePath,st.uid,st.gid);
  if (bindingDigest!==expectedBindingSha256 || databaseDigest!==expectedDatabaseSha256)
    fail('CONFIG_RESUME_BASELINE_DRIFT');

  // The immutable first migration backup must still explain the exact d090
  // config. The second transaction gets a separate backup and journal.
  const firstBackup=path.join(root,'state',NATIVE_SOURCE_BACKUP);
  const {data:firstOriginal}=readPrivateBackup(firstBackup,st.uid,st.gid);
  let derived;
  try {
    const original=JSON.parse(firstOriginal.toString('utf8'));
    derived=Buffer.from(JSON.stringify(normalizeNativeConfig(original,root,D090_SOURCE_REVISION,st),null,2)+'\n');
  } catch { fail('CONFIG_RESUME_PRIOR_BACKUP_DRIFT'); }
  const expectedD090=derived;
  if (current.source_revision===D090_SOURCE_REVISION && !expectedD090.equals(currentBytes))
    fail('CONFIG_RESUME_PRIOR_BACKUP_DRIFT');

  const state=path.join(root,'state');
  const backup=path.join(state,CONFIG_RESUME_NATIVE_BACKUP);
  const journalFile=path.join(state,CONFIG_RESUME_NATIVE_JOURNAL);
  const updated=Buffer.from(JSON.stringify({...current,source_revision:revision},null,2)+'\n');
  if (!yamlSnapshot || !/^[a-f0-9]{64}$/.test(yamlSnapshot.sha256) ||
      !Number.isInteger(yamlSnapshot.uid) || !Number.isInteger(yamlSnapshot.gid) ||
      !Number.isInteger(yamlSnapshot.mode) || yamlSnapshot.mode<0 || yamlSnapshot.mode>0o777)
    fail('CONFIG_RESUME_YAML_SNAPSHOT_INVALID');
  const yamlPath=path.join(root,'app/librechat.yaml'),yamlStat=fs.lstatSync(yamlPath),yamlBytes=fs.readFileSync(yamlPath);
  if (crypto.createHash('sha256').update(yamlBytes).digest('hex')!==yamlSnapshot.sha256 ||
      yamlStat.uid!==yamlSnapshot.uid || yamlStat.gid!==yamlSnapshot.gid ||
      (yamlStat.mode&0o777)!==yamlSnapshot.mode) fail('CONFIG_RESUME_YAML_PRESTATE_DRIFT');
  let backupStat,journalStat;
  try { backupStat=fs.lstatSync(backup); } catch (error) { if (error.code!=='ENOENT') throw error; }
  try { journalStat=fs.lstatSync(journalFile); } catch (error) { if (error.code!=='ENOENT') throw error; }
  if (backupStat || journalStat) {
    if (!backupStat || !journalStat) fail('CONFIG_RESUME_RECONCILE_REQUIRED');
    const {data:saved}=readPrivateBackup(backup,st.uid,st.gid);
    const journal=readPrivateJson(journalFile,'CONFIG_RESUME_JOURNAL_DRIFT',4096,st.uid);
    const savedObject=JSON.parse(saved.toString('utf8'));
    const savedD090=Buffer.from(JSON.stringify({...savedObject,source_revision:D090_SOURCE_REVISION},null,2)+'\n');
    if (!saved.equals(expectedD090) || !saved.equals(savedD090))
      fail('CONFIG_RESUME_BACKUP_DRIFT');
    if (journal.version!==1 || journal.predecessor!==D090_SOURCE_REVISION || journal.target!==revision ||
        journal.binding_sha256!==bindingDigest || journal.database_sha256!==databaseDigest ||
        journal.original_sha256!==crypto.createHash('sha256').update(saved).digest('hex') ||
        journal.native_uid!==st.uid || journal.native_gid!==st.gid ||
        journal.native_mode!==(st.mode&0o777) || journal.yaml_sha256!==yamlSnapshot.sha256 ||
        journal.yaml_uid!==yamlSnapshot.uid || journal.yaml_gid!==yamlSnapshot.gid ||
        journal.yaml_mode!==yamlSnapshot.mode)
      fail('CONFIG_RESUME_JOURNAL_DRIFT');
    if (currentBytes.equals(updated)) return {state:'ALREADY_CURRENT'};
    if (currentBytes.equals(saved)) return {state:'NOT_APPLIED'};
    fail('CONFIG_RESUME_RECONCILE_REQUIRED');
  }
  if (current.source_revision!==D090_SOURCE_REVISION || !expectedD090.equals(currentBytes))
    fail('CONFIG_RESUME_NATIVE_PRESTATE_DRIFT');
  const journal={version:1,predecessor:D090_SOURCE_REVISION,target:revision,
    binding_sha256:bindingDigest,database_sha256:databaseDigest,
    original_sha256:crypto.createHash('sha256').update(currentBytes).digest('hex'),
    native_uid:st.uid,native_gid:st.gid,native_mode:st.mode&0o777,
    yaml_sha256:yamlSnapshot.sha256,yaml_uid:yamlSnapshot.uid,yaml_gid:yamlSnapshot.gid,
    yaml_mode:yamlSnapshot.mode};
  writePrivateExclusive(backup,currentBytes,st.uid,st.gid);
  writePrivateExclusive(journalFile,Buffer.from(JSON.stringify(journal)+'\n'),st.uid,st.gid);
  const {data:saved}=readPrivateBackup(backup,st.uid,st.gid);
  if (!saved.equals(currentBytes) || !nativeSnapshotMatches(file,st,currentBytes) ||
      privateDigest(bindingPath,st.uid,st.gid)!==bindingDigest || privateDigest(databasePath,st.uid,st.gid)!==databaseDigest)
    fail('CONFIG_RESUME_BACKUP_DRIFT');
  atomic(file,updated,st,'.awsops-config-resume');
  const afterStat=fs.lstatSync(file), afterBytes=readNativeBytes(file);
  const after=validateNativeConfig(JSON.parse(afterBytes.toString('utf8')),root,st);
  if (!afterBytes.equals(updated) || after.source_revision!==revision || afterStat.uid!==st.uid ||
      afterStat.gid!==st.gid || (afterStat.mode&0o777)!==(st.mode&0o777) ||
      privateDigest(bindingPath,st.uid,st.gid)!==bindingDigest || privateDigest(databasePath,st.uid,st.gid)!==databaseDigest)
    fail('CONFIG_RESUME_READBACK_DRIFT');
  return {state:'UPDATED'};
}
function rollbackNativeSourcePin(root, expectedTargetRevision, expectedBindingSha256, expectedDatabaseSha256) {
  if (!path.isAbsolute(root) || fs.realpathSync(root)!==root) fail('ISOLATED_ROOT_REQUIRED');
  const {file,st}=nativeTarget(root),state=path.join(root,'state');
  const backup=path.join(state,CONFIG_RESUME_NATIVE_BACKUP),journalFile=path.join(state,CONFIG_RESUME_NATIVE_JOURNAL);
  const {data:saved}=readPrivateBackup(backup,st.uid,st.gid);
  const journal=readPrivateJson(journalFile,'CONFIG_RESUME_JOURNAL_DRIFT',4096,st.uid);
  const marker=fs.readFileSync(path.join(root,'awsops/SOURCE_REVISION'),'ascii').trim();
  if (journal.version!==1 || journal.predecessor!==D090_SOURCE_REVISION ||
      journal.target!==marker || marker!==expectedTargetRevision ||
      journal.binding_sha256!==expectedBindingSha256 || journal.database_sha256!==expectedDatabaseSha256 ||
      journal.original_sha256!==crypto.createHash('sha256').update(saved).digest('hex') ||
      journal.native_uid!==st.uid || journal.native_gid!==st.gid ||
      journal.native_mode!==(st.mode&0o777))
    fail('CONFIG_RESUME_JOURNAL_DRIFT');
  const original=JSON.parse(saved.toString('utf8'));
  const currentBytes=readNativeBytes(file);
  if (currentBytes.equals(saved)) return {state:'ALREADY_ROLLED_BACK'};
  const expected=Buffer.from(JSON.stringify({...original,source_revision:marker},null,2)+'\n');
  if (!currentBytes.equals(expected)) fail('CONFIG_RESUME_ROLLBACK_DRIFT');
  const bindingPath=path.join(state,'binding.private.json');
  if (privateDigest(bindingPath,st.uid,st.gid)!==expectedBindingSha256 ||
      privateDigest(original.database,st.uid,st.gid)!==expectedDatabaseSha256)
    fail('CONFIG_RESUME_BASELINE_DRIFT');
  validateNativeConfig(original,root,st);
  atomic(file,saved,st,'.awsops-config-resume-rollback');
  if (!readNativeBytes(file).equals(saved)) fail('CONFIG_RESUME_ROLLBACK_DRIFT');
  return {state:'ROLLED_BACK'};
}
function ownObject(value, name) {
  if (value == null) return {};
  if (typeof value !== 'object' || Array.isArray(value)) fail('CONFIG_' + name + '_UNSAFE');
  return value;
}
function desiredMcp(root) {
  return {type:'stdio', command:'/usr/bin/node',
    args:[path.join(root,'awsops/integration/canary/mcp_guard.cjs')],
    timeout:15000, initTimeout:10000, chatMenu:false, serverInstructions:true};
}
function atomic(file, data, priorStat, suffix) {
  const temp = file + suffix;
  const fd = fs.openSync(temp,'wx',priorStat.mode & 0o777);
  try {
    fs.fchownSync(fd,priorStat.uid,priorStat.gid);
    fs.fchmodSync(fd,priorStat.mode & 0o777);
    fs.writeFileSync(fd,data);
    fs.fsyncSync(fd);
  } catch (error) {
    fs.closeSync(fd);
    try { fs.unlinkSync(temp); } catch {}
    throw error;
  }
  fs.closeSync(fd);
  fs.renameSync(temp,file);
  const dir = fs.openSync(path.dirname(file),fs.constants.O_RDONLY);
  try { fs.fsyncSync(dir); } finally { fs.closeSync(dir); }
}
function transform(raw, yaml, appRoot, sourceRoot) {
  const config = yaml.load(raw.toString('utf8')) || {};
  ownObject(config.endpoints, 'ENDPOINTS'); ownObject(config.mcpServers, 'MCP');
  config.endpoints ??= {}; config.mcpServers ??= {};
  const fixture = {name:FIXTURE_ENDPOINT,apiKey:'fixture-only',baseURL:FIXTURE_URL,
    models:{default:[FIXTURE_MODEL],fetch:false},titleConvo:false};
  const previousFixture = {...fixture,baseURL:'http://localhost:4312/v1'};
  const custom = config.endpoints.custom ?? [];
  if (!Array.isArray(custom) || (custom.length !== 0 &&
      !isDeepStrictEqual(custom,[fixture]) && !isDeepStrictEqual(custom,[previousFixture])))
    fail('FIXTURE_ENDPOINT_DRIFT');
  config.endpoints.custom = [fixture];
  const addresses = config.endpoints.allowedAddresses ?? [];
  if (!isDeepStrictEqual(addresses,[]) && !isDeepStrictEqual(addresses,['localhost:4312']) &&
      !isDeepStrictEqual(addresses,['127.0.0.1:4312'])) fail('FIXTURE_ADDRESS_DRIFT');
  config.endpoints.allowedAddresses = ['127.0.0.1:4312'];
  const mcp = desiredMcp(appRoot);
  const existing = config.mcpServers.awsops;
  const legacyMcp = {...mcp, args:[mcp.args[0],appRoot]};
  if (existing && !isDeepStrictEqual(existing,mcp) && !isDeepStrictEqual(existing,legacyMcp))
    fail('MCP_AWSOPS_DRIFT');
  config.mcpServers.awsops = mcp;

  const agents = ownObject(config.endpoints.agents, 'AGENTS');
  config.endpoints.agents = agents;
  const approval = ownObject(agents.toolApproval, 'TOOL_APPROVAL');
  agents.toolApproval = approval;
  if (approval.enabled === false || (approval.mode && approval.mode !== 'default')) fail('APPROVAL_MODE_DRIFT');
  approval.enabled = true; approval.mode = 'default';
  for (const field of ['allow','ask','deny']) {
    const value = approval[field] ?? [];
    if (!Array.isArray(value) || value.some(x => typeof x !== 'string')) fail('APPROVAL_LIST_DRIFT');
    if (field !== 'ask' && value.includes(TOOL)) fail('CANARY_APPROVAL_POLICY_DRIFT');
    approval[field] = field === 'ask' ? [...new Set([...value, TOOL])].sort() : value;
  }
  const hookPath = path.join(sourceRoot,'app/api/server/controllers/agents/awsops-pause-gate.cjs');
  const matcher = '^' + TOOL + '$';
  const hooks = approval.hooks ?? [];
  if (!Array.isArray(hooks)) fail('APPROVAL_HOOKS_DRIFT');
  const exact = hooks.filter(h => h?.matcher === matcher);
  if (exact.length > 1 || (exact.length === 1 && exact[0].module !== hookPath)) fail('APPROVAL_HOOK_DRIFT');
  if (!exact.length) hooks.push({matcher, module:hookPath});
  const legacyMatcher = '^decide_s3_ssl_reject_only_mcp_awsops$';
  for (const hook of hooks.filter(h => h?.matcher === legacyMatcher)) {
    if (hook.module !== hookPath && !(typeof hook.module === 'string' &&
        hook.module.endsWith('/integration/canary/approval_hook.cjs'))) fail('LEGACY_APPROVAL_HOOK_DRIFT');
    hook.module = hookPath;
  }
  approval.hooks = hooks;
  const rendered = yaml.dump(config, {lineWidth:-1, noRefs:true});
  if (!isDeepStrictEqual(yaml.load(rendered), config)) fail('CONFIG_ROUNDTRIP_FAILED');
  return Buffer.from(rendered);
}
function configureWithBackup(appRoot, sourceRoot, backupName) {
  if (!path.isAbsolute(appRoot) || fs.realpathSync(appRoot) !== appRoot ||
      !path.isAbsolute(sourceRoot) || fs.realpathSync(sourceRoot) !== sourceRoot) fail('ISOLATED_ROOT_REQUIRED');
  const file = path.join(appRoot,'app/librechat.yaml');
  const st = privatePath(file);
  const backup = path.join(appRoot,backupName);
  const yaml = require(path.join(appRoot,'app/node_modules/js-yaml'));
  let backupStat;
  try { backupStat = fs.lstatSync(backup); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (backupStat) {
    const {data:original} = readPrivateBackup(backup,st.uid,st.gid);
    const expected = transform(original,yaml,appRoot,sourceRoot);
    if (!fs.readFileSync(file).equals(expected)) fail('CONFIG_BACKUP_DRIFT');
    atomic(file,expected,st,'.awsops-staged');
    return {state:'CONFIGURED', tool:TOOL, backup:backupName};
  } else {
    const original = fs.readFileSync(file);
    const updated = transform(original,yaml,appRoot,sourceRoot);
    const fd = fs.openSync(backup,'wx',0o600);
    try {
      fs.fchownSync(fd,st.uid,st.gid);
      fs.fchmodSync(fd,0o600);
      fs.writeFileSync(fd,original);
      fs.fsyncSync(fd);
    } finally { fs.closeSync(fd); }
    const backupDirectory = fs.openSync(path.dirname(backup),fs.constants.O_RDONLY);
    try { fs.fsyncSync(backupDirectory); } finally { fs.closeSync(backupDirectory); }
    const {data:verified,sha256} = readPrivateBackup(backup,st.uid,st.gid);
    const expectedHash = crypto.createHash('sha256').update(original).digest('hex');
    if (sha256 !== expectedHash || !verified.equals(original) ||
        !fs.readFileSync(file).equals(original)) fail('CONFIG_BACKUP_DRIFT');
    atomic(file,updated,st,'.awsops-staged');
    return {state:'CONFIGURED', tool:TOOL, backup:backupName};
  }
}
function configure(appRoot, sourceRoot=path.resolve(__dirname,'../..')) {
  return configureWithBackup(appRoot,sourceRoot,BACKUP);
}
function configureResume(appRoot, sourceRoot=path.resolve(__dirname,'../..')) {
  return configureWithBackup(appRoot,sourceRoot,CONFIG_RESUME_YAML_BACKUP);
}
function resumeConfigOnly(root, expectedTargetRevision, expectedBindingSha256, expectedDatabaseSha256) {
  if (!path.isAbsolute(root) || fs.realpathSync(root)!==root) fail('ISOLATED_ROOT_REQUIRED');
  const configFile=path.join(root,'app/librechat.yaml');
  privatePath(configFile);
  const yaml=require(path.join(root,'app/node_modules/js-yaml'));
  const raw=fs.readFileSync(configFile);
  const projection=projectFixtureShape(raw,yaml);
  if (!['EMPTY_UNCONFIGURED','KNOWN_LEGACY_FIXTURE','KNOWN_CURRENT_FIXTURE'].includes(projection.custom.state) ||
      !['ABSENT','EMPTY','KNOWN_LEGACY','KNOWN_CURRENT'].includes(projection.allowed_addresses.state))
    fail('CONFIG_RESUME_FIXTURE_DRIFT');
  // Render and validate every YAML guard before either the native pin or YAML
  // is changed; an unknown or malformed fixture cannot leave a half-update.
  transform(raw,yaml,root,root);
  const configStat=fs.lstatSync(configFile),yamlSnapshot={sha256:crypto.createHash('sha256').update(raw).digest('hex'),
    uid:configStat.uid,gid:configStat.gid,mode:configStat.mode&0o777};
  for (const backupPath of [path.join(root,'state',CONFIG_RESUME_NATIVE_BACKUP),
    path.join(root,'state',CONFIG_RESUME_NATIVE_JOURNAL),path.join(root,CONFIG_RESUME_YAML_BACKUP)]) {
    try { fs.lstatSync(backupPath); fail('CONFIG_RESUME_RECONCILE_REQUIRED'); }
    catch (error) { if (error?.message==='CONFIG_RESUME_RECONCILE_REQUIRED') throw error;
      if (error.code!=='ENOENT') fail('CONFIG_RESUME_RECONCILE_REQUIRED'); }
  }
  const result=resumeNativeSourcePin(root,expectedTargetRevision,expectedBindingSha256,expectedDatabaseSha256,yamlSnapshot);
  if (result.state==='NOT_APPLIED') fail('CONFIG_RESUME_RECONCILE_REQUIRED');
  configureResume(root,root);
  return {state:'RESUMED',native:result.state,fixture:projection.custom.state};
}
function rollbackConfigResume(root, expectedTargetRevision, expectedBindingSha256, expectedDatabaseSha256) {
  if (!path.isAbsolute(root) || fs.realpathSync(root)!==root) fail('ISOLATED_ROOT_REQUIRED');
  const state=path.join(root,'state'),{file:nativeFile,st:nativeStat}=nativeTarget(root);
  const nativeBackup=path.join(state,CONFIG_RESUME_NATIVE_BACKUP);
  const nativeJournal=readPrivateJson(path.join(state,CONFIG_RESUME_NATIVE_JOURNAL),
    'CONFIG_RESUME_JOURNAL_DRIFT',4096,nativeStat.uid);
  const {data:originalNative}=readPrivateBackup(nativeBackup,nativeStat.uid,nativeStat.gid);
  const marker=fs.readFileSync(path.join(root,'awsops/SOURCE_REVISION'),'ascii').trim();
  if (nativeJournal.version!==1 || nativeJournal.target!==marker ||
      nativeJournal.predecessor!==D090_SOURCE_REVISION || nativeJournal.target!==expectedTargetRevision ||
      nativeJournal.binding_sha256!==expectedBindingSha256 ||
      nativeJournal.database_sha256!==expectedDatabaseSha256 ||
      nativeJournal.original_sha256!==crypto.createHash('sha256').update(originalNative).digest('hex') ||
      nativeJournal.native_uid!==nativeStat.uid || nativeJournal.native_gid!==nativeStat.gid ||
      nativeJournal.native_mode!==(nativeStat.mode&0o777)) fail('CONFIG_RESUME_JOURNAL_DRIFT');
  const originalConfig=JSON.parse(originalNative.toString('utf8'));
  const expectedNative=Buffer.from(JSON.stringify({...originalConfig,source_revision:marker},null,2)+'\n');
  const currentNative=readNativeBytes(nativeFile);
  if (!currentNative.equals(originalNative) && !currentNative.equals(expectedNative))
    fail('CONFIG_RESUME_ROLLBACK_DRIFT');
  const bindingPath=path.join(state,'binding.private.json');
  if (privateDigest(bindingPath,nativeStat.uid,nativeStat.gid)!==expectedBindingSha256 ||
      privateDigest(originalConfig.database,nativeStat.uid,nativeStat.gid)!==expectedDatabaseSha256)
    fail('CONFIG_RESUME_BASELINE_DRIFT');
  validateNativeConfig(originalConfig,root,nativeStat);
  const configFile=path.join(root,'app/librechat.yaml'),configStat=fs.lstatSync(configFile);
  if (configStat.uid!==nativeJournal.yaml_uid || configStat.gid!==nativeJournal.yaml_gid ||
      (configStat.mode&0o777)!==nativeJournal.yaml_mode) fail('CONFIG_RESUME_YAML_METADATA_DRIFT');
  const yamlBackup=path.join(root,CONFIG_RESUME_YAML_BACKUP);
  let yamlResult={state:'NO_CHANGE'};
  try {
    fs.lstatSync(yamlBackup);
    const {data:yamlOriginal,sha256}=readPrivateBackup(yamlBackup,nativeJournal.yaml_uid,nativeJournal.yaml_gid);
    if (sha256!==nativeJournal.yaml_sha256) fail('CONFIG_RESUME_YAML_BACKUP_DRIFT');
    const yaml=require(path.join(root,'app/node_modules/js-yaml'));
    const expectedYaml=transform(yamlOriginal,yaml,root,root),currentYaml=fs.readFileSync(configFile);
    if (!currentYaml.equals(yamlOriginal) && !currentYaml.equals(expectedYaml)) fail('CONFIG_RESUME_YAML_DRIFT');
    if (!currentYaml.equals(yamlOriginal)) yamlResult=rollbackWithBackup(root,CONFIG_RESUME_YAML_BACKUP,false);
  } catch (error) {
    if (error.code!=='ENOENT') throw error;
    const currentYaml=fs.readFileSync(configFile);
    if (crypto.createHash('sha256').update(currentYaml).digest('hex')!==nativeJournal.yaml_sha256)
      fail('CONFIG_RESUME_YAML_DRIFT');
  }
  const nativeResult=rollbackNativeSourcePin(root,expectedTargetRevision,expectedBindingSha256,expectedDatabaseSha256);
  return {state:'ROLLED_BACK',yaml:yamlResult.state,native:nativeResult.state};
}
function rollbackWithBackup(appRoot, backupName, removeBackup=true) {
  if (!path.isAbsolute(appRoot) || fs.realpathSync(appRoot) !== appRoot) fail('ISOLATED_ROOT_REQUIRED');
  const file = path.join(appRoot,'app/librechat.yaml');
  const st = privatePath(file);
  const backup = path.join(appRoot,backupName);
  if (!fs.existsSync(backup)) return {state:'NO_CHANGE'};
  const yaml = require(path.join(appRoot,'app/node_modules/js-yaml'));
  const expected = transform(fs.readFileSync(backup),yaml,appRoot,appRoot);
  if (!fs.readFileSync(file).equals(expected)) fail('CONFIG_ROLLBACK_DRIFT');
  atomic(file,fs.readFileSync(backup),st,'.awsops-rollback');
  if (removeBackup) fs.unlinkSync(backup);
  return {state:'ROLLED_BACK'};
}
function rollback(appRoot) { return rollbackWithBackup(appRoot,BACKUP,true); }
function projectConfigShape(appRoot) {
  if (!path.isAbsolute(appRoot) || fs.realpathSync(appRoot) !== appRoot) fail('ISOLATED_ROOT_REQUIRED');
  const file=path.join(appRoot,'app/librechat.yaml');
  privatePath(file);
  const yaml=require(path.join(appRoot,'app/node_modules/js-yaml'));
  return projectFixtureShape(fs.readFileSync(file),yaml);
}
if (require.main === module) {
  try {
  const [action,root,...extra] = process.argv.slice(2);
    const digestAction=['resume-config-only','rollback-config-only'].includes(action);
    const preflightAction=action==='preflight-config-resume';
    if (!['apply','rollback','inspect-native-config','migrate-source-revision','rollback-source-revision',
          'prepare-native-binding','project-config-shape','resume-config-only','rollback-config-only',
          'preflight-config-resume'].includes(action) || !root ||
        (action === 'prepare-native-binding' ? extra.length !== 1 : digestAction ? extra.length !== 3 :
          preflightAction ? extra.length !== 3 : extra.length !== 0)) fail('INVALID_ARGS');
    const result = action === 'apply' ? configure(root,root) : action === 'rollback' ? rollback(root) :
      action === 'inspect-native-config' ? inspectNativeConfig(root) :
      action === 'migrate-source-revision' ? migrateNativeSourceRevision(root) :
      action === 'rollback-source-revision' ? rollbackNativeSourceRevision(root) :
      action === 'project-config-shape' ? projectConfigShape(root) :
      action === 'resume-config-only' ? resumeConfigOnly(root,extra[0],extra[1],extra[2]) :
      action === 'rollback-config-only' ? rollbackConfigResume(root,extra[0],extra[1],extra[2]) :
      action === 'preflight-config-resume' ? preflightConfigResume(root,extra[0],extra[1],extra[2]) :
      prepareNativeCanaryBinding(root,extra[0]);
    process.stdout.write(JSON.stringify(result) + '\n');
  } catch {
    process.stderr.write('ISOLATED_RUNTIME_CONFIG_REFUSED\n');
    process.exitCode = 2;
  }
}
module.exports={configure,rollback,transform,desiredMcp,atomic,readPrivateBackup,migrateNativeSourceRevision,
  inspectNativeConfig,rollbackNativeSourceRevision,validateNativeConfig,validateLegacyNativeConfig,validateReadConfig,
  prepareNativeCanaryBinding,projectFixtureShape,projectConfigShape,resumeNativeSourcePin,rollbackNativeSourcePin,
  preflightConfigResume,resumeConfigOnly,rollbackConfigResume,configureResume,
  CONFIG_RESUME_YAML_BACKUP,CONFIG_RESUME_NATIVE_BACKUP,
  CONFIG_RESUME_NATIVE_JOURNAL,D090_SOURCE_REVISION,LEGACY_NATIVE_GATE_COMMIT,TOOL,FIXTURE_ENDPOINT,
  FIXTURE_MODEL,FIXTURE_URL,BACKUP,NATIVE_SOURCE_BACKUP};
