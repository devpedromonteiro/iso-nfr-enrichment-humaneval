#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the fixed 30-problem list for the W1 stability test (offline)."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import stability_subset as ss  # noqa: E402

DEFAULT_BASELINE = os.path.join(
    ROOT,
    "results",
    "2026-04-09-gpt-54-2026-03-05-rq1-humaneval",
    "2026-04-25-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt0-Trail0-humaneval_evaluate_result.json",
)
DEFAULT_OUT = os.path.join(ROOT, "results", "w1-stability", "task_ids_30.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Select stratified HumanEval task_ids for W1.")
    parser.add_argument("--baseline-json", default=DEFAULT_BASELINE)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    task_ids, meta = ss.select_stratified_task_ids(
        args.baseline_json, n_total=args.n, seed=args.seed
    )
    payload = {
        "description": "Fixed HumanEval subset for W1 model-stability check (NL-simple prompt0).",
        "task_ids": task_ids,
        **meta,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"[w1] wrote {len(task_ids)} task_ids -> {args.out}")
    print(f"[w1] pass={meta['n_pass_selected']} fail={meta['n_fail_selected']} seed={args.seed}")


if __name__ == "__main__":
    main()
