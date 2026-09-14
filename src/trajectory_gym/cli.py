"""Command-line entry points wired to the Makefile (`make generate|run|demo`)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import uuid
from pathlib import Path

import requests

from .annotation.selector import Candidate, select_batch, select_random
from .annotation.store import labeled_keys, load_labels, save_label
from .config import REPO_ROOT, get_gate_config
from .data import classes, prose, split, validate
from .data.groundtruth import ANCHOR, evaluate_policy
from .env import episode
from .eval import judge as judge_module
from .eval import outcome as outcome_module
from .eval.metrics import RunRecord, compute_scoreboard
from .llm.client import complete
from .models.annotation import StepLabel
from .models.scenario import Scenario
from .models.trajectory import Trajectory
from .report.recommendation import generate_recommendation

SCENARIOS_PATH = REPO_ROOT / "data" / "scenarios.jsonl"
SPLIT_PATH = REPO_ROOT / "data" / "split.json"
RUNS_DIR = REPO_ROOT / "data" / "runs"
ANNOTATION_DIR = REPO_ROOT / "data" / "annotation"
REVIEW_QUEUE_PATH = ANNOTATION_DIR / "review_queue.json"


def _ticket_insert_sql(scenario_id: str, draw: classes.Draw, order_id_claimed: str | None, body: str):
    return (
        "INSERT INTO tickets (id, customer_id, order_id_claimed, body, created_at) VALUES (?, ?, ?, ?, ?)",
        [f"T-{scenario_id}", draw.customer_id, order_id_claimed, body, f"{ANCHOR.isoformat()}T00:00:00"],
    )


def generate_scenarios(verbose: bool = True) -> tuple[list[Scenario], list[classes.Draw]]:
    draws = classes.all_draws()
    scenarios: list[Scenario] = []

    for i, draw in enumerate(draws, start=1):
        gt = evaluate_policy(draw.facts)
        body, persona = prose.write_ticket(draw)
        scenario_id = f"{draw.scenario_class}-{draw.index:02d}"
        order_id_claimed = None if draw.scenario_class == "missing_or_wrong_id" else draw.order_id
        setup_sql = list(draw.setup_sql) + [_ticket_insert_sql(scenario_id, draw, order_id_claimed, body)]

        scenario = Scenario(
            id=scenario_id,
            scenario_class=draw.scenario_class,
            persona=persona,
            customer_id=draw.customer_id,
            order_id=draw.order_id,
            ticket_body=body,
            ground_truth=gt,
            setup_sql=setup_sql,
            force_stale_status=draw.force_stale_status,
        )
        scenarios.append(scenario)
        if verbose:
            print(f"[{i}/{len(draws)}] {scenario_id}: {gt.expected_terminal} — {body[:70]!r}")

    return scenarios, draws


def cmd_generate(args: argparse.Namespace) -> None:
    scenarios, draws = generate_scenarios()

    errors = validate.validate_all(scenarios, draws)
    if errors:
        print("\nVALIDATION FAILURES:", file=sys.stderr)
        for sid, errs in errors.items():
            for e in errs:
                print(f"  {sid}: {e}", file=sys.stderr)
        if not args.allow_invalid:
            print("\nRefusing to write scenarios.jsonl / split.json with validation failures.", file=sys.stderr)
            print("Pass --allow-invalid to write anyway (e.g. to hand-fix tickets afterward).", file=sys.stderr)
            sys.exit(1)

    SCENARIOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SCENARIOS_PATH, "w", encoding="utf-8", newline="\n") as f:
        for s in scenarios:
            f.write(s.model_dump_json() + "\n")
    print(f"\nwrote {len(scenarios)} scenarios to {SCENARIOS_PATH}")

    if SPLIT_PATH.exists():
        print(f"{SPLIT_PATH} already exists and is frozen — not overwriting. Delete it manually to regenerate.")
    else:
        split_map = split.make_split(scenarios)
        with open(SPLIT_PATH, "w", encoding="utf-8", newline="\n") as f:
            json.dump(split_map, f, indent=2)
            f.write("\n")
        print(f"wrote split ({len(split_map['dev'])} dev / {len(split_map['holdout'])} holdout) to {SPLIT_PATH}")

    print(
        "\nManual pass required next: read all 50 tickets in data/scenarios.jsonl and delete/"
        "regenerate any that leak the answer, are incoherent, or are boring (Section 6)."
    )


def load_scenarios() -> dict[str, Scenario]:
    scenarios = {}
    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                s = Scenario.model_validate_json(line)
                scenarios[s.id] = s
    return scenarios


def load_split() -> dict[str, list[str]]:
    with open(SPLIT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_trajectories(run_id: str) -> list[Trajectory]:
    path = RUNS_DIR / run_id / "trajectories.jsonl"
    with open(path, "r", encoding="utf-8") as f:
        return [Trajectory.model_validate_json(line) for line in f if line.strip()]


def load_outcomes(run_id: str) -> list[dict]:
    path = RUNS_DIR / run_id / "outcomes.jsonl"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_and_persist(
    scenario: Scenario, run_id: str, gate_config, agent_name: str, seed: int, run_dir: Path
) -> RunRecord:
    """The reusable core of `run`: execute one episode, score it, and append
    it to this run's trajectories/outcomes files. No printing — used by
    both the CLI (which adds its own console output) and the Streamlit Run
    page (which adds its own live UI updates)."""
    trajectory, conn = episode.run_episode(scenario, run_id, gate_config=gate_config, agent_name=agent_name, seed=seed)
    result = outcome_module.score_trajectory(scenario, conn, trajectory)
    conn.close()

    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "trajectories.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(trajectory.model_dump_json() + "\n")
    with open(run_dir / "outcomes.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"trajectory_id": trajectory.id, "scenario_id": scenario.id, "seed": seed, **result.model_dump()}) + "\n")

    return RunRecord(scenario=scenario, trajectory=trajectory, outcome=result)


def _run_one(
    scenario: Scenario, run_id: str, gate_config, agent_name: str, seed: int, run_dir: Path, verbose: bool
) -> RunRecord:
    record = run_and_persist(scenario, run_id, gate_config, agent_name, seed, run_dir)
    trajectory, result = record.trajectory, record.outcome

    if verbose:
        print(f"ticket: {scenario.ticket_body!r}")
        print(f"ground truth: {scenario.ground_truth.expected_terminal} amount={scenario.ground_truth.expected_amount_cents}")
        print()
        for step in trajectory.steps:
            gate_note = ""
            if step.gate_verdict is not None:
                gate_note = f"  [gate: blocked={step.gate_verdict.blocked}"
                if step.gate_verdict.judge:
                    gate_note += f" judge={step.gate_verdict.judge.label}@{step.gate_verdict.judge.confidence:.2f}"
                gate_note += "]"
            print(f"  step {step.index}: {step.reasoning!r}")
            print(f"    -> {step.tool_name}({step.arguments}) = {step.raw_result}{gate_note}")
        print()
        print(f"termination: {trajectory.termination_reason}")
        print(f"outcome: passed={result.passed} matched_terminal={result.matched_terminal} violations={result.violations}")
    else:
        flag = "PASS" if result.passed else ("VIOLATION" if result.violations else "fail")
        print(
            f"  [{scenario.scenario_class:26s}] {scenario.id:28s} seed={seed} "
            f"-> {flag:9s} term={trajectory.termination_reason} violations={result.violations}"
        )

    return record


def cmd_run(args: argparse.Namespace) -> None:
    scenarios = load_scenarios()

    if args.scenario_id:
        if args.scenario_id not in scenarios:
            print(f"unknown scenario id {args.scenario_id!r}.", file=sys.stderr)
            print("known ids:", ", ".join(sorted(scenarios)), file=sys.stderr)
            sys.exit(1)
        scenario_ids = [args.scenario_id]
    else:
        split_map = load_split()
        if args.split == "all":
            scenario_ids = split_map["dev"] + split_map["holdout"]
        else:
            scenario_ids = split_map[args.split]

    if args.limit:
        scenario_ids = scenario_ids[: args.limit]

    gate_config = get_gate_config()
    if args.gate_mode:
        gate_config = gate_config.model_copy(update={"mode": args.gate_mode})
    if args.tau is not None:
        gate_config = gate_config.model_copy(update={"tau": args.tau})

    run_id = args.run_id or f"run-{int(time.time())}"
    run_dir = RUNS_DIR / run_id
    verbose = len(scenario_ids) == 1 and args.seeds == 1

    print(
        f"run_id={run_id} agent={args.agent} gate_mode={gate_config.mode} tau={gate_config.tau} "
        f"n_scenarios={len(scenario_ids)} seeds={args.seeds}"
    )
    print()

    records: list[RunRecord] = []
    for scenario_id in scenario_ids:
        scenario = scenarios[scenario_id]
        for seed in range(args.seeds):
            records.append(_run_one(scenario, run_id, gate_config, args.agent, seed, run_dir, verbose))

    board = compute_scoreboard(records)
    with open(run_dir / "scoreboard.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(board, f, indent=2)
        f.write("\n")

    print()
    print("=== scoreboard ===")
    for k, v in board.items():
        print(f"  {k}: {v}")
    print(f"\nwrote {len(records)} trajectories + scoreboard to {run_dir}")


def _step_dict(step) -> dict:
    return {"reasoning": step.reasoning, "tool_name": step.tool_name, "arguments": step.arguments, "raw_result": step.raw_result}


def _build_candidate_pool(run_id: str) -> tuple[list[Candidate], int]:
    """Judges every step of every trajectory in a run (Section 9) and
    returns the full candidate pool — shared by `select` (which keeps only
    the top N) and `compare-selectors` (which needs the whole pool to
    contrast active vs. random selection). Real judge calls, a real,
    one-time cost per run — cheap at this scale (a few hundred short calls)."""
    scenarios = load_scenarios()
    trajectories = load_trajectories(run_id)
    outcomes = {(o["scenario_id"], o.get("seed", 0)): o for o in load_outcomes(run_id)}

    candidates: list[Candidate] = []
    n_judged = 0
    for t in trajectories:
        if not t.steps:
            continue
        scenario = scenarios[t.scenario_id]
        outcome = outcomes.get((t.scenario_id, t.seed))
        failed = outcome is not None and bool(not outcome["passed"] or outcome["violations"])

        scored: list[tuple[int, object, object]] = []  # (step_index, step, verdict)
        try:
            for i, step in enumerate(t.steps):
                steps_before = [_step_dict(s) for s in t.steps[:i]]
                verdict = None
                for attempt in range(2):
                    try:
                        verdict = judge_module.score_step(scenario, steps_before, _step_dict(step), version="v0")
                        break
                    except judge_module.JudgeParseError as e:
                        last_error = e
                if verdict is None:
                    print(f"  WARNING: judge failed twice on {t.id} step {i}, skipping this step: {last_error}")
                    continue
                scored.append((i, step, verdict))
                n_judged += 1
        except requests.exceptions.RequestException as e:
            # e.g. the judge model's own daily/rate quota ran out mid-batch. Stop judging
            # further trajectories but keep everything already scored — with ~5 steps per
            # trajectory, even a partial pass usually leaves plenty of candidates to select
            # the target N from, and losing all prior work to one exhausted quota would be
            # far worse than a slightly smaller candidate pool.
            print(f"\nSTOPPING: judge call failed fatally on {t.id}: {e}")
            print(f"Proceeding with the {n_judged} steps judged so far.\n")
            break

        print(f"judged {len(scored)}/{len(t.steps)} steps of {t.id} ({n_judged} total so far)")

        outcome_disagreement = failed and bool(scored) and all(v.label == "correct" for _, _, v in scored)
        for i, step, verdict in scored:
            candidates.append(Candidate(
                trajectory_id=t.id, scenario_id=t.scenario_id, step_index=i,
                tool_name=step.tool_name, judge_verdict=verdict, outcome_disagreement=outcome_disagreement,
            ))

    return candidates, n_judged


def cmd_select(args: argparse.Namespace) -> None:
    """Builds the ranked review queue (Section 9): judges every step of
    every trajectory in a run, computes each step's active-selection
    priority, and writes the top N to data/annotation/review_queue.json for
    the Review page to work through."""
    excluded = labeled_keys()
    candidates, n_judged = _build_candidate_pool(args.run_id)
    trajectories = load_trajectories(args.run_id)

    selections = select_batch(candidates, n=args.n, excluded_keys=excluded)
    queue = []
    for i, sel in enumerate(selections):
        queue.append({
            "run_id": args.run_id,
            "trajectory_id": sel.candidate.trajectory_id,
            "scenario_id": sel.candidate.scenario_id,
            "step_index": sel.candidate.step_index,
            "priority": sel.priority,
            "breakdown": sel.breakdown,
            "explanation": sel.explanation,
            "judge_verdict": sel.candidate.judge_verdict.model_dump(),
            "is_anchor": i < args.n_anchors,
        })

    ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)
    with open(REVIEW_QUEUE_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(queue, f, indent=2)
        f.write("\n")

    print(f"\njudged {n_judged} steps across {len(trajectories)} trajectories")
    print(f"selected {len(queue)} steps ({args.n_anchors} marked as anchor candidates)")
    print(f"wrote {REVIEW_QUEUE_PATH}")


def _selector_stats(picks: list) -> dict:
    """Summarizes one batch of picks (Selection or Candidate objects — both
    expose `.judge_verdict`/`.tool_name` either directly or via `.candidate`)
    against the criteria the priority formula targets, so active vs. random
    can be compared without needing a second round of human/assistant
    labels just to run this comparison."""
    from collections import Counter

    n = len(picks)
    candidates = [p.candidate if hasattr(p, "candidate") else p for p in picks]
    label_counts = Counter(c.judge_verdict.label for c in candidates)
    return {
        "n": n,
        "label_counts": dict(label_counts),
        "non_correct_rate": sum(v for k, v in label_counts.items() if k != "correct") / n if n else 0.0,
        "policy_violating_rate": label_counts.get("policy_violating", 0) / n if n else 0.0,
        "avg_judge_uncertainty": sum(1.0 - c.judge_verdict.confidence for c in candidates) / n if n else 0.0,
        "outcome_disagreement_rate": sum(c.outcome_disagreement for c in candidates) / n if n else 0.0,
        "irreversible_rate": sum(c.tool_name == "issue_refund" for c in candidates) / n if n else 0.0,
        "distinct_tools": len({c.tool_name for c in candidates}),
    }


def cmd_compare_selectors(args: argparse.Namespace) -> None:
    """Random-selector comparison (Section 9's accept criteria): builds the
    full judged candidate pool, then contrasts what the active selector
    (select_batch) picks against an equal-size uniform-random sample
    (select_random) on the same criteria the priority formula optimizes for
    — judge uncertainty, outcome disagreement, irreversibility, and how
    often the judge itself already flagged something wrong. Both samples
    exclude already-labeled steps, so this never re-picks the 58 items
    already graded for calibration.

    This is NOT the same as a kappa comparison (that would need a fresh
    round of human/assistant labels on the random sample too) — it answers
    "does active selection surface more informative steps than random for
    the same budget," using judge v0 verdicts that are already computed as
    part of building the pool."""
    excluded = labeled_keys()
    candidates, n_judged = _build_candidate_pool(args.run_id)
    print(f"\njudged {n_judged} steps for the comparison pool\n")

    active = select_batch(candidates, n=args.n, excluded_keys=excluded)
    random_pick = select_random(candidates, n=args.n, seed=args.seed, excluded_keys=excluded)

    active_stats = _selector_stats(active)
    random_stats = _selector_stats(random_pick)

    print(f"{'metric':<26}{'active':>12}{'random':>12}")
    for key in ("n", "non_correct_rate", "policy_violating_rate", "avg_judge_uncertainty",
                "outcome_disagreement_rate", "irreversible_rate", "distinct_tools"):
        a, r = active_stats[key], random_stats[key]
        fmt = "{:>12}" if key in ("n", "distinct_tools") else "{:>12.3f}"
        print(f"{key:<26}{fmt.format(a)}{fmt.format(r)}")
    print(f"\nactive label_counts: {active_stats['label_counts']}")
    print(f"random label_counts: {random_stats['label_counts']}")

    out_path = ANNOTATION_DIR / "selector_comparison.json"
    ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"run_id": args.run_id, "n": args.n, "seed": args.seed,
                    "active": active_stats, "random": random_stats}, f, indent=2)
        f.write("\n")
    print(f"\nwrote {out_path}")


def cmd_calibrate(args: argparse.Namespace) -> None:
    """Judge calibration (Section 10): scores every agreement-set label
    with judge v0 and v1 (v1 gets the anchor labels as few-shot examples —
    the anchors themselves are never scored here, per NON-NEGOTIABLE 2),
    and reports kappa + CI + policy_violating recall for each."""
    from .eval.calibration import (
        agreement_set,
        anchor_set,
        bootstrap_kappa_ci,
        cohens_kappa,
        policy_violating_recall,
    )

    if not REVIEW_QUEUE_PATH.exists():
        print(f"no review queue at {REVIEW_QUEUE_PATH} — run `select` first.", file=sys.stderr)
        sys.exit(1)
    with open(REVIEW_QUEUE_PATH, "r", encoding="utf-8") as f:
        queue = json.load(f)
    queue_lookup = {(item["trajectory_id"], item["step_index"]): item for item in queue}

    all_labels = load_labels()
    anchors_labeled = anchor_set(all_labels)
    agreement_labeled = agreement_set(all_labels)

    if len(anchors_labeled) < 1:
        print("no anchor labels graded yet — grade the queue in the Review page first.", file=sys.stderr)
        sys.exit(1)

    scenarios = load_scenarios()
    trajectory_cache: dict[str, Trajectory] = {}

    def _context(label: StepLabel):
        item = queue_lookup.get((label.trajectory_id, label.step_index))
        if item is None:
            return None
        run_id = item["run_id"]
        if run_id not in trajectory_cache:
            for t in load_trajectories(run_id):
                trajectory_cache[t.id] = t
        trajectory = trajectory_cache.get(label.trajectory_id)
        if trajectory is None:
            return None
        scenario = scenarios[item["scenario_id"]]
        steps_before = [_step_dict(s) for s in trajectory.steps[: label.step_index]]
        step = _step_dict(trajectory.steps[label.step_index])
        return scenario, steps_before, step

    anchors = []
    for label in anchors_labeled:
        ctx = _context(label)
        if ctx is None:
            print(f"  skipping anchor {label.trajectory_id}/{label.step_index}: not found in review queue", file=sys.stderr)
            continue
        scenario, steps_before, step = ctx
        # 8 anchors x full trajectory history blows Groq free-tier's 8000
        # TPM per-request cap once stacked into one v1 prompt; anchors only
        # need to demonstrate the label, not replay the whole trajectory.
        anchors.append(judge_module.build_anchor(scenario, steps_before[-1:], step, label))
    print(f"built {len(anchors)} anchor few-shot examples")

    human_labels, v0_labels, v1_labels = [], [], []
    for label in agreement_labeled:
        ctx = _context(label)
        if ctx is None:
            print(f"  skipping {label.trajectory_id}/{label.step_index}: not found in review queue", file=sys.stderr)
            continue
        scenario, steps_before, step = ctx
        try:
            v0 = judge_module.score_step(scenario, steps_before, step, version="v0")
            v1 = judge_module.score_step(scenario, steps_before, step, version="v1", anchors=anchors)
        except (judge_module.JudgeParseError, requests.exceptions.RequestException) as e:
            print(f"  skipping {label.trajectory_id}/{label.step_index}: {e}", file=sys.stderr)
            continue
        human_labels.append(label.label)
        v0_labels.append(v0.label)
        v1_labels.append(v1.label)

    n = len(human_labels)
    print(f"\nscored {n} agreement-set steps (anchors excluded) with judge v0 and v1\n")

    for version, judge_labels in (("v0", v0_labels), ("v1", v1_labels)):
        kappa = cohens_kappa(human_labels, judge_labels)
        lo, hi = bootstrap_kappa_ci(human_labels, judge_labels)
        recall = policy_violating_recall(human_labels, judge_labels)
        print(f"judge {version}: kappa={kappa:.3f} (95% CI [{lo:.3f}, {hi:.3f}], n={n})  "
              f"policy_violating recall={recall if recall is None else f'{recall:.3f}'}")


def cmd_grade(args: argparse.Namespace) -> None:
    label = StepLabel(
        trajectory_id=args.trajectory_id,
        step_index=args.step_index,
        label=args.label,
        policy_rule=args.policy_rule,
        reason=args.reason,
        source="human",
        is_anchor=args.anchor,
    )
    save_label(label)
    print(f"saved label: {label.trajectory_id} step {label.step_index} -> {label.label} ({label.reason!r})")


DEMO_RUN_IDS = {"ungated": "demo-ungated", "gated": "demo-gated", "escalate": "demo-escalate"}


def _run_demo_config(scenario_ids: list[str], scenarios: dict, gate_config, agent_name: str, run_id: str):
    """Actually executes the agent/gate/judge loop (backed by the frozen
    cache unless --live busted it first) — this is real code running, not
    a printout of pre-written numbers."""
    run_dir = RUNS_DIR / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    records = [
        run_and_persist(scenarios[sid], run_id, gate_config, agent_name, seed=0, run_dir=run_dir)
        for sid in scenario_ids
    ]
    board = compute_scoreboard(records)
    with open(run_dir / "scoreboard.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(board, f, indent=2)
        f.write("\n")
    return records, board


def _find_gate_block_example(records: list[RunRecord]) -> str | None:
    for r in records:
        for step in r.trajectory.steps:
            if step.gate_verdict and step.gate_verdict.blocked:
                j = step.gate_verdict.judge
                return (
                    f"{r.scenario.id} (seed 0): agent proposed {step.tool_name}({step.arguments}) "
                    f"-> gate BLOCKED it. Judge: {j.label} @ {j.confidence:.2f} confidence -- {j.reason!r}"
                )
    return None


def _live_proof_of_life() -> None:
    """--live only: one genuine network round-trip with a cache-busting
    nonce, so the run can't possibly be a cache replay. The rest of the
    demo still uses the cache (that's the point of freezing it) -- this
    just proves the pipeline can talk to a real provider when asked."""
    nonce = uuid.uuid4().hex
    print(f"[--live] Sending one cache-busting call to the configured agent provider (nonce {nonce[:8]}...)")
    t0 = time.time()
    try:
        response = complete(
            [{"role": "user", "content": f"Reply with exactly: LIVE-OK-{nonce}"}],
            role="agent",
        )
        elapsed = time.time() - t0
        print(f"[--live] Got a real response in {elapsed:.2f}s: {response.text.strip()!r}\n")
    except Exception as e:  # noqa: BLE001 -- this is a best-effort proof-of-life ping, not core demo logic
        print(f"[--live] Live call failed ({e}) -- check your API key / .env. Continuing with the cached demo.\n")


def cmd_demo(args: argparse.Namespace) -> None:
    """The three-minute demo (Section 14). Actually executes the agent
    loop, gate, and judge -- backed by the frozen LLM cache
    (data/llm_cache.sqlite3, committed) so it needs no API key and no
    network by default. Pass --live for one genuine network round-trip
    that proves this isn't just replaying canned output."""
    start = time.time()
    if args.live:
        _live_proof_of_life()

    scenarios = load_scenarios()
    holdout_ids = load_split()["holdout"]
    base_gate_config = get_gate_config()

    print("=" * 72)
    print("TRAJECTORY GYM")
    print("Can this agent safely automate our customer-support refund workflow,")
    print("and where does it still need a human?")
    print("=" * 72)
    print()

    print(f"[0:20] Running all {len(holdout_ids)} held-out scenarios, ungated...")
    ungated_records, ungated_board = _run_demo_config(
        holdout_ids, scenarios, base_gate_config.model_copy(update={"mode": "ungated"}), "llm_agent",
        DEMO_RUN_IDS["ungated"],
    )
    for r in ungated_records:
        flag = "PASS" if r.outcome.passed else ("VIOLATION" if r.outcome.violations else "fail")
        print(f"  [{r.scenario.scenario_class:26s}] {r.scenario.id:28s} -> {flag}")
    print(
        f"\n  task_success_rate={ungated_board['task_success_rate']:.2f}   "
        f"policy_violations={ungated_board['policy_violations_total']} "
        f"{ungated_board['policy_violations_by_rule']}\n"
    )

    print("[0:50] Judge calibration. Real numbers from a completed grading pass")
    print("       (`cli.py calibrate` -- live grading happens interactively in the Review page):")
    print("       judge v0: kappa=0.211 (n=50)   judge v1: kappa=0.214 (n=50)")
    print("       policy_violating recall: 0.400 for both versions.")
    print("       (v1 barely moved here -- see docs/limitations.md: the judge model was swapped")
    print("       off-quota mid-project, and these are AI-assistant-graded labels standing in")
    print("       for human ones, not a real calibration claim.)\n")

    print(f"[1:45] Re-running the same {len(holdout_ids)} scenarios with the gate on (tau=0.5)...")
    gated_records, gated_board = _run_demo_config(
        holdout_ids, scenarios, base_gate_config.model_copy(update={"mode": "gated", "tau": 0.5}), "llm_agent",
        DEMO_RUN_IDS["gated"],
    )
    print(
        f"  policy_violations: {ungated_board['policy_violations_total']} -> "
        f"{gated_board['policy_violations_total']}"
    )
    print(f"  human_touches:     {ungated_board['human_touches']} -> {gated_board['human_touches']}\n")

    _, escalate_board = _run_demo_config(
        holdout_ids, scenarios, base_gate_config.model_copy(update={"mode": "ungated"}), "always_escalate",
        DEMO_RUN_IDS["escalate"],
    )
    print(
        f"  always_escalate baseline: violations={escalate_board['policy_violations_total']}  "
        f"autonomy={escalate_board['autonomy_rate']:.0%}  "
        f"human_touches={escalate_board['human_touches']}/{escalate_board['n_scenarios']}"
    )
    print("  -> zero violations by construction, but zero autonomy and every ticket touches a human.\n")

    print("[2:15] One real failure, opened up:")
    example = _find_gate_block_example(gated_records)
    print(f"  {example}\n" if example else "  (no gate block in this seed's sample -- see docs/limitations.md.)\n")

    print("[2:40] Customer recommendation (LLM-filled from the real scoreboard, never hard-coded):\n")
    print(generate_recommendation())

    elapsed = time.time() - start
    print(f"\n{'=' * 72}")
    print(f"Demo finished in {elapsed:.1f}s (budget: 3:15 / 195s).")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="trajectory_gym")
    sub = parser.add_subparsers(dest="command", required=True)

    p_generate = sub.add_parser("generate", help="Generate the 50 scenarios (Phase 2).")
    p_generate.add_argument("--allow-invalid", action="store_true")
    p_generate.set_defaults(func=cmd_generate)

    p_run = sub.add_parser("run", help="Run the agent on one scenario or a whole split.")
    target = p_run.add_mutually_exclusive_group(required=True)
    target.add_argument("--scenario-id", default=None)
    target.add_argument("--split", choices=["dev", "holdout", "all"], default=None)
    p_run.add_argument("--agent", choices=["llm_agent", "always_escalate"], default="llm_agent")
    p_run.add_argument("--gate-mode", choices=["ungated", "gated", "human_first", "outcome_oracle"], default=None)
    p_run.add_argument("--tau", type=float, default=None)
    p_run.add_argument("--seeds", type=int, default=1)
    p_run.add_argument("--limit", type=int, default=None, help="cap the number of scenarios (cost control)")
    p_run.add_argument("--run-id", default=None)
    p_run.set_defaults(func=cmd_run)

    p_select = sub.add_parser("select", help="Build the ranked review queue for the Review page (Phase 5).")
    p_select.add_argument("--run-id", required=True)
    p_select.add_argument("--n", type=int, default=70)
    p_select.add_argument("--n-anchors", type=int, default=8)
    p_select.set_defaults(func=cmd_select)

    p_calibrate = sub.add_parser("calibrate", help="Compute judge v0/v1 kappa + CI on the agreement set (Phase 5).")
    p_calibrate.set_defaults(func=cmd_calibrate)

    p_compare = sub.add_parser("compare-selectors", help="Compare active vs. random step selection on the same candidate pool (Phase 5).")
    p_compare.add_argument("--run-id", required=True)
    p_compare.add_argument("--n", type=int, default=58)
    p_compare.add_argument("--seed", type=int, default=42)
    p_compare.set_defaults(func=cmd_compare_selectors)

    p_grade = sub.add_parser("grade", help="Hand-label one trajectory step (Phase 3's 'rough UI').")
    p_grade.add_argument("--trajectory-id", required=True)
    p_grade.add_argument("--step-index", type=int, required=True)
    p_grade.add_argument(
        "--label",
        required=True,
        choices=["correct", "unnecessary", "wrong_harmless", "policy_violating", "hallucinated_fact", "premature_terminal"],
    )
    p_grade.add_argument("--reason", required=True)
    p_grade.add_argument("--policy-rule", default=None)
    p_grade.add_argument("--anchor", action="store_true")
    p_grade.set_defaults(func=cmd_grade)

    p_demo = sub.add_parser("demo", help="Run the full three-minute demo (Phase 7).")
    p_demo.add_argument("--live", action="store_true", help="Add one genuine network round-trip proving this is real.")
    p_demo.set_defaults(func=cmd_demo)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
