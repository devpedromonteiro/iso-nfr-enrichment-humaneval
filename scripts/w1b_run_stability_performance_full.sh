#!/usr/bin/env bash
# W1 Level B: re-run NL-simple Performance prompt0 on all 164 HumanEval tasks (Aug 2026).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [[ ! -f conf.json ]]; then
  echo "[w1b] ERROR: conf.json not found (OpenAI API key required)."
  exit 1
fi

echo "[w1b] Step 1/3: build task_ids_164.json (offline)"
python3 scripts/w1b_select_all_task_ids.py

mkdir -p results/w1-stability/2026-08-07 run_logs

JSONL="results/w1-stability/2026-08-07/2026-08-07-gpt-54-2026-03-05-t00-GenPrompt-w1b-stability-performance-full-prompt0-Trail0.jsonl"
if [[ -f "$JSONL" ]]; then
  echo "[w1b] Removing stale output in results/w1-stability/2026-08-07/ (rerun)"
  rm -rf results/w1-stability/2026-08-07/*
fi

echo "[w1b] Step 2/3: generate + evaluate Performance (164 tasks, prompt0)"
NFRGEN_EXPERIMENT=configs/w1b-stability-performance-full.json python3 nfrgen_experiment.py

echo "[w1b] Step 3/3: compare April/May vs August (paired Wilcoxon, n=164)"
python3 scripts/w1_compare_stability.py \
  --nfrs performance \
  --task-ids results/w1-stability/task_ids_164.json \
  --june-dir results/w1-stability/2026-08-07 \
  --out results/w1-stability/w1b_stability_performance_164.json

echo "[w1b] Step 4/4: orphan process audit"
python3 scripts/audit_no_orphan_processes.py

echo "[w1b] Done. See results/w1-stability/w1b_stability_performance_164.json"
