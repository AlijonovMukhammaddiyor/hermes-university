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

/* The host paints its own ground behind the page, so html must carry the
   newsprint colour too — painting only body leaves a white surround. */
html { background: var(--ground); }
body { background: var(--ground); color: var(--ink);
  font-family: "Source Serif 4", Georgia, "Times New Roman", serif;
  font-size: 17px; line-height: 1.56; margin: 0;
  font-variant-numeric: oldstyle-nums; -webkit-font-smoothing: antialiased; }
.sheet { max-width: 1180px; margin: 0 auto; padding: 40px 24px 80px; }

.masthead { text-align: center; border-bottom: 2px solid var(--rule-strong);
  padding-bottom: 12px; margin-bottom: 10px; }
.masthead h1 { font-family: "Playfair Display", Georgia, serif; font-weight: 900;
  font-size: clamp(2.4rem, 8.5vw, 5.2rem); line-height: 0.94; letter-spacing: -0.02em;
  margin: 0; text-wrap: balance; }
.folio { display: flex; flex-wrap: wrap; gap: 10px 20px; justify-content: space-between;
  align-items: baseline; font-size: 0.7rem; text-transform: uppercase;
  letter-spacing: 0.16em; color: var(--muted); margin: 12px 0 34px;
  font-variant-numeric: lining-nums tabular-nums; }
.folio .motto { text-transform: none; letter-spacing: 0; font-style: italic; font-size: 0.85rem; }

.lead { border-bottom: 1px solid var(--rule); padding-bottom: 30px; margin-bottom: 30px; }
.lead h2 { font-family: "Playfair Display", Georgia, serif; font-weight: 900;
  font-size: clamp(1.85rem, 5.2vw, 3.1rem); line-height: 1.06; letter-spacing: -0.015em;
  text-align: center; margin: 0 0 14px; text-wrap: balance; }
.lead .deck { text-align: center; font-style: italic; color: var(--muted);
  font-size: 1.06rem; max-width: 46ch; margin: 0 auto 22px; line-height: 1.45; }
.lead .flow { columns: 2 19rem; column-gap: 2.6rem; }
.lead .flow > p:first-of-type::first-letter { float: left; font-family: "Playfair Display", Georgia, serif;
  font-size: 3.5em; line-height: 0.76; font-weight: 900; padding: 0.06em 0.09em 0 0; color: var(--accent); }

.body { columns: 3 17rem; column-gap: 2.6rem; }
article { break-inside: avoid; margin: 0 0 30px; }
article.long { break-inside: auto; }
article.major { margin-bottom: 34px; }
article.brief { margin-bottom: 22px; }
article.brief .deck { display: none; }

.section-head { column-span: all; border-bottom: 1.5px solid var(--rule-strong);
  margin: 18px 0 24px; padding-bottom: 5px; font-family: "Playfair Display", Georgia, serif;
  font-size: 0.82rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3em;
  color: var(--accent); }

h2 { font-family: "Playfair Display", Georgia, serif; font-weight: 700; margin: 0 0 8px;
  line-height: 1.16; text-wrap: balance; }
article.major h2 { font-size: 1.42rem; }
article.standard h2 { font-size: 1.2rem; }
article.brief h2 { font-family: "Source Serif 4", Georgia, serif; font-size: 1.04rem;
  font-weight: 700; }
.deck { font-style: italic; color: var(--muted); font-size: 0.95rem; margin: 0 0 10px;
  line-height: 1.42; }
.byline { font-size: 0.64rem; text-transform: uppercase; letter-spacing: 0.14em;
  color: var(--muted); margin: 0 0 10px; }

p { margin: 0 0 0.72em; }
p + p { text-indent: 1.1em; }
ul { margin: 0 0 0.9em; padding: 0; list-style: none; }
li { margin: 0 0 0.6em; padding-left: 1em; text-indent: -1em; }
li::before { content: "—\\00a0"; color: var(--accent); }
h3 { font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.17em; color: var(--muted);
  margin: 1.3em 0 0.5em; font-weight: 600; }

.scroll { overflow-x: auto; margin: 0 0 1em; }
table { border-collapse: collapse; width: 100%; font-size: 0.78rem;
  font-variant-numeric: lining-nums tabular-nums; }
th, td { padding: 5px 10px 5px 0; text-align: left; }
th:last-child, td:last-child { padding-right: 0; }
th { font-size: 0.64rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted);
  border-bottom: 1.5px solid var(--rule-strong); font-weight: 600; white-space: nowrap; }
tbody tr + tr td { border-top: 1px solid var(--rule); }
td.num, th.num { text-align: right; }
th:first-child, td:first-child { width: 1.6em; }

img { max-width: 100%; height: auto; display: block; margin: 8px 0 6px;
  background: var(--plate); border: 1px solid var(--rule); }
:root[data-theme="dark"] img, :root:not([data-theme="light"]) img { filter: invert(1) hue-rotate(180deg); }
@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) img { filter: none; } }
:root[data-theme="light"] img { filter: none; }
.caption { font-size: 0.72rem; font-style: italic; color: var(--muted); margin: 0 0 1em;
  line-height: 1.4; }

a { color: inherit; text-decoration: none; border-bottom: 1px solid var(--accent); }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.sources { font-size: 0.68rem; color: var(--muted); margin-top: 8px; line-height: 1.35; }
.colophon { border-top: 1px solid var(--rule); margin-top: 40px; padding-top: 14px;
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
        weight = ("major" if entry["priority"] <= 2
                  else "standard" if entry["priority"] == 3 else "brief")
        long = " long" if len(body) > 1400 else ""
        out = [] if lead else [f'<article class="{weight}{long}">']
        out.append(f"<h2>{inline(meta.get('headline', ''))}</h2>")
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
        sources = [x for x in (meta.get("sources_list") or []) if not x.startswith("url:")]
        if sources and (lead or entry["priority"] <= 2):
            inner.append('<div class="sources">Sources: '
                         + "; ".join(html.escape(x.replace("name:", "").strip()) for x in sources)
                         + "</div>")

        out.append(f'<div class="flow">{"".join(inner)}</div>' if lead else "".join(inner))
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
