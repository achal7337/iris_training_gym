"""Step and trajectory records — Section 7 (the environment) of prompt.md."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel

from .annotation import JudgeVerdict
from .scenario import Terminal, ViolationPredicate

ToolName = Literal[
    "lookup_order",
    "lookup_customer",
    "read_policy",
    "inspect_refund_history",
    "issue_refund",
    "escalate",
    "reply_and_close",
]

TerminationReason = Literal[
    "reply_and_close", "escalate", "budget_exhausted", "malformed_output"
]


class GateVerdict(BaseModel):
    blocked: bool
    judge: Optional[JudgeVerdict] = None


class Step(BaseModel):
    index: int
    model_id: str
    prompt_hash: str
    temperature: float
    reasoning: str
    tool_name: str
    arguments: dict[str, Any]
    raw_result: dict[str, Any]
    cost: int
    wall_clock_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    gate_verdict: Optional[GateVerdict] = None


class Trajectory(BaseModel):
    id: str
    scenario_id: str
    run_id: str
    agent_name: str
    gate_mode: str
    seed: int = 0
    steps: list[Step] = []
    termination_reason: Optional[TerminationReason] = None
    total_cost: int = 0
    total_wall_clock_ms: float = 0.0


class OutcomeResult(BaseModel):
    passed: bool
    matched_terminal: Optional[Terminal] = None
    violations: list[ViolationPredicate] = []
    ambiguity_recognized: Optional[bool] = None


class RunResult(BaseModel):
    trajectory_id: str
    scenario_id: str
    outcome: OutcomeResult
    human_touches: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
