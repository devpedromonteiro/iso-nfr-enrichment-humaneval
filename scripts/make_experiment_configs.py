#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the 12 experiment configs (4 NFRs x 3 conditions) under configs/.

Why a generator instead of 12 hand-written JSON files: the configs are near-identical and only
differ by (nfr, prompt_format). Hand-editing 12 files is error-prone (mismatched dates, wrong
jsonl paths, typos in slugs). This script is the single source of truth and keeps every config
consistent, so generation and evaluation always agree on filenames.

Conditions (planejamento_final.md §3):
    natural      -> NL-simples  (RobuNFR baseline)
    rich_natural -> NL-rico     (same ISO content in prose)
    structured   -> Estruturado (same content as JSON grounded in ISO/IEC 25010)

Usage:
    python scripts/make_experiment_configs.py                 # default date/model
    python scripts/make_experiment_configs.py --date 2026-06-13 --model gpt-5.4-2026-03-05
"""

from __future__ import annotations

import argparse
import json
import os

NFRS = ["performance", "errorhandle", "codesmell", "readability"]

# prompt_format -> short slug used in filenames so conditions never overwrite each other.
CONDITIONS = {
    "natural": "natural",
    "rich_natural": "rich",
    "structured": "structured",
}

# NFR -> ISO/IEC 25010:2023 characteristic (for the human-readable _readme field).
ISO_CHAR = {
    "performance": "Performance Efficiency",
    "errorhandle": "Reliability",
    "codesmell": "Maintainability (Modularity, Analysability)",
    "readability": "Maintainability (Analysability, Modifiability)",
}


def build_config(nfr: str, prompt_format: str, date: str, model_id: str,
                 model_fn_slug: str, results_dir: str) -> dict:
    """Build one experiment config dict for (nfr, prompt_format)."""
    cond_slug = CONDITIONS[prompt_format]
    file_slug = f"{nfr}-{cond_slug}"
    jsonl_paths = [
        f"../approach/{date}-{model_fn_slug}-t00-GenPrompt-{file_slug}-prompt{i}-Trail0.jsonl"
        for i in range(10)
    ]
    serialization = "json"
    readme = (
        f"{nfr} ({ISO_CHAR[nfr]}) - condition '{prompt_format}'. "
        f"RQ1/HumanEval, generation+evaluation. Run: "
        f"NFRGEN_EXPERIMENT=configs/{file_slug}.json python nfrgen_experiment.py. "
        f"Keep the SAME date across the 3 conditions of an NFR so the paired analysis lines up."
    )
    return {
        "_readme": readme,
        "phases": ["generation", "evaluation"],
        "generation": {
            "enabled": True,
            "benchmark": "humaneval",
            "mode": "rq1",
            "nfr_prompt_set": nfr,
            "prompt_format": prompt_format,
            "serialization": serialization,
            "filename_slug": file_slug,
            "model_filename_slug": model_fn_slug,
            "model": {"id": model_id},
            "date": date,
            "max_prompts": None,
            "use_second_step_enhancement": False,
            "rq2_baseline_jsonl": [],
        },
        "evaluation": {
            "enabled": True,
            "dataset": "humaneval",
            "jsonl_paths": jsonl_paths,
            "report_task": nfr,
            "approach": "direct",
            "model_label": model_id,
            "target_excel": f"{results_dir}/radon-correct-code-analysis-{file_slug}.xlsx",
            "run_rq2_summary_table": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the 12 experiment configs.")
    parser.add_argument("--date", default="2026-06-13", help="collection date (YYYY-MM-DD)")
    parser.add_argument("--model", default="gpt-5.4-2026-03-05", help="model id")
    parser.add_argument("--model-slug", default="gpt-54-2026-03-05", help="model slug for filenames")
    parser.add_argument("--out-dir", default=None, help="output dir (default: <repo>/configs)")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = args.out_dir or os.path.join(repo_root, "configs")
    os.makedirs(out_dir, exist_ok=True)
    results_dir = f"../results/{args.date}-{args.model_slug}-rq1-humaneval-3conditions"

    written = []
    for nfr in NFRS:
        for prompt_format in CONDITIONS:
            cfg = build_config(nfr, prompt_format, args.date, args.model,
                               args.model_slug, results_dir)
            file_slug = cfg["generation"]["filename_slug"]
            path = os.path.join(out_dir, f"{file_slug}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
                f.write("\n")
            written.append(path)

    print(f"[make_experiment_configs] wrote {len(written)} configs to {out_dir}")
    for p in written:
        print(f"  - {os.path.relpath(p, repo_root)}")


if __name__ == "__main__":
    main()
