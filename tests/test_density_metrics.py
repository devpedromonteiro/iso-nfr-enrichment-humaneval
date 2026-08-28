"""Tests for evaluation/density_metrics.py (threat N3: density per 10 LOC).

Run from NFRGen-8175:  python -m unittest discover -s tests
"""

import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EVAL_DIR = os.path.join(_REPO_ROOT, "evaluation")
if _EVAL_DIR not in sys.path:
    sys.path.insert(0, _EVAL_DIR)

import density_metrics as dm  # noqa: E402


class TestDensity(unittest.TestCase):
    def test_basic_density(self):
        # 5 issues over 50 LOC -> 1 issue per 10 LOC.
        self.assertAlmostEqual(dm.density_per_10_loc(5, 50), 1.0)

    def test_zero_loc_is_safe(self):
        self.assertEqual(dm.density_per_10_loc(7, 0), 0.0)
        self.assertEqual(dm.density_per_10_loc(7, None), 0.0)

    def test_length_confound_is_removed(self):
        # Same density, different sizes: 10/100 and 20/200 both equal 1.0 per 10 LOC,
        # even though raw counts (10 vs 20) differ -> this is the whole point of N3.
        self.assertAlmostEqual(dm.density_per_10_loc(10, 100), dm.density_per_10_loc(20, 200))

    def test_series(self):
        out = dm.density_series([5, 0, 30], [50, 10, 100])
        self.assertEqual(out, [1.0, 0.0, 3.0])

    def test_series_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            dm.density_series([1, 2], [10])

    def test_density_metrics_mapping(self):
        self.assertEqual(dm.DENSITY_METRICS["code-smell-density"], "Refactor")
        self.assertEqual(dm.DENSITY_METRICS["unreadability-density"], "Convention")


if __name__ == "__main__":
    unittest.main()
