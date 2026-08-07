#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aggregate experiment results into paper-ready tables + traceability map.

Primary comparison (RQ1 to RQ3): NL-simple baseline vs each intervention
  (NL-rich, Structured); per-problem paired Wilcoxon + Holm + Cliff's delta.

Secondary comparison (RQ4): NL-rich vs Structured (form), content held constant.

Reads per-prompt aggregate Excel files and per-problem evaluation JSONs.
Outputs results/tables_results.tex and results/results_numbers.json.
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys
from typing import Dict, List, Optional, Tuple

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.join(ROOT, "evaluation")
APPROACH_DIR = os.path.join(ROOT, "approach")
PAPER_DIR = os.path.join(ROOT, "results")
RUN_DIR = os.path.join(ROOT, "results", "2026-06-13-gpt-54-2026-03-05-rq1-humaneval-3conditions")
BASE_DIR = os.path.join(ROOT, "results", "2026-04-08-pylint-radon-meta-results")
BASELINE_JSON_DIRS = [
    os.path.join(ROOT, "results", "2026-04-09-gpt-54-2026-03-05-rq1-humaneval"),
    APPROACH_DIR,
]

sys.path.insert(0, EVAL_DIR)
sys.path.insert(0, ROOT)
import stats_compare as sc  # noqa: E402
import nfr_prompts  # noqa: E402

NFRS = ["performance", "errorhandle", "codesmell", "readability"]
NFR_LABEL = {
    "performance": "Performance",
    "errorhandle": "Error Handling",
    "codesmell": "Code Smell",
    "readability": "Readability",
}
BASE_FILE = {
    "performance": "radon-correct-code-analysis-performance.xlsx",
    "errorhandle": "radon-correct-code-analysis-error-handling.xlsx",
    "codesmell": "radon-correct-code-analysis-codesmell.xlsx",
    "readability": "radon-correct-code-analysis-readability.xlsx",
}
# Function-Only (no-NFR) baseline: bare function stub, no NFR block (W7).
FUNCTION_ONLY_FILE = "radon-correct-code-analysis-baseline-raw.xlsx"
PROMPT_COLS = [f"prompt{i}" for i in range(1, 11)]
DATE = "2026-06-13"
MODEL_FN = "gpt-54-2026-03-05"
METRIC_KEYS = [("pass", "Pass@1"), ("pass_et", "ET-Pass@1"), ("mean_time", "Time")]

DENSITY_METRIC_KEYS = [
    ("unreadability", "Unread."),
    ("code_smell", "Smell"),
    ("exception", "Exc."),
]

SUMMARY_METRICS = [
    ("pass@1", "Pass@1 (\\%)", True),
    ("ET-pass@1", "ET-Pass@1 (\\%)", True),
    ("exception-density", "Exc.\\ density", False),
    ("code-smell-density", "Smell density", False),
    ("unreadability-density", "Unread.\\ density", False),
    ("LOC", "LOC", False),
    ("mean-time", "Time (s)", False),
]


def _metric_row(df: pd.DataFrame, metric: str) -> Optional[pd.Series]:
    sub = df[df["metrics"] == metric]
    if sub.empty:
        return None
    return sub.iloc[0]


def _values(df: pd.DataFrame, metric: str) -> List[float]:
    row = _metric_row(df, metric)
    if row is None:
        return []
    return [float(row[c]) for c in PROMPT_COLS if c in row and pd.notna(row[c])]


def _density_values(df: pd.DataFrame, count_metric: str) -> List[float]:
    counts = _values(df, count_metric)
    locs = _values(df, "LOC")
    return [(c / l) * 10.0 if l else 0.0 for c, l in zip(counts, locs)]


def condition_values(df: pd.DataFrame, metric: str) -> List[float]:
    direct = _values(df, metric)
    if direct:
        return direct
    if metric == "code-smell-density":
        return _density_values(df, "Refactor")
    if metric == "unreadability-density":
        return _density_values(df, "Convention")
    return []


def load_excel(path: str) -> Optional[pd.DataFrame]:
    if not os.path.isfile(path):
        return None
    return pd.read_excel(path)


def result_jsons(nfr: str, cond: str) -> List[str]:
    pat = os.path.join(
        APPROACH_DIR,
        f"{DATE}-{MODEL_FN}-t00-GenPrompt-{nfr}-{cond}-prompt*-Trail0-humaneval_evaluate_result.json",
    )
    return sorted(glob.glob(pat), key=lambda p: int(p.split("prompt")[1].split("-")[0]))


def baseline_result_jsons(nfr: str) -> List[str]:
    """NL-simple (RobuNFR one-line) per-problem JSONs for gpt-5.4-2026-03-05."""
    found: List[str] = []
    for d in BASELINE_JSON_DIRS:
        pat = os.path.join(
            d,
            f"*-{MODEL_FN}-t00-GenPrompt-{nfr}-prompt*-Trail0-humaneval_evaluate_result.json",
        )
        found.extend(glob.glob(pat))
    found = [p for p in found if "-rich-" not in p and "-structured-" not in p]
    return sorted(found, key=lambda p: int(p.split("prompt")[1].split("-")[0]))[:10]


def fmt(x: float, pct: bool = False, nd: int = 3) -> str:
    if x != x:
        return "--"
    if pct:
        return f"{x*100:.1f}"
    return f"{x:.{nd}f}"


_MAG_ABBR = {"negligible": "neg.", "small": "sm.", "large": "lg.", "medium": "med."}


def _mag_abbr(magnitude: str) -> str:
    return _MAG_ABBR.get(magnitude, magnitude)


def _emit_paired_block(
    lines: List[str],
    trace: Dict[str, dict],
    trace_key: str,
    caption: str,
    label: str,
    delta_note: str,
    nfr_paths: Dict[str, Dict[str, List[str]]],
    pairs: List[Tuple[str, str, str]],
    metric_keys: Optional[List[Tuple[str, str]]] = None,
) -> None:
    """Generate a paired-comparison LaTeX table.

    pairs: list of (cond_a_key, cond_b_key, row_label) where compare_two(a, b) uses
    delta>0 favoring cond_a.
    """
    keys = metric_keys if metric_keys is not None else METRIC_KEYS
    lines.append("\\begin{table*}[t]")
    lines.append(f"  \\caption{{{caption}}}")
    lines.append(f"  \\label{{{label}}}")
    lines.append("  \\footnotesize")
    lines.append("  \\setlength{\\tabcolsep}{3.5pt}")
    lines.append("  \\begin{tabular}{@{}lllrrrr@{}}")
    lines.append("    \\toprule")
    lines.append(
        "    NFR & Comp. & Metric & $n$ & $p$ & $p_{\\mathrm{Holm}}$ & $\\delta$ \\\\"
    )
    lines.append("    \\midrule")
    for nfr in NFRS:
        paths = nfr_paths.get(nfr, {})
        first_nfr = True
        for cond_a, cond_b, comp_label in pairs:
            if cond_a not in paths or cond_b not in paths:
                continue
            rows = []
            pvals = []
            for mk, mlab in keys:
                a_map = sc.load_condition(paths[cond_a], mk)
                b_map = sc.load_condition(paths[cond_b], mk)
                if not a_map or not b_map:
                    rows.append(None)
                    pvals.append(1.0)
                    continue
                r = sc.compare_two(a_map, b_map, f"{nfr}:{comp_label}:{mk}")
                rows.append((mk, mlab, r))
                pvals.append(float(r["p_value"]))
            holm = sc.holm_correction(pvals)
            first_comp = True
            for (mk, mlab, r), ph in zip(
                [x for x in rows if x is not None], holm
            ):
                if r is None:
                    continue
                nfr_cell = NFR_LABEL[nfr] if first_nfr else ""
                comp_cell = comp_label if first_comp else ""
                lines.append(
                    f"    {nfr_cell} & {comp_cell} & {mlab} & {r['n_problems']} & "
                    f"{fmt(float(r['p_value']), nd=3)} & {fmt(ph, nd=3)} & "
                    f"{fmt(float(r['cliffs_delta']), nd=3)} ({_mag_abbr(r['effect_magnitude'])}) \\\\"
                )
                trace[trace_key].setdefault(nfr, {}).setdefault(comp_label, {})[mk] = {
                    "n": r["n_problems"],
                    "median_a": r["median_a"],
                    "median_b": r["median_b"],
                    "p_value": r["p_value"],
                    "p_holm": ph,
                    "cliffs_delta": r["cliffs_delta"],
                    "magnitude": r["effect_magnitude"],
                    "cond_a": cond_a,
                    "cond_b": cond_b,
                }
                first_nfr = False
                first_comp = False
            lines.append("    \\midrule")
    if lines[-1].strip() == "\\midrule":
        lines[-1] = "    \\bottomrule"
    lines.append("  \\end{tabular}")
    lines.append(f"  \\\\{{\\scriptsize {delta_note}}}")
    lines.append("\\end{table*}")
    lines.append("")


def main() -> None:
    trace: Dict[str, dict] = {
        "summary": {},
        "paired_vs_baseline": {},
        "paired_density_baseline": {},
        "paired_form": {},
        "robustness": {},
        "diversity": {},
        "sources": {
            "baseline_json_dirs": BASELINE_JSON_DIRS,
            "baseline_excel_dir": BASE_DIR,
            "intervention_run_dir": RUN_DIR,
        },
    }
    dfs: Dict[str, Dict[str, pd.DataFrame]] = {}
    json_paths: Dict[str, Dict[str, List[str]]] = {}

    for nfr in NFRS:
        dfs[nfr] = {}
        json_paths[nfr] = {}
        rich = load_excel(os.path.join(RUN_DIR, f"radon-correct-code-analysis-{nfr}-rich.xlsx"))
        struct = load_excel(os.path.join(RUN_DIR, f"radon-correct-code-analysis-{nfr}-structured.xlsx"))
        base = load_excel(os.path.join(BASE_DIR, BASE_FILE[nfr]))
        if rich is not None:
            dfs[nfr]["rich"] = rich
        if struct is not None:
            dfs[nfr]["structured"] = struct
        if base is not None:
            dfs[nfr]["nl_simple"] = base
        base_jsons = baseline_result_jsons(nfr)
        rich_jsons = result_jsons(nfr, "rich")
        struct_jsons = result_jsons(nfr, "structured")
        if base_jsons:
            json_paths[nfr]["nl_simple"] = base_jsons
            trace["sources"].setdefault("baseline_jsons", {})[nfr] = base_jsons
        if rich_jsons:
            json_paths[nfr]["rich"] = rich_jsons
        if struct_jsons:
            json_paths[nfr]["structured"] = struct_jsons

    lines: List[str] = []
    lines.append("% Auto-generated by scripts/analyze_results.py -- do not edit by hand.")

    # -------- summary table --------
    lines.append("\\begin{table*}[t]")
    lines.append("  \\caption{Mean over ten prompt variations per (NFR, condition) on HumanEval. "
                 "Densities are issues per ten LOC. The Function-Only (no-NFR) row is an NFR-independent "
                 "context baseline (bare stub, no quality clause). NL-s=NL-simple baseline, NL-r=NL-rich, St=Structured. "
                 "Source: aggregate Excel files (see \\texttt{results\\_numbers.json}).}")
    lines.append("  \\label{tab:summary}")
    lines.append("  \\small")
    lines.append("  \\begin{tabular}{ll" + "r" * len(SUMMARY_METRICS) + "}")
    lines.append("    \\toprule")
    header = "    NFR & Cond. & " + " & ".join(h for _, h, _ in SUMMARY_METRICS) + " \\\\"
    lines.append(header)
    lines.append("    \\midrule")

    # Function-Only (no-NFR) context row (W7): NFR-independent baseline.
    func_only = load_excel(os.path.join(BASE_DIR, FUNCTION_ONLY_FILE))
    if func_only is not None:
        cells = []
        for m, _, pct in SUMMARY_METRICS:
            vals = condition_values(func_only, m)
            mean = statistics.mean(vals) if vals else float("nan")
            cells.append(fmt(mean, pct=pct, nd=(2 if "density" in m or m == "mean-time" else 1)))
            trace["summary"].setdefault("function_only", {}).setdefault("none", {})[m] = (
                None if mean != mean else mean
            )
        lines.append("    \\multicolumn{2}{l}{Function-Only (no NFR)} & " + " & ".join(cells) + " \\\\")
        lines.append("    \\midrule")

    for nfr in NFRS:
        conds = [("nl_simple", "NL-s"), ("rich", "NL-r"), ("structured", "St")]
        first = True
        for ckey, clab in conds:
            if ckey not in dfs[nfr]:
                continue
            df = dfs[nfr][ckey]
            cells = []
            for m, _, pct in SUMMARY_METRICS:
                vals = condition_values(df, m)
                mean = statistics.mean(vals) if vals else float("nan")
                cells.append(fmt(mean, pct=pct, nd=(2 if "density" in m or m == "mean-time" else 1)))
                trace["summary"].setdefault(nfr, {}).setdefault(ckey, {})[m] = (
                    None if mean != mean else mean
                )
            nfr_cell = NFR_LABEL[nfr] if first else ""
            lines.append(f"    {nfr_cell} & {clab} & " + " & ".join(cells) + " \\\\")
            first = False
        lines.append("    \\midrule")
    lines[-1] = "    \\bottomrule"
    lines.append("  \\end{tabular}")
    lines.append("\\end{table*}")
    lines.append("")

    # -------- PRIMARY: intervention vs baseline --------
    _emit_paired_block(
        lines,
        trace,
        "paired_vs_baseline",
        "Primary paired comparison vs.\\ NL-simple baseline per problem "
        "(Wilcoxon signed-rank, Cliff's $\\delta$, Holm-corrected $p$ within each comparison). "
        "$\\delta>0$ favors the intervention (NL-rich or Structured) over NL-simple.",
        "tab:paired_baseline",
        "$\\delta>0$: intervention better than NL-simple baseline.",
        json_paths,
        [
            ("rich", "nl_simple", "NL-r vs NL-s"),
            ("structured", "nl_simple", "St vs NL-s"),
        ],
    )

    # -------- RQ2: per-problem density vs baseline (W2) --------
    _emit_paired_block(
        lines,
        trace,
        "paired_density_baseline",
        "Paired per-problem comparison of quality densities vs.\\ NL-simple baseline "
        "(Wilcoxon signed-rank, Cliff's $\\delta$, Holm-corrected $p$ within each comparison). "
        "For density metrics, lower is better: $\\delta<0$ favors the intervention.",
        "tab:paired_density",
        "$\\delta<0$: intervention lower density than NL-simple (improvement for smell/unreadability). "
        "For exception density, higher values in the intervention are consistent with the Error Handling "
        "NFR's fault-tolerance intent; see Section~5.2 for interpretation.",
        json_paths,
        [
            ("rich", "nl_simple", "NL-r vs NL-s"),
            ("structured", "nl_simple", "St vs NL-s"),
        ],
        metric_keys=DENSITY_METRIC_KEYS,
    )

    # -------- SECONDARY: form (rich vs structured) --------
    _emit_paired_block(
        lines,
        trace,
        "paired_form",
        "Secondary paired comparison \\emph{Structured vs.\\ NL-rich} (form only; content held constant). "
        "$\\delta>0$ favors Structured.",
        "tab:paired_form",
        "$\\delta>0$: Structured better than NL-rich.",
        json_paths,
        [("structured", "rich", "St vs NL-r")],
    )

    # -------- robustness + diversity (all three conditions) --------
    lines.append("\\begin{table}[t]")
    lines.append("  \\caption{Robustness (STDEV across ten prompt variations; lower = more stable) "
                 "and prompt diversity (mean pairwise Jaccard distance). "
                 "STDEV and Jaccard are reported descriptively; no inferential tests are applied to these metrics.}")
    lines.append("  \\label{tab:robustness}")
    lines.append("  \\small")
    lines.append("  \\begin{tabular}{llrrrrr}")
    lines.append("    \\toprule")
    lines.append("    NFR & Cond. & Pass@1 & Exc. & Smell & Unread. & Div. \\\\")
    lines.append("    \\midrule")
    rob_metrics = ["pass@1", "exception-density", "code-smell-density", "unreadability-density"]
    for nfr in NFRS:
        first = True
        for ckey, clab in [("nl_simple", "NL-s"), ("rich", "NL-r"), ("structured", "St")]:
            if ckey not in dfs[nfr]:
                continue
            df = dfs[nfr][ckey]
            cells = []
            for m in rob_metrics:
                vals = condition_values(df, m)
                sd = sc.stdev_across_variations(vals) if vals else float("nan")
                cells.append(fmt(sd, nd=4 if "pass" in m else 3))
                trace["robustness"].setdefault(nfr, {}).setdefault(ckey, {})[m] = (
                    None if sd != sd else sd
                )
            div = float("nan")
            if ckey == "nl_simple":
                try:
                    prompts = nfr_prompts.get_prompts(nfr, "rq1", "natural", "json")
                    div = sc.prompt_diversity(prompts)
                except Exception:
                    pass
            elif ckey in ("rich", "structured"):
                try:
                    fmt_name = "rich_natural" if ckey == "rich" else "structured"
                    prompts = nfr_prompts.get_prompts(nfr, "rq1", fmt_name, "json")
                    div = sc.prompt_diversity(prompts)
                except Exception:
                    pass
            trace["diversity"].setdefault(nfr, {})[ckey] = None if div != div else div
            nfr_cell = NFR_LABEL[nfr] if first else ""
            lines.append(f"    {nfr_cell} & {clab} & " + " & ".join(cells) + f" & {fmt(div, nd=3)} \\\\")
            first = False
        lines.append("    \\midrule")
    lines[-1] = "    \\bottomrule"
    lines.append("  \\end{tabular}")
    lines.append("\\end{table}")
    lines.append("")

    with open(os.path.join(PAPER_DIR, "tables_results.tex"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(os.path.join(PAPER_DIR, "results_numbers.json"), "w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2, ensure_ascii=False)
    print("[analyze_results] wrote results/tables_results.tex and results/results_numbers.json")
    print(f"[analyze_results] baseline JSONs found: "
          f"{sum(len(json_paths[n].get('nl_simple', [])) for n in NFRS)} files across 4 NFRs")


if __name__ == "__main__":
    main()
