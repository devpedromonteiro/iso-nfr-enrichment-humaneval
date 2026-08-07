# ISO-Grounded NFR Code Generation: Replication Package

Replication artifact for **Does ISO-Grounded NFR Specification Improve LLM Code Generation?**
(SBCARS 2026). Compares **NL-simple**, **NL-rich**, and **Structured** (JSON) NFR
specifications on HumanEval / HumanEval-ET with `gpt-5.4-2026-03-05` (temperature 0).

**Authors:** João Pedro Monteiro Pereira, Vinicius Cardoso Garcia, Centro de Informática,
Universidade Federal de Pernambuco (UFPE/CIn), Recife, Brazil.

Built on the [RobuNFR](https://arxiv.org/abs/2503.22851) evaluation pipeline. This package
contains prompts, generated completions, evaluation outputs, analysis scripts, and aggregated
metrics for four NFRs: performance, error handling, code smell, and readability.

## Requirements

- Python **3.9**
- Linux recommended (Ubuntu 22.04+)
- OpenAI API key (for re-generation only; evaluation re-runs use bundled outputs)

```bash
python3.9 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp conf.json.example conf.json   # add your API key locally; never commit conf.json
```

On Ubuntu, install build headers if needed: `sudo apt install python3.9-dev python3.9-venv`

## Quick start

```bash
source .venv/bin/activate

# Preview prompts offline (no API calls)
python scripts/preview_prompts.py --nfr performance --format structured --index 0

# Regenerate the 12 experiment configs (4 NFRs × 3 conditions)
python scripts/make_experiment_configs.py --date 2026-06-13 --model gpt-5.4-2026-03-05

# Run one condition (generation + evaluation)
NFRGEN_EXPERIMENT=configs/performance-structured.json python nfrgen_experiment.py

# Reproduce paper tables and traceability JSON
python scripts/analyze_results.py

# Unit tests
python -m unittest discover -s tests
```

Optional throughput for generation only (does not affect metrics):

```bash
NFRGEN_GEN_THREADS=10 NFRGEN_EXPERIMENT=configs/performance-rich.json python nfrgen_experiment.py
```

## Package layout

| Path | Contents |
|------|----------|
| `configs/` | JSON configs per (NFR, condition); W1/W1B stability configs |
| `approach/` | Generated `.jsonl` completions and per-problem evaluation JSON |
| `results/2026-04-09-.../` | NL-simple baseline (Apr to May 2026) |
| `results/2026-06-13-.../` | Aggregated Excel summaries for interventions |
| `results/w1-stability/` | Snapshot stability checks (pilot n=30; full Performance n=164) |
| `results/results_numbers.json` | Traceability map for reported numbers |
| `results/tables_results.tex` | Regenerated LaTeX tables |
| `scripts/analyze_results.py` | Wilcoxon / Cliff's delta / Holm aggregation |
| `scripts/w1_compare_stability.py` | W1/W1B stability statistics |
| `evaluation/` | Metric computation (Pylint densities, Pass@1, execution time) |
| `nfr_prompts.py` | ISO/IEC 25010-grounded prompt templates |
| `reproducibility.md` | Environment, commands, artifact list |
| `RUNTIME_NOTES.md` | Infrastructure changes that do not alter experimental factors |

## Study conditions

| Condition | Description |
|-----------|-------------|
| **NL-simple** | RobuNFR-style one-line NFR phrase (baseline) |
| **NL-rich** | Same ISO content as structured form, rendered as prose |
| **Structured** | ISO content serialized as JSON (intent, constraints, acceptance criteria) |

NL-simple baseline was collected Apr to May 2026; NL-rich and Structured interventions in June 2026
(same model snapshot, temperature 0). See `results/w1-stability/` for post-hoc stability checks
(pilot subset and August 2026 full-set re-run on Performance).

## Citation

When reusing prompts, metrics, or this package, cite RobuNFR and the SBCARS 2026 paper
(Pereira and Garcia, UFPE/CIn).

## License

Research replication artifact distributed for verification. Code inherits RobuNFR structure.
