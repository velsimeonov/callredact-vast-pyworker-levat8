#!/usr/bin/env bash
set -euo pipefail

WORK=/opt/fpbx-stt-pyworker
BOOTLOG=/var/log/fpbx-stt-bootstrap.log

mkdir -p /var/log
touch "$BOOTLOG"

exec >>"$BOOTLOG" 2>&1

echo "=== FreePBX STT bootstrap started $(date -u) ==="

export WORKER_PORT="${WORKER_PORT:-3000}"

echo "WORKER_PORT=$WORKER_PORT"
echo "FPBX_WHISPER_MODEL=${FPBX_WHISPER_MODEL:-small}"
echo "PYWORKER_REPO=${PYWORKER_REPO:-<NOT SET>}"

: "${PYWORKER_REPO:?Set PYWORKER_REPO to the public FPBX STT PyWorker git repository URL}"

if ! command -v git >/dev/null 2>&1; then
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git ca-certificates
fi

rm -rf "$WORK"

echo "Cloning PyWorker repository..."
git clone --depth 1 "$PYWORKER_REPO" "$WORK"

chmod +x "$WORK/start-server.sh"

echo "Starting FreePBX STT PyWorker..."
nohup "$WORK/start-server.sh" >>"$BOOTLOG" 2>&1 </dev/null &

echo "FreePBX STT PyWorker bootstrap launched as PID $!"
