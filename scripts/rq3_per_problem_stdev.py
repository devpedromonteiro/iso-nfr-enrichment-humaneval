#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RQ3 inferential tests: per-problem STDEV across ten prompt variations.

For each HumanEval task, compute the sample STDEV of a metric across the ten
prompt-variation JSONs, then run paired Wilcoxon tests (intervention vs NL-simple)
with Cliff's delta and Holm--Bonferroni within each (NFR, comparison) family.

Lower STDEV is better (RobuNFR robustness). With compare_two(intervention, baseline),
delta < 0 indicates the intervention has lower per-problem variation.
"""

from __future__ import annotations

import glob
import json
import os
import statistics
import sys
from typing import Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.join(ROOT, "evaluation")
APPROACH_DIR = os.path.join(ROOT, "approach")
BASELINE_JSON_DIRS = [
    os.path.join(ROOT, "results", "2026-04-09-gpt-54-2026-03-05-rq1-humaneval"),
    APPROACH_DIR,
]

sys.path.insert(0, EVAL_DIR)
sys.path.insert(0, ROOT)
import stats_compare as sc  # noqa: E402

DATE = "2026-06-13"
MODEL_FN = "gpt-54-2026-03-05"
NFRS = ["performance", "errorhandle", "codesmell", "readability"]
NFR_LABEL = {
    "performance": "Performance",
    "errorhandle": "Error Handling",
    "codesmell": "Code Smell",
    "readability": "Readability",
}
METRICS: List[Tuple[str, str]] = [
    ("pass", "Pass@1 STDEV"),
    ("unreadability", "Unread. STDEV"),
    ("code_smell", "Smell STDEV"),
    ("exception", "Exc. STDEV"),
]
OUT_JSON = os.path.join(ROOT, "results", "rq3_per_problem_stdev.json")


def result_jsons(nfr: str, cond: str) -> List[str]:
    pat = os.path.join(
        APPROACH_DIR,
        f"{DATE}-{MODEL_FN}-t00-GenPrompt-{nfr}-{cond}-prompt*-Trail0-humaneval_evaluate_result.json",
    )
    return sorted(glob.glob(pat), key=lambda p: int(p.split("prompt")[1].split("-")[0]))


def baseline_result_jsons(nfr: str) -> List[str]:
    found: List[str] = []
    for d in BASELINE_JSON_DIRS:
        pat = os.path.join(
            d,
            f"*-{MODEL_FN}-t00-GenPrompt-{nfr}-prompt*-Trail0-humaneval_evaluate_result.json",
        )
        found.extend(glob.glob(pat))
    found = [p for p in found if "-rich-" not in p and "-structured-" not in p]
    return sorted(found, key=lambda p: int(p.split("prompt")[1].split("-")[0]))[:10]


def load_per_problem_stdev(
    json_paths: List[str], metric: str, dataset: str = "humaneval"
) -> Dict[str, float]:
    """Per-task STDEV of metric values across prompt variations."""
    if not json_paths:
        return {}
    per_variation = [sc.load_problem_metric(p, metric, dataset) for p in json_paths]
    common = sorted(set.intersection(*[set(d.keys()) for d in per_variation]))
    out: Dict[str, float] = {}
    for task_id in common:
        vals = [d[task_id] for d in per_variation]
        out[task_id] = sc.stdev_across_variations(vals)
    return out


def mean_stdev(stdev_map: Dict[str, float]) -> float:
    if not stdev_map:
        return float("nan")
    return float(statistics.mean(stdev_map.values()))


def run_comparison(
    intervention: Dict[str, float],
    baseline: Dict[str, float],
    label: str,
) -> Dict[str, object]:
    """Wilcoxon: intervention vs baseline per-problem STDEV (lower intervention is better)."""
    result = sc.compare_two(intervention, baseline, label)
    xa, xb, _ = sc.paired_vectors(intervention, baseline)
    result["mean_stdev_intervention"] = statistics.mean(xa) if xa else float("nan")
    result["mean_stdev_baseline"] = statistics.mean(xb) if xb else float("nan")
    result["pct_reduction"] = (
        (1.0 - result["mean_stdev_intervention"] / result["mean_stdev_baseline"]) * 100.0
        if result["mean_stdev_baseline"] and result["mean_stdev_baseline"] == result["mean_stdev_baseline"]
        else float("nan")
    )
    return result


def main() -> None:
    json_paths: Dict[str, Dict[str, List[str]]] = {}
    for nfr in NFRS:
        json_paths[nfr] = {}
        base = baseline_result_jsons(nfr)
        rich = result_jsons(nfr, "rich")
        struct = result_jsons(nfr, "structured")
        if base:
            json_paths[nfr]["nl_simple"] = base
        if rich:
            json_paths[nfr]["rich"] = rich
        if struct:
            json_paths[nfr]["structured"] = struct

    output: Dict[str, object] = {
        "description": "Per-problem STDEV across 10 prompt variations; paired Wilcoxon vs NL-simple.",
        "metrics": [m for m, _ in METRICS],
        "interpretation": {
            "lower_stdev_better": True,
            "cliffs_delta": "delta<0 favors intervention (lower per-problem STDEV than NL-simple)",
            "holm_family": "per (NFR, comparison label, all metrics in METRICS)",
        },
        "descriptive_mean_stdev": {},
        "inferential": {},
    }

    pairs = [
        ("rich", "nl_simple", "NL-r vs NL-s"),
        ("structured", "nl_simple", "St vs NL-s"),
    ]

    for nfr in NFRS:
        paths = json_paths.get(nfr, {})
        desc_block: Dict[str, object] = {}
        inf_block: Dict[str, object] = {}
        for cond_key, clab in [
            ("nl_simple", "NL-s"),
            ("rich", "NL-r"),
            ("structured", "St"),
        ]:
            if cond_key not in paths:
                continue
            desc_block[clab] = {}
            for mk, _ in METRICS:
                stdev_map = load_per_problem_stdev(paths[cond_key], mk)
                desc_block[clab][mk] = {
                    "mean_per_problem_stdev": mean_stdev(stdev_map),
                    "n_problems": len(stdev_map),
                }
        output["descriptive_mean_stdev"][NFR_LABEL[nfr]] = desc_block

        for cond_a, cond_b, comp_label in pairs:
            if cond_a not in paths or cond_b not in paths:
                continue
            rows: List[Dict[str, object]] = []
            pvals: List[float] = []
            for mk, mlab in METRICS:
                a_map = load_per_problem_stdev(paths[cond_a], mk)
                b_map = load_per_problem_stdev(paths[cond_b], mk)
                if not a_map or not b_map:
                    continue
                r = run_comparison(a_map, b_map, f"{nfr}:{comp_label}:{mk}")
                r["metric"] = mk
                r["metric_label"] = mlab
                rows.append(r)
                pvals.append(float(r["p_value"]))
            holm = sc.holm_correction(pvals)
            for r, ph in zip(rows, holm):
                r["p_holm"] = ph
                r["significant_holm_005"] = ph < 0.05
            inf_block[comp_label] = rows
        output["inferential"][NFR_LABEL[nfr]] = inf_block

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[rq3_per_problem_stdev] wrote {OUT_JSON}")
    for nfr_label, comps in output["inferential"].items():
        for comp_label, rows in comps.items():
            for r in rows:
                sig = "*" if r["significant_holm_005"] else ""
                print(
                    f"  {nfr_label} {comp_label} {r['metric_label']}: "
                    f"mean {r['mean_stdev_intervention']:.4f} vs {r['mean_stdev_baseline']:.4f} "
                    f"p={r['p_value']:.4g} p_holm={r['p_holm']:.4g} "
                    f"delta={r['cliffs_delta']:.3f}{sig}"
                )


if __name__ == "__main__":
    main()
