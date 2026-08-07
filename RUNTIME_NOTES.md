# Runtime Notes (Infrastructure Only)

These changes affect **execution infrastructure** only. Experimental factors (model, temperature,
prompts, benchmark, metrics) were not altered.

## 1. Generation concurrency (`approach/run_hunmaneval.py`)

- **Issue:** With a single API key, generation was strictly sequential and too slow for the full
  study matrix.
- **Change:** Environment variable `NFRGEN_GEN_THREADS` (default: number of keys). Workers share
  the same queue; generation time is not a reported metric.
- **Default:** Unset variable preserves original single-thread behavior.

## 2. LLM call retries (`approach/run_hunmaneval.py`)

- **Issue:** Transient API errors could drop problems silently under concurrency.
- **Change:** `_get_solution_with_retry()` with exponential backoff (up to 5 attempts). Failed
  problems remain retrievable via `temp_data/` on re-run.

## 3. Orphan evaluation processes (`scripts/run_conditions.sh`)

- **Issue:** Infinite-loop solutions left orphan `test_scripts/test*.py` processes after evaluation.
- **Change:** Sequential condition driver kills known orphan patterns after each condition.
  Sequential execution avoids CPU contention on `mean-time` (five runs per problem).

## 4. Statistical analysis reframe (`scripts/analyze_results.py`)

- **Issue:** Primary comparisons are intervention vs NL-simple baseline, not NL-rich vs Structured.
- **Change:** Paired tests load per-problem vectors from baseline JSONs (`results/2026-04-09-.../`
  and `approach/2026-05-25|27-.../`). Outputs `results/tables_results.tex` and
  `results/results_numbers.json`.

## 4b. W2 per-problem density paired tests (`evaluation/stats_compare.py`, `scripts/analyze_results.py`)

- **Issue:** RQ2 density claims used aggregate Excel means only; no per-problem Wilcoxon (reviewer W2).
- **Change:** `load_problem_metric()` now exports unreadability, code-smell, and exception densities
  per HumanEval task from evaluation JSONs (Pylint Convention/Refactor + exception count / LOC × 10).
  `analyze_results.py` emits Table `tab:paired_density` and `paired_density_baseline` in
  `results/results_numbers.json`.

## 4c. W7 Function-Only summary row (`scripts/analyze_results.py`)

- **Issue:** Summary table lacked an NFR-independent baseline (bare HumanEval stub, no quality clause).
- **Change:** Loads `results/2026-04-08-pylint-radon-meta-results/radon-correct-code-analysis-baseline-raw.xlsx`
  and adds a Function-Only (no NFR) context row to the summary table and `results_numbers.json`.

## 5. W1 snapshot stability (`stability_subset.py`, `scripts/w1_*.py`)

- **Issue:** NL-simple baseline (Apr to May) and interventions (Jun) were separate batches.
- **Change:** Post-hoc re-run of NL-simple prompt0 on 30 stratified tasks; see
  `results/w1-stability/w1_stability_comparison.json`.

## 5b. W1B full-set stability (Performance, n=164) (`scripts/w1b_*.py`)

- **Issue:** The 30-task pilot subset over-sampled failing tasks; reviewers requested a full-set check.
- **Change:** Re-ran NL-simple prompt0 on all 164 HumanEval tasks (August 2026). Outputs under
  `results/w1-stability/2026-08-07/` and summary `w1b_stability_performance_164.json`.
  Statistics via `scripts/w1_compare_stability.py` (paired Wilcoxon + bootstrap CI).

## 6. Evaluation jsonl `prompt` field (`approach/run_hunmaneval.py`)

- **Issue:** Some cached rows lacked `prompt`, causing EvalPlus KeyError during evaluation.
- **Change:** Unknown/missing rows receive `prompt=""` when writing jsonl.
