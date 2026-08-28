#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Summarize token usage (and optional cost) from generated .jsonl files.

Generation now stores per-problem token usage (prompt_tokens / completion_tokens / total_tokens)
in each saved result, so we can document how many input/output tokens an experiment consumed and
estimate its cost. This is the "save and document tokens/values" requirement, kept simple.

Usage:
    python scripts/token_report.py path/to/file1.jsonl [more.jsonl ...]
    python scripts/token_report.py *.jsonl --input-rate 1.25 --output-rate 10 --out tokens.csv

Rates are USD per 1,000,000 tokens (set them to your model's pricing). Cost is omitted if rates
are not given.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
from typing import Dict, List


def _read_jsonl(path: str) -> List[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def summarize_file(path: str) -> Dict[str, float]:
    """Sum token usage across the entries of one .jsonl file."""
    prompt_tokens = completion_tokens = total_tokens = 0
    n_with_usage = 0
    n_entries = 0
    for entry in _read_jsonl(path):
        n_entries += 1
        pt = entry.get("prompt_tokens")
        ct = entry.get("completion_tokens")
        tt = entry.get("total_tokens")
        if pt is None and ct is None and tt is None:
            continue
        n_with_usage += 1
        prompt_tokens += int(pt or 0)
        completion_tokens += int(ct or 0)
        total_tokens += int(tt or ((pt or 0) + (ct or 0)))
    return {
        "file": os.path.basename(path),
        "entries": n_entries,
        "entries_with_usage": n_with_usage,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def add_cost(row: Dict[str, float], input_rate: float, output_rate: float) -> None:
    """Add a USD cost estimate using per-1M-token rates."""
    row["cost_usd"] = round(
        row["prompt_tokens"] / 1_000_000 * input_rate
        + row["completion_tokens"] / 1_000_000 * output_rate,
        4,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Token usage / cost report for generated .jsonl files.")
    parser.add_argument("paths", nargs="+", help="jsonl files or globs")
    parser.add_argument("--input-rate", type=float, default=None, help="USD per 1M input tokens")
    parser.add_argument("--output-rate", type=float, default=None, help="USD per 1M output tokens")
    parser.add_argument("--out", default=None, help="optional CSV output path")
    args = parser.parse_args()

    files: List[str] = []
    for p in args.paths:
        files.extend(sorted(glob.glob(p)) if any(c in p for c in "*?[") else [p])

    has_rates = args.input_rate is not None and args.output_rate is not None
    rows = []
    grand = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for path in files:
        if not os.path.isfile(path):
            print(f"[token_report] skip (not found): {path}")
            continue
        row = summarize_file(path)
        if has_rates:
            add_cost(row, args.input_rate, args.output_rate)
        for k in grand:
            grand[k] += row[k]
        rows.append(row)
        msg = (f"{row['file']}: in={row['prompt_tokens']} out={row['completion_tokens']} "
               f"total={row['total_tokens']} (usage on {row['entries_with_usage']}/{row['entries']})")
        if has_rates:
            msg += f" cost=${row['cost_usd']}"
        print(msg)

    print(f"TOTAL: in={grand['prompt_tokens']} out={grand['completion_tokens']} total={grand['total_tokens']}")
    if has_rates:
        total_cost = round(grand["prompt_tokens"] / 1_000_000 * args.input_rate
                           + grand["completion_tokens"] / 1_000_000 * args.output_rate, 4)
        print(f"TOTAL cost=${total_cost}")

    if args.out and rows:
        fieldnames = list(rows[0].keys())
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        print(f"[token_report] wrote {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
