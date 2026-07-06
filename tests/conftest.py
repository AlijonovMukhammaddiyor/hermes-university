from datetime import datetime, timezone

from engine.gradebook import GradeRecord, Proof


def rec(outcome, score, *, ts="2026-07-06T20:00:00+00:00", kind="hw", credits_weight=0.3,
        semester=1, course="CS250", tier=None, weak=None, passed=True):
    band = "A" if score >= 0.9 else "B" if score >= 0.8 else "C" if score >= 0.7 else "F"
    return GradeRecord(ts=ts, course=course, outcome=outcome, kind=kind, band=band,
                       score=score, credits_weight=credits_weight, semester=semester,
                       tier=tier, weak_areas=weak or [],
                       proof=Proof(source="test", passed=passed))


def dt(iso):
    d = datetime.fromisoformat(iso)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
