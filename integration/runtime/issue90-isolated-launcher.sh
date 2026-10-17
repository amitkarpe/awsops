#!/usr/bin/env bash
set -Eeuo pipefail

# Starts only the three Issue90 processes in exact transient systemd units.
# No persistent units, retained services, credential files, or network rules
# are edited. Each unit has a 30-minute hard lifetime and exact cgroup stop.
ROOT=/opt/awsops-native-canary
STATE=$ROOT/state
APP=$ROOT/app
AWSOPS=$ROOT/awsops
DB_UNIT=awsops-issue90-isolated-db.service
MODEL_UNIT=awsops-issue90-isolated-model.service
APP_UNIT=awsops-issue90-isolated-app.service
PID_FILE=$STATE/.issue90-runtime.pids
MAX_RUNTIME=1800

refuse() { printf '%s\n' "ISSUE90_ISOLATED_RUNTIME_REFUSED" >&2; exit 2; }

root_guard() {
  [[ $EUID -eq 0 && -d $ROOT && ! -L $ROOT && $(realpath -e -- "$ROOT") == "$ROOT" ]] || refuse
  [[ $(stat -c '%U:%G:%a' "$ROOT") == 'ssm-user:ssm-user:700' ]] || refuse
  for directory in "$STATE" "$APP" "$AWSOPS"; do
    [[ -d $directory && ! -L $directory && $(stat -c '%U' "$directory") == ssm-user ]] || refuse
  done
  for file in "$ROOT/manifest.json" "$STATE/login.json" "$APP/.env" \
    "$STATE/native.json" "$STATE/read.json"; do
    [[ -f $file && ! -L $file && $(stat -c '%U:%a' "$file") == 'ssm-user:600' ]] || refuse
  done
  [[ -f $AWSOPS/SOURCE_REVISION && ! -L $AWSOPS/SOURCE_REVISION &&
     $(stat -c '%U:%a' "$AWSOPS/SOURCE_REVISION") == 'ssm-user:644' ]] || refuse
  [[ -f $STATE/candidate.json && ! -L $STATE/candidate.json &&
     $(stat -c '%U:%a' "$STATE/candidate.json") == 'ssm-user:600' ]] || refuse
  if ! /usr/bin/node - "$ROOT" <<'NODE'
const fs = require('node:fs');
const path = require('node:path');
const root = process.argv[2];
try {
  const manifest = JSON.parse(fs.readFileSync(path.join(root,'manifest.json')));
  const login = JSON.parse(fs.readFileSync(path.join(root,'state/login.json')));
  const native = JSON.parse(fs.readFileSync(path.join(root,'state/native.json')));
  const read = JSON.parse(fs.readFileSync(path.join(root,'state/read.json')));
  const dotenv = require(path.join(root,'app/node_modules/dotenv'));
  const env = dotenv.parse(fs.readFileSync(path.join(root,'app/.env')));
  const mongo = new URL(env.MONGO_URI);
  const binding = native.application_binding;
  const bindingStat = fs.lstatSync(binding);
  const nativeStat = fs.lstatSync(path.join(root,'state/native.json'));
  const bindingValue = JSON.parse(fs.readFileSync(binding));
  const runtimeConfig = require(path.join(root,'awsops/integration/librechat/runtime_config.cjs'));
  runtimeConfig.validateNativeConfig(native,root,nativeStat);
  if (Object.keys(native).sort().join(',') !== 'agent_id,application_binding,application_database,database,enabled,python,source_revision,source_root,source_version,version' ||
      manifest.purpose !== 'awsops-issue11-isolated-auth-canary' ||
      manifest.model !== 'DETERMINISTIC_FIXTURE' ||
      !login || typeof login.email !== 'string' || !login.email ||
      typeof login.password !== 'string' || !login.password ||
      native.version !== 1 || !native.enabled || typeof native.agent_id !== 'string' || !native.agent_id ||
      native.source_root !== path.join(root,'awsops') ||
      native.application_database !== path.join(root,'state/canary.sqlite') ||
      native.source_revision !== fs.readFileSync(path.join(root,'awsops/SOURCE_REVISION'),'utf8').trim() ||
      !read ||
      !path.isAbsolute(binding) || !binding.startsWith(path.join(root,'state') + path.sep) ||
      fs.realpathSync(binding) !== binding || !bindingStat.isFile() ||
      bindingStat.uid !== nativeStat.uid || (bindingStat.mode & 0o077) !== 0 ||
      Object.keys(bindingValue).sort().join(',') !== 'account_id,bucket' ||
      !/^[0-9]{12}$/.test(bindingValue.account_id) ||
      !/^awsops-dev-issue90-s3-canary-[a-z0-9]{12}$/.test(bindingValue.bucket) ||
      typeof native.source_version !== 'string' || !/^v[0-9]+\.[0-9]+\.[0-9]+-mock$/.test(native.source_version) ||
      mongo.protocol !== 'mongodb:' || mongo.hostname !== '127.0.0.1' || mongo.port !== '27111') process.exit(2);
  const pkg = JSON.parse(fs.readFileSync(path.join(root,'app/package.json')));
  if (pkg.name !== 'LibreChat' || pkg.version !== 'v0.8.8-rc1') process.exit(2);
  const yaml = require(path.join(root,'app/node_modules/js-yaml'));
  const appConfig = yaml.load(fs.readFileSync(path.join(root,'app/librechat.yaml'),'utf8'));
  const fixture = appConfig?.endpoints?.custom;
  const approval = appConfig?.endpoints?.agents?.toolApproval;
  const mcp = appConfig?.mcpServers?.awsops;
  if (!Array.isArray(fixture) || fixture.length !== 1 || fixture[0].name !== 'awsops_canary_fixture' ||
      fixture[0].apiKey !== 'fixture-only' || fixture[0].baseURL !== 'http://127.0.0.1:4312/v1' ||
      JSON.stringify(fixture[0].models) !== JSON.stringify({default:['awsops-canary-fixed'],fetch:false}) ||
      JSON.stringify(appConfig.endpoints.allowedAddresses) !== JSON.stringify(['127.0.0.1:4312']) ||
      !Array.isArray(approval?.ask) || !approval.ask.includes('approve_s3_canary_once_mcp_awsops') ||
      !approval.hooks?.some(h => h.matcher === '^approve_s3_canary_once_mcp_awsops$' &&
        h.module === path.join(root,'app/api/server/controllers/agents/awsops-pause-gate.cjs')) ||
      mcp?.type !== 'stdio' || mcp.command !== '/usr/bin/node' ||
      JSON.stringify(mcp.args) !== JSON.stringify([path.join(root,'awsops/integration/canary/mcp_guard.cjs')])) process.exit(2);
} catch { process.exit(2); }
NODE
  then refuse; fi
  if ! runuser -u ssm-user -- env PYTHONPATH="$AWSOPS/src" /usr/bin/python3 -B - "$STATE/read.json" "$STATE/native.json" <<'PY'
import json,sys
from pathlib import Path
from awsops.aws.s3_ssl import REGION
from awsops.runtime.read_probe import load_config
read_path,native_path=map(Path,sys.argv[1:])
settings,_=load_config(read_path)
native=json.loads(native_path.read_text(encoding='utf-8'))
binding=json.loads(Path(native['application_binding']).read_text(encoding='utf-8'))
if settings['profile'] != 'amit' or settings['region'] != REGION or settings['source_account_id'] != binding['account_id']:
    raise SystemExit(2)
PY
  then refuse; fi
  for db in "$STATE/canary.sqlite"; do
    if [[ -e $db || -L $db ]]; then
      [[ -f $db && ! -L $db && $(stat -c '%U:%a' "$db") == 'ssm-user:600' ]] || refuse
    fi
  done
}
ports_closed() {
  local port listeners=()
  for port in "$@"; do
    mapfile -t listeners < <(ss -Hln "sport = :$port")
    [[ ${#listeners[@]} -eq 0 ]] || return 1
  done
}

unit_state() { systemctl show "$1" --property=LoadState --value 2>/dev/null || true; }
require_absent() { [[ $(unit_state "$1") == not-found ]] || refuse; }
listen_free() {
  /usr/bin/python3 - "$1" <<'PY'
import socket,sys
s=socket.socket()
try:
    s.bind(('127.0.0.1',int(sys.argv[1])))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
}
loopback_listener() {
  local port=$1 listeners=()
  mapfile -t listeners < <(ss -Hln "sport = :$port")
  [[ ${#listeners[@]} -eq 1 ]] || return 1
  # ss local-address is column four. Reject wildcard, IPv6 and extra binds.
  awk -v expected="127.0.0.1:$port" 'NF < 4 || $4 != expected { exit 1 }' <<<"${listeners[0]}"
}
wait_listen() {
  local port=$1 unit=$2 i state
  for ((i=0;i<60;i++)); do
    state=$(systemctl show "$unit" --property=ActiveState --value 2>/dev/null || true)
    [[ $state != failed && $state != deactivating ]] || refuse
    if [[ $state == active ]] && /usr/bin/python3 - "$port" <<'PY'
import socket,sys
s=socket.create_connection(('127.0.0.1',int(sys.argv[1])),timeout=0.5)
s.close()
PY
    then
      loopback_listener "$port" || refuse
      return 0
    fi
    sleep 1
  done
  refuse
}
append_pid_record() {
  local unit=$1 tmp=$PID_FILE.stage.$$
  local record
  record=$(unit_pid_record "$unit") || return 1
  { [[ ! -e $PID_FILE ]] || cat -- "$PID_FILE"; printf '%s\n' "$record"; } >"$tmp"
  chown root:root "$tmp"; chmod 0600 "$tmp"; mv -- "$tmp" "$PID_FILE"
}
STARTED_UNITS=()
unit_pid_record() {
  local unit=$1 pid start cgroup
  pid=$(systemctl show "$unit" --property=MainPID --value)
  [[ $pid =~ ^[1-9][0-9]*$ && -r /proc/$pid/stat ]] || return 1
  start=$(/usr/bin/python3 - "$pid" <<'PY'
import sys
raw=open('/proc/'+sys.argv[1]+'/stat',encoding='ascii').read()
print(raw[raw.rfind(')')+2:].split()[19])
PY
  )
  cgroup=$(systemctl show "$unit" --property=ControlGroup --value)
  [[ $cgroup == "/system.slice/$unit" && $(stat -c '%U' "/proc/$pid") == ssm-user ]] || return 1
  printf '%s|%s|%s|%s\n' "$unit" "$pid" "$start" "$cgroup"
}
start_unit() {
  local unit=$1 user=$2 group=$3 directory=$4 memory=$5
  shift 5
  systemd-run --unit="${unit%.service}" --service-type=exec --uid="$user" --gid="$group" \
    --working-directory="$directory" --property=RuntimeMaxSec="$MAX_RUNTIME" \
    --property=KillMode=control-group --property=TasksMax=128 --property=CPUQuota=70% \
    --property="MemoryMax=$memory" --property=PrivateTmp=yes --property=NoNewPrivileges=yes \
    --property=ProtectSystem=strict --property=ProtectHome=read-only \
    --property="ReadWritePaths=$ROOT" "$@" >/dev/null
  STARTED_UNITS+=("$unit")
  [[ $(systemctl show "$unit" --property=User --value) == ssm-user ]] || refuse
  [[ $(systemctl show "$unit" --property=FragmentPath --value) == "/run/systemd/transient/$unit" ]] || refuse
  local i state
  for ((i=0;i<30;i++)); do
    append_pid_record "$unit" && return 0
    state=$(systemctl show "$unit" --property=ActiveState --value 2>/dev/null || true)
    [[ $state != failed && $state != deactivating ]] || refuse
    sleep 1
  done
  refuse
}
stop_unrecorded_start() {
  local unit=$1 port=$2 pid start cgroup
  [[ $(unit_state "$unit") != not-found ]] || return 2
  [[ $(systemctl show "$unit" --property=FragmentPath --value 2>/dev/null || true) == "/run/systemd/transient/$unit" &&
     $(systemctl show "$unit" --property=User --value 2>/dev/null || true) == ssm-user ]] || return 2
  pid=$(systemctl show "$unit" --property=MainPID --value 2>/dev/null || true)
  if [[ $pid =~ ^[1-9][0-9]*$ && -r /proc/$pid/stat ]]; then
    start=$(/usr/bin/python3 - "$pid" <<'PY'
import sys
raw=open('/proc/'+sys.argv[1]+'/stat',encoding='ascii').read()
print(raw[raw.rfind(')')+2:].split()[19])
PY
    )
    cgroup=$(systemctl show "$unit" --property=ControlGroup --value 2>/dev/null || true)
    [[ $cgroup == "/system.slice/$unit" && $(stat -c '%U' "/proc/$pid") == ssm-user ]] || return 2
  else pid=0; start=''; fi
  systemctl stop "$unit"
  [[ $(unit_state "$unit") == not-found ||
     ( $(systemctl show "$unit" --property=ActiveState --value) == inactive && $(systemctl show "$unit" --property=MainPID --value) == 0 ) ]] || return 2
  if [[ $pid != 0 && -e /proc/$pid/stat ]]; then
    local after
    after=$(/usr/bin/python3 - "$pid" <<'PY'
import sys
raw=open('/proc/'+sys.argv[1]+'/stat',encoding='ascii').read()
print(raw[raw.rfind(')')+2:].split()[19])
PY
    )
    [[ $after != "$start" ]] || return 2
  fi
  ports_closed "$port" || return 2
}
stop_unit() {
  local unit=$1 state fragment user pid record_start record_cgroup now_start='' now_cgroup=''
  state=$(unit_state "$unit")
  [[ -f $PID_FILE && ! -L $PID_FILE && $(stat -c '%U:%G:%a' "$PID_FILE") == 'root:root:600' ]] || return 2
  IFS='|' read -r _ saved_pid record_start record_cgroup < <(awk -F'|' -v u="$unit" '$1==u {print;found=1} END {if(!found)exit 1}' "$PID_FILE") || return 2
  [[ $saved_pid =~ ^[1-9][0-9]*$ && $record_start =~ ^[0-9]+$ && $record_cgroup == "/system.slice/${unit}" ]] || return 2
  if [[ -e /proc/$saved_pid/stat ]]; then
    now_start=$(/usr/bin/python3 - "$saved_pid" <<'PY'
import sys
raw=open('/proc/'+sys.argv[1]+'/stat',encoding='ascii').read()
print(raw[raw.rfind(')')+2:].split()[19])
PY
    )
    now_cgroup=$(systemctl show "$unit" --property=ControlGroup --value 2>/dev/null || true)
    if [[ $now_start == "$record_start" ]]; then
      [[ $now_cgroup == "$record_cgroup" && $(stat -c '%U' "/proc/$saved_pid") == ssm-user ]] || return 2
    fi
  fi
  if [[ $state == not-found ]]; then
    [[ ! -e /proc/$saved_pid/stat || $now_start != "$record_start" ]] || return 2
    return 0
  fi
  fragment=$(systemctl show "$unit" --property=FragmentPath --value 2>/dev/null || true)
  user=$(systemctl show "$unit" --property=User --value 2>/dev/null || true)
  pid=$(systemctl show "$unit" --property=MainPID --value 2>/dev/null || true)
  [[ $fragment == "/run/systemd/transient/$unit" && $user == ssm-user ]] || return 2
  [[ $pid == "$saved_pid" || $pid == 0 ]] || return 2
  systemctl stop "$unit"
  state=$(unit_state "$unit")
  if [[ $state != not-found ]]; then
    [[ $(systemctl show "$unit" --property=ActiveState --value) == inactive &&
       $(systemctl show "$unit" --property=MainPID --value) == 0 ]] || return 2
  fi
  if [[ -e /proc/$saved_pid/stat ]]; then
    now_start=$(/usr/bin/python3 - "$saved_pid" <<'PY'
import sys
raw=open('/proc/'+sys.argv[1]+'/stat',encoding='ascii').read()
print(raw[raw.rfind(')')+2:].split()[19])
PY
    )
    [[ $now_start != "$record_start" ]] || return 2
  fi
}

start_runtime() {
  root_guard
  for unit in "$DB_UNIT" "$MODEL_UNIT" "$APP_UNIT"; do require_absent "$unit"; done
  [[ ! -e $PID_FILE && ! -L $PID_FILE ]] || refuse
  for port in 27111 4312 4311; do listen_free "$port" || refuse; done
  for directory in "$STATE/mongo" "$STATE/logs"; do
    if [[ -e $directory || -L $directory ]]; then
      [[ -d $directory && ! -L $directory && $(stat -c '%U:%G:%a' "$directory") == 'ssm-user:ssm-user:700' ]] || refuse
    else install -d -o ssm-user -g ssm-user -m 0700 "$directory"; fi
  done
  runuser -u ssm-user -- env PYTHONPATH="$AWSOPS/src" /usr/bin/python3 -B - "$STATE/native.json" <<'PY'
import json,sys
from pathlib import Path
from awsops.approval.decisions import DecisionStore
native=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
DecisionStore.validate_existing(Path(native['database']))
PY
  umask 077
  : >"$PID_FILE"
  chown root:root "$PID_FILE"; chmod 0600 "$PID_FILE"
  cleanup_on_error() {
    local rc=$? cleanup_failed=0
    if (( rc != 0 )); then
      local unit port
      for unit in "$APP_UNIT" "$MODEL_UNIT" "$DB_UNIT"; do
        [[ " ${STARTED_UNITS[*]} " == *" $unit "* ]] || continue
        case $unit in "$APP_UNIT") port=4311 ;; "$MODEL_UNIT") port=4312 ;; *) port=27111 ;; esac
        if [[ -f $PID_FILE ]] && awk -F'|' -v u="$unit" '$1==u {found=1} END {exit !found}' "$PID_FILE"; then
          stop_unit "$unit" || cleanup_failed=1
        else stop_unrecorded_start "$unit" "$port" || cleanup_failed=1; fi
      done
      ports_closed 4311 4312 27111 || cleanup_failed=1
      if (( cleanup_failed == 0 )) && [[ -f $PID_FILE ]]; then rm -- "$PID_FILE"; fi
    fi
  }
  trap cleanup_on_error EXIT
  start_unit "$DB_UNIT" ssm-user ssm-user "$AWSOPS" 512M \
    --setenv="HOME=$STATE/home" /usr/bin/mongod --dbpath "$STATE/mongo" --bind_ip 127.0.0.1 \
    --port 27111 --wiredTigerCacheSizeGB 0.25 --logpath "$STATE/logs/mongo.log" \
    --nounixsocket --setParameter diagnosticDataCollectionEnabled=false
  wait_listen 27111 "$DB_UNIT"
  start_unit "$MODEL_UNIT" ssm-user ssm-user "$AWSOPS" 192M \
    --setenv="HOME=$STATE/home" /usr/bin/node "$AWSOPS/integration/canary/fixture_model.cjs" "$ROOT"
  wait_listen 4312 "$MODEL_UNIT"
  start_unit "$APP_UNIT" ssm-user ssm-user "$APP" 768M \
    --setenv="HOME=$STATE/home" --setenv=NODE_ENV=production --setenv=NODE_OPTIONS=--max-old-space-size=512 \
    --setenv=HOST=127.0.0.1 --setenv=PORT=4311 \
    --setenv="AWSOPS_NATIVE_CONFIG=$STATE/native.json" --setenv="AWSOPS_READ_CONFIG=$STATE/read.json" \
    --setenv=DOMAIN_CLIENT=http://127.0.0.1:4311 --setenv=DOMAIN_SERVER=http://127.0.0.1:4311 \
    /usr/bin/node api/server/index.js
  wait_listen 4311 "$APP_UNIT"
  trap - EXIT
  printf '%s\n' 'ISSUE90_ISOLATED_RUNTIME_STARTED; SYNTHETIC_MODEL_STIMULUS_ONLY; HUMAN_REJECT_REQUIRED; STOP_AFTER_REVIEW'
}

stop_runtime() {
  local failed=0 unit
  for unit in "$APP_UNIT" "$MODEL_UNIT" "$DB_UNIT"; do stop_unit "$unit" || failed=1; done
  ports_closed 4311 4312 27111 || failed=1
  (( failed == 0 )) || return 2
  rm -- "$PID_FILE"
  printf '%s\n' 'ISSUE90_ISOLATED_RUNTIME_STOPPED'
}

case "${1:-}" in
  start) (($# == 1)) || refuse; start_runtime ;;
  stop) (($# == 1)) || refuse; [[ $EUID -eq 0 ]] || refuse; stop_runtime ;;
  *) refuse ;;
esac
