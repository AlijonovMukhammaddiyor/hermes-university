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


def test_render_syllabus_is_a_complete_academic_plan():
    syl = docs.render_syllabus(load_course(CDIR / "GEN101" / "course.yaml"))
    assert "Basics" in syl and "Assessment & grading" in syl and "proof:" in syl
    assert "Assessment plan" in syl
    assert "What the best in this field can do" in syl and "How this course is taught" in syl
    # RFC-009: who it's for / not for
    assert "Who this course is for" in syl and "Not for" in syl
    # RFC-009: the week-by-week table is a full calendar — assignments + assessment slots
    assert "| Week | Focus | Readings | Assignment (take-home) | Assessment |" in syl
    assert "Unit quiz" in syl and "🏁 Finals" in syl and "🎯 Midterm exam" in syl
    assert "problem set 1" in syl and "timed mock" in syl


def test_week_plan_weeks_agree_with_unit_calendar():
    """The week-by-week table and the Units section share one calendar spine (_unit_spans), so a
    session.week authored as a within-unit offset still renders to the correct absolute week and
    never collapses (the AG201 bug: 12 units' first sessions all stamped 'Week 1')."""
    from engine.course import Course

    def unit(uid, order, weeks, n_sessions):
        return {"id": uid, "title": uid, "order_index": order, "semester": 1, "est_weeks": weeks,
                "outcomes": [{"id": f"{uid}.o", "statement": "s", "bloom_level": "apply",
                              "proof": f"a.{uid}"}],
                # sessions authored with WITHIN-UNIT weeks (1..n), like AG201
                "sessions": [{"week": w, "focus": f"{uid} wk{w}"} for w in range(1, n_sessions + 1)]}

    c = Course.model_validate({
        "id": "RX", "title": "T", "subject_domain": "cs", "credits": 3, "north_star": "n",
        "assessments": [{"id": f"a.{u}", "outcome_id": f"{u}.o", "type": "summative",
                         "modality": "project", "bloom_target": "apply", "proof_gate": "p"}
                        for u in ("A", "B")],
        "units": [unit("A", 1, 2, 2), unit("B", 2, 3, 3)],
    })
    syl = docs.render_syllabus(c)
    # A spans weeks 1–2, B spans 3–5 — five distinct absolute weeks, no collapse
    for wk in ("S1 W1", "S1 W2", "S1 W3", "S1 W4", "S1 W5"):
        assert f"| {wk} |" in syl, wk
    assert syl.count("| S1 W1 |") == 1                     # not one-per-unit
    assert "### Sem 1 · Weeks 3–5 · B" in syl               # Units header agrees


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
    miss = set(out["missing_for_authored"])
    assert {"professor_profile", "mastery_model"} <= miss
    assert any(x.startswith("research-dossier") for x in miss)

    # a THIN dossier (no cited URLs / confidence / open-questions) must still fail the hardened gate
    base["professor_profile"] = {"persona": "p", "teaching_stance": "s"}
    base["mastery_model"] = {"excellence_bar": "be the best",
                             "staying_current": [{"type": "reference", "title": "feed"}]}
    (cdir / "course.yaml").write_text(yaml.safe_dump(base))
    (cdir / "research").mkdir()
    (cdir / "research" / "dossier.md").write_text("# Dossier\n" + "a topic i remember\n" * 20)
    main(["course", "validate", "--file", str(cdir / "course.yaml")])
    assert any(x.startswith("research-dossier")
               for x in _json.loads(capsys.readouterr().out)["missing_for_authored"])

    # a REAL cited dossier (>=5 URLs + confidence + open-questions) -> authored
    (cdir / "research" / "dossier.md").write_text(
        "# Dossier\n" + "".join(f"- src{i} https://ex{i}.com confidence: high\n" for i in range(6))
        + "\n## Open Questions\n- none\n")
    main(["course", "validate", "--file", str(cdir / "course.yaml")])
    out = _json.loads(capsys.readouterr().out)
    assert out["authored"] is True and out["missing_for_authored"] == []


def test_render_my_plan_prunes_and_renumbers():
    c = load_course(CDIR / "GEN101" / "course.yaml")
    # nothing mastered -> full plan, both teaching units' weeks present, renumbered from 1
    full = docs.render_my_plan(c, mastered=set())
    assert "My Plan" in full and "| Week |" in full and "Placed out" not in full
    assert "| 1 |" in full and "| 4 |" in full          # 2 units × 2 weeks = weeks 1..4
    # master all of unit 'basics' -> it's placed out, remaining weeks renumber from 1
    pruned = docs.render_my_plan(c, mastered={"f1.apply"})
    assert "Placed out (tested):** Basics" in pruned
    assert "Two pointers" in pruned and "| 1 |" in pruned   # intermediate now starts at week 1


def test_home_control_center_aggregates_status(tmp_path):
    (tmp_path / "Registrar").mkdir(parents=True); (tmp_path / "records").mkdir()
    s = fresh_state(name="Ada", timezone="UTC", started_on="2026-07-06")
    R.enroll(s, CDIR, "GEN102", today="2026-07-06")        # not authored -> researching (blocked)
    R.enroll(s, CDIR, "GEN101", today="2026-07-06")        # authored -> placement
    R.activate_course(s, "GEN101")
    s.save(tmp_path / "Registrar" / "state.json")
    (tmp_path / "records" / "grades.jsonl").write_text("")
    snap = docs.status_snapshot(tmp_path, CDIR)
    assert snap["learner"] == "Ada" and snap["semester"] == 1
    by = {c["code"]: c for c in snap["courses"]}
    assert by["GEN101"]["status"] == "active" and by["GEN102"]["status"] == "researching"
    assert any(b["code"] == "GEN102" for b in snap["blocked"])   # research handoff shows as blocked
    home = docs.render_home(snap)
    assert "🏛️ Home — Ada" in home and "🟢 active" in home
    assert "waiting for your research report" in home and "[[Board]]" in home


def test_render_all_writes_home(tmp_path):
    (tmp_path / "Registrar").mkdir(parents=True)
    fresh_state(name="M", timezone="UTC", started_on="2026-07-06").save(
        tmp_path / "Registrar" / "state.json")
    written = docs.render_all(tmp_path, CDIR)
    assert "Home.md" in written and (tmp_path / "Home.md").exists()


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
