from engine import cards
from tests.conftest import dt


def test_deck_name():
    assert cards.deck_name("Hermes University", "CS250") == "Hermes University::CS250"
    assert cards.deck_name("HU", "CS250", "two-pointers") == "HU::CS250::two-pointers"


def test_build_card_has_deck_fields_and_fsrs():
    c = cards.build_card(prefix="HU", course_code="CS250", unit="two-pointers",
                         front="  What invariant makes two pointers O(n)?  ",
                         back="  A sorted order lets each pointer move monotonically.  ",
                         tags=["pattern", "two-pointers"], now=dt("2026-07-06T20:00:00+00:00"))
    assert c.deck == "HU::CS250::two-pointers"
    assert c.front.startswith("What") and not c.front.endswith(" ")  # stripped
    assert c.tags == ["pattern", "two-pointers"]
    assert isinstance(c.fsrs, dict) and c.fsrs  # has an initial FSRS state


def test_build_cards_batch():
    items = [{"front": "f1", "back": "b1"}, {"front": "f2", "back": "b2", "tags": ["t"]}]
    out = cards.build_cards(prefix="HU", course_code="CS270", items=items,
                            now=dt("2026-07-06T20:00:00+00:00"))
    assert len(out) == 2 and out[1].tags == ["t"] and out[0].deck == "HU::CS270"
