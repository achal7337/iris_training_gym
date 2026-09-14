from trajectory_gym.annotation.store import labeled_keys, load_labels, save_label
from trajectory_gym.models.annotation import StepLabel


def _label(trajectory_id="t1", step_index=0, label="correct", reason="x", **kw) -> StepLabel:
    return StepLabel(trajectory_id=trajectory_id, step_index=step_index, label=label, reason=reason, **kw)


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "labels.jsonl"
    save_label(_label(), path)
    save_label(_label(trajectory_id="t2", step_index=1), path)
    labels = load_labels(path)
    assert len(labels) == 2


def test_regrading_a_step_keeps_only_the_latest(tmp_path):
    path = tmp_path / "labels.jsonl"
    save_label(_label(label="correct", reason="first pass"), path)
    save_label(_label(label="policy_violating", reason="changed my mind"), path)

    labels = load_labels(path)
    assert len(labels) == 1
    assert labels[0].label == "policy_violating"
    assert labels[0].reason == "changed my mind"

    raw = load_labels(path, dedupe=False)
    assert len(raw) == 2  # audit trail keeps both


def test_labeled_keys(tmp_path):
    path = tmp_path / "labels.jsonl"
    save_label(_label(trajectory_id="t1", step_index=0), path)
    save_label(_label(trajectory_id="t1", step_index=3), path)
    assert labeled_keys(path) == {("t1", 0), ("t1", 3)}


def test_labeled_keys_empty_when_no_file(tmp_path):
    assert labeled_keys(tmp_path / "does_not_exist.jsonl") == set()
