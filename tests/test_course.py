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


def test_resources_schema_optional_and_typed():
    from engine.course import Course, Resource
    # existing courses validate WITHOUT resources (additive, non-breaking)
    c = load_course(ROOT / "courses" / "CS250" / "course.yaml")
    assert isinstance(c.resources, list)
    # a fully-specified researched course carries typed resources on course + unit
    r = Resource(type="textbook", title="CLRS", author="Cormen", locator="ch. 6",
                 why="canonical", tier="core", cost="paid")
    assert r.cost == "paid" and r.type == "textbook"
    m = Course.model_validate({
        "id": "RX", "title": "x", "subject_domain": "d", "credits": 1, "north_star": "n",
        "description": "researched desc", "primary_text": r.model_dump(),
        "assessments": [{"id": "a1", "outcome_id": "o1", "type": "summative", "modality": "project",
                         "bloom_target": "apply", "proof_gate": "g"}],
        "units": [{"id": "u", "title": "U", "order_index": 1, "semester": 1, "est_weeks": 2,
                   "summary": "builds x", "resources": [r.model_dump()],
                   "outcomes": [{"id": "o1", "statement": "s", "bloom_level": "apply", "proof": "a1"}]}],
    })
    assert m.primary_text.title == "CLRS" and m.units[0].est_weeks == 2
    assert m.units[0].resources[0].locator == "ch. 6"


def test_invalid_resource_type_rejected():
    from engine.course import Resource
    with pytest.raises(ValidationError):
        Resource(type="tweet", title="x")


def test_professor_profile_and_mastery_model_load():
    from engine.course import Course, MasteryModel, ProfessorProfile, Resource
    pp = ProfessorProfile(persona="rigorous systems mentor", teaching_stance="build-then-generalize",
                          common_misconceptions=["cache = free"], assessment_philosophy="ship + defend")
    mm = MasteryModel(excellence_bar="designs planet-scale systems",
                      expert_practices=["writes design docs first"], frontier="serverless + edge",
                      staying_current=[Resource(type="reference", title="High Scalability")],
                      signature_work="a public design portfolio")
    c = Course.model_validate({
        "id": "RX", "title": "x", "subject_domain": "d", "credits": 1, "north_star": "n",
        "description": "d", "professor_profile": pp.model_dump(), "mastery_model": mm.model_dump(),
        "assessments": [{"id": "a1", "outcome_id": "o1", "type": "summative", "modality": "project",
                         "bloom_target": "apply", "proof_gate": "g"}],
        "units": [{"id": "u", "title": "U", "order_index": 1, "semester": 1,
                   "outcomes": [{"id": "o1", "statement": "s", "bloom_level": "apply", "proof": "a1"}]}],
    })
    assert c.professor_profile.persona.startswith("rigorous")
    assert c.mastery_model.excellence_bar and c.mastery_model.staying_current[0].title == "High Scalability"


@pytest.mark.parametrize("path", sorted((ROOT / "courses").glob("*/course.yaml")),
                         ids=lambda p: p.parent.name)
def test_every_course_module_satisfies_contract(path):
    c = load_course(path)                     # raises if the backward-design contract is violated
    assert c.id and c.credits >= 1
    assert c.all_outcomes(), "a course must have outcomes"


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
