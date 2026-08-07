#!/usr/bin/env bash
# Sequential runner for the 3-condition experiment (one condition at a time).
#
# Why sequential: evaluation reports test_time / test_time_ET (mean over 5 reruns),
# so two evaluations must NOT share the CPU. Each condition runs to completion, then
# we kill any stray code-execution subprocesses before starting the next one (the
# user previously hit Python eval subprocesses stuck at 100% CPU).
#
# Usage: scripts/run_conditions.sh config1 [config2 ...]
#   e.g. scripts/run_conditions.sh errorhandle-rich codesmell-rich
#
# Env: NFRGEN_GEN_THREADS controls generation concurrency (default 10).

set -u
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="$ROOT/.venv/bin/python"
export NFRGEN_GEN_THREADS="${NFRGEN_GEN_THREADS:-10}"
LOGDIR="$ROOT/run_logs"
mkdir -p "$LOGDIR"

cleanup_stray_python() {
  # Kill leftover evaluation code-execution subprocesses only (safe, specific patterns).
  pkill -9 -f "test_scripts/test" 2>/dev/null || true
  pkill -9 -f "multiprocessing.resource_tracker" 2>/dev/null || true
  pkill -9 -f "multiprocessing.spawn" 2>/dev/null || true
  sleep 1
}

for cfg in "$@"; do
  ts="$(date +%H:%M:%S)"
  echo "==================================================================="
  echo "[driver] START $cfg at $ts"
  echo "==================================================================="
  NFRGEN_EXPERIMENT="configs/${cfg}.json" "$PY" -u nfrgen_experiment.py \
      > "$LOGDIR/${cfg}.log" 2>&1
  rc=$?
  echo "[driver] DONE $cfg rc=$rc at $(date +%H:%M:%S)"
  cleanup_stray_python
  echo "[driver] cleanup done for $cfg; stray test procs:" \
       "$(pgrep -fc 'test_scripts/test' 2>/dev/null || echo 0)"
done
echo "[driver] ALL DONE at $(date +%H:%M:%S)"
