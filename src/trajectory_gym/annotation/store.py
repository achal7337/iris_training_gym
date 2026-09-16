"""Minimal JSONL-backed label store. Deliberately dumb for Phase 3 (the
vertical slice explicitly wants a "rough UI"); the real Review page and
active selector arrive in Phase 5.
"""
from __future__ import annotations

from pathlib import Path

from ..config import REPO_ROOT
from ..models.annotation import StepLabel

DEFAULT_STORE_PATH = REPO_ROOT / "data" / "runs" / "labels.jsonl"


def save_label(label: StepLabel, path: Path | str = DEFAULT_STORE_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(label.model_dump_json() + "\n")


def load_labels(path: Path | str = DEFAULT_STORE_PATH, dedupe: bool = True) -> list[StepLabel]:
    """The store is append-only (re-grading a step writes a new row rather
    than editing in place), so by default this keeps only the latest label
    per (trajectory_id, step_index). Pass dedupe=False for the raw audit
    trail."""
    path = Path(path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        labels = [StepLabel.model_validate_json(line) for line in f if line.strip()]
    if not dedupe:
        return labels
    latest: dict[tuple[str, int], StepLabel] = {}
    for label in labels:
        latest[(label.trajectory_id, label.step_index)] = label
    return list(latest.values())


def labeled_keys(path: Path | str = DEFAULT_STORE_PATH, source: str | None = None) -> set[tuple[str, int]]:
    """Keys with a saved label. Pass source (e.g. "human") to count only
    labels from that source as done — a step already labeled by another
    source stays available to relabel."""
    return {
        (label.trajectory_id, label.step_index)
        for label in load_labels(path)
        if source is None or label.source == source
    }
