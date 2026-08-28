"""Tests for stability_subset.py (W1 model-stability helpers)."""

import json
import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import stability_subset as ss  # noqa: E402

_BASELINE = os.path.join(
    _REPO_ROOT,
    "results",
    "2026-04-09-gpt-54-2026-03-05-rq1-humaneval",
    "2026-04-25-gpt-54-2026-03-05-t00-GenPrompt-performance-prompt0-Trail0-humaneval_evaluate_result.json",
)


class TestStabilitySubset(unittest.TestCase):
    def test_select_stratified_task_ids(self):
        if not os.path.isfile(_BASELINE):
            self.skipTest("baseline JSON not present")
        task_ids, meta = ss.select_stratified_task_ids(_BASELINE, n_total=30, seed=42)
        self.assertEqual(len(task_ids), 30)
        self.assertEqual(meta["n_fail_selected"], 11)
        self.assertEqual(meta["n_pass_selected"], 19)
        self.assertEqual(len(set(task_ids)), 30)

    def test_select_is_reproducible(self):
        if not os.path.isfile(_BASELINE):
            self.skipTest("baseline JSON not present")
        a, _ = ss.select_stratified_task_ids(_BASELINE, seed=42)
        b, _ = ss.select_stratified_task_ids(_BASELINE, seed=42)
        self.assertEqual(a, b)

    def test_pass_vector_from_result_json(self):
        if not os.path.isfile(_BASELINE):
            self.skipTest("baseline JSON not present")
        task_ids, _ = ss.select_stratified_task_ids(_BASELINE, n_total=4, seed=1)
        vec = ss.pass_vector_from_result_json(_BASELINE, task_ids)
        self.assertEqual(set(vec.keys()), set(task_ids))
        self.assertTrue(all(v in (0.0, 1.0) for v in vec.values()))

    def test_is_subset_mode_default_off(self):
        os.environ.pop("NFRGEN_STABILITY_SUBSET", None)
        self.assertFalse(ss.is_subset_mode())

    def test_is_subset_mode_on(self):
        os.environ["NFRGEN_STABILITY_SUBSET"] = "1"
        try:
            self.assertTrue(ss.is_subset_mode())
        finally:
            os.environ.pop("NFRGEN_STABILITY_SUBSET", None)

    def test_load_task_ids_roundtrip(self):
        if not os.path.isfile(_BASELINE):
            self.skipTest("baseline JSON not present")
        task_ids, _ = ss.select_stratified_task_ids(_BASELINE, n_total=6, seed=7)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ids.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"task_ids": task_ids}, f)
            loaded = ss.load_task_ids(path)
            self.assertEqual(loaded, sorted(task_ids))

    def test_allowed_indices_cover_task_ids(self):
        if not os.path.isfile(_BASELINE):
            self.skipTest("baseline JSON not present")
        task_ids, _ = ss.select_stratified_task_ids(_BASELINE, n_total=8, seed=3)
        idx_map = ss.task_index_map()
        indices = ss.allowed_indices()
        os.environ["NFRGEN_STABILITY_SUBSET"] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ids.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"task_ids": task_ids}, f)
            os.environ["NFRGEN_STABILITY_TASK_IDS"] = path
            try:
                indices = ss.allowed_indices(path)
            finally:
                os.environ.pop("NFRGEN_STABILITY_SUBSET", None)
                os.environ.pop("NFRGEN_STABILITY_TASK_IDS", None)
        self.assertEqual(len(indices), len(task_ids))
        for tid in task_ids:
            self.assertIn(idx_map[tid], indices)


class TestW1CompareSelfConsistency(unittest.TestCase):
    """April baseline compared to itself should be perfectly stable."""

    def test_baseline_vs_itself(self):
        if not os.path.isfile(_BASELINE):
            self.skipTest("baseline JSON not present")
        task_ids, _ = ss.select_stratified_task_ids(_BASELINE, n_total=30, seed=42)
        sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts"))
        import w1_compare_stability as w1c  # noqa: E402

        row = w1c.compare_nfr("performance", _BASELINE, _BASELINE, task_ids)
        self.assertEqual(row["pass_at_1_agreement"], 1.0)
        self.assertEqual(row["pass_at_1_april_mean"], row["pass_at_1_june_mean"])
        self.assertTrue(row["stable_pass_at_1"])


if __name__ == "__main__":
    unittest.main()
