#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Export all 164 HumanEval task_ids for W1 Level B comparison."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import stability_subset as ss  # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "results", "w1-stability", "task_ids_164.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write all HumanEval task_ids for W1 Level B.")
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    task_ids = sorted(ss.task_index_map().keys())
    payload = {
        "description": "All 164 HumanEval tasks for W1 Level B stability comparison (NL-simple prompt0).",
        "n_total": len(task_ids),
        "task_ids": task_ids,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"[w1b] wrote {len(task_ids)} task_ids -> {args.out}")


if __name__ == "__main__":
    main()
