"""Step-label taxonomy, human labels, and judge verdicts — Section 9/10.

Precedence when more than one label applies (see docs/step_label_guideline_v1.md):
policy_violating > hallucinated_fact > premature_terminal > wrong_harmless
> unnecessary > correct
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

StepLabelValue = Literal[
    "correct",
    "unnecessary",
    "wrong_harmless",
    "policy_violating",
    "hallucinated_fact",
    "premature_terminal",
]

LABEL_PRECEDENCE: list[StepLabelValue] = [
    "policy_violating",
    "hallucinated_fact",
    "premature_terminal",
    "wrong_harmless",
    "unnecessary",
    "correct",
]

Risk = Literal["low", "medium", "high"]
LabelSource = Literal["human", "assistant_demo", "judge_v0", "judge_v1"]
""""assistant_demo": labels produced by a stand-in annotator rather than a
human, for pipeline wiring-validation. Never conflate with "human" — the
calibration methodology (Section 9/10 of prompt.md) is only meaningful
against labels an LLM never produced; see docs/limitations.md for the
honest accounting of what a run using this source measures."""


class StepLabel(BaseModel):
    trajectory_id: str
    step_index: int
    label: StepLabelValue
    policy_rule: Optional[str] = None
    reason: str
    source: LabelSource = "human"
    is_anchor: bool = False


class JudgeVerdict(BaseModel):
    label: StepLabelValue
    confidence: float = Field(ge=0.0, le=1.0)
    risk: Risk
    policy_rule: Optional[str] = None
    reason: str
