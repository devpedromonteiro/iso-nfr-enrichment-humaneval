#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Load nfrgen_experiment.json and run generation and/or evaluation from one place."""

from __future__ import annotations

import datetime
import importlib.util
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import nfr_prompts

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def repo_root() -> str:
    return _REPO_ROOT


def default_config_path() -> str:
    return os.environ.get(
        "NFRGEN_EXPERIMENT",
        os.path.join(_REPO_ROOT, "nfrgen_experiment.json"),
    )


def load_config(explicit_path: Optional[str] = None) -> Tuple[Dict[str, Any], str, str]:
    path = explicit_path or default_config_path()
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Missing experiment config {path!r}. Copy nfrgen_experiment.example.json to nfrgen_experiment.json."
        )
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg, _REPO_ROOT, path


def _today() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


def _resolve_evaluation_paths(paths: List[str], evaluation_dir: str) -> List[str]:
    """Paths in JSON are relative to evaluation/ (same convention as rq1_evaluate.py)."""
    out = []
    for p in paths:
        if os.path.isabs(p):
            out.append(p)
        else:
            out.append(os.path.normpath(os.path.join(evaluation_dir, p)))
    return out


def resolve_prompt_lines(gen: Dict[str, Any]) -> List[str]:
    """Build the list of prompt strings for a generation config.

    Single place that turns (nfr_prompt_set, mode, prompt_format, serialization, max_prompts)
    into the actual prompts. Supports the three paired conditions of the experiment:
    prompt_format in {"natural" (NL-simples), "rich_natural" (NL-rico), "structured" (Estruturado)}.
    Defaults keep full backward compatibility: prompt_format "natural" + serialization "json".
    """
    mode = gen.get("mode", "rq1").lower()
    nfr_key = gen["nfr_prompt_set"]
    prompt_format = gen.get("prompt_format", "natural")
    serialization = gen.get("serialization", "json")
    prompt_lines = nfr_prompts.get_prompts(nfr_key, mode, prompt_format, serialization)
    max_p = gen.get("max_prompts")
    if max_p is not None:
        prompt_lines = prompt_lines[: int(max_p)]
    return prompt_lines


def _load_run_module(script_name: str):
    """Load approach/{script_name}.py with that directory as cwd (module also chdir's)."""
    approach_dir = os.path.join(_REPO_ROOT, "approach")
    path = os.path.join(approach_dir, script_name)
    spec = importlib.util.spec_from_file_location(f"_nfrgen_{script_name[:-3]}", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    cwd = os.getcwd()
    path_added = False
    try:
        if approach_dir not in sys.path:
            sys.path.insert(0, approach_dir)
            path_added = True
        os.chdir(approach_dir)
        spec.loader.exec_module(mod)
    finally:
        os.chdir(cwd)
        if path_added:
            try:
                sys.path.remove(approach_dir)
            except ValueError:
                pass
    return mod


def _apply_generation_env(gen: Dict[str, Any], repo_root: str) -> None:
    """Optional stability subset + output directory (W1); default pipeline unchanged."""
    subset = gen.get("stability_subset") or {}
    if subset.get("enabled"):
        os.environ["NFRGEN_STABILITY_SUBSET"] = "1"
        path = subset.get("task_ids_file", "results/w1-stability/task_ids_30.json")
        if not os.path.isabs(path):
            path = os.path.join(repo_root, path)
        os.environ["NFRGEN_STABILITY_TASK_IDS"] = path
    else:
        os.environ.pop("NFRGEN_STABILITY_SUBSET", None)
        os.environ.pop("NFRGEN_STABILITY_TASK_IDS", None)

    out = gen.get("output_dir")
    if out:
        if not os.path.isabs(out):
            out = os.path.join(repo_root, out)
        os.environ["NFRGEN_OUTPUT_DIR"] = out
    else:
        os.environ.pop("NFRGEN_OUTPUT_DIR", None)


def run_generation_humaneval(cfg: Dict[str, Any]) -> None:
    gen = cfg["generation"]
    if not gen.get("enabled", True):
        print("[nfrgen] generation disabled in config (generation.enabled: false)")
        return
    _apply_generation_env(gen, _REPO_ROOT)
    mode = gen.get("mode", "rq1").lower()
    if gen.get("benchmark", "humaneval") != "humaneval":
        raise ValueError("run_generation_humaneval only supports benchmark: humaneval")

    nfr_key = gen["nfr_prompt_set"]
    nfr_prompts.validate_nfr_key(nfr_key, "rq1" if mode == "rq1" else "rq2")

    date_str = gen.get("date") or _today()
    model_fn_slug = gen["model_filename_slug"]
    file_slug = gen["filename_slug"]
    model_id = gen["model"]["id"]

    mod = _load_run_module("run_hunmaneval.py")
    mod.EXPERIMENT_SECOND_STEP = bool(gen.get("use_second_step_enhancement", False) and mode == "rq2")

    prompt_lines = resolve_prompt_lines(gen)

    baseline_rel = gen.get("rq2_baseline_jsonl") or []
    if mode == "rq2" and mod.EXPERIMENT_SECOND_STEP and len(baseline_rel) < len(prompt_lines):
        raise ValueError(
            "rq2 + use_second_step_enhancement requires rq2_baseline_jsonl with one path per prompt line (including empty lines in the block)."
        )

    approach_dir = os.path.join(_REPO_ROOT, "approach")
    os.chdir(approach_dir)
    try:
        if gen.get("stability_subset", {}).get("enabled"):
            mod.clear_stability_temp()
        for i, line in enumerate(prompt_lines):
            mod.PROMPT = line
            if mode == "rq2" and mod.EXPERIMENT_SECOND_STEP:
                mod.BASELINE = baseline_rel[i]
            prefix = f"{date_str}-{model_fn_slug}-t00-GenPrompt-{file_slug}-prompt{i}"
            print(f"[*] [nfrgen] humaneval {prefix}")
            mod.run_humaneval(turn=0, PREFIX=prefix, model=model_id)
    finally:
        os.chdir(_REPO_ROOT)


def run_generation_mbpp(cfg: Dict[str, Any]) -> None:
    gen = cfg["generation"]
    if not gen.get("enabled", True):
        print("[nfrgen] generation disabled in config (generation.enabled: false)")
        return
    if gen.get("benchmark", "humaneval") != "mbpp":
        raise ValueError("run_generation_mbpp requires generation.benchmark: mbpp")

    mode = gen.get("mode", "rq1").lower()
    nfr_key = gen["nfr_prompt_set"]
    nfr_prompts.validate_nfr_key(nfr_key, "rq1" if mode == "rq1" else "rq2")

    date_str = gen.get("date") or _today()
    model_fn_slug = gen["model_filename_slug"]
    file_slug = gen["filename_slug"]
    model_id = gen["model"]["id"]

    mod = _load_run_module("run_mbpp.py")
    mod.EXPERIMENT_SECOND_STEP = bool(gen.get("use_second_step_enhancement", False) and mode == "rq2")

    prompt_lines = resolve_prompt_lines(gen)

    baseline_rel = gen.get("rq2_baseline_jsonl") or []
    if mode == "rq2" and mod.EXPERIMENT_SECOND_STEP and len(baseline_rel) < len(prompt_lines):
        raise ValueError(
            "rq2 + use_second_step_enhancement requires rq2_baseline_jsonl with one path per prompt line (including empty lines in the block)."
        )

    approach_dir = os.path.join(_REPO_ROOT, "approach")
    os.chdir(approach_dir)
    try:
        for i, line in enumerate(prompt_lines):
            mod.PROMPT = line
            if mode == "rq2" and mod.EXPERIMENT_SECOND_STEP:
                mod.BASELINE = baseline_rel[i]
            prefix = f"{date_str}-{model_fn_slug}-t00-GenPrompt-{file_slug}-prompt{i}"
            print(f"[*] [nfrgen] mbpp {prefix}")
            mod.run_mbpp(turn=0, PREFIX=prefix, model=model_id)
    finally:
        os.chdir(_REPO_ROOT)


def run_evaluation(cfg: Dict[str, Any]) -> None:
    ev = cfg.get("evaluation") or {}
    if not ev.get("enabled", False):
        print("[nfrgen] evaluation disabled (evaluation.enabled: false)")
        return

    eval_dir = os.path.join(_REPO_ROOT, "evaluation")
    if "PYTHONPATH" in os.environ:
        os.environ["PYTHONPATH"] = eval_dir + os.pathsep + os.environ["PYTHONPATH"]
    else:
        os.environ["PYTHONPATH"] = eval_dir
    if eval_dir not in sys.path:
        sys.path.insert(0, eval_dir)

    import rq1_evaluate as evmod  # noqa: E402

    os.chdir(eval_dir)
    try:
        evmod.reset_nfr_report()
        paths = _resolve_evaluation_paths(ev["jsonl_paths"], eval_dir)
        for p in paths:
            if not os.path.isfile(p):
                raise FileNotFoundError(f"evaluation jsonl not found: {p}")

        dataset = ev["dataset"]
        final_results = evmod.get_final_result(paths, dataset=dataset)
        evmod.generate_nfr_report(
            final_results,
            dataset,
            ev["report_task"],
            ev["approach"],
            ev["model_label"],
        )
        target = ev["target_excel"]
        if not os.path.isabs(target):
            target = os.path.normpath(os.path.join(eval_dir, target))
        out_dir = os.path.dirname(target)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        evmod.NFR_REPORT.to_excel(target, index=False)
        if ev.get("run_rq2_summary_table", False):
            evmod.generate_rq2_summary_table(target)
    finally:
        os.chdir(_REPO_ROOT)


def main_cli() -> None:
    cfg, _, path = load_config()
    print(f"[nfrgen] using config: {path}")
    phases = cfg.get("phases") or ["generation", "evaluation"]

    if "generation" in phases:
        if not isinstance(cfg.get("generation"), dict):
            raise ValueError("nfrgen_experiment.json must include a 'generation' object when phases includes \"generation\".")
        bench = cfg["generation"].get("benchmark", "humaneval")
        if bench == "humaneval":
            run_generation_humaneval(cfg)
        elif bench == "mbpp":
            run_generation_mbpp(cfg)
        else:
            raise ValueError(f"Unknown generation.benchmark: {bench!r}")

    if "evaluation" in phases:
        if not isinstance(cfg.get("evaluation"), dict):
            raise ValueError("nfrgen_experiment.json must include an 'evaluation' object when phases includes \"evaluation\".")
        run_evaluation(cfg)


if __name__ == "__main__":
    main_cli()
