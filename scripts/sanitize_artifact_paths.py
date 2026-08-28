#!/usr/bin/env python3
"""Replace absolute local paths in evaluation JSON artifacts with neutral relative paths."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Common absolute prefixes observed in traceback strings inside evaluate_result JSON.
PATH_PREFIXES = (
    "/home/nimbus/Documentos/Mestrado/Reproduzir/RobuNFR/NFRGen-8175/",
    "/home/nimbus/Documentos/Mestrado/Reproduzir/anonimo/nfr-form-vs-content/",
    "/home/master/Documentos/Mestrado/Reproduzir/RobuNFR/NFRGen-8175/",
    "/Users/watch/PycharmProjects/LLMCodeReGen/",
)

REPLACEMENT = ""


def sanitize_text(text: str) -> tuple[str, int]:
    """Return sanitized text and number of replacements."""
    count = 0
    for prefix in PATH_PREFIXES:
        occurrences = text.count(prefix)
        if occurrences:
            text = text.replace(prefix, REPLACEMENT)
            count += occurrences
    return text, count


def sanitize_file(path: Path) -> int:
    original = path.read_text(encoding="utf-8", errors="replace")
    sanitized, count = sanitize_text(original)
    if count and sanitized != original:
        path.write_text(sanitized, encoding="utf-8")
    return count


def iter_target_files(dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for base in dirs:
        if not base.exists():
            continue
        files.extend(base.rglob("*-humaneval_evaluate_result.json"))
        files.extend(base.rglob("*-humaneval_et_evaluate_result.json"))
    return sorted(set(files))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dirs",
        nargs="*",
        default=[
            "approach/2026-05-25-gpt-54-2026-03-05-t00-GenPrompt-codesmell-prompt0-Trail0-humaneval_evaluate_result.json",
        ],
        help="Ignored when --all-study is set",
    )
    parser.add_argument(
        "--all-study",
        action="store_true",
        help="Sanitize all study result directories",
    )
    parser.add_argument(
        "--all-json",
        action="store_true",
        help="Sanitize all *.json files under the repository (traceability + W1 manifests)",
    )
    args = parser.parse_args()

    if args.all_json:
        targets = sorted(ROOT.rglob("*.json"))
    elif args.all_study:
        targets = iter_target_files(
            [
                ROOT / "approach",
                ROOT / "results" / "2026-04-09-gpt-54-2026-03-05-rq1-humaneval",
                ROOT / "results" / "2026-06-13-gpt-54-2026-03-05-rq1-humaneval-3conditions",
                ROOT / "results" / "w1-stability",
            ]
        )
    else:
        targets = [ROOT / p for p in args.dirs]

    total = 0
    touched = 0
    for path in targets:
        if not path.is_file():
            continue
        n = sanitize_file(path)
        if n:
            touched += 1
            total += n
            print(f"sanitized {path.relative_to(ROOT)} ({n} replacements)")
    print(f"done: {touched} files, {total} replacements")


if __name__ == "__main__":
    main()
