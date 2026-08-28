"""Tests for evaluation/stats_compare.py (paired stats: Wilcoxon, Cliff's delta, Holm, N2/N5/N6).

Run from NFRGen-8175:  python -m unittest discover -s tests
"""

import json
import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EVAL_DIR = os.path.join(_REPO_ROOT, "evaluation")
if _EVAL_DIR not in sys.path:
    sys.path.insert(0, _EVAL_DIR)

import stats_compare as sc  # noqa: E402


class TestCliffsDelta(unittest.TestCase):
    def test_full_dominance(self):
        delta, mag = sc.cliffs_delta([10, 11, 12], [1, 2, 3])
        self.assertAlmostEqual(delta, 1.0)
        self.assertEqual(mag, "large")

    def test_no_difference(self):
        delta, mag = sc.cliffs_delta([5, 5, 5], [5, 5, 5])
        self.assertAlmostEqual(delta, 0.0)
        self.assertEqual(mag, "negligible")

    def test_sign(self):
        delta, _ = sc.cliffs_delta([1, 2, 3], [10, 11, 12])
        self.assertAlmostEqual(delta, -1.0)


class TestRankdata(unittest.TestCase):
    def test_average_ties(self):
        # values [1, 2, 2, 3] -> ranks [1, 2.5, 2.5, 4]
        self.assertEqual(sc._rankdata_average([1, 2, 2, 3]), [1.0, 2.5, 2.5, 4.0])


class TestWilcoxon(unittest.TestCase):
    def test_all_zero_diff(self):
        stat, p = sc.wilcoxon_signed_rank([1, 2, 3], [1, 2, 3])
        self.assertEqual(p, 1.0)

    def test_normal_approx_known_value(self):
        # diffs 1..10 (all positive, no ties): expected two-sided p ~= 0.0059.
        diffs = list(range(1, 11))
        stat, p = sc._wilcoxon_normal_approx(diffs)
        self.assertAlmostEqual(stat, 55.0)
        self.assertAlmostEqual(p, 0.0059, places=3)

    def test_strong_effect_is_significant(self):
        x = [1.0] * 20
        y = [0.0] * 20
        _, p = sc.wilcoxon_signed_rank(x, y)
        self.assertLess(p, 0.05)


class TestHolm(unittest.TestCase):
    def test_known(self):
        adj = sc.holm_correction([0.01, 0.04])
        self.assertAlmostEqual(adj[0], 0.02)
        self.assertAlmostEqual(adj[1], 0.04)

    def test_monotonic_and_capped(self):
        adj = sc.holm_correction([0.5, 0.6])
        self.assertTrue(all(0.0 <= a <= 1.0 for a in adj))
        self.assertGreaterEqual(adj[1], adj[0])


class TestDiversityRobustness(unittest.TestCase):
    def test_identical_prompts_zero_diversity(self):
        self.assertAlmostEqual(sc.prompt_diversity(["a b c", "a b c", "a b c"]), 0.0)

    def test_disjoint_prompts_max_diversity(self):
        self.assertAlmostEqual(sc.prompt_diversity(["a b", "c d"]), 1.0)

    def test_stdev(self):
        self.assertAlmostEqual(sc.stdev_across_variations([2, 4, 4, 4, 5, 5, 7, 9]), 2.13808, places=4)


class TestPairedN2(unittest.TestCase):
    def test_intersection_only(self):
        a = {"t1": 1.0, "t2": 2.0, "t3": 3.0}
        b = {"t2": 5.0, "t3": 6.0, "t4": 7.0}
        xa, xb, common = sc.paired_vectors(a, b)
        self.assertEqual(common, ["t2", "t3"])
        self.assertEqual(xa, [2.0, 3.0])
        self.assertEqual(xb, [5.0, 6.0])

    def test_compare_conditions_two_rows_with_holm(self):
        conditions = {
            "nl_simple": {f"t{i}": 0.0 for i in range(20)},
            "nl_rich": {f"t{i}": 0.5 for i in range(20)},
            "structured": {f"t{i}": 1.0 for i in range(20)},
        }
        rows = sc.compare_conditions(conditions)
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertIn("p_value_holm", r)
            self.assertEqual(r["n_problems"], 20)


class TestLoader(unittest.TestCase):
    def test_load_problem_metric_pass(self):
        data = {
            "HumanEval/0": {"humaneval_result": "....\nOK\n"},
            "HumanEval/1": {"humaneval_result": "FAILED"},
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            out = sc.load_problem_metric(path, "pass", dataset="humaneval")
            self.assertEqual(out["HumanEval/0"], 1.0)
            self.assertEqual(out["HumanEval/1"], 0.0)
        finally:
            os.remove(path)

    def test_load_condition_averages(self):
        d1 = {"t0": {"humaneval_result": "OK"}, "t1": {"humaneval_result": "no"}}
        d2 = {"t0": {"humaneval_result": "no"}, "t1": {"humaneval_result": "no"}}
        paths = []
        for d in (d1, d2):
            f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
            json.dump(d, f)
            f.close()
            paths.append(f.name)
        try:
            out = sc.load_condition(paths, "pass", dataset="humaneval")
            self.assertAlmostEqual(out["t0"], 0.5)  # OK then no -> mean 0.5
            self.assertAlmostEqual(out["t1"], 0.0)
        finally:
            for p in paths:
                os.remove(p)

    def test_load_problem_metric_densities(self):
        data = {
            "HumanEval/0": {
                "code": "def f():\n    pass\ncandidate = f\n",
                "pylint": {
                    "Convention": ["c1", "c2"],
                    "Refactor": ["r1"],
                },
            },
            "HumanEval/1": {
                "code": "def g():\n    try:\n        pass\n    except ValueError:\n        pass\ncandidate = g\n",
                "pylint": {"Convention": [], "Refactor": []},
            },
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            unread = sc.load_problem_metric(path, "unreadability")
            smell = sc.load_problem_metric(path, "code_smell")
            exc = sc.load_problem_metric(path, "exception")
            # HumanEval/0: 2 lines LOC, 2 Convention -> 10.0 per 10 LOC
            self.assertAlmostEqual(unread["HumanEval/0"], 10.0)
            self.assertAlmostEqual(smell["HumanEval/0"], 5.0)
            self.assertAlmostEqual(exc["HumanEval/0"], 0.0)
            # HumanEval/1: 5 lines, 1 except -> 2.0 per 10 LOC
            self.assertAlmostEqual(exc["HumanEval/1"], 2.0)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
