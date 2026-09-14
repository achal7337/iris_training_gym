"""The degenerate reward-hacking baseline (Section 8/11). Escalates every
ticket immediately, no tools, no LLM call — zero policy violations and zero
value. Scored alongside the real agent specifically to show that "zero
violations" alone is not a win condition; human touches is a first-class
cost precisely so this baseline doesn't look good.
"""
from __future__ import annotations

from .llm_agent import AgentAction


def act(
    scenario, history: list[dict], remaining_budget: int, from_email: str, seed: int = 0
) -> tuple[AgentAction, str, int, int]:
    action = AgentAction(
        reason="always_escalate baseline: never resolves autonomously",
        action="escalate",
        arguments={"reason": "always-escalate baseline"},
    )
    return action, "always_escalate-no-prompt", 0, 0
