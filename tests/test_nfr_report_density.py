"""Integration test: generate_nfr_report emits density-per-10-LOC rows (threat N3).

Uses synthetic in-memory data (no API, no real generations).
Run from NFRGen-8175:  python -m unittest discover -s tests
"""

import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EVAL_DIR = os.path.join(_REPO_ROOT, "evaluation")
if _EVAL_DIR not in sys.path:
    sys.path.insert(0, _EVAL_DIR)

import rq1_evaluate as ev  # noqa: E402


def _details(loc, refactor, convention):
    benchmark = "HumanEval"
    return {
        benchmark: 0.95,
        f"{benchmark}-ET": 0.90,
        "LOC": loc,
        "exception_density": 1.0,
        "comment_loc": 0,
        "non_code_length": 0,
        "non_code_word": 0,
        "test_time": 0.01,
        "test_time_ET": 0.02,
        "pylint_result": {
            "Fatal": {}, "Error": {}, "Warning": {},
            "Convention": {"C0001": convention},
            "Refactor": {"R0001": refactor},
            "Information": {},
        },
    }


class TestReportDensity(unittest.TestCase):
    def test_density_rows_present_and_correct(self):
        ev.reset_nfr_report()
        result = {
            "promptA": _details(loc=50, refactor=5, convention=10),
            "promptB": _details(loc=100, refactor=20, convention=10),
        }
        ev.generate_nfr_report(result, "HumanEval", "performance", "direct", "gpt-5.4-2026-03-05")

        report = ev.NFR_REPORT
        names = set(report["metrics"].tolist())
        self.assertIn("code-smell-density", names)
        self.assertIn("unreadability-density", names)

        smell = report[report["metrics"] == "code-smell-density"].iloc[0]
        # Refactor: 5/50*10=1.0 and 20/100*10=2.0
        self.assertAlmostEqual(smell["prompt1"], 1.0)
        self.assertAlmostEqual(smell["prompt2"], 2.0)
        self.assertAlmostEqual(smell["AVG"], 1.5)

        unread = report[report["metrics"] == "unreadability-density"].iloc[0]
        # Convention: 10/50*10=2.0 and 10/100*10=1.0
        self.assertAlmostEqual(unread["prompt1"], 2.0)
        self.assertAlmostEqual(unread["prompt2"], 1.0)

    def test_raw_counts_still_present(self):
        # N3 is additive: the raw Convention/Refactor rows must remain (appendix/back-compat).
        ev.reset_nfr_report()
        result = {"promptA": _details(loc=50, refactor=5, convention=10)}
        ev.generate_nfr_report(result, "HumanEval", "performance", "direct", "m")
        names = set(ev.NFR_REPORT["metrics"].tolist())
        self.assertIn("Refactor", names)
        self.assertIn("Convention", names)


if __name__ == "__main__":
    unittest.main()
