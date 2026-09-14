"""Stratified dev/held-out split — NON-NEGOTIABLE 1.

3 dev / 2 held-out per class -> 30 dev / 20 held-out. Written once to
data/split.json and committed; never regenerated, never inspected while
iterating on prompts, rubric, or thresholds.

The split is randomized independently of which index within a class carries
a scenario's fact-variant (e.g. C1's partial-return pair, C5's downloaded/
not-downloaded pair) so neither dev nor held-out silently loses an entire
outcome variant.
"""
from __future__ import annotations

import random

from .classes import CLASS_NAMES, N_PER_CLASS, SEED
from ..models.scenario import Scenario

N_DEV_PER_CLASS = 3
N_HOLDOUT_PER_CLASS = N_PER_CLASS - N_DEV_PER_CLASS


def class_split_indices(scenario_class: str) -> tuple[list[int], list[int]]:
    rng = random.Random(f"{SEED}|split|{scenario_class}")
    indices = list(range(1, N_PER_CLASS + 1))
    rng.shuffle(indices)
    dev = sorted(indices[:N_DEV_PER_CLASS])
    holdout = sorted(indices[N_DEV_PER_CLASS:])
    return dev, holdout


def make_split(scenarios: list[Scenario]) -> dict[str, list[str]]:
    dev_ids: list[str] = []
    holdout_ids: list[str] = []

    by_class: dict[str, list[Scenario]] = {c: [] for c in CLASS_NAMES}
    for s in scenarios:
        by_class[s.scenario_class].append(s)

    for cls in CLASS_NAMES:
        class_scenarios = sorted(by_class[cls], key=lambda s: s.id)
        dev_idx, holdout_idx = class_split_indices(cls)
        for i, s in enumerate(class_scenarios, start=1):
            (dev_ids if i in dev_idx else holdout_ids).append(s.id)

    return {"dev": dev_ids, "holdout": holdout_ids}
