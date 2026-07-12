"""The `plan` command's adaptive difficulty (regression: it was keyed by unit id, not topic)."""

import json
from pathlib import Path

from engine import cli
from engine.gradebook import append_record, topic_of_outcome
from engine.learner_model import LearnerModel, difficulty_for, recompute
from tests.conftest import dt, rec

ROOT = Path(__file__).resolve().parents[1]
GEN101 = ROOT / "tests" / "fixtures" / "GEN101" / "course.yaml"


def test_difficulty_is_keyed_by_topic_not_unit_id():
    # a hard-tier pass on outcome f1.apply → topic 'f1' (NOT unit id 'basics')
    m = recompute(
        LearnerModel(),
        [rec("f1.apply", 0.78, course="GEN101", tier="hard")],
        tz="UTC",
        now=dt("2026-07-06T21:00:00"),
    )
    assert difficulty_for(m, "basics") == "easy"  # unit id misses → baseline (the bug)
    assert (
        difficulty_for(m, topic_of_outcome("f1.apply")) == "med"
    )  # topic key → elevated off baseline


def test_plan_cli_reports_elevated_difficulty(tmp_path, capsys):
    """End-to-end through the CLI: with hard-tier f1 history, `plan` must report a difficulty above
    the 'easy' baseline. Before the fix it keyed the learner model by unit id and always said 'easy'."""
    (tmp_path / "records").mkdir(parents=True)
    append_record(
        tmp_path / "records" / "grades.jsonl", rec("f1.apply", 0.78, course="GEN101", tier="hard")
    )
    code = cli.main(["plan", "--vault", str(tmp_path), "--course-file", str(GEN101), "--tz", "UTC"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["next_outcome"] == "f1.apply"
    assert out["difficulty"] == "med"
