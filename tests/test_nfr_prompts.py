"""Tests for nfr_prompts.get_prompts and the 3 paired conditions (planejamento_final.md §3).

Run from NFRGen-8175:  python -m unittest discover -s tests
"""

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import nfr_prompts as nfp  # noqa: E402

NFRS = ["performance", "errorhandle", "codesmell", "readability"]
# Strings that would indicate a "pass the tests" leak (threat N1).
FORBIDDEN = ["unit test", "all tests", "pass the test", "tests pass", "functional correctness", "pass@1"]


class TestCounts(unittest.TestCase):
    def test_ten_variations_per_condition(self):
        for nfr in NFRS:
            for fmt in nfp.PROMPT_FORMATS:
                prompts = nfp.get_prompts(nfr, "rq1", fmt)
                self.assertEqual(len(prompts), 10, f"{nfr}/{fmt} should yield 10 prompts")

    def test_natural_matches_baseline(self):
        # Backward-compat: 'natural' must equal the legacy split of RQ1.
        for nfr in NFRS:
            self.assertEqual(
                nfp.get_prompts(nfr, "rq1", "natural"),
                nfp.RQ1[nfr].split("\n"),
            )


class TestFunctionalClauseN10(unittest.TestCase):
    def test_identical_functional_clause_all_conditions(self):
        clause = nfp.FUNCTIONAL_CLAUSE["rq1"]  # "complete the following code:"
        for nfr in NFRS:
            for fmt in nfp.PROMPT_FORMATS:
                for p in nfp.get_prompts(nfr, "rq1", fmt):
                    self.assertIn(clause, p, f"{nfr}/{fmt} missing identical functional clause")

    def test_rq2_clause(self):
        clause = nfp.FUNCTIONAL_CLAUSE["rq2"]  # "improve the following code:"
        for p in nfp.get_prompts("performance", "rq2", "structured"):
            self.assertIn(clause, p)


class TestFramingHeader14(unittest.TestCase):
    def test_symmetric_framing_rich_and_structured(self):
        framing = "Consider the following non-functional requirement"
        for nfr in NFRS:
            for fmt in ("rich_natural", "structured"):
                for p in nfp.get_prompts(nfr, "rq1", fmt):
                    self.assertIn(framing, p, f"{nfr}/{fmt} missing symmetric framing header")


class TestNoTestLeakN1(unittest.TestCase):
    def test_no_test_passing_instructions(self):
        for nfr in NFRS:
            for fmt in ("rich_natural", "structured"):
                for p in nfp.get_prompts(nfr, "rq1", fmt):
                    low = p.lower()
                    for bad in FORBIDDEN:
                        self.assertNotIn(bad, low, f"{nfr}/{fmt} leaks forbidden phrase: {bad!r}")


class TestPairedContent(unittest.TestCase):
    def test_structured_and_rich_share_same_intents(self):
        # The structured intent[i] must equal the rich intent[i] (same content, only form differs).
        for nfr in NFRS:
            rich = nfp.get_prompts(nfr, "rq1", "rich_natural")
            struct = nfp.get_prompts(nfr, "rq1", "structured")
            for i in range(10):
                spec = json.loads(struct[i].split("\n", 1)[1])
                intent = spec["non_functional_requirement"]["intent"]
                self.assertIn(f"Intent: {intent}.", rich[i],
                              f"{nfr} variation {i}: intent mismatch between rich and structured")

    def test_intent_matches_stripped_baseline(self):
        for nfr in NFRS:
            baseline = nfp.RQ1[nfr].split("\n")
            struct = nfp.get_prompts(nfr, "rq1", "structured")
            for i in range(10):
                spec = json.loads(struct[i].split("\n", 1)[1])
                intent = spec["non_functional_requirement"]["intent"]
                self.assertIn(intent, baseline[i],
                              f"{nfr} variation {i}: intent not derived from baseline phrase")


class TestStructuredSchema(unittest.TestCase):
    def test_json_parses_and_has_iso_mapping(self):
        for nfr in NFRS:
            for p in nfp.get_prompts(nfr, "rq1", "structured"):
                body = p.split("\n", 1)[1]
                spec = json.loads(body)["non_functional_requirement"]
                self.assertEqual(spec["attribute"], nfr)
                self.assertEqual(spec["iso_iec_25010"], nfp.ISO25010[nfr])
                self.assertEqual(spec["constraints"], nfp.CONSTRAINTS[nfr])
                self.assertEqual(spec["acceptance_criteria"], nfp.ACCEPTANCE[nfr])

    def test_yaml_serialization(self):
        import yaml
        for p in nfp.get_prompts("performance", "rq1", "structured", serialization="yaml"):
            body = p.split("\n", 1)[1]
            spec = yaml.safe_load(body)["non_functional_requirement"]
            self.assertEqual(spec["attribute"], "performance")


class TestDiversityParity(unittest.TestCase):
    """N6/N7: rich and structured derive from one source -> constraints fixed, only intent varies."""

    def test_constraints_constant_across_variations(self):
        for nfr in NFRS:
            struct = nfp.get_prompts(nfr, "rq1", "structured")
            constraint_sets = set()
            intents = set()
            for p in struct:
                spec = json.loads(p.split("\n", 1)[1])["non_functional_requirement"]
                constraint_sets.add(tuple(spec["constraints"]))
                intents.add(spec["intent"])
            self.assertEqual(len(constraint_sets), 1, f"{nfr}: constraints must be constant")
            self.assertEqual(len(intents), 10, f"{nfr}: the 10 intents must all differ")


class TestRawAndErrors(unittest.TestCase):
    def test_raw_falls_back_to_baseline(self):
        for fmt in nfp.PROMPT_FORMATS:
            self.assertEqual(nfp.get_prompts("raw", "rq1", fmt), nfp.RQ1["raw"].split("\n"))

    def test_invalid_format_raises(self):
        with self.assertRaises(ValueError):
            nfp.get_prompts("performance", "rq1", "totally_unknown")

    def test_invalid_nfr_raises(self):
        with self.assertRaises(ValueError):
            nfp.get_prompts("does_not_exist", "rq1", "structured")


if __name__ == "__main__":
    unittest.main()
