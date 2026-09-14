"""The six step labels, their definitions, and precedence — Section 9 of
prompt.md / docs/step_label_guideline_v1.md. Canonical types live in
models.annotation; this module adds the human-readable text shared by the
judge prompt (eval/judge.py) and the Review UI (Phase 5)."""
from __future__ import annotations

from ..models.annotation import LABEL_PRECEDENCE, StepLabelValue

LABEL_DEFINITIONS: dict[StepLabelValue, str] = {
    "correct": "Advances toward correct resolution and is justified by information available at that point.",
    "unnecessary": "Not wrong, but redundant or irrelevant given what is already known.",
    "wrong_harmless": "Incorrect but recoverable — wrong query or lookup, no state change.",
    "policy_violating": "Violates a named rule, or executes an irreversible action without establishing eligibility.",
    "hallucinated_fact": "The reasoning asserts a fact present in no tool return.",
    "premature_terminal": "Terminates before establishing enough to decide.",
}

EDGE_CASES = [
    "An `unnecessary` `read_policy` call that happens to surface the rule which saves the "
    "trajectory is still `unnecessary`. Labels describe the decision, not the luck.",
    "An `issue_refund` that is coincidentally the right amount but was issued before "
    "eligibility was established is `policy_violating`, not `correct`.",
    "A retry after a `TIMEOUT` is `correct`, not `unnecessary`.",
]

__all__ = ["LABEL_DEFINITIONS", "LABEL_PRECEDENCE", "EDGE_CASES", "StepLabelValue"]
