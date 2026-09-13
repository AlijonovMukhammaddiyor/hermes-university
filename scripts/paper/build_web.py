#!/usr/bin/env python3
"""Render an edition as a screen page — the same paper, read on a phone.

The print build sets a fixed sheet; a screen has no sheet, so the measure has to
reflow: three columns on a desk, two on a tablet, one in a hand. Chart plates are
inlined as data URIs so the page is a single self-contained file.

Emits body-level HTML (title + style + content, no document wrapper), which is
what the Artifact publisher expects.

Usage:
    build_web.py <edition_dir> [--out FILE]
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_pdf import inline, issue_number, render_markdown, split_frontmatter  # noqa: E402

STYLE = """
:root {
  --ground: #f7f4ec; --ink: #17140f; --muted: #6f6659; --rule: #d9d2c2;
  --rule-strong: #17140f; --accent: #9c2b1b; --plate: #efeadd;
  /* One spacing rhythm. Every gap below is a step on it, so the page breathes
     evenly instead of drifting with hand-picked values. */
  --s1: 0.45rem; --s2: 0.85rem; --s3: 1.5rem; --s4: 2.6rem; --s5: 4rem;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground: #14120f; --ink: #ece6da; --muted: #9b9284; --rule: #2f2a23;
    --rule-strong: #6d6558; --accent: #e0784f; --plate: #1d1a15;
  }
}
:root[data-theme="dark"] {
  --ground: #14120f; --ink: #ece6da; --muted: #9b9284; --rule: #2f2a23;
  --rule-strong: #6d6558; --accent: #e0784f; --plate: #1d1a15;
}

/* The host paints its own ground behind the page and its own wrapper around it,
   so setting html/body is not enough — the surround stayed white. A fixed
   full-viewport layer behind everything is the one thing no ancestor can undo. */
html, body { background: var(--ground); }
body::before { content: ""; position: fixed; inset: 0; background: var(--ground);
  z-index: -1; pointer-events: none; }
body { background: var(--ground); color: var(--ink);
  font-family: "Source Serif 4", Georgia, "Times New Roman", serif;
  font-size: 17px; line-height: 1.66; margin: 0;
  font-variant-numeric: oldstyle-nums; -webkit-font-smoothing: antialiased; }
.sheet { background: var(--ground); max-width: 1220px; margin: 0 auto; padding: var(--s5) var(--s3) calc(var(--s5) * 1.5); }

.masthead { text-align: center; border-bottom: 2px solid var(--rule-strong);
  padding-bottom: var(--s2); margin-bottom: var(--s2); }
.masthead h1 { font-family: "Playfair Display", Georgia, serif; font-weight: 900;
  font-size: clamp(2.4rem, 8.5vw, 5.2rem); line-height: 0.94; letter-spacing: -0.02em;
  margin: 0; text-wrap: balance; }
.folio { display: flex; flex-wrap: wrap; gap: 10px 20px; justify-content: space-between;
  align-items: baseline; font-size: 0.7rem; text-transform: uppercase;
  letter-spacing: 0.16em; color: var(--muted); margin: var(--s2) 0 var(--s5);
  font-variant-numeric: lining-nums tabular-nums; }
.folio .motto { text-transform: none; letter-spacing: 0; font-style: italic; font-size: 0.85rem; }

.lead { border-bottom: 1px solid var(--rule); padding-bottom: var(--s5);
  margin-bottom: var(--s5); }
.lead h2 { font-family: "Playfair Display", Georgia, serif; font-weight: 900;
  font-size: clamp(1.85rem, 5.2vw, 3.1rem); line-height: 1.06; letter-spacing: -0.015em;
  text-align: center; margin: 0 0 var(--s3); text-wrap: balance; }
.lead .deck { text-align: center; font-style: italic; color: var(--muted);
  font-size: 1.06rem; max-width: 46ch; margin: 0 auto var(--s4); line-height: 1.5; }
.lead .flow { columns: 2 21rem; column-gap: var(--s4); }
.lead .flow > p:first-of-type::first-letter { float: left; font-family: "Playfair Display", Georgia, serif;
  font-size: 3.5em; line-height: 0.76; font-weight: 900; padding: 0.06em 0.09em 0 0; color: var(--accent); }

/* A wider minimum column: three cramped measures is most of what made this
   feel dense, so the grid drops to two before it squeezes. */
/* A modular grid, not a flow. Stories are rectangles spanning a whole number of
   columns; the span is what encodes importance, and the reader sees where one
   story ends without reading a word. `columns:` here is what made the page read
   as a journal. */
.body { display: grid; grid-template-columns: repeat(6, 1fr);
  grid-auto-flow: dense;
        column-gap: var(--s4); row-gap: var(--s5); align-items: start; }

/* Span for rank. The text inside still sets in a narrow measure — a four-column
   story has four columns of text, never four-column-long lines. */
article.major { grid-column: span 3; }
article.major .cols { columns: 2; column-gap: var(--s3); }
article.standard { grid-column: span 2; }
/* The rail: one column. Three distinct widths on the page (3 / 2 / 1) is what
   lets a reader rank the stories by shape before reading any of them; two
   widths reads as a two-column layout with a wide bit. */
article.brief { grid-column: span 1; }
article.brief h2 { font-size: 0.98rem; }

/* The rail: short items live in one narrow column so they do not fragment the
   grid, and the reader learns where the briefs are. */
article.digest { grid-column: span 2; background: var(--plate);
  padding: var(--s3); border-top: 2px solid var(--rule-strong); }
article.digest h2 { font-size: 1rem; }

/* A hairline separates adjacent STORIES — never the columns inside one. */
article + article { border-left: 1px solid var(--rule); padding-left: var(--s3); }
article.digest + article, article + article.digest { border-left: 0; }

@media (max-width: 1000px) {
  .body { grid-template-columns: repeat(2, 1fr); }
  article.major { grid-column: 1 / -1; }
  article.major .cols { columns: 2; }
  article.standard, article.brief, article.digest { grid-column: span 1; }
}
@media (max-width: 680px) {
  .body { grid-template-columns: 1fr; row-gap: var(--s4); }
  article, article.major, article.standard, article.brief, article.digest { grid-column: 1 / -1; }
  article.major .cols { columns: 1; }
  article + article { border-left: 0; padding-left: 0; border-top: 1px solid var(--rule);
    padding-top: var(--s4); }
}
article { break-inside: avoid; margin: 0; }
article.long { break-inside: auto; }


article.brief .deck { display: none; }

.section-head { grid-column: 1 / -1; border-bottom: 1.5px solid var(--rule-strong);
  margin: var(--s5) 0 var(--s4); padding-bottom: var(--s1); font-family: "Playfair Display", Georgia, serif;
  font-size: 0.82rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3em;
  color: var(--accent); }

h2 { font-family: "Playfair Display", Georgia, serif; font-weight: 700; margin: 0 0 var(--s2);
  line-height: 1.16; text-wrap: balance; }
article.major h2 { font-size: 1.42rem; }
article.standard h2 { font-size: 1.2rem; }
/* One display face throughout. Hierarchy is carried by size and weight, not by
   swapping the typeface — a second face in the headlines reads as inconsistency,
   not as rank. */
article.brief h2 { font-size: 1.04rem; font-weight: 700; }
.deck { font-style: italic; color: var(--muted); font-size: 0.95rem; margin: 0 0 var(--s2);
  line-height: 1.5; }
.byline { font-size: 0.64rem; text-transform: uppercase; letter-spacing: 0.14em;
  color: var(--muted); margin: 0 0 var(--s3); }

p { margin: 0 0 var(--s2); }
p + p { text-indent: 1.1em; }
ul { margin: var(--s2) 0 var(--s3); padding: 0; list-style: none; }
li { margin: 0 0 var(--s2); padding-left: 1em; text-indent: -1em; }
li::before { content: "—\\00a0"; color: var(--accent); }
h3 { font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.17em; color: var(--muted);
  margin: var(--s3) 0 var(--s1); font-weight: 600; }

.scroll { overflow-x: auto; margin: var(--s2) 0 var(--s3); }
table { border-collapse: collapse; width: 100%; font-size: 0.78rem;
  font-variant-numeric: lining-nums tabular-nums; }
th, td { padding: var(--s1) var(--s2) var(--s1) 0; text-align: left; }
th:last-child, td:last-child { padding-right: 0; }
th { font-size: 0.64rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted);
  border-bottom: 1.5px solid var(--rule-strong); font-weight: 600; white-space: nowrap; }
tbody tr + tr td { border-top: 1px solid var(--rule); }
td.num, th.num { text-align: right; }
th:first-child, td:first-child { width: 1.6em; }

img { max-width: 100%; height: auto; display: block; margin: var(--s2) 0 var(--s1);
  background: var(--plate); border: 1px solid var(--rule); }
:root[data-theme="dark"] img, :root:not([data-theme="light"]) img { filter: invert(1) hue-rotate(180deg); }
@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) img { filter: none; } }
:root[data-theme="light"] img { filter: none; }
.caption { font-size: 0.72rem; font-style: italic; color: var(--muted); margin: 0 0 1em;
  line-height: 1.4; }

a { color: inherit; text-decoration: none; border-bottom: 1px solid var(--accent); }
/* The headline is the link; it keeps its own weight rather than wearing a rule. */
h2 a.headline { border-bottom: 0; }
h2 a.headline:hover { color: var(--accent); }
.sources a { border-bottom-color: var(--rule); }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.sources { font-size: 0.68rem; color: var(--muted); margin-top: var(--s3);
  line-height: 1.45; }
.colophon { border-top: 1px solid var(--rule); margin-top: var(--s5); padding-top: var(--s3);
  font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.14em; }
* { overflow-wrap: anywhere; }
@media (max-width: 640px) { body { font-size: 16px; } .sheet { padding: 20px 16px 56px; } }
"""


def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def build(edition_dir: Path, paper: dict) -> str:
    order = {s["id"]: i for i, s in enumerate(paper.get("sections") or [])}
    names = {s["id"]: s["name"] for s in (paper.get("sections") or [])}

    parsed = []
    for path in sorted((edition_dir / "articles").glob("*.md")):
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

    def render(entry, lead=False):
        meta, body = entry["meta"], entry["body"]
        # A digest is the rail: several short items in one module, so it is packaged
        # rather than ranked. Everything else takes its span from priority.
        is_digest = "digest" in entry["name"].lower() or body.count("\n- ") >= 3
        weight = ("digest" if is_digest and not lead
                  else "major" if entry["priority"] <= 2
                  else "standard" if entry["priority"] == 3 else "brief")
        out = [] if lead else [f'<article class="{weight}">']
        link = next((src["url"] for src in (meta.get("sources_list") or [])
                     if str(src.get("url", "")).startswith(("http://", "https://"))), None)
        title = inline(meta.get("headline", ""))
        out.append(f'<h2><a class="headline" href="{html.escape(link, quote=True)}" '
                   f'target="_blank" rel="noopener">{title}</a></h2>'
                   if link else f"<h2>{title}</h2>")
        if meta.get("deck"):
            out.append(f'<p class="deck">{inline(meta["deck"])}</p>')
        if meta.get("byline") and (lead or entry["priority"] <= 2):
            out.append(f'<div class="byline">By {html.escape(meta["byline"])}</div>')

        inner = []
        plate = edition_dir / "images" / f"{meta.get('id', '')}-chart.png"
        if plate.is_file():
            inner.append(f'<img src="{data_uri(plate)}" alt="{html.escape(meta.get("caption", "chart"))}">')
            if meta.get("caption"):
                inner.append(f'<p class="caption">{inline(meta["caption"])}</p>')
        # wide tables scroll in their own box rather than pushing the page sideways
        inner.append(render_markdown(body).replace("<table>", '<div class="scroll"><table>')
                                          .replace("</table>", "</table></div>"))
        sources = meta.get("sources_list") or []
        if sources and (lead or entry["priority"] <= 2):
            linked = []
            for src in sources:
                name = html.escape(src.get("name", "") or "source")
                url = src.get("url", "")
                linked.append(f'<a href="{html.escape(url, quote=True)}" target="_blank" '
                              f'rel="noopener">{name}</a>'
                              if str(url).startswith(("http://", "https://")) else name)
            inner.append('<div class="sources">' + " · ".join(linked) + "</div>")

        # A wide module keeps a narrow measure by setting its own text in columns.
        body_html = "".join(inner)
        if lead:
            out.append(f'<div class="flow">{body_html}</div>')
        elif weight == "major":
            out.append(f'<div class="cols">{body_html}</div>')
        else:
            out.append(body_html)
        if not lead:
            out.append("</article>")
        return "".join(out)

    lead = next((a for a in parsed if a["priority"] == 1), None)
    chunks = ['<div class="sheet">', '<header class="masthead">',
              f"<h1>{html.escape(masthead)}</h1>", "</header>",
              '<div class="folio">',
              f"<span>Vol. 1 · No. {number}</span>" if number else "<span></span>",
              f'<span class="motto">{html.escape(paper.get("motto", ""))}</span>',
              f"<span>{html.escape(date_str)}</span>", "</div>"]
    if lead:
        chunks.append(f'<section class="lead">{render(lead, lead=True)}</section>')

    chunks.append('<div class="body">')
    current = None
    for entry in parsed:
        if entry is lead:
            continue
        if entry["section"] != current:
            current = entry["section"]
            chunks.append(f'<div class="section-head">{html.escape(names.get(current, current.title()))}</div>')
        chunks.append(render(entry))
    chunks.append("</div>")
    chunks.append(f'<div class="colophon">{html.escape(masthead)} · '
                  f'{len(parsed)} stories · set from the edition of {html.escape(date_str)}</div>')
    chunks.append("</div>")

    return (f"<title>{html.escape(masthead)}</title>\n"
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
            'family=Playfair+Display:wght@700;900&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&display=swap">\n'
            f"<style>{STYLE}</style>\n" + "".join(chunks))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edition_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    edition = args.edition_dir.expanduser().resolve()
    paper = json.loads((edition.parent / "paper.json").read_text())
    out = args.out or edition / f"{edition.name}.html"
    out.write_text(build(edition, paper))
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
