"""state.json schema (v3) + load/save/validate. Engine-owned; see RFC §4.1."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, NonNegativeInt

SCHEMA_VERSION = 3
Standing = Literal["good", "honors", "probation"]
Persona = Literal["guide", "collaborator", "peer", "launcher"]
# Course lifecycle (RFC-009). Engine-owned; surfaces read it, never set it directly.
#   draft: enrolled, not yet authored · researching: blocked on the learner's research upload
#   authoring: report in, building · placement: authored, awaiting placement · active: live
#   archived: dropped (soft, reversible)
CourseStatus = Literal["draft", "researching", "authoring", "placement", "active", "archived"]


class Program(BaseModel):
    # The engine is built around exactly two semesters (phase logic, the s1_/s2_ Assessments fields,
    # the Degree requirement) — so this is fixed, not a knob. Literal[2] rejects any other value loudly.
    total_semesters: Literal[2] = 2
    weeks_per_semester: int = 12
    started_on: str | None = None  # YYYY-MM-DD


class Position(BaseModel):
    semester: int = 1
    week_in_semester: int = 1
    absolute_week: int = 1
    phase: str = "foundations"


class Gpa(BaseModel):
    semester: float | None = None
    cumulative: float | None = None


class Streak(BaseModel):
    current: NonNegativeInt = 0
    longest: NonNegativeInt = 0
    last_completed_date: str | None = None


class Learner(BaseModel):
    name: str | None = None
    timezone: str = "Asia/Tashkent"
    persona_stage: Persona = "guide"


class Course(BaseModel):
    title: str
    credits: int
    runs_in: list[int] = Field(default_factory=lambda: [1, 2])
    active: bool = False
    unit: str | None = None
    unit_index: int = 0
    activates_week: int | None = None
    grade_weights: dict[str, float] = Field(
        default_factory=dict
    )  # copied from the module at enroll
    enrolled_on: str | None = None
    status: CourseStatus = "draft"  # lifecycle (RFC-009); advanced only by the engine
    archived_on: str | None = None  # set when moved to archived (soft drop)


class Assessments(BaseModel):
    s1_midterm: str | None = None
    s1_finals: str | None = None
    s2_midterm: str | None = None
    s2_finals: str | None = None


class SemesterRecord(BaseModel):
    semester: int
    gpa: float | None
    standing: Standing
    finals_grade: str | None
    completed_on: str


class EnrollmentRecord(BaseModel):
    code: str
    enrolled_on: str
    dropped_on: str | None = None


class Enrollment(BaseModel):
    credit_cap: int = 14
    records: list[EnrollmentRecord] = Field(default_factory=list)


class Degree(BaseModel):
    name: str = "Hermes University Certificate of Mastery"  # from profile.credential_name (RFC-005)
    requirement: str = "pass finals of both 3-month semesters (>=B)"
    awarded_on: str | None = None


class State(BaseModel):
    schema_version: Literal[3] = SCHEMA_VERSION
    program: Program = Field(default_factory=Program)
    position: Position = Field(default_factory=Position)
    gpa: Gpa = Field(default_factory=Gpa)
    standing: Standing = "good"
    streak: Streak = Field(default_factory=Streak)
    learner: Learner = Field(default_factory=Learner)
    courses: dict[str, Course] = Field(default_factory=dict)
    assessments: Assessments = Field(default_factory=Assessments)
    history: list[SemesterRecord] = Field(default_factory=list)
    enrollment: Enrollment = Field(default_factory=Enrollment)
    hold: str | None = None  # e.g. "probation" — blocks new material
    degree: Degree = Field(default_factory=Degree)

    @classmethod
    def load(cls, path: str | Path) -> State:
        return cls.model_validate_json(Path(path).read_text())

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.model_dump_json(indent=2) + "\n")


def fresh_state(
    *,
    name: str,
    timezone: str,
    started_on: str,
    weeks_per_semester: int = 12,
    credential_name: str | None = None,
) -> State:
    """A clean day-1 state (no courses yet; registration adds them)."""
    degree = Degree(name=credential_name) if credential_name else Degree()
    return State(
        program=Program(
            weeks_per_semester=weeks_per_semester,
            started_on=started_on,
        ),
        learner=Learner(name=name, timezone=timezone),
        degree=degree,
    )
