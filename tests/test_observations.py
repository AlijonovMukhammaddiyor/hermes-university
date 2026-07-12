"""RFC-013 — continuous learner-model observations: observe/forget/reset/decay, CLI, surface, caps."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from engine import cli, docs
from engine import learner_model as LM
from engine.learner_model import LearnerModel
from engine.render import check_skill_caps
from engine.state import fresh_state

CDIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _now(day="2026-07-12"):
    return datetime.fromisoformat(f"{day}T12:00:00+00:00")


# ---- model API ----
def test_single_valued_observe_overwrites_keeping_first_seen():
    m = LearnerModel()
    LM.observe(m, "format", "lectures", now=_now("2026-07-01"))
    LM.observe(m, "format", "worked examples", now=_now("2026-07-12"))
    o = m.preferences["format"]
    assert set(m.preferences) == {"format"}
    assert (
        o.value == "worked examples"
        and o.first_seen == "2026-07-01"
        and o.last_seen == "2026-07-12"
    )


def test_list_observe_reinforces_matching_value_case_insensitively():
    m = LearnerModel()
    LM.observe(m, "constraint", "no mornings", now=_now("2026-07-01"), confidence=0.5)
    LM.observe(m, "constraint", "No Mornings", now=_now("2026-07-12"), confidence=0.5)
    assert len(m.constraints) == 1
    assert m.constraints[0].confidence > 0.5 and m.constraints[0].last_seen == "2026-07-12"


def test_observe_rejects_unknown_aspect():
    with pytest.raises(ValueError):
        LM.observe(LearnerModel(), "mood", "happy", now=_now())


def test_forget_by_value_and_whole_aspect():
    m = LearnerModel()
    LM.observe(m, "constraint", "no mornings", now=_now())
    LM.observe(m, "constraint", "max 1h", now=_now())
    assert LM.forget(m, "constraint", "no mornings") == 1 and len(m.constraints) == 1
    LM.observe(m, "format", "video", now=_now())
    assert LM.forget(m, "format") == 1 and "format" not in m.preferences
    assert LM.forget(m, "interest") == 0


def test_consolidate_decays_and_drops_stale():
    m = LearnerModel()
    LM.observe(m, "format", "video", now=_now("2026-06-01"), confidence=0.6)  # ~41 days old
    LM.observe(m, "motivation", "shipping", now=_now("2026-07-12"), confidence=0.6)  # fresh
    dropped = LM.consolidate(m, _now("2026-07-12"))
    assert "motivation" in m.preferences and "format" not in m.preferences and dropped == 1


def test_reset_clears_learned_but_keeps_grade_stats():
    m = LearnerModel()
    LM.observe(m, "format", "video", now=_now())
    LM.observe(m, "constraint", "no mornings", now=_now())
    m.routine.best_hours = ["20:00-22:00"]
    LM.reset(m)
    assert not m.preferences and not m.constraints and not m.interests
    assert m.routine.best_hours == ["20:00-22:00"]


def test_load_save_roundtrip(tmp_path):
    p = tmp_path / "records" / "learner_model.json"
    m = LearnerModel()
    LM.observe(m, "format", "video", now=_now())
    LM.save(m, p)
    assert LM.load(p).preferences["format"].value == "video"
    assert LM.load(tmp_path / "missing.json").preferences == {}


# ---- CLI ----
def test_cli_observe_forget_reset(tmp_path, capsys):
    v = str(tmp_path)
    assert (
        cli.main(
            [
                "learner",
                "observe",
                "--vault",
                v,
                "--aspect",
                "format",
                "--value",
                "worked examples",
                "--evidence",
                "said so",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["observed"]["aspect"] == "format"
    assert (
        LM.load(tmp_path / "records" / "learner_model.json").preferences["format"].value
        == "worked examples"
    )
    assert cli.main(["learner", "forget", "--vault", v, "--aspect", "format"]) == 0
    assert json.loads(capsys.readouterr().out)["forgot"] == 1
    cli.main(["learner", "observe", "--vault", v, "--aspect", "interest", "--value", "rl"])
    capsys.readouterr()
    assert cli.main(["learner", "reset", "--vault", v]) == 0
    assert LM.all_observations(LM.load(tmp_path / "records" / "learner_model.json")) == []


def test_cli_observe_rejects_bad_aspect(tmp_path, capsys):
    code = cli.main(
        ["learner", "observe", "--vault", str(tmp_path), "--aspect", "mood", "--value", "x"]
    )
    assert code == 2 and json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_consolidate_runs(tmp_path, capsys):
    v = str(tmp_path)
    cli.main(["learner", "observe", "--vault", v, "--aspect", "format", "--value", "v"])
    capsys.readouterr()
    assert cli.main(["learner", "consolidate", "--vault", v]) == 0
    assert "dropped" in json.loads(capsys.readouterr().out)


# ---- visible surface ----
def test_render_learner_model_shows_beliefs_and_facts():
    m = LearnerModel()
    LM.observe(m, "format", "worked examples", now=_now(), confidence=0.7, source="chat")
    m.routine.best_hours = ["20:00-22:00"]
    md = docs.render_learner_model(m)
    assert "What I've learned about you" in md
    assert "worked examples" in md and "chat" in md and "70%" in md
    assert "Best hours" in md and "20:00-22:00" in md


def test_render_learner_model_empty():
    assert "Nothing yet" in docs.render_learner_model(LearnerModel())


def test_home_and_snapshot_surface_learned_count(tmp_path):
    (tmp_path / "Registrar").mkdir(parents=True)
    (tmp_path / "records").mkdir()
    fresh_state(name="Ada", timezone="UTC", started_on="2026-07-06").save(
        tmp_path / "Registrar" / "state.json"
    )
    (tmp_path / "records" / "grades.jsonl").write_text("")
    m = LearnerModel()
    LM.observe(m, "format", "video", now=_now())
    LM.save(m, tmp_path / "records" / "learner_model.json")
    snap = docs.status_snapshot(tmp_path, CDIR)
    assert snap["learned_count"] == 1
    home = docs.render_home(snap)
    assert "learned **1** things" in home and "[[LearnerModel]]" in home


# ---- renderer cap-guard ----
def test_check_skill_caps_ok_warn_and_reject(tmp_path):
    d = tmp_path / "prof"
    d.mkdir()
    p = d / "SKILL.md"
    p.write_text("---\nname: prof\ndescription: short\n---\nbody")
    assert check_skill_caps(p) == []
    p.write_text("---\nname: prof\ndescription: " + "x" * 80 + "\n---\nbody")
    assert check_skill_caps(p)  # >60 shown → a soft warning
    p.write_text("---\nname: prof\ndescription: ok\n---\n" + "y" * 100_001)
    with pytest.raises(ValueError):
        check_skill_caps(p)
