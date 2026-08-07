#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print the prompts for an NFR/condition WITHOUT calling any model (free, offline).

Great for: (1) sanity-checking the exact text before paying for generation, (2) the manual
inspection that threats N1 (no test-passing leak) and N10 (identical functional clause) call for.

Usage:
    python scripts/preview_prompts.py --nfr performance --format structured
    python scripts/preview_prompts.py --nfr errorhandle --format rich_natural --index 0
    python scripts/preview_prompts.py --nfr codesmell --format structured --serialization yaml
"""

from __future__ import annotations

import argparse
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import nfr_prompts as nfp  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline preview of experiment prompts.")
    parser.add_argument("--nfr", required=True, choices=sorted(nfp.RQ1.keys()))
    parser.add_argument("--format", default="structured", choices=list(nfp.PROMPT_FORMATS))
    parser.add_argument("--mode", default="rq1", choices=["rq1", "rq2"])
    parser.add_argument("--serialization", default="json", choices=["json", "yaml"])
    parser.add_argument("--index", type=int, default=None, help="show only this variation (0-9)")
    args = parser.parse_args()

    prompts = nfp.get_prompts(args.nfr, args.mode, args.format, args.serialization)
    indices = [args.index] if args.index is not None else range(len(prompts))
    for i in indices:
        print(f"\n===== {args.nfr} / {args.format} / variation {i} =====")
        print(prompts[i])


if __name__ == "__main__":
    main()
