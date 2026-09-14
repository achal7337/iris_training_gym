"""The step loop — Section 7/8 of prompt.md. Ties the agent, the tools, and
the gate together into one episode: reset -> apply scenario fixture -> loop
(agent decides, gate may veto, tool executes) -> terminate.
"""
from __future__ import annotations

import sqlite3
import time

from ..agent import always_escalate, llm_agent
from ..config import GateConfig, get_env_config, get_gate_config, get_models_config
from ..eval import gate as gate_module
from ..models.scenario import Scenario
from ..models.trajectory import Step, Trajectory
from . import tools
from .database import apply_setup, connect, reset_from_dump
from .state import EpisodeState

AGENTS = {"llm_agent": llm_agent, "always_escalate": always_escalate}


def run_episode(
    scenario: Scenario,
    run_id: str,
    gate_config: GateConfig | None = None,
    agent_name: str = "llm_agent",
    seed: int = 0,
) -> tuple[Trajectory, sqlite3.Connection]:
    env_cfg = get_env_config()
    gate_config = gate_config or get_gate_config()
    agent_cfg = get_models_config().agent
    agent_module = AGENTS[agent_name]

    conn = connect(":memory:")
    reset_from_dump(conn)
    apply_setup(conn, scenario.setup_sql)
    state = EpisodeState(conn=conn, scenario_id=scenario.id, force_stale_status=scenario.force_stale_status)

    from_email = conn.execute(
        "SELECT email FROM customers WHERE id = ?", (scenario.customer_id,)
    ).fetchone()[0]

    steps: list[Step] = []
    history: list[dict] = []
    termination_reason = None
    malformed_retry_used = False
    step_index = 0
    gate_block_count = 0

    while True:
        used_cost = sum(s.cost for s in steps)
        remaining = env_cfg.action_budget - used_cost
        if remaining <= 0:
            termination_reason = "budget_exhausted"
            break

        t0 = time.monotonic()
        try:
            action, prompt_hash, input_tokens, output_tokens = agent_module.act(
                scenario, history, remaining, from_email, seed
            )
        except llm_agent.MalformedOutputError:
            if malformed_retry_used:
                termination_reason = "malformed_output"
                break
            malformed_retry_used = True
            continue
        wall_ms = (time.monotonic() - t0) * 1000

        if action.action not in tools.TOOLS:
            if malformed_retry_used:
                termination_reason = "malformed_output"
                break
            malformed_retry_used = True
            continue

        cost = env_cfg.tool_costs[action.action]
        if cost > remaining:
            # Record what the agent tried, even though it can't be afforded —
            # dropping it silently would hide a would-be action (possibly a
            # violation) from later failure analysis.
            steps.append(Step(
                index=step_index,
                model_id=agent_cfg.model,
                prompt_hash=prompt_hash,
                temperature=agent_cfg.temperature,
                reasoning=action.reason,
                tool_name=action.action,
                arguments=action.arguments,
                raw_result={"error": "BUDGET_EXCEEDED", "would_have_cost": cost, "remaining": remaining},
                cost=0,
                wall_clock_ms=wall_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ))
            termination_reason = "budget_exhausted"
            break

        proposed = {"reasoning": action.reason, "tool_name": action.action, "arguments": action.arguments}
        gate_verdict = gate_module.check_gate(scenario, history, proposed, gate_config, conn=state.conn)

        if gate_verdict.blocked:
            gate_block_count += 1
            judge_reason = gate_verdict.judge.reason if gate_verdict.judge else "blocked by gate"
            raw_result = {"error": "BLOCKED", "reason": judge_reason}
        else:
            try:
                raw_result = tools.call_tool(state, action.action, action.arguments)
            except (tools.ToolError, TypeError) as e:
                raw_result = {"error": "BAD_ARGUMENTS", "detail": str(e)}

        step = Step(
            index=step_index,
            model_id=agent_cfg.model,
            prompt_hash=prompt_hash,
            temperature=agent_cfg.temperature,
            reasoning=action.reason,
            tool_name=action.action,
            arguments=action.arguments,
            raw_result=raw_result,
            cost=cost,
            wall_clock_ms=wall_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            gate_verdict=gate_verdict if gate_config.mode != "ungated" else None,
        )
        steps.append(step)
        history.append(
            {"reasoning": action.reason, "tool_name": action.action, "arguments": action.arguments, "raw_result": raw_result}
        )
        step_index += 1
        malformed_retry_used = False

        if action.action in ("escalate", "reply_and_close"):
            termination_reason = action.action
            break

        if gate_block_count >= 2:
            # Section 10: "The agent may retry once; a second block forces
            # escalate." This bypasses the agent and the budget check — it's
            # a safety backstop, not a discretionary action.
            forced_result = tools.call_tool(state, "escalate", {"reason": "forced escalation after repeated gate block"})
            steps.append(Step(
                index=step_index,
                model_id=agent_cfg.model,
                prompt_hash="forced-escalate",
                temperature=agent_cfg.temperature,
                reasoning="gate blocked this action twice; forcing escalation per policy",
                tool_name="escalate",
                arguments={"reason": "forced escalation after repeated gate block"},
                raw_result=forced_result,
                cost=env_cfg.tool_costs["escalate"],
                wall_clock_ms=0.0,
            ))
            termination_reason = "escalate"
            break

    trajectory = Trajectory(
        id=f"{run_id}-{scenario.id}-seed{seed}",
        scenario_id=scenario.id,
        run_id=run_id,
        agent_name=agent_name,
        gate_mode=gate_config.mode,
        seed=seed,
        steps=steps,
        termination_reason=termination_reason,
        total_cost=sum(s.cost for s in steps),
        total_wall_clock_ms=sum(s.wall_clock_ms for s in steps),
    )
    return trajectory, conn
