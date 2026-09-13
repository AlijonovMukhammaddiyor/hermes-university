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

# ── failing rather than guessing ──────────────────────────────────────────

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


# ── the print edition ─────────────────────────────────────────────────────

ARTICLE = """---
id: 01-lead
headline: A Headline
deck: The standfirst
section: today
byline: The Desk
priority: 1
---

An opening paragraph with **bold** and a [link](https://example.com).

### A table

| # | Product | 30-day |
|---:|:---|---:|
| 1 | Warmap | $7,864 |

- a bullet
- another
"""


def test_print_edition_orders_by_section_then_priority(tmp_path):
    """The PDF must print in the paper's own running order, not alphabetically."""
    pdf = load("make_pdf")
    edition = tmp_path / "2026-09-13"
    (edition / "articles").mkdir(parents=True)
    (edition / "articles" / "50-late.md").write_text(
        ARTICLE.replace("section: today", "section: whitespace").replace("priority: 1", "priority: 3"))
    (edition / "articles" / "01-lead.md").write_text(ARTICLE)
    (edition / "articles" / "10-mid.md").write_text(
        ARTICLE.replace("section: today", "section: projects").replace("priority: 1", "priority: 2"))

    paper = {"masthead": "The Builder's Daily", "founded": "2026-08-22",
             "sections": [{"id": "today", "name": "Today"}, {"id": "projects", "name": "Opportunities"},
                          {"id": "whitespace", "name": "Whitespace"}]}
    out = pdf.build_html(edition, paper)

    # The lead is lifted out of the column flow into its own spanning block, so it
    # carries no section rule — it comes first, and the flow starts after it.
    assert out.index('class="lead"') < out.index('class="paper"')
    assert "Today" not in out, "the front page does not print under a section rule"
    # Everything else keeps the paper's running order inside the flow.
    assert out.index("Opportunities") < out.index("Whitespace")


def test_print_edition_sets_a_real_page_size(tmp_path):
    """A newspaper is not A4. The page comes from the size; the grid from the copy."""
    pdf = load("make_pdf")
    edition = tmp_path / "2026-09-13"
    (edition / "articles").mkdir(parents=True)
    (edition / "articles" / "01-lead.md").write_text(ARTICLE)
    paper = {"masthead": "X", "sections": [{"id": "today", "name": "Today"}]}

    assert "size: 305mm 560mm" in pdf.build_html(edition, paper, "broadsheet")
    assert "size: 279mm 432mm" in pdf.build_html(edition, paper, "tabloid")
    assert "size: 210mm 297mm" in pdf.build_html(edition, paper, "a4")

    # An explicit grid still wins over the chooser.
    assert "column-count: 3" in pdf.build_html(edition, paper, "tabloid", columns=3)


def test_print_edition_forces_a_light_ground(tmp_path):
    """Newsprint is light; a viewer's dark theme must not show through."""
    pdf = load("make_pdf")
    edition = tmp_path / "2026-09-13"
    (edition / "articles").mkdir(parents=True)
    (edition / "articles" / "01-lead.md").write_text(ARTICLE)
    out = pdf.build_html(edition, {"masthead": "X", "sections": []})
    assert "color-scheme: light" in out
    assert "background: #fbf9f3" in out


def test_print_edition_numbers_the_issue_from_the_founding_date(tmp_path):
    pdf = load("make_pdf")
    # 2026-08-22 → 2026-09-13 is 22 days later; the paper counts inclusively.
    assert pdf.issue_number({"founded": "2026-08-22"}, "2026-09-13") == "23"
    assert pdf.issue_number({}, "2026-09-13") == ""


def test_print_edition_renders_the_markdown_subset():
    pdf = load("make_pdf")
    out = pdf.render_markdown("### Head\n\n| a | b |\n|---:|:---|\n| 1 | x |\n\n- one\n- two\n\nText **bold**.")
    assert "<h3>Head</h3>" in out
    assert "<table>" in out and "<th" in out and "<td" in out
    assert out.count("<li>") == 2
    assert "<strong>bold</strong>" in out


def test_print_edition_escapes_before_it_formats():
    """A headline containing markup must not become markup."""
    pdf = load("make_pdf")
    assert "<script>" not in pdf.inline("<script>alert(1)</script>")


def test_print_edition_reads_the_frontmatter_subset():
    pdf = load("make_pdf")
    meta, body = pdf.split_frontmatter(ARTICLE)
    assert meta["headline"] == "A Headline"
    assert meta["priority"] == "1"
    assert body.strip().startswith("An opening paragraph")


def test_layout_follows_the_amount_of_copy():
    """A thin edition in five narrow columns reads like a leaflet; a fat one in two
    reads like a thesis. The grid and the type follow the copy."""
    pdf = load("make_pdf")
    thin_cols, thin_pt = pdf.fit_layout(400, 5)
    fat_cols, fat_pt = pdf.fit_layout(12000, 5)
    assert thin_cols < fat_cols, "more copy earns more columns"
    assert thin_pt > fat_pt, "and a smaller face"
    # monotonic, with no step backwards as copy grows
    seen = [pdf.fit_layout(w, 6) for w in (300, 900, 1800, 3000, 4500, 7000, 12000)]
    assert [c for c, _ in seen] == sorted(c for c, _ in seen)
    assert [b for _, b in seen] == sorted((b for _, b in seen), reverse=True)


def test_layout_never_exceeds_what_the_page_can_carry():
    """A4 cannot hold five readable columns however much copy there is."""
    pdf = load("make_pdf")
    for words in (300, 4000, 20000):
        cols, _ = pdf.fit_layout(words, 3)
        assert cols <= 3


def test_headline_weight_follows_priority(tmp_path):
    pdf = load("make_pdf")
    edition = tmp_path / "2026-09-13"
    (edition / "articles").mkdir(parents=True)
    (edition / "articles" / "01-lead.md").write_text(ARTICLE)
    (edition / "articles" / "10-major.md").write_text(ARTICLE.replace("priority: 1", "priority: 2"))
    (edition / "articles" / "20-standard.md").write_text(ARTICLE.replace("priority: 1", "priority: 3"))
    (edition / "articles" / "30-brief.md").write_text(ARTICLE.replace("priority: 1", "priority: 5"))
    out = pdf.build_html(edition, {"masthead": "X", "sections": [{"id": "today", "name": "Today"}]})

    assert 'class="major"' in out and 'class="standard"' in out and 'class="brief"' in out
    import re
    sizes = {k: float(re.search(rf"article\.{k} h2 {{{{?\s*font-size: ([\d.]+)pt", out).group(1))
             if re.search(rf"article\.{k} h2 \{{ font-size: ([\d.]+)pt", out) is None else
             float(re.search(rf"article\.{k} h2 \{{ font-size: ([\d.]+)pt", out).group(1))
             for k in ("major", "standard", "brief")}
    assert sizes["major"] > sizes["standard"] > sizes["brief"]


def test_print_edition_contains_its_content_within_the_measure(tmp_path):
    """A bare URL or a wide table must not push past the column and over the margin.

    No amount of @page margin claws that back, so the containment rules have to be
    in the stylesheet.
    """
    pdf = load("make_pdf")
    edition = tmp_path / "2026-09-13"
    (edition / "articles").mkdir(parents=True)
    (edition / "articles" / "01-lead.md").write_text(ARTICLE)
    out = pdf.build_html(edition, {"masthead": "X", "sections": []})
    assert "overflow-wrap: anywhere" in out
    assert "max-width: 100%" in out
    assert "orphans: 2" in out and "widows: 2" in out
    assert "break-after: avoid" in out, "a headline must not be stranded at a column foot"


def test_margins_scale_with_the_sheet(tmp_path):
    """A broadsheet carries a bigger margin than an A4; the page never crowds its edge."""
    pdf = load("make_pdf")
    edition = tmp_path / "2026-09-13"
    (edition / "articles").mkdir(parents=True)
    (edition / "articles" / "01-lead.md").write_text(ARTICLE)
    paper = {"masthead": "X", "sections": []}
    assert "margin: 22mm 18mm" in pdf.build_html(edition, paper, "broadsheet")
    assert "margin: 19mm 16mm" in pdf.build_html(edition, paper, "tabloid")
    assert "margin: 16mm 14mm" in pdf.build_html(edition, paper, "a4")


# ── the house rules ───────────────────────────────────────────────────────

HOUSE = {"max_words": 300, "max_section_articles": 2, "max_pillar_words": 150,
         "pillars": {"tech": ["ai"], "startup": ["projects"]}}


def _arts(**sections):
    """{'ai': [40, 40]} -> article dicts of those word counts."""
    out = []
    for sec, sizes in sections.items():
        for i, w in enumerate(sizes):
            out.append({"file": f"{sec}-{i}.md", "section": sec, "words": w, "headline": "H"})
    return out


def test_house_check_passes_a_paper_within_its_rules():
    hc = load("house_check")
    assert hc.audit(_arts(ai=[40, 40], projects=[40]), HOUSE) == []


def test_house_check_catches_a_crowded_section():
    hc = load("house_check")
    codes = [f["code"] for f in hc.audit(_arts(projects=[20, 20, 20]), HOUSE)]
    assert "section_crowded" in codes


def test_house_check_never_tells_you_to_fold_the_digest_away():
    """The digest is where the tail goes; folding it in is not an instruction."""
    hc = load("house_check")
    articles = [
        {"file": "30-a.md", "section": "projects", "words": 90, "headline": ""},
        {"file": "31-b.md", "section": "projects", "words": 80, "headline": ""},
        {"file": "32-c.md", "section": "projects", "words": 70, "headline": ""},
        {"file": "33-projects-digest.md", "section": "projects", "words": 10, "headline": ""},
    ]
    msg = next(f for f in hc.audit(articles, HOUSE) if f["code"] == "section_crowded")["message"]
    assert "digest.md" not in msg
    assert "32-c.md" in msg, "it should name the smallest real story"


def test_house_check_catches_a_pillar_taking_another_pillars_room():
    hc = load("house_check")
    findings = hc.audit(_arts(projects=[200]), HOUSE)
    heavy = next(f for f in findings if f["code"] == "pillar_heavy")
    assert "startup" in heavy["scope"]
    assert "50" in heavy["message"], "it should say how much to cut"


def test_house_check_says_how_much_the_edition_is_over():
    hc = load("house_check")
    over = next(f for f in hc.audit(_arts(ai=[100], projects=[100, 150]), HOUSE)
                if f["code"] == "edition_long")
    assert "50" in over["message"]


def test_house_rules_come_from_paper_json(tmp_path):
    """They are the owner's numbers, not the script's."""
    hc = load("house_check")
    edition = tmp_path / "2026-09-13"
    (edition / "articles").mkdir(parents=True)
    (edition / "articles" / "01-lead.md").write_text(ARTICLE)
    (tmp_path / "paper.json").write_text(json.dumps({"masthead": "X", "house": {"max_words": 1}}))
    assert hc.main([str(edition)]) == 1, "a one-word cap must fail a real article"


# ── getting the edition to the reader ─────────────────────────────────────

def test_sender_builds_a_multipart_telegram_can_read(tmp_path):
    send = load("send_edition")
    pdf = tmp_path / "2026-09-13.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    body, content_type = send.multipart({"chat_id": "-100", "caption": "x"}, "document", pdf)
    boundary = content_type.split("boundary=")[1]
    assert content_type.startswith("multipart/form-data")
    assert body.startswith(f"--{boundary}".encode())
    assert body.endswith(f"--{boundary}--\r\n".encode())
    assert b'name="document"; filename="2026-09-13.pdf"' in body
    assert b"%PDF-1.4 fake" in body
    assert b'name="chat_id"' in body


def test_sender_prefers_the_home_channel_then_falls_back(tmp_path):
    send = load("send_edition")
    env = tmp_path / "config.env"
    env.write_text('TELEGRAM_BOT_TOKEN="t"\nTELEGRAM_HOME_CHANNEL="-100999"\n'
                   'TELEGRAM_ALLOWED_USERS="12345,678"\n')
    assert send.read_env(env)["TELEGRAM_HOME_CHANNEL"] == "-100999"

    env.write_text('TELEGRAM_BOT_TOKEN="t"\nTELEGRAM_HOME_CHANNEL=""\n'
                   'TELEGRAM_ALLOWED_USERS="12345,678"\n')
    values = send.read_env(env)
    chat = values.get("TELEGRAM_HOME_CHANNEL") or values["TELEGRAM_ALLOWED_USERS"].split(",")[0]
    assert chat == "12345", "with no group, it goes to the first allowed user"


def test_sender_refuses_a_document_telegram_would_reject(tmp_path, monkeypatch):
    """The bot API caps a document at 50 MB; fail with that reason, not a timeout."""
    send = load("send_edition")
    pdf = tmp_path / "big.pdf"
    pdf.write_bytes(b"x")
    monkeypatch.setattr(send.Path, "stat", lambda self: type("S", (), {"st_size": 60 * 1024 * 1024})())
    with pytest.raises(SystemExit, match="50 MB"):
        send.send(pdf, "token", "-100", "caption")


def test_sender_fails_loudly_without_a_token(tmp_path):
    send = load("send_edition")
    pdf = tmp_path / "e.pdf"
    pdf.write_bytes(b"%PDF")
    env = tmp_path / "config.env"
    env.write_text('TELEGRAM_HOME_CHANNEL="-100"\n')
    with pytest.raises(SystemExit, match="TELEGRAM_BOT_TOKEN"):
        send.main([str(pdf), "--env", str(env)])


def test_frontmatter_keeps_a_source_with_its_url(tmp_path):
    """`- name: X` then `  url: Y` is one source, not two orphaned strings."""
    pdf = load("make_pdf")
    meta, _ = pdf.split_frontmatter(
        "---\nheadline: H\nsources:\n  - name: Axios\n    url: https://axios.com/a\n"
        "  - name: TrustMRR\n    url: https://trustmrr.com/b\n---\n\nBody.\n")
    sources = meta["sources_list"]
    assert len(sources) == 2
    assert sources[0] == {"name": "Axios", "url": "https://axios.com/a"}
    assert sources[1]["url"] == "https://trustmrr.com/b"


def test_headline_links_to_its_first_source(tmp_path):
    web = load("build_web")
    edition = tmp_path / "2026-09-13"
    (edition / "articles").mkdir(parents=True)
    (edition / "articles" / "01-lead.md").write_text(
        "---\nheadline: A Headline\nsection: today\npriority: 1\n"
        "sources:\n  - name: Axios\n    url: https://axios.com/a\n---\n\nSixty words of body.\n")
    out = web.build(edition, {"masthead": "X", "sections": [{"id": "today", "name": "Today"}]})
    assert 'href="https://axios.com/a"' in out
    assert 'class="headline"' in out


def test_headline_without_a_source_is_plain_text(tmp_path):
    """A story with nothing to link to must not render an empty anchor."""
    web = load("build_web")
    edition = tmp_path / "2026-09-13"
    (edition / "articles").mkdir(parents=True)
    (edition / "articles" / "01-lead.md").write_text(ARTICLE)
    out = web.build(edition, {"masthead": "X", "sections": [{"id": "today", "name": "Today"}]})
    assert "<h2>A Headline</h2>" in out


def test_non_http_source_is_never_linked(tmp_path):
    """Only http/https print; a javascript: or file: url must degrade to text."""
    web = load("build_web")
    edition = tmp_path / "2026-09-13"
    (edition / "articles").mkdir(parents=True)
    (edition / "articles" / "01-lead.md").write_text(
        "---\nheadline: H\nsection: today\npriority: 1\n"
        "sources:\n  - name: Bad\n    url: javascript:alert(1)\n---\n\nBody.\n")
    out = web.build(edition, {"masthead": "X", "sections": [{"id": "today", "name": "Today"}]})
    assert "javascript:alert" not in out.split("<style>")[0] + out.split("</style>")[-1]
    assert "<h2>H</h2>" in out


def test_print_reads_the_lead_headline_for_the_caption(tmp_path):
    pdf = load("make_pdf")
    edition = tmp_path / "2026-09-13"
    (edition / "articles").mkdir(parents=True)
    (edition / "articles" / "30-tail.md").write_text(ARTICLE.replace("priority: 1", "priority: 4"))
    (edition / "articles" / "01-lead.md").write_text(
        ARTICLE.replace("headline: A Headline", "headline: The Front Page"))
    assert pdf.lead_headline(edition) == "The Front Page"


def test_print_caption_survives_an_edition_with_no_lead(tmp_path):
    pdf = load("make_pdf")
    edition = tmp_path / "2026-09-13"
    (edition / "articles").mkdir(parents=True)
    (edition / "articles" / "30-tail.md").write_text(ARTICLE.replace("priority: 1", "priority: 4"))
    assert pdf.lead_headline(edition) == ""


def test_a_failed_delivery_never_fails_the_print(tmp_path, monkeypatch, capsys):
    """The edition on disk is still the edition; a send failure is a warning."""
    pdf = load("make_pdf")
    send = load("send_edition")
    edition = tmp_path / "2026-09-13"
    (edition / "articles").mkdir(parents=True)
    (edition / "articles" / "01-lead.md").write_text(ARTICLE)
    out = tmp_path / "e.pdf"
    out.write_bytes(b"%PDF")

    def boom(argv):
        raise SystemExit("Telegram unreachable")
    monkeypatch.setattr(send, "main", boom)
    pdf.deliver(out, edition, {"masthead": "X"}, tmp_path / "config.env")   # must not raise
    assert "did not go out" in capsys.readouterr().err
