import json

from engine import board as B


def test_render_parse_roundtrip():
    cols = {
        "Today": [
            B.Card(
                title="Two Sum",
                line="solve it + jot the hash-map trick",
                outcome="ah.apply",
                course="GEN101",
                tier="easy",
            )
        ],
        "Done": [
            B.Card(
                title="Big-O",
                line="derive the bound",
                outcome="bo.apply",
                course="GEN101",
                checked=True,
            )
        ],
    }
    md = B.render_board(cols)
    assert "kanban-plugin: board" in md and "## Today" in md and "## Proof Pending" in md
    parsed = B.parse_board(md)
    t = parsed["Today"][0]
    assert (
        t.title == "Two Sum"
        and t.outcome == "ah.apply"
        and t.course == "GEN101"
        and t.tier == "easy"
    )
    assert t.checked is False and "hash-map" in t.line
    d = parsed["Done"][0]
    assert d.title == "Big-O" and d.outcome == "bo.apply" and d.checked is True


def test_hidden_metadata_not_shown_as_title():
    md = B.render_board(
        {"Today": [B.Card(title="Ship an agent", outcome="s1.finals", course="AG201")]}
    )
    # the machine mapping is an HTML comment, not visible card text
    assert "<!--hu:o=s1.finals;c=AG201-->" in md
    assert B.parse_board(md)["Today"][0].title == "Ship an agent"


def test_done_column_detects_learner_moves():
    # a learner dragged a card to Done + checked it in Obsidian; the audit must see it
    md = """---
kanban-plugin: board
---

## Today

## Done

- [x] **URL shortener** — designed + defended <!--hu:o=sd.create;c=SD101-->
"""
    done = B.parse_board(md)["Done"]
    assert len(done) == 1 and done[0].outcome == "sd.create" and done[0].checked is True


def test_board_cli_write_then_read(tmp_path, capsys):
    from engine.cli import main

    spec = {"Today": [{"title": "Recursion", "outcome": "rec.apply", "course": "GEN101"}]}
    assert main(["board", "write", "--vault", str(tmp_path), "--json", json.dumps(spec)]) == 0
    capsys.readouterr()
    assert (tmp_path / "Board.md").exists()
    assert main(["board", "read", "--vault", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["Today"][0]["outcome"] == "rec.apply" and "Done" in out
