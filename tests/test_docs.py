from pathlib import Path

from engine import docs, registrar as R
from engine.course import load_course
from engine.state import fresh_state
from tests.conftest import rec

ROOT = Path(__file__).resolve().parents[1]
CDIR = ROOT / "courses"


def test_render_catalog_lists_all_courses():
    mods = [load_course(p) for p in sorted(CDIR.glob("*/course.yaml")) if p.parent.name != "_TEMPLATE"]
    cat = docs.render_catalog(mods)
    for code in ("CS250", "CS301", "CS270", "PD101"):
        assert code in cat
    assert "enroll CS250" in cat and "credits" in cat


def test_render_syllabus_has_units_and_grading():
    syl = docs.render_syllabus(load_course(CDIR / "CS250" / "course.yaml"))
    assert "Arrays & Hashing" in syl and "Grading policy" in syl and "proof:" in syl


def test_render_transcript_and_degree(tmp_path):
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    R.enroll(s, CDIR, "CS250", today="2026-07-06")
    records = [rec("ah.apply", 0.95, course="CS250", kind="hw")]
    R.refresh(s, records)
    tr = docs.render_transcript(s, records)
    assert "CS250" in tr and "Cumulative GPA" in tr and "4.00" in tr
    mods = {"CS250": load_course(CDIR / "CS250" / "course.yaml")}
    dp = docs.render_degree_progress(s, records, mods)
    assert "Degree Progress" in dp and "Outcomes mastered" in dp


def test_schedule_has_real_dates():
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    sch = docs.render_schedule(s)
    assert "Term start: 2026-07-06" in sch and "Projected graduation" in sch and "Semester 2" in sch


def test_diploma_render_when_awarded():
    s = fresh_state(name="the maintainer", timezone="UTC", started_on="2026-07-06")
    s.degree.awarded_on = "2027-01-01"
    s.gpa.cumulative = 3.6
    dip = docs.render_diploma(s)
    assert "Diploma" in dip and "2027-01-01" in dip and "the maintainer" in dip and "3.60" in dip


def test_render_all_writes_files(tmp_path):
    (tmp_path / "Registrar").mkdir(parents=True)
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    R.enroll(s, CDIR, "CS250", today="2026-07-06")
    s.save(tmp_path / "Registrar" / "state.json")
    written = docs.render_all(tmp_path, CDIR)
    assert "Catalog.md" in written
    assert "Courses/CS250/Syllabus.md" in written
    assert "Registrar/Transcript.md" in written
    assert (tmp_path / "Catalog.md").exists()
    assert (tmp_path / "Registrar" / "DegreeProgress.md").exists()
