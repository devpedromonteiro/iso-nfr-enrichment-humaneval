#!/usr/bin/env bash
# W1 model-stability check: re-run NL-simple prompt0 on 30 HumanEval tasks (Performance + Error Handling).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "[w1] Step 1/4: select stratified task_ids (offline)"
python3 scripts/w1_select_task_ids.py

if [[ ! -f conf.json ]]; then
  echo "[w1] ERROR: conf.json not found (OpenAI API key required for generation)."
  echo "[w1] Create conf.json with {\"openai-key\": \"...\"} and re-run this script."
  exit 1
fi

mkdir -p results/w1-stability/2026-06-18

echo "[w1] Step 2/4: generate + evaluate Performance (30 tasks)"
NFRGEN_EXPERIMENT=configs/w1-stability-performance.json python3 nfrgen_experiment.py

echo "[w1] Step 3/4: generate + evaluate Error Handling (30 tasks)"
NFRGEN_EXPERIMENT=configs/w1-stability-errorhandle.json python3 nfrgen_experiment.py

echo "[w1] Step 4/4: compare April/May vs June (paired Wilcoxon)"
python3 scripts/w1_compare_stability.py

echo "[w1] Done. See results/w1-stability/w1_stability_comparison.json and w1.md"
