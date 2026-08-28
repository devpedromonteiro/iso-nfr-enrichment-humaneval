#!/bin/env python3
# -*- coding: utf-8 -*-
"""Paired statistical comparison of the three conditions (planejamento_final.md §7).

This module implements the confirmatory analysis that turns raw per-problem metrics into
defensible claims, mitigating several conclusion-validity threats:

    - 4.3 (unit of analysis) : tests are PAIRED PER PROBLEM (task_id), not per aggregated variation.
    - 4.1 (multiple comparisons) : Holm-Bonferroni correction across the family of tests.
    - 4.4 (effect size) : Cliff's delta reported next to every p-value.
    - N2 (same problem set) : paired vectors are built on the INTERSECTION of task_ids present in
                              both conditions, so metrics compare the same problems.
    - N5 (robustness/STDEV) : stdev_across_variations() exposes the RobuNFR robustness construct.
    - N6 (diversity parity) : prompt_diversity() quantifies how diverse the 10 variations are, so a
                              smaller STDEV cannot be silently attributed to robustness when it is
                              really lower input diversity.

The two pre-registered comparisons (planejamento_final.md §7):
    H1 (content) : NL-simples vs NL-rico
    H2 (form)    : NL-rico   vs Estruturado   <- the central hypothesis

Stats are implemented in pure Python/NumPy (no SciPy dependency). If SciPy is installed it is used
for an exact Wilcoxon p-value; otherwise a normal approximation with tie/zero correction is used.

CLI:
    python stats_compare.py --metric pass --dataset humaneval \
        --nl-simple  <report.json>[,<report.json>...] \
        --nl-rich    <report.json>[,...] \
        --structured <report.json>[,...] \
        --out comparison.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    from density_metrics import density_per_10_loc
except ImportError:
    from evaluation.density_metrics import density_per_10_loc  # type: ignore

# Per-problem density metrics (W2 / RQ2).
DENSITY_METRICS = ("unreadability", "code_smell", "exception")
PAIRED_METRICS = ("pass", "pass_et", "mean_time") + DENSITY_METRICS
_CLIFF_THRESHOLDS = ((0.147, "negligible"), (0.33, "small"), (0.474, "medium"))


# ---------------------------------------------------------------------------
# Effect size
# ---------------------------------------------------------------------------
def cliffs_delta(x: Sequence[float], y: Sequence[float]) -> Tuple[float, str]:
    """Cliff's delta and its magnitude label. delta>0 means x tends to be larger than y."""
    if not x or not y:
        raise ValueError("cliffs_delta needs non-empty samples")
    gt = lt = 0
    for xi in x:
        for yj in y:
            if xi > yj:
                gt += 1
            elif xi < yj:
                lt += 1
    delta = (gt - lt) / (len(x) * len(y))
    mag = "large"
    a = abs(delta)
    for thr, label in _CLIFF_THRESHOLDS:
        if a < thr:
            mag = label
            break
    return delta, mag


# ---------------------------------------------------------------------------
# Wilcoxon signed-rank (paired)
# ---------------------------------------------------------------------------
def _rankdata_average(values: Sequence[float]) -> List[float]:
    """Ranks with average ties (1-based), mirroring scipy.stats.rankdata('average')."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # average of ranks (i+1 .. j+1)
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _wilcoxon_normal_approx(diffs: Sequence[float]) -> Tuple[float, float]:
    """Normal approximation of the Wilcoxon signed-rank test with tie correction.

    Returns (statistic W+, two-sided p-value). Zero differences are dropped (Wilcoxon method).
    """
    nonzero = [d for d in diffs if d != 0]
    n = len(nonzero)
    if n == 0:
        return 0.0, 1.0
    abs_ranks = _rankdata_average([abs(d) for d in nonzero])
    w_plus = sum(r for d, r in zip(nonzero, abs_ranks) if d > 0)
    mean_w = n * (n + 1) / 4.0
    # Tie correction term for the variance.
    from collections import Counter
    tie_term = 0.0
    for count in Counter(abs(d) for d in nonzero).values():
        if count > 1:
            tie_term += count ** 3 - count
    var_w = (n * (n + 1) * (2 * n + 1) - tie_term / 2.0) / 24.0
    if var_w <= 0:
        return w_plus, 1.0
    # Continuity correction.
    z = (w_plus - mean_w)
    z = (z - math.copysign(0.5, z)) / math.sqrt(var_w)
    p = 2.0 * (1.0 - statistics.NormalDist().cdf(abs(z)))
    return w_plus, max(0.0, min(1.0, p))


def wilcoxon_signed_rank(x: Sequence[float], y: Sequence[float]) -> Tuple[float, float]:
    """Paired Wilcoxon signed-rank test. Uses SciPy when available, else a normal approximation.

    Returns (statistic, two-sided p-value).
    """
    if len(x) != len(y):
        raise ValueError("wilcoxon requires paired samples of equal length")
    diffs = [xi - yi for xi, yi in zip(x, y)]
    if all(d == 0 for d in diffs):
        return 0.0, 1.0
    try:
        from scipy.stats import wilcoxon as _scipy_wilcoxon  # type: ignore
        stat, p = _scipy_wilcoxon(x, y)
        return float(stat), float(p)
    except Exception:
        return _wilcoxon_normal_approx(diffs)


# ---------------------------------------------------------------------------
# Multiple-comparison correction
# ---------------------------------------------------------------------------
def holm_correction(pvalues: Sequence[float]) -> List[float]:
    """Holm-Bonferroni step-down adjusted p-values (monotone, capped at 1.0)."""
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * pvalues[idx]
        running_max = max(running_max, val)
        adjusted[idx] = min(1.0, running_max)
    return adjusted


# ---------------------------------------------------------------------------
# Robustness (N5) and diversity (N6)
# ---------------------------------------------------------------------------
def stdev_across_variations(values: Sequence[float]) -> float:
    """Sample STDEV (ddof=1) across the variations of one condition (RobuNFR robustness)."""
    if len(values) < 2:
        return 0.0
    return float(np.std(values, ddof=1))


def _jaccard_distance(a: str, b: str) -> float:
    """1 - Jaccard similarity over whitespace token sets."""
    sa, sb = set(a.split()), set(b.split())
    if not sa and not sb:
        return 0.0
    union = sa | sb
    if not union:
        return 0.0
    return 1.0 - len(sa & sb) / len(union)


def prompt_diversity(prompts: Sequence[str]) -> float:
    """Mean pairwise Jaccard distance among the variations (0 = identical, 1 = disjoint).

    Lets reviewers see that NL and structured conditions have comparable input diversity (N6).
    """
    n = len(prompts)
    if n < 2:
        return 0.0
    total = 0.0
    pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += _jaccard_distance(prompts[i], prompts[j])
            pairs += 1
    return total / pairs if pairs else 0.0


# ---------------------------------------------------------------------------
# Paired comparison on common problem set (N2 + 4.3)
# ---------------------------------------------------------------------------
def paired_vectors(
    a: Dict[str, float], b: Dict[str, float]
) -> Tuple[List[float], List[float], List[str]]:
    """Align two task_id->value maps on their intersection (N2). Returns (xa, xb, task_ids)."""
    common = sorted(set(a) & set(b))
    return [a[t] for t in common], [b[t] for t in common], common


def compare_two(
    a: Dict[str, float], b: Dict[str, float], label: str
) -> Dict[str, object]:
    """Run the paired Wilcoxon + Cliff's delta for one comparison (a vs b) on the common set."""
    xa, xb, common = paired_vectors(a, b)
    stat, p = wilcoxon_signed_rank(xa, xb)
    delta, mag = cliffs_delta(xa, xb)
    return {
        "comparison": label,
        "n_problems": len(common),
        "median_a": statistics.median(xa) if xa else float("nan"),
        "median_b": statistics.median(xb) if xb else float("nan"),
        "wilcoxon_stat": stat,
        "p_value": p,
        "cliffs_delta": delta,
        "effect_magnitude": mag,
    }


def compare_conditions(
    conditions: Dict[str, Dict[str, float]]
) -> List[Dict[str, object]]:
    """Run the two pre-registered comparisons and apply Holm correction across them.

    conditions maps {"nl_simple"|"nl_rich"|"structured" -> {task_id -> metric value}}.
    """
    rows: List[Dict[str, object]] = []
    if "nl_simple" in conditions and "nl_rich" in conditions:
        rows.append(compare_two(conditions["nl_rich"], conditions["nl_simple"],
                                "H1_content: NL-rico vs NL-simples"))
    if "nl_rich" in conditions and "structured" in conditions:
        rows.append(compare_two(conditions["structured"], conditions["nl_rich"],
                                "H2_form: Estruturado vs NL-rico"))
    adjusted = holm_correction([float(r["p_value"]) for r in rows])
    for r, adj in zip(rows, adjusted):
        r["p_value_holm"] = adj
    return rows


# ---------------------------------------------------------------------------
# Loader: per-problem metric vectors from evaluation result JSON files
# ---------------------------------------------------------------------------
def _result_json_for(report_path: str) -> str:
    return report_path


def code_loc(code: str) -> int:
    """Non-empty LOC up to the EvalPlus ``candidate`` sentinel line."""
    count = 0
    for line in (code or "").split("\n"):
        if line.startswith("candidate "):
            break
        if line.strip():
            count += 1
    return count


def exception_count(code: str) -> int:
    """Exception-handling statements per RobuNFR (``exceptions_density_evaluate``)."""
    import re

    raw = code or ""
    result = len(re.findall(r"except.*:", raw))
    result += len(re.findall(r"if.+:\n.+raise", raw))
    return result


def pylint_issue_count(entry: dict, bucket: str) -> int:
    """Number of Pylint messages in a checker bucket for one problem."""
    pylint = entry.get("pylint") or {}
    issues = pylint.get(bucket) or []
    return len(issues)


def load_problem_metric(result_json_path: str, metric: str, dataset: str = "humaneval") -> Dict[str, float]:
    """Extract a {task_id -> value} map from one evaluation result JSON.

    metric:
        "pass"           -> 1.0 if the (rerun) result is OK else 0.0 (functional correctness)
        "pass_et"        -> same on the extended tests
        "mean_time"      -> per-problem execution time (seconds)
        "unreadability"  -> Pylint Convention issues per 10 LOC
        "code_smell"     -> Pylint Refactor issues per 10 LOC
        "exception"      -> exception-handling statements per 10 LOC
    Averaging these maps across problems reproduces the aggregate metrics; here we keep them
    per-problem so the comparison can be PAIRED (N2 / 4.3).
    """
    with open(result_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: Dict[str, float] = {}
    for task_id, entry in data.items():
        if metric == "pass":
            res = entry.get(f"{dataset}_result", "")
            out[task_id] = 1.0 if "OK" in res else 0.0
        elif metric == "pass_et":
            res = entry.get(f"{dataset}_et_result", "")
            out[task_id] = 1.0 if "OK" in res else 0.0
        elif metric == "mean_time":
            if "mean_time" in entry:
                out[task_id] = float(entry["mean_time"])
        elif metric in DENSITY_METRICS:
            loc = code_loc(entry.get("code", ""))
            if metric == "unreadability":
                count = pylint_issue_count(entry, "Convention")
            elif metric == "code_smell":
                count = pylint_issue_count(entry, "Refactor")
            else:
                count = exception_count(entry.get("code", ""))
            out[task_id] = density_per_10_loc(float(count), float(loc) if loc else None)
        else:
            raise ValueError(f"Unknown metric {metric!r}")
    return out


def load_condition(result_json_paths: Sequence[str], metric: str, dataset: str = "humaneval") -> Dict[str, float]:
    """Average a per-problem metric across the variation files of one condition (task_id -> mean)."""
    acc: Dict[str, List[float]] = {}
    for path in result_json_paths:
        for task_id, value in load_problem_metric(path, metric, dataset).items():
            acc.setdefault(task_id, []).append(value)
    return {task_id: statistics.mean(values) for task_id, values in acc.items() if values}


def _split_paths(arg: Optional[str]) -> List[str]:
    if not arg:
        return []
    return [p.strip() for p in arg.split(",") if p.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired comparison of NL-simples / NL-rico / Estruturado.")
    parser.add_argument("--metric", default="pass", choices=list(PAIRED_METRICS))
    parser.add_argument("--dataset", default="humaneval")
    parser.add_argument("--nl-simple", default="", help="comma-separated result JSON paths")
    parser.add_argument("--nl-rich", default="", help="comma-separated result JSON paths")
    parser.add_argument("--structured", default="", help="comma-separated result JSON paths")
    parser.add_argument("--out", default="comparison.csv")
    args = parser.parse_args()

    conditions: Dict[str, Dict[str, float]] = {}
    mapping = {
        "nl_simple": _split_paths(args.nl_simple),
        "nl_rich": _split_paths(args.nl_rich),
        "structured": _split_paths(args.structured),
    }
    for name, paths in mapping.items():
        if paths:
            conditions[name] = load_condition(paths, args.metric, args.dataset)

    rows = compare_conditions(conditions)
    if not rows:
        print("[stats_compare] need at least two conditions to compare.")
        return
    fieldnames = ["comparison", "n_problems", "median_a", "median_b", "wilcoxon_stat",
                  "p_value", "p_value_holm", "cliffs_delta", "effect_magnitude"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
    for r in rows:
        print(f"[{r['comparison']}] n={r['n_problems']} p={r['p_value']:.4g} "
              f"p_holm={r['p_value_holm']:.4g} delta={r['cliffs_delta']:.3f} ({r['effect_magnitude']})")
    print(f"[stats_compare] wrote {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
