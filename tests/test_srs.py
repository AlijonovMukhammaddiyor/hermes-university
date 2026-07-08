"""The Anki forward pipeline (RFC-009 §5)."""

from datetime import datetime, timezone

from engine.srs import due_count, queue_cards

NOW = datetime(2026, 7, 8, tzinfo=timezone.utc)


def test_queue_cards_writes_push_queue_and_ledger(tmp_path):
    n = queue_cards(tmp_path, "CS101", "Hermes", "unit1",
                    [{"front": "What is O(1)?", "back": "constant time"},
                     {"front": "What is O(n)?", "back": "linear", "tags": ["complexity"]}], NOW)
    assert n == 2
    pend = (tmp_path / "SRS" / "pending.jsonl").read_text().splitlines()
    assert len(pend) == 2
    import json
    first = json.loads(pend[0])
    assert first["deck"] == "Hermes::CS101::unit1" and first["front"] == "What is O(1)?"
    assert set(first) == {"deck", "front", "back", "tags"}          # exactly what anki_sync reads
    ledger = (tmp_path / "SRS" / "ledger.jsonl").read_text().splitlines()
    assert len(ledger) == 2 and "fsrs" in json.loads(ledger[0])


def test_due_count_reflects_queue_and_ledger(tmp_path):
    assert due_count(tmp_path, NOW) == {"queued": 0, "created": 0, "due": 0}
    queue_cards(tmp_path, "CS101", "Hermes", "", [{"front": "q", "back": "a"}], NOW)
    d = due_count(tmp_path, NOW)
    assert d["queued"] == 1 and d["created"] == 1 and d["due"] == 1
    # appends accumulate the ledger; the push queue is cleared by the syncer (not tested here)
    queue_cards(tmp_path, "CS101", "Hermes", "", [{"front": "q2", "back": "a2"}], NOW)
    assert due_count(tmp_path, NOW)["created"] == 2
