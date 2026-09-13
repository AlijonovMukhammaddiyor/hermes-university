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

STYLE = """
@page { size: A4; margin: 16mm 14mm 18mm; }
body { font-family: "Source Serif 4", Georgia, serif; font-size: 10.5pt; line-height: 1.42;
       color: #14110c; margin: 0; }
.masthead { text-align: center; border-bottom: 2.5pt solid #14110c; padding-bottom: 6pt;
            margin-bottom: 14pt; }
.masthead h1 { font-size: 30pt; margin: 0 0 4pt; letter-spacing: -0.5pt; font-weight: 700; }
.masthead .rule { font-size: 8pt; text-transform: uppercase; letter-spacing: 1.4pt; color: #5b5348; }
article { break-inside: auto; margin: 0 0 16pt; }
article + article { border-top: 0.5pt solid #cfc7b8; padding-top: 12pt; }
h2 { font-size: 15pt; line-height: 1.2; margin: 0 0 3pt; }
.deck { font-style: italic; color: #5b5348; margin: 0 0 5pt; font-size: 10pt; }
.byline { font-size: 7.5pt; text-transform: uppercase; letter-spacing: 1pt; color: #7a7062;
          margin: 0 0 7pt; }
.section-tag { font-size: 7.5pt; text-transform: uppercase; letter-spacing: 1.2pt;
               color: #a8480f; font-weight: 600; }
p { margin: 0 0 6pt; }
ul { margin: 0 0 7pt; padding-left: 13pt; }
li { margin: 0 0 3pt; }
h3 { font-size: 9pt; text-transform: uppercase; letter-spacing: 1pt; margin: 9pt 0 4pt;
     color: #5b5348; }
table { border-collapse: collapse; width: 100%; font-size: 8.5pt; margin: 0 0 8pt; }
th, td { border-bottom: 0.5pt solid #cfc7b8; padding: 2.5pt 4pt; text-align: left; }
th { font-size: 7.5pt; text-transform: uppercase; letter-spacing: 0.6pt; color: #5b5348; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
img { max-width: 100%; height: auto; margin: 5pt 0; }
.caption { font-size: 8pt; font-style: italic; color: #5b5348; margin: 0 0 8pt; }
a { color: inherit; text-decoration: none; border-bottom: 0.4pt solid #b9b0a0; }
.sources { font-size: 7.5pt; color: #7a7062; margin-top: 5pt; }
.lead h2 { font-size: 21pt; }
.lead { break-after: page; }
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


def build_html(edition_dir: Path, paper: dict) -> str:
    articles = sorted((edition_dir / "articles").glob("*.md"))
    if not articles:
        raise SystemExit(f"no articles in {edition_dir}")

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
        parsed.append((order.get(section, 99), priority, path.name, meta, body, section))
    # the paper's own running order: section, then priority, then filename
    parsed.sort(key=lambda row: (row[0], row[1], row[2]))

    date_str = edition_dir.name
    number = issue_number(paper, date_str)
    chunks = [
        '<div class="masthead">',
        f'<h1>{html.escape(paper.get("masthead", "The Daily"))}</h1>',
        f'<div class="rule">{html.escape(paper.get("motto", ""))}'
        + (f" &nbsp;·&nbsp; No. {number}" if number else "")
        + f" &nbsp;·&nbsp; {html.escape(date_str)}</div>",
        "</div>",
    ]

    for _, priority, _, meta, body, section in parsed:
        lead = " lead" if priority == 1 else ""
        chunks.append(f'<article class="{lead.strip()}">')
        if section in names:
            chunks.append(f'<div class="section-tag">{html.escape(names[section])}</div>')
        chunks.append(f'<h2>{inline(meta.get("headline", ""))}</h2>')
        if meta.get("deck"):
            chunks.append(f'<p class="deck">{inline(meta["deck"])}</p>')
        if meta.get("byline"):
            chunks.append(f'<div class="byline">By {html.escape(meta["byline"])}</div>')

        plate = edition_dir / "images" / f"{meta.get('id', '')}-chart.png"
        if plate.is_file():
            chunks.append(f'<img src="{plate.as_uri()}" alt="chart">')
        if meta.get("caption"):
            chunks.append(f'<p class="caption">{inline(meta["caption"])}</p>')

        chunks.append(render_markdown(body))

        sources = meta.get("sources_list") or []
        if sources:
            chunks.append('<div class="sources">Sources: '
                          + "; ".join(html.escape(s.replace("name:", "").strip()) for s in sources
                                      if not s.startswith("url:"))
                          + "</div>")
        chunks.append("</article>")

    return (f"<!doctype html><meta charset='utf-8'><title>"
            f"{html.escape(paper.get('masthead', 'Daily'))} {html.escape(date_str)}</title>"
            f"<style>{STYLE}</style>" + "\n".join(chunks))


def to_pdf(html_text: str, out: Path, chrome: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "edition.html"
        source.write_text(html_text)
        cmd = [
            chrome, "--headless", "--disable-gpu", "--no-sandbox",
            "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
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
    args = parser.parse_args(argv)

    edition = args.edition_dir.expanduser().resolve()
    paper = read_paper(edition.parent)
    out = (args.out or edition / f"{edition.name}.pdf").expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    to_pdf(build_html(edition, paper), out, find_chrome(args.chrome))
    size = out.stat().st_size
    print(f"wrote {out} ({size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
