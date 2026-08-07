"""Tests for token-usage capture (Solution._extract_*_usage) and token_report summary.

No network: feed fake completion/response objects. Run from NFRGen-8175:
    python -m unittest discover -s tests
"""

import json
import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APPROACH_DIR = os.path.join(_REPO_ROOT, "approach")
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "scripts")
for d in (_APPROACH_DIR, _SCRIPTS_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)

import prompt_based_solution as pbs  # noqa: E402
import token_report as tr  # noqa: E402


class _FakeUsage:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeCompletion:
    def __init__(self, usage):
        self.usage = usage


class TestUsageExtraction(unittest.TestCase):
    def test_openai_usage(self):
        comp = _FakeCompletion(_FakeUsage(prompt_tokens=100, completion_tokens=40, total_tokens=140))
        usage = pbs.Solution._extract_openai_usage(comp, "gpt-5.4-2026-03-05")
        self.assertEqual(usage["prompt_tokens"], 100)
        self.assertEqual(usage["completion_tokens"], 40)
        self.assertEqual(usage["total_tokens"], 140)
        self.assertEqual(usage["model"], "gpt-5.4-2026-03-05")

    def test_openai_usage_none_safe(self):
        self.assertEqual(pbs.Solution._extract_openai_usage(_FakeCompletion(None), "m"), {})

    def test_claude_usage(self):
        resp = _FakeCompletion(_FakeUsage(input_tokens=70, output_tokens=15))
        usage = pbs.Solution._extract_claude_usage(resp, "claude-x")
        self.assertEqual(usage["prompt_tokens"], 70)
        self.assertEqual(usage["completion_tokens"], 15)


class TestTokenReport(unittest.TestCase):
    def test_summarize_file(self):
        rows = [
            {"task_id": "t0", "prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
            {"task_id": "t1", "prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
            {"task_id": "t2", "completion": "no usage here"},
        ]
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        for r in rows:
            f.write(json.dumps(r) + "\n")
        f.close()
        try:
            summary = tr.summarize_file(f.name)
            self.assertEqual(summary["entries"], 3)
            self.assertEqual(summary["entries_with_usage"], 2)
            self.assertEqual(summary["prompt_tokens"], 150)
            self.assertEqual(summary["completion_tokens"], 50)
            self.assertEqual(summary["total_tokens"], 200)
        finally:
            os.remove(f.name)

    def test_cost(self):
        row = {"prompt_tokens": 1_000_000, "completion_tokens": 500_000}
        tr.add_cost(row, input_rate=1.0, output_rate=10.0)
        self.assertAlmostEqual(row["cost_usd"], 1.0 + 5.0)


if __name__ == "__main__":
    unittest.main()
