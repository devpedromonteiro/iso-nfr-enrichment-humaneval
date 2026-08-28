"""Validate experiment configs and that each builds prompts (no API).

Run from repo root:  python -m unittest discover -s tests
"""

import glob
import json
import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import nfr_prompts as nfp  # noqa: E402
import nfrgen_experiment as nx  # noqa: E402

_CONFIG_DIR = os.path.join(_REPO_ROOT, "configs")
_CONFIG_FILES = sorted(glob.glob(os.path.join(_CONFIG_DIR, "*.json")))
_MAIN_CONFIG_FILES = [
    p for p in _CONFIG_FILES
    if not os.path.basename(p).startswith(("w1-", "w1b-"))
]
_HUMANEVAL_CONFIG_FILES = [
    p for p in _MAIN_CONFIG_FILES if not os.path.basename(p).startswith("mbpp-")
]
_W1_CONFIG_FILES = [p for p in _CONFIG_FILES if os.path.basename(p).startswith("w1-stability-")]
_W1B_CONFIG_FILES = [p for p in _CONFIG_FILES if os.path.basename(p).startswith("w1b-")]


class TestConfigs(unittest.TestCase):
    def test_twelve_humaneval_configs_exist(self):
        self.assertEqual(
            len(_HUMANEVAL_CONFIG_FILES),
            12,
            "expected 4 NFRs x 3 conditions = 12 HumanEval configs",
        )

    def test_each_config_is_valid_and_builds_prompts(self):
        seen = set()
        for path in _HUMANEVAL_CONFIG_FILES:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            gen = cfg["generation"]
            ev = cfg["evaluation"]

            self.assertIn(gen["prompt_format"], nfp.PROMPT_FORMATS, path)
            self.assertIn(gen["nfr_prompt_set"], nfp.STRUCTURED_NFRS, path)
            self.assertEqual(len(ev["jsonl_paths"]), 10, path)
            seen.add((gen["nfr_prompt_set"], gen["prompt_format"]))

            lines = nx.resolve_prompt_lines(gen)
            self.assertEqual(len(lines), 10, path)
            if gen["prompt_format"] == "structured":
                spec = json.loads(lines[0].split("\n", 1)[1])["non_functional_requirement"]
                self.assertEqual(spec["attribute"], gen["nfr_prompt_set"])

        expected = {(nfr, fmt) for nfr in nfp.STRUCTURED_NFRS for fmt in nfp.PROMPT_FORMATS}
        self.assertEqual(seen, expected)

    def test_filenames_match_slug(self):
        for path in _HUMANEVAL_CONFIG_FILES:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            slug = cfg["generation"]["filename_slug"]
            self.assertEqual(os.path.basename(path), f"{slug}.json")

    def test_w1_stability_configs(self):
        self.assertEqual(len(_W1_CONFIG_FILES), 2)
        for path in _W1_CONFIG_FILES:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            gen = cfg["generation"]
            self.assertTrue(gen.get("stability_subset", {}).get("enabled"))
            self.assertEqual(gen.get("max_prompts"), 1)
            lines = nx.resolve_prompt_lines(gen)
            self.assertEqual(len(lines), 1)

    def test_w1b_stability_full_config(self):
        self.assertEqual(len(_W1B_CONFIG_FILES), 1)
        path = _W1B_CONFIG_FILES[0]
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        gen = cfg["generation"]
        self.assertFalse(gen.get("stability_subset", {}).get("enabled", False))
        self.assertEqual(gen.get("max_prompts"), 1)
        lines = nx.resolve_prompt_lines(gen)
        self.assertEqual(len(lines), 1)
        self.assertEqual(len(cfg["evaluation"]["jsonl_paths"]), 1)


if __name__ == "__main__":
    unittest.main()
