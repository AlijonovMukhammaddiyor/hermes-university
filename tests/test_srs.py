"""The Anki forward pipeline (RFC-009 §5)."""

from datetime import UTC, datetime

from engine.srs import due_count, queue_cards

NOW = datetime(2026, 7, 8, tzinfo=UTC)


def test_queue_cards_writes_push_queue_and_ledger(tmp_path):
    n = queue_cards(
        tmp_path,
        "CS101",
        "Hermes",
        "unit1",
        [
            {"front": "What is O(1)?", "back": "constant time"},
            {"front": "What is O(n)?", "back": "linear", "tags": ["complexity"]},
        ],
        NOW,
    )
    assert n == 2
    pend = (tmp_path / "SRS" / "pending.jsonl").read_text().splitlines()
    assert len(pend) == 2
    import json

    first = json.loads(pend[0])
    assert first["deck"] == "Hermes::CS101::unit1" and first["front"] == "What is O(1)?"
    assert set(first) == {"deck", "front", "back", "tags"}  # exactly what anki_sync reads
    ledger = (tmp_path / "SRS" / "ledger.jsonl").read_text().splitlines()
    assert len(ledger) == 2 and "fsrs" in json.loads(ledger[0])


def test_due_count_reflects_queue_and_ledger(tmp_path):
    assert due_count(tmp_path, NOW) == {"queued": 0, "created": 0, "due": 0, "review_due": 0}
    queue_cards(tmp_path, "CS101", "Hermes", "", [{"front": "q", "back": "a"}], NOW)
    d = due_count(tmp_path, NOW)
    assert d["queued"] == 1 and d["created"] == 1 and d["due"] == 1
    # appends accumulate the ledger; the push queue is cleared by the syncer (not tested here)
    queue_cards(tmp_path, "CS101", "Hermes", "", [{"front": "q2", "back": "a2"}], NOW)
    assert due_count(tmp_path, NOW)["created"] == 2


def test_cards_are_tagged_with_the_outcome(tmp_path):
    from engine.srs import outcome_tag

    queue_cards(
        tmp_path, "CS101", "Hermes", "u1", [{"front": "q", "back": "a"}], NOW, outcome="f1.apply"
    )
    import json

    card = json.loads((tmp_path / "SRS" / "pending.jsonl").read_text().splitlines()[0])
    assert outcome_tag("f1.apply") in card["tags"]  # review-back linkage survives
    led = json.loads((tmp_path / "SRS" / "ledger.jsonl").read_text().splitlines()[0])
    assert led["outcome"] == "f1.apply"


def test_review_ingest_flags_and_clears_review_due(tmp_path):
    from engine.srs import ingest_reviews, review_due

    # a lapse (Again=1) marks the outcome review-due; GPA/transcript are untouched here by design
    r = ingest_reviews(tmp_path, [{"outcome": "f1.apply", "ease": 1, "ts": "2026-07-08T01:00"}])
    assert r["ingested"] == 1 and review_due(tmp_path) == ["f1.apply"]
    # a later Good (3) clears it (recovered)
    ingest_reviews(tmp_path, [{"outcome": "f1.apply", "ease": 3, "ts": "2026-07-08T02:00"}])
    assert review_due(tmp_path) == []
    # counters accumulate; due_count surfaces the review-due total
    ingest_reviews(tmp_path, [{"outcome": "f2.apply", "ease": 1, "ts": "2026-07-08T03:00"}])
    assert due_count(tmp_path, NOW)["review_due"] == 1
    from engine.srs import load_retention

    assert load_retention(tmp_path)["f1.apply"]["reviews"] == 2


def test_review_ingest_drops_malformed_events_without_raising(tmp_path):
    from engine.srs import ingest_reviews, load_retention

    events = [
        {"outcome": "f1.apply", "ease": 3, "ts": "2026-07-08T01:00"},  # valid
        {"outcome": "f1.apply", "ease": 0, "ts": "2026-07-08T02:00"},  # ease out of 1..4
        {"outcome": "f1.apply", "ease": 5, "ts": "2026-07-08T03:00"},  # ease out of 1..4
        {"ease": 3, "ts": "2026-07-08T04:00"},  # missing outcome
        {"outcome": "f1.apply", "ts": "2026-07-08T05:00"},  # missing ease
    ]
    r = ingest_reviews(tmp_path, events)  # must not raise
    assert r["ingested"] == 1  # only the valid one counted
    assert load_retention(tmp_path)["f1.apply"]["reviews"] == 1


def test_review_ingest_tolerates_null_ts_without_dropping_the_batch(tmp_path):
    # regression: explicit null ts must not abort batch (sort key did None < str -> TypeError)
    from engine.srs import ingest_reviews

    events = [
        {"outcome": "a.apply", "ease": 3, "ts": None},
        {"outcome": "b.apply", "ease": 1, "ts": "2026-01-01"},
    ]
    r = ingest_reviews(tmp_path, events)  # must not raise
    assert r["ingested"] == 2
