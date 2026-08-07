# Reproducibility

This file documents everything required to reproduce the **intervention vs NL-simple baseline**
experiment: all three conditions (NL-simple, NL-rich, Structured) for four NFRs with
`gpt-5.4-2026-03-05`. NL-simple was collected in Apr--May 2026; NL-rich and Structured in
June 2026 (same model snapshot and pipeline).

**Authors:** João Pedro Monteiro Pereira, Vinicius Cardoso Garcia, UFPE/CIn, Recife, Brazil.

## 1. Hardware and software environment

| Item | Value (observed during execution) |
|------|-----------------------------------|
| OS | Ubuntu 26.04 LTS |
| Python | 3.9.x (virtualenv `.venv`) |
| Key Python deps | `openai`, `evalplus` 0.2.0, `pylint` 3.2.5, `numpy`, `pandas` |

> Note: `radon` is **not** required by the active evaluation path; LOC and densities are
> computed by the project pipeline + Pylint. Execution time is hardware-dependent, so only
> internal deltas (intervention vs baseline, or NL-rich vs Structured in the same environment)
> are compared.

## 2. Model version

- `gpt-5.4-2026-03-05` (OpenAI Chat Completions API), `temperature = 0` (greedy), the only
  decoding configuration used. API key read from `conf.json` (`openai-key`), not stored in
  any artifact. Copy `conf.json.example` to `conf.json` locally.

## 3. Execution date

- Intervention runs: starting **2026-06-14** (UTC-3). Aggregated outputs:
  `results/2026-06-13-gpt-54-2026-03-05-rq1-humaneval-3conditions/`.
- NL-simple baseline: Apr--May 2026 under `results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/`.
- W1B stability re-run: **2026-08-07** under `results/w1-stability/2026-08-07/`.

## 4. Prompts used

- Generated offline (no API) by `nfr_prompts.get_prompts(<nfr>, "rq1", <format>, "json")`:
  - `rich_natural` → NL-rich condition;
  - `structured` → Structured (JSON) condition.
- Both conditions share the same ISO/IEC 25010-grounded source per NFR; only representation
  form differs. Ten prompt variations per condition.
- Inspect prompts: `python scripts/preview_prompts.py --nfr performance --format structured --index 0`.

## 5. Datasets

- HumanEval (164 tasks) and HumanEval-ET (extended tests), loaded via EvalPlus.
- NL-simple baseline: `results/2026-04-08-pylint-radon-meta-results/`,
  `results/2026-04-09-gpt-54-2026-03-05-rq1-humaneval/`, and `approach/2026-05-25|27-.../`.

## 6. Commands executed

```bash
source .venv/bin/activate

python scripts/make_experiment_configs.py --date 2026-06-13 \
    --model gpt-5.4-2026-03-05 --model-slug gpt-54-2026-03-05 \
    --out-dir results/2026-06-13-gpt-54-2026-03-05-rq1-humaneval-3conditions

NFRGEN_GEN_THREADS=10 NFRGEN_EXPERIMENT=configs/performance-rich.json python nfrgen_experiment.py
scripts/run_conditions.sh errorhandle-rich codesmell-rich readability-rich \
    performance-structured errorhandle-structured codesmell-structured readability-structured

python scripts/analyze_results.py
python -m unittest discover -s tests

# W1B full-set stability (optional re-run; bundled outputs included)
NFRGEN_EXPERIMENT=configs/w1b-stability-performance-full.json python nfrgen_experiment.py
python scripts/w1_compare_stability.py --full-set
```

## 7. Generated artifacts

- Per-variation completions: `approach/<date>-<model>-...-<nfr>-<cond>-prompt<i>-Trail0.jsonl`
- Per-problem evaluation: `approach/...-humaneval_evaluate_result.json`
- Per-condition aggregates: `results/2026-06-13-.../radon-correct-code-analysis-*.xlsx`
- Analysis outputs: `results/tables_results.tex`, `results/results_numbers.json`
- W1 stability: `results/w1-stability/w1_stability_comparison.json` (pilot n=30)
- W1B stability: `results/w1-stability/w1b_stability_performance_164.json` (full n=164)

## 8. Path sanitization

- Do not commit `conf.json` (API keys).
- Evaluation JSON tracebacks were scrubbed of absolute local paths via
  `python scripts/sanitize_artifact_paths.py --all-study`.
- Infrastructure-only code changes are documented in `RUNTIME_NOTES.md`.
