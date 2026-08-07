#!/bin/env python3
# -*- coding: utf-8 -*-
"""Density-per-10-LOC helpers (threat N3).

RobuNFR defines code-smell and unreadability as *densities per 10 LOC* (Pylint Refactor /
Convention checkers), not raw counts. Longer code (structured / error-handling prompts) yields
more issues automatically, so comparing raw counts confounds *size* with *quality*. These pure
functions normalize counts by LOC so the report can publish densities alongside the raw counts.

Kept dependency-free on purpose so it can be unit-tested without importing the heavy evaluation
stack (pylint, evalplus, ...).
"""

from typing import List, Optional, Sequence


def density_per_10_loc(count: float, loc: Optional[float]) -> float:
    """Issues per 10 lines of code. Returns 0.0 when LOC is missing or zero (avoids div-by-zero)."""
    if not loc or loc <= 0:
        return 0.0
    return float(count) / float(loc) * 10.0


def density_series(counts: Sequence[float], locs: Sequence[float]) -> List[float]:
    """Element-wise density_per_10_loc over paired (count, loc) sequences."""
    if len(counts) != len(locs):
        raise ValueError(f"counts ({len(counts)}) and locs ({len(locs)}) must have equal length")
    return [density_per_10_loc(c, l) for c, l in zip(counts, locs)]


# Mapping of the published density metric name -> the Pylint checker bucket it normalizes.
# Matches RobuNFR: code smell = Refactor, unreadability = Convention.
DENSITY_METRICS = {
    "code-smell-density": "Refactor",
    "unreadability-density": "Convention",
}
