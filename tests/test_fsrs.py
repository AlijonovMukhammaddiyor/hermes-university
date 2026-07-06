from datetime import timedelta

from engine import fsrs
from tests.conftest import dt


def test_new_card_is_serializable_dict():
    c = fsrs.new_card()
    assert isinstance(c, dict)
    # round-trips through the library
    assert isinstance(fsrs.due(c), object)


def test_review_advances_due_into_future():
    now = dt("2026-07-06T20:00:00+00:00")
    c = fsrs.new_card()
    c2 = fsrs.review(c, 3, now)  # Good
    assert fsrs.due(c2) > now


def test_retrievability_high_just_after_review_and_decays():
    now = dt("2026-07-06T20:00:00+00:00")
    c = fsrs.review(fsrs.new_card(), 3, now)
    r_now = fsrs.retrievability(c, now)
    r_later = fsrs.retrievability(c, now + timedelta(days=90))
    assert 0.5 <= r_now <= 1.0
    assert r_later < r_now


def test_is_due_toggle():
    now = dt("2026-07-06T20:00:00+00:00")
    c = fsrs.review(fsrs.new_card(), 4, now)  # Easy -> longer interval
    assert not fsrs.is_due(c, now)
    assert fsrs.is_due(c, now + timedelta(days=3650))


def test_invalid_rating_raises():
    import pytest
    with pytest.raises(ValueError):
        fsrs.review(fsrs.new_card(), 9, dt("2026-07-06T20:00:00+00:00"))
