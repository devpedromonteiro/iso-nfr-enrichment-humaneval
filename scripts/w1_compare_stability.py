#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare April/May vs June NL-simple Pass@1 on the fixed W1 stability subset."""

from __future__ import annotations

import argparse
import glob
import json
import os
import random
import statistics
import sys
from typing import Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.join(ROOT, "evaluation")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if EVAL_DIR not in sys.path:
    sys.path.insert(0, EVAL_DIR)

import stability_subset as ss  # noqa: E402
import stats_compare as sc  # noqa: E402

BASELINES = {
    "performance": os.path.join(
        ROOT,
        "results",
        "2026-04-09-gpt-54-2026-03-05-rq1-humaneval",
        "2026-04-25-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt0-Trail0-humaneval_evaluate_result.json",
    ),
    "errorhandle": os.path.join(
        ROOT,
        "results",
        "2026-04-09-gpt-54-2026-03-05-rq1-humaneval",
        "2026-05-16-gpt-54-2026-03-05-t00-GenPrompt-errorhandle-prompt0-Trail0-humaneval_evaluate_result.json",
    ),
}

JUNE_GLOB = {
    "performance": "*w1*stability*performance*prompt0*humaneval_evaluate_result.json",
    "errorhandle": "*w1-stability-errorhandle*prompt0*humaneval_evaluate_result.json",
}


def find_june_json(june_dir: str, nfr: str) -> str:
    """Locate the June stability evaluation JSON for an NFR."""
    hits = sorted(glob.glob(os.path.join(june_dir, JUNE_GLOB[nfr])))
    if not hits:
        raise FileNotFoundError(
            f"No June evaluation JSON matching {JUNE_GLOB[nfr]!r} under {june_dir}"
        )
    if len(hits) > 1:
        raise RuntimeError(f"Multiple June JSONs for {nfr}: {hits}")
    return hits[0]


def _aggregate_rate(vec: Dict[str, float], task_ids: List[str]) -> float:
    return statistics.mean(vec[t] for t in task_ids)


def _agreement(april: Dict[str, float], june: Dict[str, float], task_ids: List[str]) -> float:
    agree = sum(1 for t in task_ids if april[t] == june[t])
    return agree / len(task_ids)


def _bootstrap_mean_ci(
    diffs: List[float],
    n_resamples: int = 10_000,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """Return mean difference and 95% bootstrap CI (percentile method)."""
    if not diffs:
        return 0.0, 0.0, 0.0
    mean_diff = statistics.mean(diffs)
    rng = random.Random(seed)
    n = len(diffs)
    boots = sorted(
        statistics.mean(diffs[rng.randrange(n)] for _ in range(n))
        for _ in range(n_resamples)
    )
    lo = boots[int(0.025 * n_resamples)]
    hi = boots[int(0.975 * n_resamples) - 1]
    return mean_diff, lo, hi


def compare_nfr(
    nfr: str,
    april_json: str,
    june_json: str,
    task_ids: List[str],
) -> Dict[str, object]:
    """Run paired Wilcoxon on Pass@1 and ET-Pass@1 for one NFR."""
    april_pass = ss.pass_vector_from_result_json(april_json, task_ids)
    june_pass = ss.pass_vector_from_result_json(june_json, task_ids)
    april_et = ss.pass_vector_from_result_json(april_json, task_ids, dataset="humaneval_et")
    june_et = ss.pass_vector_from_result_json(june_json, task_ids, dataset="humaneval_et")

    pass_cmp = sc.compare_two(april_pass, june_pass, f"{nfr}:apr_vs_jun:pass")
    et_cmp = sc.compare_two(april_et, june_et, f"{nfr}:apr_vs_jun:pass_et")

    pass_diffs = [june_pass[t] - april_pass[t] for t in task_ids]
    pass_mean_diff, pass_ci_lo, pass_ci_hi = _bootstrap_mean_ci(pass_diffs)
    tasks_improved = sum(1 for d in pass_diffs if d > 0)
    tasks_worsened = sum(1 for d in pass_diffs if d < 0)

    return {
        "nfr": nfr,
        "baseline_april_json": april_json,
        "baseline_june_json": june_json,
        "n_tasks": len(task_ids),
        "pass_at_1_april_mean": _aggregate_rate(april_pass, task_ids),
        "pass_at_1_june_mean": _aggregate_rate(june_pass, task_ids),
        "pass_at_1_mean_diff_june_minus_april": pass_mean_diff,
        "pass_at_1_bootstrap_ci_95": [pass_ci_lo, pass_ci_hi],
        "pass_at_1_tasks_improved": tasks_improved,
        "pass_at_1_tasks_worsened": tasks_worsened,
        "pass_at_1_agreement": _agreement(april_pass, june_pass, task_ids),
        "pass_at_1_wilcoxon": pass_cmp,
        "et_pass_at_1_april_mean": _aggregate_rate(april_et, task_ids),
        "et_pass_at_1_june_mean": _aggregate_rate(june_et, task_ids),
        "et_pass_at_1_agreement": _agreement(april_et, june_et, task_ids),
        "et_pass_at_1_wilcoxon": et_cmp,
        "stable_pass_at_1": float(pass_cmp["p_value"]) >= 0.05,
        "stable_et_pass_at_1": float(et_cmp["p_value"]) >= 0.05,
        "per_task_pass_at_1": {
            t: {"april": april_pass[t], "june": june_pass[t]} for t in task_ids
        },
    }


def interpret_overall(results: List[Dict[str, object]]) -> str:
    """Human-readable stability verdict (conservative; see paper Section 4.6)."""
    for row in results:
        ci = row.get("pass_at_1_bootstrap_ci_95") or [0.0, 0.0]
        if ci[0] > 0 or (not row["stable_pass_at_1"] and row["pass_at_1_april_mean"] != row["pass_at_1_june_mean"]):
            return "unresolved_drift_suspected"
    if all(r["stable_pass_at_1"] and r["stable_et_pass_at_1"] for r in results):
        return "no_strong_evidence_of_drift"
    return "inconclusive"


def main() -> None:
    parser = argparse.ArgumentParser(description="W1 stability comparison (paired Wilcoxon).")
    parser.add_argument(
        "--task-ids",
        default=os.path.join(ROOT, "results", "w1-stability", "task_ids_30.json"),
    )
    parser.add_argument(
        "--june-dir",
        default=os.path.join(ROOT, "results", "w1-stability", "2026-06-18"),
        help="Directory with June re-run *humaneval_evaluate_result.json files",
    )
    parser.add_argument("--out", default=os.path.join(ROOT, "results", "w1-stability", "w1_stability_comparison.json"))
    parser.add_argument(
        "--nfrs",
        default=None,
        help="Comma-separated NFR keys to compare (default: all configured baselines)",
    )
    args = parser.parse_args()

    task_ids = ss.load_task_ids(args.task_ids)
    nfr_keys = [k.strip() for k in args.nfrs.split(",")] if args.nfrs else list(BASELINES.keys())
    comparisons: List[Dict[str, object]] = []

    for nfr in nfr_keys:
        if nfr not in BASELINES:
            raise ValueError(f"Unknown NFR {nfr!r}; expected one of {list(BASELINES.keys())}")
        april_path = BASELINES[nfr]
        june_path = find_june_json(args.june_dir, nfr)
        comparisons.append(compare_nfr(nfr, april_path, june_path, task_ids))

    payload = {
        "task_ids_file": args.task_ids,
        "task_ids": task_ids,
        "june_dir": args.june_dir,
        "interpretation": interpret_overall(comparisons),
        "comparisons": comparisons,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"[w1] wrote {args.out}")
    print(f"[w1] interpretation: {payload['interpretation']}")
    for row in comparisons:
        p = row["pass_at_1_wilcoxon"]
        print(
            f"  {row['nfr']}: Pass@1 apr={row['pass_at_1_april_mean']:.3f} "
            f"jun={row['pass_at_1_june_mean']:.3f} agreement={row['pass_at_1_agreement']:.3f} "
            f"p={p['p_value']:.4f} delta={p['cliffs_delta']:.3f}"
        )


if __name__ == "__main__":
    main()
