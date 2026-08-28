# ISO-Grounded NFR Code Generation: Replication Package

Replication artifact for **Does ISO-Grounded NFR Specification Improve LLM Code Generation?**
(SBCARS 2026). Compares **NL-simple**, **NL-rich**, and **Structured** (JSON) NFR
specifications on HumanEval / HumanEval-ET with `gpt-5.4-2026-03-05` (temperature 0).

**Authors:** João Pedro Monteiro Pereira, Vinicius Cardoso Garcia, Centro de Informática,
Universidade Federal de Pernambuco (UFPE/CIn), Recife, Brazil.

Built on the [RobuNFR](https://arxiv.org/abs/2503.22851) evaluation pipeline. This package
contains prompts, generated completions, evaluation outputs, analysis scripts, and aggregated
metrics for four NFRs: performance, error handling, code smell, and readability.

## Accepted paper

Pereira, J. P. M.; Garcia, V. C. *Does ISO-Grounded NFR Specification Improve LLM Code
Generation? A Comparison of Rich and Structured Interventions against a Natural-Language
Baseline.* SBCARS 2026, CBSoft 2026, São Paulo, Brazil.

- **GitHub release (v1.0.6):** https://github.com/devpedromonteiro/iso-nfr-enrichment-humaneval/releases/tag/v1.0.6
- **Zenodo (v1.0.6):** https://doi.org/10.5281/zenodo.22135439
- **Camera-ready PDF:** [`docs/sbcars2026-camera-ready.pdf`](docs/sbcars2026-camera-ready.pdf) (GitHub repository and replication zip); [`sbcars2026-camera-ready.pdf`](sbcars2026-camera-ready.pdf) (Zenodo record root)
- Event page: https://cbsoft.sbc.org.br/2026/en/sbcars/

## Zenodo download layout (v1.0.6)

Zenodo does not accept folder upload in the web interface. The version DOI provides:

- **Standalone files at the record root** (not inside the zip): `LICENSE`, `README.md` (this
  file), and `sbcars2026-camera-ready.pdf`.
- **Full replication zip:** `iso-nfr-enrichment-humaneval-v1.0.6-flat.zip` (same content as
  this GitHub repository, flat layout; includes `LICENSE`, `README.md`, and
  `docs/sbcars2026-camera-ready.pdf` at the zip root as well).

You may use either the standalone files or the zip alone; content is aligned with release
`v1.0.6`. The GitHub clone contains the complete tree in one step.

## Requirements

- **Python:** 3.9 (tested with 3.9.x in a virtual environment)
- **Operating system:** Linux recommended (Ubuntu 22.04+; observed on Ubuntu 26.04 LTS)
- **Hardware:** sufficient disk space for bundled JSON/JSONL outputs (~2 GB); re-generation
  requires network access to the OpenAI API
- **Software environment:** see pinned dependencies in `requirements.txt` (EvalPlus 0.2.0,
  Pylint 3.2.5, NumPy, Pandas, OpenAI client, etc.)
- **Optional:** OpenAI API key only if re-running LLM generation (`conf.json` from
  `conf.json.example`); bundled evaluation outputs allow analysis without API calls
- **Build tools (Ubuntu):** see system packages below before `pip install`

## Installation

**System packages (Ubuntu/Debian):** install before Python dependencies:

```bash
sudo apt update
sudo apt install -y python3.9 python3.9-dev python3.9-venv python3-pip \
  build-essential libffi-dev graphviz libgraphviz-dev pkg-config wget
```

On Ubuntu 24.04+, Python 3.9 may require the [deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa).
On Ubuntu 26.04, if `pip install -r requirements.txt` fails on `pygraphviz`, run
`bash scripts/install_deps_ubuntu26.sh` first (see comments in `requirements.txt`).

**Python environment:**

```bash
git clone https://github.com/devpedromonteiro/iso-nfr-enrichment-humaneval.git
cd iso-nfr-enrichment-humaneval
git checkout v1.0.6

python3.9 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools wheel
pip install -r requirements.txt
cp conf.json.example conf.json   # only needed for re-generation; never commit conf.json
```

Verify the installation (no API calls):

```bash
source .venv/bin/activate
python -m unittest discover -s tests
```

Expected result: all unit tests pass (e.g., `Ran N tests in ... OK`). You can also smoke-test
the analysis pipeline on bundled data:

```bash
python scripts/analyze_results.py
```

This regenerates `results/tables_results.tex` and `results/results_numbers.json` from the
included evaluation JSONs.

## Quick start

```bash
source .venv/bin/activate

# Preview prompts offline (no API calls)
python scripts/preview_prompts.py --nfr performance --format structured --index 0

# Regenerate the 12 experiment configs (4 NFRs × 3 conditions)
python scripts/make_experiment_configs.py --date 2026-06-13 --model gpt-5.4-2026-03-05

# Run one condition (generation + evaluation; requires API key)
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
| `docs/ZENODO_PUBLISHING.md` | Tagging releases and publishing on Zenodo |
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

Distributed under the **MIT License**; see the `LICENSE` file in the repository root.
Bundled HumanEval data follow EvalPlus/HumanEval terms; generated outputs are provided for
research replication and verification.
