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
    "broadsheet": ("305mm", "560mm", 6),
    "tabloid":    ("279mm", "432mm", 5),
    "berliner":   ("315mm", "470mm", 5),
    "a3":         ("297mm", "420mm", 5),
    "a4":         ("210mm", "297mm", 3),
}

STYLE = """
@page {{ size: {w} {h}; margin: 13mm 11mm 15mm; }}
@media print {{ body {{ background: #fff; }} }}

html, body {{ margin: 0; padding: 0; }}
/* Newsprint is a light surface, always. Without this the viewer's dark theme
   shows through on screen and the page renders dark-on-dark. */
html {{ color-scheme: light; }}
body {{
  background: #fbf9f3; color: #16130d;
  font-family: "Source Serif 4", "Georgia", "Times New Roman", serif;
  font-size: {body}pt; line-height: 1.33;
  text-rendering: optimizeLegibility;
  -webkit-font-feature-settings: "kern" 1, "liga" 1, "onum" 1;
}}

/* ── the masthead: full measure, once, on page one ───────────────── */
.masthead {{ text-align: center; border-bottom: 3pt double #16130d; padding-bottom: 5pt;
             margin: 0 0 7pt; }}
.masthead h1 {{ font-family: "Playfair Display", "Didot", "Bodoni MT", Georgia, serif;
  font-size: {mast}pt; font-weight: 900; letter-spacing: -1pt; margin: 0; line-height: 0.95; }}
.masthead .rule {{ display: flex; justify-content: space-between; align-items: baseline;
  border-top: 0.6pt solid #16130d; margin-top: 5pt; padding-top: 3pt;
  font-size: 7pt; text-transform: uppercase; letter-spacing: 1.6pt; color: #4a433a; }}
.masthead .motto {{ font-style: italic; text-transform: none; letter-spacing: 0; font-size: 8pt; }}

/* ── the lead: spans the page, then breaks into its own columns ──── */
.lead {{ border-bottom: 1.2pt solid #16130d; padding-bottom: 7pt; margin: 0 0 8pt; }}
.lead h2 {{ font-family: "Playfair Display", Georgia, serif; font-size: {leadsize}pt;
  line-height: 1.02; font-weight: 900; text-align: center; margin: 2pt 0 4pt;
  letter-spacing: -0.4pt; }}
.lead .deck {{ text-align: center; font-size: {deck}pt; font-style: italic; color: #3d3730;
  margin: 0 auto 6pt; max-width: 82%; line-height: 1.3; }}
.lead .flow {{ column-count: {leadcols}; column-gap: 6mm; column-rule: 0.4pt solid #c8c0b0; }}
.lead .flow > p:first-of-type::first-letter {{
  float: left; font-family: "Playfair Display", Georgia, serif; font-size: {dropcap}pt;
  line-height: 0.78; font-weight: 900; padding: 2pt 3pt 0 0; }}

/* ── the body of the paper flows in columns ─────────────────────── */
.paper {{ column-count: {cols}; column-gap: 5mm; column-rule: 0.4pt solid #c8c0b0;
          text-align: justify; hyphens: auto; -webkit-hyphens: auto; }}

article {{ break-inside: avoid-column; margin: 0 0 9pt; padding-bottom: 7pt;
           border-bottom: 0.4pt solid #ddd6c8; }}
article.long {{ break-inside: auto; }}

.section-head {{ column-span: all; border-top: 1.6pt solid #16130d;
  border-bottom: 0.5pt solid #16130d; margin: 6pt 0 7pt; padding: 2pt 0;
  font-family: "Playfair Display", Georgia, serif; font-size: 10pt; font-weight: 700;
  text-transform: uppercase; letter-spacing: 3pt; text-align: center; }}

h2 {{ font-family: "Playfair Display", Georgia, serif; font-size: {head}pt; line-height: 1.08;
  font-weight: 700; margin: 0 0 3pt; text-align: left; letter-spacing: -0.2pt; }}
.deck {{ font-style: italic; color: #4a433a; font-size: {deck}pt; margin: 0 0 4pt;
         text-align: left; line-height: 1.25; }}
.byline {{ font-size: 6.2pt; text-transform: uppercase; letter-spacing: 1.1pt; color: #6d6558;
  margin: 0 0 4pt; text-align: left; }}

p {{ margin: 0 0 4pt; }}
p + p {{ text-indent: 1.1em; }}
ul {{ margin: 0 0 5pt; padding-left: 10pt; }}
li {{ margin: 0 0 2.5pt; text-align: left; }}
h3 {{ font-size: 6.6pt; text-transform: uppercase; letter-spacing: 1.3pt; color: #4a433a;
  margin: 6pt 0 3pt; border-bottom: 0.4pt solid #c8c0b0; padding-bottom: 1.5pt;
  text-align: left; }}

table {{ border-collapse: collapse; width: 100%; font-size: 6.4pt; margin: 0 0 5pt;
         break-inside: avoid; }}
th, td {{ border-bottom: 0.35pt solid #ddd6c8; padding: 1.6pt 2.4pt; text-align: left; }}
th {{ font-size: 5.9pt; text-transform: uppercase; letter-spacing: 0.5pt; color: #4a433a;
      border-bottom: 0.7pt solid #16130d; }}
td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums lining-nums; }}

img {{ max-width: 100%; height: auto; margin: 3pt 0 2pt; break-inside: avoid;
       filter: grayscale(100%) contrast(108%); }}
.caption {{ font-size: 6.2pt; font-style: italic; color: #4a433a; margin: 0 0 5pt;
  line-height: 1.25; text-align: left; border-bottom: 0.4pt solid #c8c0b0; padding-bottom: 3pt; }}

a {{ color: inherit; text-decoration: none; }}
.sources {{ font-size: 5.8pt; color: #6d6558; margin-top: 3pt; text-align: left;
            line-height: 1.2; }}
strong {{ font-weight: 700; }}
code {{ font-family: "SF Mono", Menlo, monospace; font-size: 6pt; }}
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

    width, height, default_cols = SIZES[size]
    cols = columns or default_cols
    # Type scales with the measure: a broadsheet column is wider, so it can carry
    # a larger face without the line getting too long to track.
    body_pt = 9.2 if cols >= 6 else 9.0 if cols >= 5 else 9.6
    style = STYLE.format(
        w=width, h=height, cols=cols, body=body_pt,
        mast=64 if cols >= 6 else 54 if cols >= 5 else 40,
        leadsize=34 if cols >= 6 else 30 if cols >= 5 else 24,
        head=12.5 if cols >= 5 else 13.5,
        deck=7.6 if cols >= 5 else 8.2,
        leadcols=max(2, cols - 2),
        dropcap=34 if cols >= 5 else 28,
    )

    order = {s["id"]: i for i, s in enumerate(paper.get("sections") or [])}
    names = {s["id"]: s["name"] for s in (paper.get("sections") or [])}

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

    date_str = edition_dir.name
    number = issue_number(paper, date_str)
    masthead = paper.get("masthead", "The Daily")

    def article_html(entry: dict, *, lead: bool = False) -> str:
        meta, body = entry["meta"], entry["body"]
        out = []
        # A long piece may break across columns; a short one should not be split.
        long = len(body) > 1400
        out.append(f'<article class="{"long" if long else ""}">' if not lead else "")
        out.append(f'<h2>{inline(meta.get("headline", ""))}</h2>')
        if meta.get("deck"):
            out.append(f'<p class="deck">{inline(meta["deck"])}</p>')
        if meta.get("byline"):
            out.append(f'<div class="byline">By {html.escape(meta["byline"])}</div>')

        inner = []
        plate = edition_dir / "images" / f"{meta.get('id', '')}-chart.png"
        if plate.is_file():
            inner.append(f'<img src="{plate.as_uri()}" alt="">')
            if meta.get("caption"):
                inner.append(f'<p class="caption">{inline(meta["caption"])}</p>')
        inner.append(render_markdown(body))
        sources = [x for x in (meta.get("sources_list") or []) if not x.startswith("url:")]
        if sources:
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
