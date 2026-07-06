from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.course import load_course
from engine.learner_model import next_topic

ROOT = Path(__file__).resolve().parents[1]


def test_cs250_module_loads_and_satisfies_contract():
    c = load_course(ROOT / "courses" / "CS250" / "course.yaml")
    assert c.id == "CS250" and c.credits == 4
    # backward-design contract holds (validator would have raised otherwise)
    assert len(c.all_outcomes()) >= 12
    # every outcome resolves to an assessment for that outcome
    assess = {a.id: a for a in c.assessments}
    for o in c.all_outcomes():
        assert assess[o.proof].outcome_id == o.id


def test_template_loads():
    assert load_course(ROOT / "courses" / "_TEMPLATE" / "course.yaml").id == "XXNNN"


def test_cs250_dag_drives_next_topic():
    c = load_course(ROOT / "courses" / "CS250" / "course.yaml")
    units = c.dag()
    first = next_topic(units, mastered=set())
    assert first == "ah.apply"                      # arrays-hashing is the entry
    # sliding-window depends on two-pointers -> not offered until tp.apply mastered
    got = next_topic(units, mastered={"ah.apply", "ah.analyze"})
    assert got == "tp.apply"


def test_orphan_outcome_is_rejected():
    bad = {
        "id": "BAD", "title": "x", "subject_domain": "d", "credits": 1, "north_star": "x",
        "assessments": [],
        "units": [{"id": "u", "title": "U", "order_index": 1, "semester": 1,
                   "outcomes": [{"id": "o", "statement": "s", "bloom_level": "apply", "proof": "missing"}]}],
    }
    from engine.course import Course
    with pytest.raises(ValidationError):
        Course.model_validate(bad)


def test_cycle_is_rejected():
    bad = {
        "id": "BAD", "title": "x", "subject_domain": "d", "credits": 1, "north_star": "x",
        "assessments": [
            {"id": "a1", "outcome_id": "o1", "type": "formative", "modality": "explain",
             "bloom_target": "apply", "proof_gate": "x"},
            {"id": "a2", "outcome_id": "o2", "type": "formative", "modality": "explain",
             "bloom_target": "apply", "proof_gate": "x"},
        ],
        "units": [{"id": "u", "title": "U", "order_index": 1, "semester": 1, "outcomes": [
            {"id": "o1", "statement": "s", "bloom_level": "apply", "proof": "a1", "depends_on": ["o2"]},
            {"id": "o2", "statement": "s", "bloom_level": "apply", "proof": "a2", "depends_on": ["o1"]},
        ]}],
    }
    from engine.course import Course
    with pytest.raises(ValidationError):
        Course.model_validate(bad)
