"""Offline tests for the recommendation generator's data assembly (Section
11) — the LLM call itself (generate_recommendation) is exercised live via
`cli.py demo` / `--live`, not here."""
import json

from trajectory_gym.report import recommendation as rec


def test_human_load_per_1000_scales_correctly():
    board = {"n_scenarios": 40, "human_touches": 3, "human_minutes_estimated": 9}
    result = rec._human_load_per_1000(board)
    assert result["touches_per_1000"] == 75.0
    assert result["minutes_per_1000"] == 225.0
    assert result["hours_per_1000"] == 3.75


def _board(**kw) -> dict:
    base = {
        "n_scenarios": 40, "human_touches": 3, "human_minutes_estimated": 9,
        "policy_violations_total": 0, "task_success_rate": 0.2,
    }
    base.update(kw)
    return base


def test_build_context_assembles_real_numbers_never_invents_any(tmp_path, monkeypatch):
    runs_dir = tmp_path / "runs"
    annotation_dir = tmp_path / "annotation"
    policy_path = tmp_path / "policy.md"
    annotation_dir.mkdir()
    policy_path.write_text("policy text", encoding="utf-8")

    boards = {
        "ungated": _board(policy_violations_total=5),
        "gated-tau0.5-holdout": _board(),
        "oracle": _board(),
        "always-escalate": _board(human_touches=20),
        "gated-tau0.3-holdout": _board(),
        "gated-tau0.7-holdout": _board(),
        "gated-tau0.9-holdout": _board(policy_violations_total=6),
    }
    for run_id, board in boards.items():
        d = runs_dir / run_id
        d.mkdir(parents=True)
        (d / "scoreboard.json").write_text(json.dumps(board), encoding="utf-8")

    (annotation_dir / "failure_modes.json").write_text(
        json.dumps({"findings": [{"id": "F5"}], "tau_sweep_finding": {"mode": "x"}}), encoding="utf-8"
    )

    monkeypatch.setattr(rec, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(rec, "ANNOTATION_DIR", annotation_dir)
    monkeypatch.setattr(rec, "POLICY_PATH", policy_path)

    context = rec.build_context(
        ungated_run_id="ungated", gated_run_id="gated-tau0.5-holdout",
        oracle_run_id="oracle", always_escalate_run_id="always-escalate",
    )

    assert context["ungated"]["policy_violations_total"] == 5
    assert context["always_escalate"]["human_touches"] == 20
    assert [p["tau"] for p in context["tau_frontier"]] == [0.3, 0.5, 0.7, 0.9]
    assert context["tau_frontier"][3]["policy_violations_total"] == 6  # the 0.9 dead zone
    assert context["policy_document_verbatim"] == "policy text"
    assert context["hand_counted_failure_modes"] == [{"id": "F5"}]
    assert "ambiguity_rule_4_1" in context["known_deliberate_policy_defects"]
    assert "inconsistency_1_1_3_2_4_1" in context["known_deliberate_policy_defects"]
    assert "subscription_ambiguity" in context["scenario_class_notes"]
    assert len(context["scenario_class_notes"]) == 10


def test_build_context_missing_runs_are_none_not_crashes(tmp_path, monkeypatch):
    runs_dir = tmp_path / "runs"
    annotation_dir = tmp_path / "annotation"
    policy_path = tmp_path / "policy.md"
    runs_dir.mkdir()
    annotation_dir.mkdir()
    policy_path.write_text("policy text", encoding="utf-8")

    monkeypatch.setattr(rec, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(rec, "ANNOTATION_DIR", annotation_dir)
    monkeypatch.setattr(rec, "POLICY_PATH", policy_path)

    context = rec.build_context(
        ungated_run_id="missing", gated_run_id="also-missing",
        oracle_run_id="missing2", always_escalate_run_id="missing3",
    )
    assert context["ungated"] is None
    assert context["human_load_per_1000_tickets_gated"] is None
    assert context["tau_frontier"] == []
