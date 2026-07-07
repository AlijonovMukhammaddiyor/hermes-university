from pathlib import Path

from engine import docs, registrar as R
from engine.course import load_course
from engine.state import fresh_state
from tests.conftest import rec

ROOT = Path(__file__).resolve().parents[1]
CDIR = ROOT / "tests" / "fixtures"      # generic courses; the shipped catalog is empty (RFC-005)


def test_render_catalog_lists_all_courses():
    mods = [load_course(p) for p in sorted(CDIR.glob("*/course.yaml"))]
    cat = docs.render_catalog(mods)
    for code in ("GEN101", "GEN102"):
        assert code in cat
    assert "enroll GEN101" in cat and "credits" in cat


def test_render_syllabus_has_units_and_grading():
    syl = docs.render_syllabus(load_course(CDIR / "GEN101" / "course.yaml"))
    assert "Basics" in syl and "Grading policy" in syl and "proof:" in syl
    assert "Assessment plan" in syl
    assert "What the best in this field can do" in syl and "How this course is taught" in syl
    # RFC-006: Ivy-grade week-by-week plan with readings + deliverables
    assert "Week-by-week plan" in syl and "| Week | Focus | Readings | Deliverable |" in syl
    assert "problem set 1" in syl and "timed mock" in syl


def test_syllabus_and_resources_render_researched_materials():
    from engine.course import Course, Resource
    r = Resource(type="textbook", title="CLRS", locator="ch. 6", why="canonical", cost="paid")
    c = Course.model_validate({
        "id": "RX", "title": "Algo", "subject_domain": "cs", "credits": 3, "north_star": "n",
        "description": "researched course", "primary_text": r.model_dump(),
        "assessments": [{"id": "a1", "outcome_id": "o1", "type": "summative", "modality": "project",
                         "bloom_target": "apply", "proof_gate": "ship it"}],
        "units": [{"id": "u1", "title": "Heaps", "order_index": 1, "semester": 1, "est_weeks": 2,
                   "summary": "priority queues", "resources": [r.model_dump()],
                   "outcomes": [{"id": "o1", "statement": "s", "bloom_level": "apply", "proof": "a1"}]}],
    })
    syl = docs.render_syllabus(c)
    assert "Primary text" in syl and "CLRS" in syl and "ch. 6" in syl and "paid" in syl
    assert "Weeks 1–2" in syl and "priority queues" in syl and "readings" in syl
    res = docs.render_resources(c)
    assert "Resources — RX" in res and "By unit" in res and "Heaps" in res and "CLRS" in res


def test_render_all_writes_resources(tmp_path):
    (tmp_path / "Registrar").mkdir(parents=True)
    fresh_state(name="M", timezone="UTC", started_on="2026-07-06").save(
        tmp_path / "Registrar" / "state.json")
    written = docs.render_all(tmp_path, CDIR)
    assert "Courses/GEN101/Resources.md" in written
    assert (tmp_path / "Courses" / "GEN101" / "Resources.md").exists()


def test_course_validate_cli(capsys):
    import json as _json

    from engine.cli import main
    rc = main(["course", "validate", "--file", str(CDIR / "GEN101" / "course.yaml")])
    out = _json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"] is True and out["id"] == "GEN101" and out["outcomes"] >= 3
    assert "authored" in out


def test_authored_gate_requires_full_depth(capsys, tmp_path):
    import json as _json

    import yaml

    from engine.cli import main
    # a minimal course (no resources/profile/mastery/dossier) -> needs authoring
    main(["course", "validate", "--file", str(CDIR / "GEN102" / "course.yaml")])
    out = _json.loads(capsys.readouterr().out)
    assert out["authored"] is False and "unit-resources" in out["missing_for_authored"]

    # resources present but no professor_profile/mastery_model/dossier -> not authored (RFC-004 bar)
    base = load_course(CDIR / "GEN101" / "course.yaml").model_dump()
    base.pop("professor_profile", None)
    base.pop("mastery_model", None)
    cdir = tmp_path / "GEN101"; cdir.mkdir()
    (cdir / "course.yaml").write_text(yaml.safe_dump(base))
    main(["course", "validate", "--file", str(cdir / "course.yaml")])
    out = _json.loads(capsys.readouterr().out)
    assert out["authored"] is False
    assert {"professor_profile", "mastery_model", "research-dossier"} <= set(out["missing_for_authored"])

    # add profile + mastery_model + a dossier -> now authored
    base["professor_profile"] = {"persona": "p", "teaching_stance": "s"}
    base["mastery_model"] = {"excellence_bar": "be the best",
                             "staying_current": [{"type": "reference", "title": "feed"}]}
    (cdir / "course.yaml").write_text(yaml.safe_dump(base))
    (cdir / "research").mkdir()
    (cdir / "research" / "dossier.md").write_text("# Dossier\n" + "source · url · why\n" * 20)
    main(["course", "validate", "--file", str(cdir / "course.yaml")])
    out = _json.loads(capsys.readouterr().out)
    assert out["authored"] is True and out["missing_for_authored"] == []


def test_render_transcript_and_degree(tmp_path):
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    R.enroll(s, CDIR, "GEN101", today="2026-07-06")
    records = [rec("f1.apply", 0.95, course="GEN101", kind="hw")]
    R.refresh(s, records)
    tr = docs.render_transcript(s, records)
    assert "GEN101" in tr and "Cumulative GPA" in tr and "4.00" in tr
    mods = {"GEN101": load_course(CDIR / "GEN101" / "course.yaml")}
    dp = docs.render_degree_progress(s, records, mods)
    assert "Degree Progress" in dp and "Outcomes mastered" in dp


def test_schedule_has_real_dates():
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    sch = docs.render_schedule(s)
    assert "Term start: 2026-07-06" in sch and "Projected graduation" in sch and "Semester 2" in sch


def test_diploma_render_when_awarded():
    s = fresh_state(name="Ada Lovelace", timezone="UTC", started_on="2026-07-06")
    s.degree.awarded_on = "2027-01-01"
    s.gpa.cumulative = 3.6
    dip = docs.render_diploma(s)
    assert "Diploma" in dip and "2027-01-01" in dip and "Ada Lovelace" in dip and "3.60" in dip


def test_render_all_writes_files(tmp_path):
    (tmp_path / "Registrar").mkdir(parents=True)
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    R.enroll(s, CDIR, "GEN101", today="2026-07-06")
    s.save(tmp_path / "Registrar" / "state.json")
    written = docs.render_all(tmp_path, CDIR)
    assert "Catalog.md" in written
    assert "Courses/GEN101/Syllabus.md" in written
    assert "Registrar/Transcript.md" in written
    assert (tmp_path / "Catalog.md").exists()
    assert (tmp_path / "Registrar" / "DegreeProgress.md").exists()
