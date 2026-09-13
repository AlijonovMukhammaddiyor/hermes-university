"""The Hermes Daily data desks — the house rules, held to by test.

Two rules carry over from the desk model and both are checked here: a data
desk is code and never a model, and a desk that cannot read its source fails
rather than guessing. Nothing here touches a network or a real vault.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

DESKS = Path(__file__).resolve().parents[1] / "scripts" / "paper"

# The paper sets tables in a ~52-character column: every cell must be under 26
# and every chart label under 13 (vael-paper docs/WRITING.md).
CELL_CEILING = 26
LABEL_CEILING = 13


def load(name):
    """Load a desk by path — they are scripts, not an installed package."""
    if str(DESKS) not in sys.path:
        sys.path.insert(0, str(DESKS))
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, DESKS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    # Register before executing: a desk's `from _common import ...` must resolve
    # to this same module object, or its DeskError is a different class.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def vault(tmp_path):
    """A minimal vault with the three files the offline desks read."""
    (tmp_path / "Registrar").mkdir()
    (tmp_path / "records").mkdir()
    (tmp_path / "Registrar" / "state.json").write_text(json.dumps({
        "schema_version": 3,
        "program": {"total_semesters": 2, "weeks_per_semester": 12, "started_on": "2026-07-06"},
        "position": {"semester": 1, "week_in_semester": 3, "phase": "foundations"},
        "gpa": {"semester": 2.5, "cumulative": 2.5},
        "standing": "probation",
        "hold": "probation",
        "streak": {"current": 0, "longest": 4},
        "learner": {"name": "Test", "timezone": "Asia/Tashkent"},
        "courses": {"AG201": {"title": "AI Agent Engineering", "credits": 4, "status": "active"}},
    }))
    (tmp_path / "records" / "grades.jsonl").write_text(
        json.dumps({"ts": "2026-08-09T13:04:49+00:00", "course": "AG201", "band": "F", "score": 0.0}) + "\n"
    )
    (tmp_path / "records" / "learner_model.json").write_text(json.dumps({
        "outcomes": {"u1.transformer": {"mastery_band": "F", "attempts": 4}},
        "topics": {"Attention from First Principles": {"proficiency": 0.0,
                                                       "difficulty_ceiling": "easy", "attempts": 1}},
        "routine": {"best_hours": ["21:00-23:00"], "adherence_by_slot": {"21:00-23:00": 3, "18:00-20:00": 1}},
        "pace": {"task_cap_observed": 2, "rest_day": "Monday"},
        "preferences": {"energy_window": {"aspect": "energy_window", "value": "unidentified",
                                          "evidence": "four missed blocks", "confidence": 0.5,
                                          "source": "calendar"}},
    }))
    return tmp_path


def frontmatter_of(path):
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(path.read_text().split("---")[1])


def cells_of(path):
    for line in path.read_text().splitlines():
        if line.startswith("|") and not set(line) <= set("|:- "):
            yield from (cell.strip() for cell in line.strip("|").split("|"))


# ── the shared emitter ────────────────────────────────────────────────────

def test_colon_scalars_are_quoted():
    """YAML 1.1 reads 21:00 as sexagesimal; a time label must survive as a string."""
    common = load("_common")
    rendered = common.frontmatter({"chart": {"labels": ["21:00-23:00"]}})
    assert '"21:00-23:00"' in rendered
    assert frontmatter_of_text(rendered)["chart"]["labels"] == ["21:00-23:00"]


def frontmatter_of_text(text):
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(text.strip().strip("-"))


def test_clip_drops_whole_words_not_characters():
    common = load("_common")
    assert common.clip("Attention from First Principles") == "Attention from First"
    assert common.clip("short") == "short"
    # A single unbreakable word still has to fit the column.
    assert len(common.clip("x" * 80)) <= common.CELL_LIMIT


# ── the desks ─────────────────────────────────────────────────────────────

def test_standing_desk_reports_the_record(vault, tmp_path):
    desk = load("standing_desk")
    edition = tmp_path / "edition"
    written = desk.build_article(edition, vault)

    front = frontmatter_of(written)
    assert front["section"] == "standing"
    assert front["priority"] != 1, "priority 1 belongs to the lead"

    body = written.read_text()
    assert "week 3 of 12" in body
    assert "2.50" in body, "the GPA must come from the record, not be rounded away"
    assert "probation" in body
    assert all(len(cell) < CELL_CEILING for cell in cells_of(written))


def test_model_desk_charts_only_real_variation(vault, tmp_path):
    desk = load("model_desk")
    edition = tmp_path / "edition"
    front = frontmatter_of(desk.build_article(edition, vault))

    assert front["chart"]["values"] == [3, 1]
    assert all(len(label) < LABEL_CEILING for label in front["chart"]["labels"])
    assert front["priority"] != 1


def test_model_desk_omits_chart_below_two_slots(vault, tmp_path):
    """One bar is not a distribution, and the check wants two values."""
    desk = load("model_desk")
    model = json.loads((vault / "records" / "learner_model.json").read_text())
    model["routine"]["adherence_by_slot"] = {"21:00-23:00": 3}
    (vault / "records" / "learner_model.json").write_text(json.dumps(model))

    front = frontmatter_of(desk.build_article(tmp_path / "edition", vault))
    assert "chart" not in front


def test_model_desk_quotes_a_belief_without_hardening_it(vault, tmp_path):
    desk = load("model_desk")
    body = desk.build_article(tmp_path / "edition", vault).read_text()
    assert "unidentified" in body, "the belief is quoted as written"
    assert "50% confidence" in body, "and carries its confidence"
    assert "four missed blocks" in body, "and its evidence"


# ── failing rather than guessing ──────────────────────────────────────────

@pytest.mark.parametrize("name", ["standing_desk", "model_desk"])
def test_desk_fails_when_its_source_is_missing(name, tmp_path):
    desk = load(name)
    with pytest.raises(desk.DeskError):
        desk.build_article(tmp_path / "edition", tmp_path / "no-vault-here")


@pytest.mark.parametrize("name", ["standing_desk", "model_desk"])
def test_desk_exits_nonzero_when_it_cannot_source(name, tmp_path):
    desk = load(name)
    assert desk.main([str(tmp_path / "edition"), "--vault", str(tmp_path / "missing")]) == 1


# ── the revenue desk ──────────────────────────────────────────────────────

DISCOVERY = {
    "fastestGrowingStartups": [
        {"name": "Rocketship", "slug": "rocket", "url": "https://trustmrr.com/startup/rocket",
         "category": "AI", "paymentProvider": "stripe", "onSale": False,
         "revenue": {"last30Days": 180000, "mrr": 175000, "total": 2000000}},
        {"name": "Warmap.lol", "slug": "warmap", "url": "https://trustmrr.com/startup/warmap",
         "category": "Marketplace", "paymentProvider": "dodopayment", "onSale": True,
         "revenue": {"last30Days": 7864.08, "mrr": 0, "total": 9487.08}},
    ],
    "recentlyAddedStartups": [
        # the same product in both feeds must be counted once
        {"name": "Warmap.lol", "slug": "warmap", "url": "https://trustmrr.com/startup/warmap",
         "category": "Marketplace", "paymentProvider": "dodopayment", "onSale": True,
         "revenue": {"last30Days": 7864.08, "mrr": 0, "total": 9487.08}},
        {"name": "Qoest", "slug": "qoest", "url": "https://trustmrr.com/startup/qoest",
         "category": "", "paymentProvider": "lemonsqueezy", "onSale": False,
         "revenue": {"last30Days": 771, "mrr": 4274, "total": 3520}},
        {"name": "Nothing Yet", "slug": "nothing", "url": "https://trustmrr.com/startup/nothing",
         "category": "Dev", "paymentProvider": "paddle", "onSale": False,
         "revenue": {"last30Days": 0, "mrr": 0, "total": 0}},
    ],
}


def test_revenue_desk_keeps_the_three_metrics_apart(tmp_path):
    """30-day, MRR and all-time are different numbers; conflating them is the whole risk."""
    desk = load("trustmrr_desk")
    rows = desk.rows_from(DISCOVERY, desk.FEEDS["both"], 500.0, 25000.0, 8)
    warmap = next(r for r in rows if r["slug"] == "warmap")
    assert (warmap["last30"], warmap["mrr"], warmap["total"]) == (7864.08, 0, 9487.08)

    body = desk.build_body(rows, 500.0, 25000.0)
    assert "| # | Product | 30-day | MRR | All-time |" in body
    assert "$7,864" in body and "$9,487" in body


def test_revenue_desk_excludes_rocketships_and_zero_revenue(tmp_path):
    """A $180k/month product is not something one person copies; £0 is not revenue."""
    desk = load("trustmrr_desk")
    slugs = {r["slug"] for r in desk.rows_from(DISCOVERY, desk.FEEDS["both"], 500.0, 25000.0, 8)}
    assert slugs == {"warmap", "qoest"}, "band should drop the rocketship and the zero"


def test_revenue_desk_deduplicates_across_feeds(tmp_path):
    desk = load("trustmrr_desk")
    rows = desk.rows_from(DISCOVERY, desk.FEEDS["both"], 500.0, 25000.0, 8)
    assert [r["slug"] for r in rows].count("warmap") == 1


def test_revenue_desk_survives_a_missing_category(tmp_path):
    """A blank category must not print as a stray dash mid-sentence."""
    desk = load("trustmrr_desk")
    rows = desk.rows_from(DISCOVERY, desk.FEEDS["both"], 500.0, 25000.0, 8)
    body = desk.build_body(rows, 500.0, 25000.0)
    assert "— via lemonsqueezy." in body
    assert "— , via" not in body


def test_revenue_desk_fails_rather_than_printing_an_empty_board(tmp_path, monkeypatch):
    desk = load("trustmrr_desk")
    monkeypatch.setattr(desk, "fetch", lambda *a, **k: {"recentlyAddedStartups": [], "fastestGrowingStartups": []})
    with pytest.raises(desk.DeskError):
        desk.build_article(tmp_path / "edition", 8, 500.0, 25000.0, "both")


def test_revenue_desk_drops_the_story_when_the_api_is_down(tmp_path, monkeypatch):
    desk = load("trustmrr_desk")
    def boom(*a, **k):
        raise desk.DeskError("TrustMRR discovery unreachable: timed out")
    monkeypatch.setattr(desk, "fetch", boom)
    assert desk.main([str(tmp_path / "edition")]) == 1


def test_revenue_desk_chart_labels_fit_the_column(tmp_path, monkeypatch):
    desk = load("trustmrr_desk")
    monkeypatch.setattr(desk, "fetch", lambda *a, **k: DISCOVERY)
    front = frontmatter_of(desk.build_article(tmp_path / "edition", 8, 500.0, 25000.0, "both"))
    assert front["section"] == "projects"
    assert front["priority"] != 1
    assert all(len(label) < LABEL_CEILING for label in front["chart"]["labels"])
    assert front["chart"]["values"] == [7864, 771]


# ── the launch desk (the audience half) ───────────────────────────────────

def _hit(title, points, comments=0, url="", oid="1"):
    return {"title": title, "points": points, "num_comments": comments,
            "url": url, "objectID": oid, "author": "someone",
            "created_at": "2026-09-12T10:00:00Z"}


def test_launch_desk_pulls_the_project_name_out_of_the_title():
    """A dash or colon separates name from pitch; a comma only when prose follows."""
    desk = load("showhn_desk")
    assert desk._project_name("Toast, a by default in-terminal IDE") == "Toast"
    assert desk._project_name("Hacker News, Without AI") == "Hacker News, Without AI"
    assert desk._project_name("ResolveHQ – A Helpdesk Built on Cloudflare") == "ResolveHQ"
    assert desk._project_name("Graphify C#: compiler-accurate graphs") == "Graphify C#"
    assert desk._project_name("Hopera") == "Hopera"


def _fake_urlopen(payload):
    import io
    import json as _json

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return lambda *a, **k: _Resp(_json.dumps(payload).encode())


def test_launch_desk_counts_a_relisted_launch_once(monkeypatch):
    """The same launch gets posted twice; the better-scored copy is the one that counts."""
    desk = load("showhn_desk")
    payload = {"hits": [
        _hit("Show HN: Hacker News, without AI", 193, 80, "https://a.example", "1"),
        _hit("Show HN: Hacker News, Without AI", 200, 88, "https://b.example", "2"),
        _hit("Show HN: Toast, a by default in-terminal IDE", 81, 88, "https://c.example", "3"),
    ]}
    monkeypatch.setattr(desk.urllib.request, "urlopen", _fake_urlopen(payload))
    rows = desk.fetch(48, 20, 8)
    assert len(rows) == 2, "the relist must collapse"
    assert rows[0]["points"] == 200, "and keep the higher score"


def test_launch_desk_says_points_are_not_users(tmp_path, monkeypatch):
    desk = load("showhn_desk")
    payload = {"hits": [_hit("Show HN: A", 100, 10, "https://a.example", "1"),
                        _hit("Show HN: B", 50, 5, "https://b.example", "2")]}
    monkeypatch.setattr(desk.urllib.request, "urlopen", _fake_urlopen(payload))
    body = desk.build_article(tmp_path / "edition", 48, 20, 8).read_text()
    assert "not adoption" in body or "not users" in body


def test_launch_desk_drops_the_story_when_nothing_clears_the_bar(tmp_path, monkeypatch):
    desk = load("showhn_desk")
    monkeypatch.setattr(desk, "fetch", lambda *a, **k: [])
    with pytest.raises(desk.DeskError):
        desk.build_article(tmp_path / "edition", 48, 20, 8)
    assert desk.main([str(tmp_path / "edition")]) == 1
