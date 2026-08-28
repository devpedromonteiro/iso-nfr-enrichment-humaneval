"""HumanEval task subset helpers for W1 model-stability checks.

Activated only when ``NFRGEN_STABILITY_SUBSET=1``. Default pipeline behaviour
(164 problems, all prompt variations) is unchanged when the flag is unset.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Set, Tuple

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TASK_IDS_PATH = os.path.join(_REPO_ROOT, "results", "w1-stability", "task_ids_30.json")


def is_subset_mode() -> bool:
    """Return True when stability subset generation is enabled."""
    return os.environ.get("NFRGEN_STABILITY_SUBSET", "").strip() == "1"


def task_ids_file() -> str:
    """Path to the JSON file listing allowed HumanEval task_ids."""
    return os.environ.get("NFRGEN_STABILITY_TASK_IDS", DEFAULT_TASK_IDS_PATH)


def load_task_ids(path: Optional[str] = None) -> List[str]:
    """Load and return task_ids from the stability JSON (sorted for reproducibility)."""
    path = path or task_ids_file()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    ids = data.get("task_ids") or data
    if not isinstance(ids, list) or not ids:
        raise ValueError(f"No task_ids found in {path!r}")
    return sorted(str(t) for t in ids)


def load_task_id_set(path: Optional[str] = None) -> Set[str]:
    """Return task_ids as a set for fast membership tests."""
    return set(load_task_ids(path))


def task_index_map() -> Dict[str, int]:
    """Map HumanEval task_id -> problem index (0..163) using EvalPlus ordering."""
    from evalplus.data import get_human_eval_plus

    problems = get_human_eval_plus()
    return {problems[key]["task_id"]: idx for idx, key in enumerate(problems)}


def allowed_indices(path: Optional[str] = None) -> Set[int]:
    """Problem indices corresponding to the stability task_id list."""
    idx_by_task = task_index_map()
    allowed: Set[int] = set()
    for task_id in load_task_ids(path):
        if task_id not in idx_by_task:
            raise KeyError(f"task_id {task_id!r} not found in HumanEval+ ordering")
        allowed.add(idx_by_task[task_id])
    return allowed


def pass_vector_from_result_json(
    result_json_path: str,
    task_ids: List[str],
    dataset: str = "humaneval",
) -> Dict[str, float]:
    """Extract Pass@1 (0/1) per task_id from an evaluation result JSON."""
    with open(result_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: Dict[str, float] = {}
    result_key = f"{dataset}_result"
    for task_id in task_ids:
        entry = data.get(task_id)
        if entry is None:
            raise KeyError(f"{task_id!r} missing from {result_json_path}")
        res = entry.get(result_key, "")
        out[task_id] = 1.0 if "OK" in res else 0.0
    return out


def select_stratified_task_ids(
    result_json_path: str,
    n_total: int = 30,
    seed: int = 42,
    dataset: str = "humaneval",
) -> Tuple[List[str], Dict[str, object]]:
    """Pick a fixed, stratified subset (~half pass, ~half fail) from a baseline JSON."""
    import random

    with open(result_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    result_key = f"{dataset}_result"
    passed: List[str] = []
    failed: List[str] = []
    for task_id, entry in sorted(data.items()):
        if not task_id.startswith("HumanEval/"):
            continue
        ok = "OK" in entry.get(result_key, "")
        (passed if ok else failed).append(task_id)

    rng = random.Random(seed)
    n_fail = min(n_total // 2, len(failed))
    n_pass = n_total - n_fail
    if len(passed) < n_pass:
        raise ValueError(
            f"Not enough passing tasks for stratified sample: "
            f"pass={len(passed)}, need {n_pass}"
        )
    if len(failed) < n_fail:
        raise ValueError(
            f"Not enough failing tasks for stratified sample: "
            f"fail={len(failed)}, need {n_fail}"
        )
    chosen_pass = sorted(rng.sample(passed, n_pass))
    chosen_fail = sorted(rng.sample(failed, n_fail))
    task_ids = sorted(chosen_pass + chosen_fail)
    meta = {
        "source_baseline_json": result_json_path,
        "seed": seed,
        "n_total": n_total,
        "n_pass_selected": len(chosen_pass),
        "n_fail_selected": len(chosen_fail),
        "baseline_pass_count_full": len(passed),
        "baseline_fail_count_full": len(failed),
        "baseline_pass_rate_full": len(passed) / (len(passed) + len(failed)),
        "note": (
            "When the baseline has fewer than n_total/2 failures, all available failures "
            "are included and the remainder is filled with passing tasks."
        ),
    }
    return task_ids, meta
