#!/usr/bin/env python3
"""Set an edition for print and render it to PDF.

The reader is a screen-paginated web app with no print stylesheet, so printing it
gives nothing useful. This builds its own print HTML from the same markdown the
reader consumes — one narrow column, real page breaks, the chart plates inline —
and hands it to headless Chromium.

Chromium comes from wherever it already is: the Playwright cache the agent host
already carries, or a system chrome. Nothing is installed.

Standard library only. Markdown is rendered by a deliberately small subset — the
edition format allows headings to ###, bullets, pipe tables, bold/italic, links
and images, and nothing else (docs/FORMAT.md), so a full parser would be more
surface than the job needs.

Usage:
    make_pdf.py <edition_dir> [--out FILE] [--chrome PATH]
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import tempfile
from pathlib import Path

CHROME_CANDIDATES = [
    "/root/.cache/ms-playwright/chromium-*/chrome-linux64/chrome",
    "/root/.cache/ms-playwright/chromium_headless_shell-*/chrome-linux64/headless_shell",
    "~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome",
    "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]

# Page sizes a paper is actually set at. Broadsheet is the real thing; tabloid and
# berliner are what compacts use; a4 exists for anyone printing at home.
SIZES = {
    # width, height, and how much column room the page can carry before the
    # measure gets too narrow to read. The count itself is chosen from content.
    # width, height, column ceiling, and the margin the sheet is printed with.
    # A bigger sheet carries a bigger margin; the page never crowds its edge.
    "broadsheet": ("305mm", "560mm", 6, "22mm", "18mm"),
    "tabloid":    ("279mm", "432mm", 5, "19mm", "16mm"),
    "berliner":   ("315mm", "470mm", 5, "20mm", "17mm"),
    "a3":         ("297mm", "420mm", 5, "19mm", "16mm"),
    "a4":         ("210mm", "297mm", 3, "16mm", "14mm"),
}


def measure(parsed: list[dict]) -> int:
    """Words in the edition — the number the layout is chosen from."""
    return sum(len(re.findall(r"\S+", a["body"])) for a in parsed)


def fit_layout(words: int, ceiling: int) -> tuple[int, float]:
    """Pick a column count and body size for this much copy.

    A thin edition set in five narrow columns reads like a leaflet with gaps; a
    fat one set in two reads like a thesis. So the grid follows the copy: fewer,
    wider columns and larger type when there is little to say, more and smaller
    when there is a lot — never past what the page can carry.
    """
    for limit, cols, body in (
        (700,  2, 11.4),
        (1400, 3, 10.8),
        (2400, 3, 10.2),
        (3800, 4, 9.9),
        (5600, 4, 9.5),
        (8000, 5, 9.2),
    ):
        if words <= limit:
            return min(cols, ceiling), body
    return min(6, ceiling), 8.9


STYLE = """
@page {{ size: {w} {h}; margin: {mv} {mh}; }}
@media print {{ body {{ background: #fff; }} }}

html {{ color-scheme: light; }}
html, body {{ margin: 0; padding: 0; }}

/* Nothing may cross the measure. A bare URL or a long product name would
   otherwise push past its column and out over the page margin, which no amount
   of @page margin can claw back. */
* {{ overflow-wrap: anywhere; word-break: normal; }}
p, li, td, th, .deck, .caption, .sources {{ orphans: 2; widows: 2; }}
body {{
  background: #fbf9f3; color: #1a1712;
  font-family: "Source Serif 4", "Georgia", "Times New Roman", serif;
  font-size: {body}pt; line-height: 1.46;
  text-rendering: optimizeLegibility;
  -webkit-font-feature-settings: "kern" 1, "liga" 1, "onum" 1;
}}

.masthead {{ text-align: center; border-bottom: 1pt solid #1a1712;
            padding-bottom: {gap}pt; margin: 0 0 {gap3}pt; }}
.masthead h1 {{ font-family: "Playfair Display", "Didot", Georgia, serif;
  font-size: {mast}pt; font-weight: 900; letter-spacing: -1pt; margin: 0; line-height: 0.95; }}
.masthead .rule {{ display: flex; justify-content: space-between; align-items: baseline;
  margin-top: 7pt; font-size: 7pt; text-transform: uppercase; letter-spacing: 1.8pt;
  color: #6b6154; }}
.masthead .motto {{ font-style: italic; text-transform: none; letter-spacing: 0; font-size: 8pt; }}

.lead {{ margin: 0 0 {gap3}pt; padding-bottom: {gap2}pt;
         border-bottom: 0.6pt solid #d8d0c0; break-inside: avoid; }}
.lead h2 {{ font-family: "Playfair Display", Georgia, serif; font-size: {leadsize}pt;
  line-height: 1.06; font-weight: 900; text-align: center; margin: 0 0 7pt;
  letter-spacing: -0.4pt; }}
.lead .deck {{ text-align: center; font-size: {deck}pt; font-style: italic; color: #4a4238;
  margin: 0 auto 12pt; max-width: 74%; line-height: 1.4; }}
.lead .flow {{ column-count: {leadcols}; column-gap: 9mm; }}
.lead .flow > p:first-of-type::first-letter {{
  float: left; font-family: "Playfair Display", Georgia, serif; font-size: {dropcap}pt;
  line-height: 0.76; font-weight: 900; padding: 3pt 5pt 0 0; }}

.paper {{ column-count: {cols}; column-gap: 9mm;
         text-align: justify; hyphens: auto; -webkit-hyphens: auto; }}

article {{ break-inside: avoid-column; margin: 0 0 {gap3}pt; }}
article.long {{ break-inside: auto; }}

.section-head {{ column-span: all; border-bottom: 0.8pt solid #1a1712;
  margin: {gap2}pt 0 {gap2}pt; padding-bottom: 3pt; break-after: avoid; break-inside: avoid;
  font-family: "Playfair Display", Georgia, serif; font-size: 8.5pt; font-weight: 700;
  text-transform: uppercase; letter-spacing: 3.4pt; color: #1a1712; }}

h2 {{ font-family: "Playfair Display", Georgia, serif; line-height: 1.14;
  font-weight: 700; margin: 0 0 {gap}pt; text-align: left; letter-spacing: -0.1pt;
  break-after: avoid; }}
/* Weight follows priority: a section's lead story is set larger than its tail,
   which is how a reader sees what matters without being told. */
article.major h2 {{ font-size: {h_major}pt; line-height: 1.08; }}
article.standard h2 {{ font-size: {h_standard}pt; }}
article.brief h2 {{ font-size: {h_brief}pt; font-family: "Source Serif 4", Georgia, serif;
  font-weight: 700; letter-spacing: 0; }}
article.major {{ margin-bottom: {gap3}pt; }}
article.brief {{ margin-bottom: {gap2}pt; }}
article.brief .deck {{ display: none; }}
.deck {{ font-style: italic; color: #4a4238; font-size: {deck}pt; margin: 0 0 6pt;
        text-align: left; line-height: 1.34; }}
.byline {{ font-size: 6pt; text-transform: uppercase; letter-spacing: 1.2pt; color: #8a8073;
  margin: 0 0 6pt; text-align: left; }}

p {{ margin: 0 0 {gap}pt; }}
p + p {{ text-indent: 1.15em; }}
ul {{ margin: 0 0 7pt; padding-left: 0; list-style: none; }}
li {{ margin: 0 0 5pt; text-align: left; padding-left: 8pt; text-indent: -8pt; }}
li::before {{ content: "— "; color: #a89e8e; }}
h3 {{ font-size: 6.4pt; text-transform: uppercase; letter-spacing: 1.5pt; color: #8a8073;
  margin: 9pt 0 4pt; text-align: left; font-weight: 600; }}

/* auto, not fixed: fixed contains but forces equal columns, which wraps a name
   onto three lines beside a two-character rank. overflow-wrap above is what
   actually keeps a long cell inside the measure. */
table {{ border-collapse: collapse; width: 100%; max-width: 100%; table-layout: auto;
        font-size: {tbl}pt; margin: 2pt 0 {gap2}pt; break-inside: avoid; }}
th:first-child, td:first-child {{ width: 1.4em; }}
th, td {{ padding: 2.6pt 5pt 2.6pt 0; text-align: left; border: 0; }}
th:last-child, td:last-child {{ padding-right: 0; }}
th {{ font-size: 5.9pt; text-transform: uppercase; letter-spacing: 0.7pt; color: #8a8073;
     border-bottom: 0.6pt solid #1a1712; font-weight: 600; }}
tbody tr + tr td {{ border-top: 0.3pt solid #e8e1d4; }}
/* Right-aligned figures keep their gutter — only the last column loses it,
   or the rank runs straight into the name beside it. */
td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums lining-nums; }}

img {{ max-width: 100%; height: auto; margin: 4pt 0 3pt; break-inside: avoid;
      filter: grayscale(100%) contrast(105%); }}
.caption {{ font-size: 6.4pt; font-style: italic; color: #6b6154; margin: 0 0 8pt;
  line-height: 1.35; text-align: left; }}

a {{ color: inherit; text-decoration: none; }}
.sources {{ font-size: 5.8pt; color: #a89e8e; margin-top: 5pt; text-align: left;
           line-height: 1.3; }}
strong {{ font-weight: 700; }}
code {{ font-family: "SF Mono", Menlo, monospace; font-size: 6.4pt; }}
"""




def find_chrome(explicit: str | None) -> str:
    if explicit:
        return explicit
    for pattern in CHROME_CANDIDATES:
        expanded = Path(pattern).expanduser()
        if "*" in pattern:
            matches = sorted(Path(expanded.anchor).glob(str(expanded.relative_to(expanded.anchor))))
            if matches:
                return str(matches[-1])
        elif expanded.exists():
            return str(expanded)
    raise SystemExit(
        "no Chromium found. Pass --chrome PATH, or install one.\n"
        "  (the agent host usually has one under ~/.cache/ms-playwright/)"
    )


def split_frontmatter(text: str) -> tuple[dict, str]:
    """The subset of YAML the edition format uses — scalars and simple lists."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    raw, body = text[3:end], text[end + 4:]
    meta: dict = {}
    key = None
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if re.match(r"^\s+-\s", line) and key:
            meta.setdefault(key + "_list", []).append(line.strip()[2:].strip())
        elif re.match(r"^\s+\w+:", line) and key:
            continue                                   # nested (chart:) — not needed in print
        elif ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if value:
                meta[key] = value
    return meta, body


def inline(text: str) -> str:
    out = html.escape(text)
    out = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


def render_markdown(body: str) -> str:
    lines, out, table = body.strip().splitlines(), [], []

    def flush_table():
        if not table:
            return
        head, rest = table[0], table[2:] if len(table) > 2 else []
        aligns = []
        if len(table) > 1:
            aligns = ["num" if cell.strip().endswith("-:") else ""
                      for cell in table[1].strip("|").split("|")]
        cells = [c.strip() for c in head.strip("|").split("|")]
        out.append("<table><thead><tr>" + "".join(
            f'<th class="{aligns[i] if i < len(aligns) else ""}">{inline(c)}</th>'
            for i, c in enumerate(cells)) + "</tr></thead><tbody>")
        for row in rest:
            cells = [c.strip() for c in row.strip("|").split("|")]
            out.append("<tr>" + "".join(
                f'<td class="{aligns[i] if i < len(aligns) else ""}">{inline(c)}</td>'
                for i, c in enumerate(cells)) + "</tr>")
        out.append("</tbody></table>")
        table.clear()

    in_list = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            table.append(stripped)
            continue
        flush_table()
        if not stripped:
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if stripped.startswith("###"):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h3>{inline(stripped.lstrip('#').strip())}</h3>")
        elif stripped.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(stripped[2:])}</li>")
        elif stripped.startswith("> "):
            out.append(f'<p class="caption">{inline(stripped[2:])}</p>')
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p>{inline(stripped)}</p>")
    if in_list:
        out.append("</ul>")
    flush_table()
    return "\n".join(out)


def issue_number(paper: dict, edition_date: str) -> str:
    """Days since the paper was founded — the same arithmetic the reader uses."""
    from datetime import date
    founded = paper.get("founded")
    if not founded:
        return ""
    try:
        started = date.fromisoformat(founded)
        today = date.fromisoformat(edition_date)
    except ValueError:
        return ""
    return str((today - started).days + 1)


def read_paper(editions_root: Path) -> dict:
    meta = {}
    target = editions_root / "paper.json"
    if target.is_file():
        import json
        meta = json.loads(target.read_text())
    return meta


def build_html(edition_dir: Path, paper: dict, size: str = "tabloid",
               columns: int | None = None) -> str:
    """The edition as one print-ready newspaper page-flow."""
    articles = sorted((edition_dir / "articles").glob("*.md"))
    if not articles:
        raise SystemExit(f"no articles in {edition_dir}")

    width, height, ceiling, margin_v, margin_h = SIZES[size]

    order = {sec["id"]: i for i, sec in enumerate(paper.get("sections") or [])}
    parsed = []
    for path in articles:
        meta, body = split_frontmatter(path.read_text())
        section = (meta.get("section") or "misc").lower()
        try:
            priority = int(meta.get("priority") or 5)
        except ValueError:
            priority = 5
        parsed.append({"order": order.get(section, 99), "priority": priority,
                       "name": path.name, "meta": meta, "body": body, "section": section})
    parsed.sort(key=lambda a: (a["order"], a["priority"], a["name"]))

    words = measure(parsed)
    auto_cols, body_pt = fit_layout(words, ceiling)
    cols = columns or auto_cols
    if columns:                      # an explicit grid still gets a sane measure
        body_pt = max(8.8, min(11.6, body_pt * (auto_cols / cols) ** 0.5))

    # Everything else is a ratio of the body size, so the page scales as one thing.
    style = STYLE.format(
        w=width, h=height, mv=margin_v, mh=margin_h, cols=cols,
        body=round(body_pt, 2),
        gap=round(body_pt * 0.62, 2),      # the vertical unit everything spaces by
        gap2=round(body_pt * 1.3, 2),
        gap3=round(body_pt * 1.85, 2),
        tbl=round(body_pt * 0.72, 2),
        mast=round(body_pt * (5.2 if cols >= 4 else 4.2), 1),
        leadsize=round(body_pt * (3.3 if cols >= 4 else 2.6), 1),
        deck=round(body_pt * 0.82, 2),
        leadcols=max(2, cols - 1),
        dropcap=round(body_pt * 3.4, 1),
        h_major=round(body_pt * 1.5, 2),
        h_standard=round(body_pt * 1.24, 2),
        h_brief=round(body_pt * 1.04, 2),
    )

    names = {sec["id"]: sec["name"] for sec in (paper.get("sections") or [])}

    date_str = edition_dir.name
    number = issue_number(paper, date_str)
    masthead = paper.get("masthead", "The Daily")

    def article_html(entry: dict, *, lead: bool = False) -> str:
        meta, body = entry["meta"], entry["body"]
        out = []
        # A long piece may break across columns; a short one should not be split.
        long = len(body) > 1400
        weight = ("major" if entry["priority"] <= 2
                  else "standard" if entry["priority"] == 3 else "brief")
        classes = " ".join(filter(None, [weight, "long" if long else ""]))
        out.append(f'<article class="{classes}">' if not lead else "")
        out.append(f'<h2>{inline(meta.get("headline", ""))}</h2>')
        if meta.get("deck"):
            out.append(f'<p class="deck">{inline(meta["deck"])}</p>')
        # A byline on every one of sixteen items is noise; the lead and the
        # section's lead story carry one, the tail does not.
        if meta.get("byline") and (lead or entry["priority"] <= 2):
            out.append(f'<div class="byline">By {html.escape(meta["byline"])}</div>')

        inner = []
        plate = edition_dir / "images" / f"{meta.get('id', '')}-chart.png"
        if plate.is_file():
            inner.append(f'<img src="{plate.as_uri()}" alt="">')
            if meta.get("caption"):
                inner.append(f'<p class="caption">{inline(meta["caption"])}</p>')
        inner.append(render_markdown(body))
        sources = [x for x in (meta.get("sources_list") or []) if not x.startswith("url:")]
        if sources and (lead or entry["priority"] <= 2):
            inner.append('<div class="sources">Sources: '
                         + "; ".join(html.escape(x.replace("name:", "").strip()) for x in sources)
                         + "</div>")

        if lead:
            out.append('<div class="flow">' + "\n".join(inner) + "</div>")
        else:
            out.append("\n".join(inner))
            out.append("</article>")
        return "\n".join(out)

    chunks = [
        '<div class="masthead">',
        f"<h1>{html.escape(masthead)}</h1>",
        '<div class="rule">',
        f"<span>Vol. 1 &nbsp;·&nbsp; No. {number}</span>" if number else "<span></span>",
        f'<span class="motto">{html.escape(paper.get("motto", ""))}</span>',
        f"<span>{html.escape(date_str)}</span>",
        "</div></div>",
    ]

    lead = next((a for a in parsed if a["priority"] == 1), None)
    if lead:
        chunks.append('<div class="lead">' + article_html(lead, lead=True) + "</div>")

    chunks.append('<div class="paper">')
    current = None
    for entry in parsed:
        if entry is lead:
            continue
        if entry["section"] != current:
            current = entry["section"]
            label = names.get(current, current.title())
            chunks.append(f'<div class="section-head">{html.escape(label)}</div>')
        chunks.append(article_html(entry))
    chunks.append("</div>")

    return (f"<!doctype html><meta charset='utf-8'><title>{html.escape(masthead)} "
            f"{html.escape(date_str)}</title><style>{style}</style>" + "\n".join(chunks))


def to_pdf(html_text: str, out: Path, chrome: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "edition.html"
        source.write_text(html_text)
        cmd = [
            chrome, "--headless", "--disable-gpu", "--no-sandbox",
            "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
            # the @page size is authoritative; without this Chromium refits to Letter
            "--print-to-pdf-no-header",
            "--virtual-time-budget=10000",
            f"--print-to-pdf={out}", source.as_uri(),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if not out.is_file():
            raise SystemExit(f"chromium did not write a PDF:\n{result.stderr[-800:]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edition_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--chrome", default=None)
    parser.add_argument("--size", choices=sorted(SIZES), default="tabloid",
                        help="page size; broadsheet is the full-size original")
    parser.add_argument("--columns", type=int, default=None,
                        help="override the column count for the size")
    args = parser.parse_args(argv)

    edition = args.edition_dir.expanduser().resolve()
    paper = read_paper(edition.parent)
    out = (args.out or edition / f"{edition.name}.pdf").expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    to_pdf(build_html(edition, paper, args.size, args.columns),
           out, find_chrome(args.chrome))
    size = out.stat().st_size
    print(f"wrote {out} ({size // 1024} KB, {args.size}"
          f"{f', {args.columns} cols' if args.columns else ''})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
