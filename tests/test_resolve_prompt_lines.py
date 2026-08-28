"""Tests for nfrgen_experiment.resolve_prompt_lines (config -> prompt strings, no API).

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
import nfrgen_experiment as nx  # noqa: E402


class TestResolvePromptLines(unittest.TestCase):
    def test_default_is_natural_backward_compatible(self):
        gen = {"nfr_prompt_set": "performance", "mode": "rq1"}
        self.assertEqual(nx.resolve_prompt_lines(gen), nfp.RQ1["performance"].split("\n"))

    def test_structured_selected(self):
        gen = {"nfr_prompt_set": "codesmell", "mode": "rq1", "prompt_format": "structured"}
        lines = nx.resolve_prompt_lines(gen)
        self.assertEqual(len(lines), 10)
        spec = json.loads(lines[0].split("\n", 1)[1])["non_functional_requirement"]
        self.assertEqual(spec["attribute"], "codesmell")
        self.assertEqual(spec["iso_iec_25010"]["characteristic"], "Maintainability")

    def test_rich_natural_selected(self):
        gen = {"nfr_prompt_set": "readability", "mode": "rq1", "prompt_format": "rich_natural"}
        lines = nx.resolve_prompt_lines(gen)
        self.assertEqual(len(lines), 10)
        self.assertIn("Consider the following non-functional requirement", lines[0])

    def test_max_prompts_limit(self):
        gen = {"nfr_prompt_set": "errorhandle", "mode": "rq1",
               "prompt_format": "structured", "max_prompts": 1}
        self.assertEqual(len(nx.resolve_prompt_lines(gen)), 1)

    def test_yaml_serialization(self):
        import yaml
        gen = {"nfr_prompt_set": "performance", "mode": "rq1",
               "prompt_format": "structured", "serialization": "yaml"}
        lines = nx.resolve_prompt_lines(gen)
        spec = yaml.safe_load(lines[0].split("\n", 1)[1])["non_functional_requirement"]
        self.assertEqual(spec["attribute"], "performance")


if __name__ == "__main__":
    unittest.main()
