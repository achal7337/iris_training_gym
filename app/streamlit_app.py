"""Streamlit UI — Section 11 of prompt.md. Four pages total; Run and
Trajectory (Phase 4) plus Review (Phase 5) here. Report lands in Phase 6.
Deliberately plain.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trajectory_gym.annotation.store import labeled_keys, save_label  # noqa: E402
from trajectory_gym.annotation.taxonomy import LABEL_DEFINITIONS  # noqa: E402
from trajectory_gym.cli import (  # noqa: E402
    ANNOTATION_DIR,
    REVIEW_QUEUE_PATH,
    RUNS_DIR,
    load_outcomes,
    load_scenarios,
    load_split,
    load_trajectories,
    run_and_persist,
)
from trajectory_gym.config import get_gate_config  # noqa: E402
from trajectory_gym.eval.metrics import compute_scoreboard  # noqa: E402
from trajectory_gym.models.annotation import StepLabel  # noqa: E402
from trajectory_gym.models.scenario import Scenario  # noqa: E402
from trajectory_gym.report.recommendation import generate_recommendation  # noqa: E402

st.set_page_config(page_title="Trajectory Gym", layout="wide")


@st.cache_data
def _load_scenarios() -> dict[str, Scenario]:
    return load_scenarios()


@st.cache_data
def _load_split() -> dict[str, list[str]]:
    return load_split()


def _existing_run_ids() -> list[str]:
    if not RUNS_DIR.exists():
        return []
    return sorted(
        (p.name for p in RUNS_DIR.iterdir() if p.is_dir() and (p / "trajectories.jsonl").exists()),
        reverse=True,
    )


def _load_trajectories(run_id: str) -> list:
    return load_trajectories(run_id)


def _load_outcomes(run_id: str) -> list[dict]:
    return load_outcomes(run_id)


# ---------------------------------------------------------------------------
# Run page
# ---------------------------------------------------------------------------


def run_page() -> None:
    st.title("Run")
    scenarios = _load_scenarios()
    split_map = _load_split()
    gate_cfg = get_gate_config()

    col1, col2 = st.columns(2)
    with col1:
        source = st.radio("Scenario pack", ["dev", "holdout", "all", "single scenario"], horizontal=True)
        if source == "single scenario":
            scenario_id = st.selectbox("Scenario", sorted(scenarios.keys()))
            scenario_ids = [scenario_id]
        else:
            scenario_ids = split_map["dev"] + split_map["holdout"] if source == "all" else split_map[source]
        limit = st.number_input("Limit (0 = no cap)", min_value=0, value=0, step=1)
        if limit:
            scenario_ids = scenario_ids[:limit]

        agent_name = st.selectbox("Agent", ["llm_agent", "always_escalate"])
        seeds = st.number_input("Seeds", min_value=1, max_value=5, value=1)

    with col2:
        gate_mode = st.selectbox("Gate mode", ["ungated", "gated", "human_first"], index=["ungated", "gated", "human_first"].index(gate_cfg.mode))
        tau = st.slider("τ (gate threshold)", 0.0, 1.0, gate_cfg.tau, 0.05, disabled=(gate_mode != "gated"))
        run_id = st.text_input("Run ID", value=f"streamlit-{int(time.time())}")

    st.caption(f"{len(scenario_ids)} scenario(s) × {seeds} seed(s) = {len(scenario_ids) * seeds} episode(s)")

    if st.button("Run", type="primary"):
        gate_config = gate_cfg.model_copy(update={"mode": gate_mode, "tau": tau})
        run_dir = RUNS_DIR / run_id
        progress = st.progress(0.0)
        results_box = st.container()
        records = []
        total = len(scenario_ids) * seeds
        done = 0
        for scenario_id in scenario_ids:
            scenario = scenarios[scenario_id]
            for seed in range(seeds):
                record = run_and_persist(scenario, run_id, gate_config, agent_name, seed, run_dir)
                records.append(record)
                done += 1
                progress.progress(done / total)
                outcome = record.outcome
                with results_box:
                    label = f"`{scenario.id}` seed={seed} — {record.trajectory.termination_reason}"
                    if outcome.violations:
                        st.error(f"{label} — VIOLATION: {outcome.violations}")
                    elif outcome.passed:
                        st.success(f"{label} — PASS")
                    else:
                        st.warning(f"{label} — fail")

        board = compute_scoreboard(records)
        with open(run_dir / "scoreboard.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(board, f, indent=2)
            f.write("\n")

        st.subheader("Scoreboard")
        st.json(board)
        st.success(f"Wrote {len(records)} trajectories to `{run_dir}`. Open the Trajectory page to inspect them.")


# ---------------------------------------------------------------------------
# Trajectory page
# ---------------------------------------------------------------------------


def trajectory_page() -> None:
    st.title("Trajectory")
    run_ids = _existing_run_ids()
    if not run_ids:
        st.info("No runs yet — use the Run page first.")
        return

    run_id = st.selectbox("Run", run_ids)
    trajectories = _load_trajectories(run_id)
    outcomes = {(o["scenario_id"], o.get("seed", 0)): o for o in _load_outcomes(run_id)}
    scenarios = _load_scenarios()

    options = [f"{t.scenario_id} (seed {t.seed})" for t in trajectories]
    idx = st.selectbox("Trajectory", range(len(trajectories)), format_func=lambda i: options[i])
    trajectory = trajectories[idx]
    scenario = scenarios.get(trajectory.scenario_id)
    outcome = outcomes.get((trajectory.scenario_id, trajectory.seed))

    if scenario:
        st.markdown(f"**Ticket** ({scenario.scenario_class}):")
        st.info(scenario.ticket_body)
        gt = scenario.ground_truth
        st.caption(
            f"Ground truth: **{gt.expected_terminal}**"
            + (f" / ${gt.expected_amount_cents / 100:.2f}" if gt.expected_amount_cents else "")
            + (f" (alt: {gt.accepted_alternates})" if gt.accepted_alternates else "")
        )

    st.divider()
    for step in trajectory.steps:
        is_error = isinstance(step.raw_result, dict) and "error" in step.raw_result
        header = f"Step {step.index}: {step.tool_name}"
        if step.gate_verdict is not None:
            header += "  🚫 BLOCKED" if step.gate_verdict.blocked else "  ✅ allowed"
        with st.container(border=True):
            if is_error:
                st.markdown(f":red[**{header}**]")
            else:
                st.markdown(f"**{header}**")
            st.write(f"*{step.reasoning}*")
            st.code(json.dumps(step.arguments, indent=2), language="json")
            st.write("Result:")
            if is_error:
                st.error(step.raw_result)
            else:
                st.json(step.raw_result, expanded=False)
            if step.gate_verdict and step.gate_verdict.judge:
                j = step.gate_verdict.judge
                st.caption(f"Judge: **{j.label}** @ {j.confidence:.2f} confidence ({j.risk} risk) — {j.reason}")

    st.divider()
    st.markdown(f"**Termination:** {trajectory.termination_reason}")
    if outcome:
        if outcome["violations"]:
            st.error(f"Violations: {outcome['violations']}")
        elif outcome["passed"]:
            st.success(f"PASS — matched terminal: {outcome['matched_terminal']}")
        else:
            st.warning(f"Fail — matched terminal: {outcome['matched_terminal']}")


# ---------------------------------------------------------------------------
# Review page
# ---------------------------------------------------------------------------


def _load_queue() -> list[dict]:
    if not REVIEW_QUEUE_PATH.exists():
        return []
    with open(REVIEW_QUEUE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def review_page() -> None:
    st.title("Review")
    queue = _load_queue()
    if not queue:
        st.info(
            "No review queue yet. Build one with:\n\n"
            "`python -m trajectory_gym.cli select --run-id <run> --n 70`"
        )
        return

    human_keys = labeled_keys(source="human")
    remaining = [item for item in queue if (item["trajectory_id"], item["step_index"]) not in human_keys]

    st.caption(
        f"{len(human_keys)} / {len(queue)} graded by a human. "
        "The rest already carry an `assistant_demo` label (an LLM stand-in used to validate "
        "the pipeline — see docs/limitations.md) and are open here to grade for real."
    )
    st.progress(min(1.0, len(human_keys) / len(queue)) if queue else 0.0)

    if not remaining:
        st.success("Every queue item has a human label. Head to the Report page for calibration numbers.")
        return

    item = remaining[0]
    run_trajectories = {t.id: t for t in _load_trajectories(item["run_id"])}
    trajectory = run_trajectories.get(item["trajectory_id"])
    scenarios = _load_scenarios()
    scenario = scenarios.get(item["scenario_id"])

    if scenario:
        st.markdown(f"**Ticket** ({scenario.scenario_class}):")
        st.info(scenario.ticket_body)

    if trajectory:
        step_index = item["step_index"]
        st.markdown("**Trajectory so far:**")
        for s in trajectory.steps[:step_index]:
            st.caption(f"Step {s.index}: {s.tool_name}({s.arguments}) -> {s.raw_result}")
        step = trajectory.steps[step_index]
        with st.container(border=True):
            st.markdown(f"**Step {step.index} (grade this one): {step.tool_name}**")
            st.write(f"*{step.reasoning}*")
            st.code(json.dumps(step.arguments, indent=2), language="json")
            st.write("Result:")
            st.json(step.raw_result, expanded=False)

    with st.expander("Why was this step selected?", expanded=True):
        st.write(item["explanation"])
        jv = item["judge_verdict"]
        st.caption(f"Judge v0: **{jv['label']}** @ {jv['confidence']:.2f} confidence ({jv['risk']} risk) — {jv['reason']}")
        if item["is_anchor"]:
            st.caption("📌 Anchor candidate — this label may be used as a few-shot example in judge v1.")

    st.divider()
    label_options = list(LABEL_DEFINITIONS.keys())
    with st.form(key=f"grade-{item['trajectory_id']}-{item['step_index']}", clear_on_submit=True):
        label = st.radio(
            "Label", label_options,
            format_func=lambda l: f"{l} — {LABEL_DEFINITIONS[l]}",
        )
        reason = st.text_input("Reason (one sentence, required)")
        policy_rule = st.text_input("Policy rule (optional, e.g. 6.1)")
        is_anchor = st.checkbox("Mark as anchor", value=item["is_anchor"])
        submitted = st.form_submit_button("Save & Next", type="primary")

    if submitted:
        if not reason.strip():
            st.error("Reason is required.")
        else:
            save_label(StepLabel(
                trajectory_id=item["trajectory_id"], step_index=item["step_index"],
                label=label, policy_rule=policy_rule or None, reason=reason,
                source="human", is_anchor=is_anchor,
            ))
            st.rerun()


# ---------------------------------------------------------------------------
# Report page
# ---------------------------------------------------------------------------

FAILURE_MODES_PATH = ANNOTATION_DIR / "failure_modes.json"

REPORT_METRICS = [
    "task_success_rate", "policy_violations_total", "autonomy_rate", "human_touches",
    "human_minutes_estimated", "avg_actions_per_ticket", "avg_tokens_per_ticket", "avg_cost_usd_per_ticket",
]


def _load_scoreboard(run_id: str) -> dict | None:
    path = RUNS_DIR / run_id / "scoreboard.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_tau(run_id: str) -> float | None:
    m = re.search(r"tau([0-9.]+)", run_id)
    return float(m.group(1)) if m else None


def report_page() -> None:
    st.title("Report")
    run_ids = _existing_run_ids()
    if not run_ids:
        st.info("No runs yet. Use the Run page or `cli.py run` first.")
        return

    st.subheader("Before / after comparison")
    preferred = ["baseline-holdout-ungated", "gated-tau0.5-holdout", "outcome-oracle-holdout", "always-escalate-holdout"]
    default = [r for r in preferred if r in run_ids] or run_ids[:4]
    selected = st.multiselect("Runs to compare", run_ids, default=default)
    boards = {rid: b for rid in selected if (b := _load_scoreboard(rid))}
    if boards:
        table = {"metric": REPORT_METRICS}
        for rid, b in boards.items():
            table[rid] = [b.get(m) for m in REPORT_METRICS]
        st.dataframe(table, width="stretch")
        for rid, b in boards.items():
            if b.get("policy_violations_by_rule"):
                st.caption(f"**{rid}** violations by rule: {b['policy_violations_by_rule']}")

    st.divider()
    st.subheader("Tau frontier (held-out)")
    tau_runs = sorted(
        ((tau, rid) for rid in run_ids if (tau := _parse_tau(rid)) is not None), key=lambda x: x[0]
    )
    if tau_runs:
        taus, violations, touches = [], [], []
        for tau, rid in tau_runs:
            b = _load_scoreboard(rid)
            if not b:
                continue
            taus.append(tau)
            violations.append(b["policy_violations_total"])
            touches.append(b["human_touches"])
        st.line_chart({"tau": taus, "policy_violations": violations, "human_touches": touches}, x="tau")
        st.caption(
            "x = tau, y = policy violations and human touches (2 seeds x 20 held-out scenarios per point). "
            "See the tau=0.9 dead-zone note below the failure modes if violations jump back up at the right edge."
        )
    else:
        st.info("No tau-swept runs found (expected run_ids like `gated-tau0.5-holdout`).")

    st.divider()
    st.subheader("Failure modes (hand-counted)")
    if FAILURE_MODES_PATH.exists():
        with open(FAILURE_MODES_PATH, "r", encoding="utf-8") as f:
            fm = json.load(f)
        st.caption(fm.get("note", ""))
        for finding in fm.get("findings", []):
            tag = "predicted" if finding.get("predicted") else "unpredicted"
            with st.expander(f"[{finding['id']}] {finding['mode']} — count: {finding['count']} ({tag})"):
                for ex in finding.get("examples", []):
                    st.write(f"- `{ex['trajectory_id']}`: {ex['note']}")
        tsf = fm.get("tau_sweep_finding")
        if tsf:
            st.warning(f"**{tsf['mode']}**: {tsf['detail']}\n\n{tsf.get('recommendation', '')}")
    else:
        st.info(f"No failure-mode file yet at {FAILURE_MODES_PATH}.")

    st.divider()
    st.subheader("Customer recommendation")
    st.caption("LLM-filled from the scoreboard and hand-counted failure data above — never a hard-coded number.")
    if st.button("Generate recommendation"):
        with st.spinner("Writing recommendation from the real scoreboard..."):
            try:
                st.markdown(generate_recommendation())
            except Exception as exc:  # missing scoreboard/run data, no cached LLM response, etc.
                st.error(f"Couldn't generate a recommendation: {exc}")


# ---------------------------------------------------------------------------


page = st.sidebar.radio("Page", ["Run", "Trajectory", "Review", "Report"])
if page == "Run":
    run_page()
elif page == "Trajectory":
    trajectory_page()
elif page == "Review":
    review_page()
else:
    report_page()
