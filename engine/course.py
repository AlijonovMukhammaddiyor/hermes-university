"""Course-module schema + loader/validator (RFC §4.3, §6). A course is DATA, not code.

Enforces the backward-design contract at load time:
  - every Outcome has a proof (an Assessment for that outcome),
  - assessment Bloom target >= the outcome's Bloom level,
  - depends_on references exist and form a DAG (no cycles),
  - rubrics referenced by assessments exist.
Invalid course files fail loudly here, before anything schedules them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

Bloom = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]
BLOOM_ORDER = ["remember", "understand", "apply", "analyze", "evaluate", "create"]


class Resource(BaseModel):
    """A concrete learning material (RFC-003 §3) — researched, not a topic label."""
    type: Literal["textbook", "course", "paper", "docs", "video", "problemset", "reference"]
    title: str
    author: str | None = None
    url: str | None = None
    locator: str | None = None      # "ch. 3–4" | "Lectures 5–7" | "§2.1"
    why: str | None = None          # why THIS resource for THIS topic/learner
    tier: Literal["core", "supplementary"] = "core"
    cost: Literal["free", "paid"] = "free"


class ProfessorProfile(BaseModel):
    """The researched teaching character for a field (RFC-004) — data, not code."""
    persona: str                                         # voice/character for the field + learner
    teaching_stance: str                                 # pedagogical approach for this domain
    common_misconceptions: list[str] = Field(default_factory=list)   # preempted by the professor
    assessment_philosophy: str = ""                      # what "excellent" is + how to grade it
    hint_style: str | None = None


class MasteryModel(BaseModel):
    """How this course makes the learner one of the best AND keeps them evolving (RFC-004)."""
    excellence_bar: str                                  # what the best in this field can DO
    expert_practices: list[str] = Field(default_factory=list)   # how top practitioners work
    frontier: str = ""                                   # state of the art + trajectory
    staying_current: list["Resource"] = Field(default_factory=list)  # people/communities/feeds/papers
    signature_work: str = ""                             # portfolio/reputation to work with the best
    deliberate_practice: str = ""                        # the regimen to reach the bar


class Criterion(BaseModel):
    name: str
    target_descriptor: str
    below_descriptor: str | None = None
    above_descriptor: str | None = None


class Rubric(BaseModel):
    id: str
    shape: Literal["analytic", "single_point"] = "single_point"
    criteria: list[Criterion]
    score_to_grade: dict[str, float] | None = None  # optional per-rubric override


class Assessment(BaseModel):
    id: str
    outcome_id: str
    type: Literal["formative", "summative"]
    modality: str                      # recall_quiz | worked-completion | open_problem | explain | project | ...
    bloom_target: Bloom
    rubric_id: str | None = None
    proof_gate: str                    # human-readable pass condition
    gate: str | None = None            # engine proof-gate name (e.g. "leetcode"); None => rubric-only
    gate_args: dict = Field(default_factory=dict)   # e.g. {"slug": "two-sum"}
    scaffold_stage: Literal["worked_example", "completion", "independent"] = "independent"


class Outcome(BaseModel):
    id: str
    statement: str                     # A-SMART
    bloom_level: Bloom
    depends_on: list[str] = Field(default_factory=list)
    proof: str                         # assessment id
    spaced_items: list[str] = Field(default_factory=list)
    mastery_threshold: float = 0.8


class Unit(BaseModel):
    id: str
    title: str
    order_index: int
    semester: int
    outcomes: list[Outcome]
    summary: str | None = None                                # one-line what/why of the unit
    resources: list[Resource] = Field(default_factory=list)   # per-unit reading list (researched)
    est_weeks: int = 1                                         # schedule span
    prereq_outcomes: list[str] = Field(default_factory=list)
    entry_gate: float = 0.8
    exit_gate: float = 0.8


class Course(BaseModel):
    id: str
    title: str
    subject_domain: str
    credits: int
    north_star: str
    description: str = ""                                      # syllabus/catalog prose (researched)
    primary_text: Resource | None = None                      # the anchoring textbook/course
    resources: list[Resource] = Field(default_factory=list)   # course-level library
    professor_profile: ProfessorProfile | None = None         # researched teaching character (RFC-004)
    mastery_model: MasteryModel | None = None                 # become-the-best + keep-evolving (RFC-004)
    starting_tier: Literal["easy", "med", "hard"] = "easy"  # difficulty floor for a new learner
    runs_in: list[int] = Field(default_factory=lambda: [1, 2])
    active_default: bool = True          # inactive until activates_week if False
    activates_week: int | None = None    # week_in_semester it turns on (e.g. PD101 = 9)
    prerequisites: list[str] = Field(default_factory=list)
    enduring_understandings: list[str] = Field(default_factory=list)
    grading_scale: dict[str, float] = Field(
        default_factory=lambda: {"A": 4.0, "B": 3.0, "C": 2.0, "F": 0.0})
    grade_weights: dict[str, float] = Field(  # policy over assessment kinds (renormalized in use)
        default_factory=lambda: {"hw": 0.30, "quiz": 0.20, "exam": 0.20,
                                 "midterm": 0.10, "finals": 0.20})
    rubrics: list[Rubric] = Field(default_factory=list)
    assessments: list[Assessment] = Field(default_factory=list)
    units: list[Unit] = Field(default_factory=list)

    # ---- derived helpers ----
    def all_outcomes(self) -> list[Outcome]:
        return [o for u in self.units for o in u.outcomes]

    def unit_of(self, outcome_id: str) -> Unit | None:
        for u in self.units:
            if any(o.id == outcome_id for o in u.outcomes):
                return u
        return None

    def outcome(self, outcome_id: str) -> Outcome | None:
        return next((o for o in self.all_outcomes() if o.id == outcome_id), None)

    def dag(self) -> list[dict]:
        """[{outcome, depends_on}] in unit/order sequence — for learner_model.next_topic."""
        out = []
        for u in sorted(self.units, key=lambda x: (x.semester, x.order_index)):
            for o in u.outcomes:
                out.append({"outcome": o.id, "depends_on": o.depends_on})
        return out

    @model_validator(mode="after")
    def _check_contract(self):
        rubric_ids = {r.id for r in self.rubrics}
        assess = {a.id: a for a in self.assessments}
        outcomes = {o.id: o for o in self.all_outcomes()}
        if len(outcomes) != len(self.all_outcomes()):
            raise ValueError("duplicate outcome ids")
        for o in self.all_outcomes():
            a = assess.get(o.proof)
            if a is None:
                raise ValueError(f"outcome {o.id!r} references missing assessment {o.proof!r}")
            if a.outcome_id != o.id:
                raise ValueError(f"assessment {a.id!r} outcome_id != {o.id!r}")
            if BLOOM_ORDER.index(a.bloom_target) < BLOOM_ORDER.index(o.bloom_level):
                raise ValueError(f"assessment {a.id!r} bloom below outcome {o.id!r}")
            if a.rubric_id and a.rubric_id not in rubric_ids:
                raise ValueError(f"assessment {a.id!r} references missing rubric {a.rubric_id!r}")
            for dep in o.depends_on:
                if dep not in outcomes:
                    raise ValueError(f"outcome {o.id!r} depends_on missing {dep!r}")
        _assert_acyclic(outcomes)
        return self


def _assert_acyclic(outcomes: dict[str, Outcome]) -> None:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {k: WHITE for k in outcomes}

    def visit(n: str):
        color[n] = GRAY
        for dep in outcomes[n].depends_on:
            if color[dep] == GRAY:
                raise ValueError(f"dependency cycle at outcome {n!r} -> {dep!r}")
            if color[dep] == WHITE:
                visit(dep)
        color[n] = BLACK

    for k in outcomes:
        if color[k] == WHITE:
            visit(k)


def load_course(path: str | Path) -> Course:
    return Course.model_validate(yaml.safe_load(Path(path).read_text()))
