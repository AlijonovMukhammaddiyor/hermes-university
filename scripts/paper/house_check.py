#!/usr/bin/env python3
"""Hold an edition to the paper's house rules — length and balance.

vael-paper-check says whether an edition will print. This says whether it is the
paper it is meant to be: short enough to read, and balanced across its pillars.

Written as code because asking did not work. The instruction to cap a section at
three stories was in the skill for two runs and the section came back with six
both times; a number the model has to satisfy holds where a sentence does not.

The rules live in paper.json under "house", so they are the owner's to change:

    "house": {
      "max_words": 3000,
      "max_section_articles": 4,
      "max_pillar_words": 1000,
      "pillars": {"tech": ["ai", "engineering"], ...}
    }

Exits 1 when a rule is broken, naming what to cut and by how much.

Usage:
    house_check.py <edition_dir> [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_pdf import split_frontmatter  # noqa: E402

DEFAULTS = {
    "max_words": 3000,
    "max_section_articles": 4,
    "max_pillar_words": 1000,
    "pillars": {},
}


def read_edition(edition_dir: Path) -> list[dict]:
    out = []
    for path in sorted((edition_dir / "articles").glob("*.md")):
        meta, body = split_frontmatter(path.read_text())
        out.append({
            "file": path.name,
            "section": (meta.get("section") or "misc").lower(),
            "words": len(re.findall(r"\S+", body)),
            "headline": meta.get("headline", ""),
        })
    return out


def audit(articles: list[dict], rules: dict) -> list[dict]:
    """Every broken rule, with the size of the overrun."""
    findings = []
    total = sum(a["words"] for a in articles)
    if total > rules["max_words"]:
        findings.append({
            "code": "edition_long", "scope": "edition",
            "message": f"{total} words is over the {rules['max_words']} the paper is set at; "
                       f"cut about {total - rules['max_words']}.",
        })

    by_section: dict[str, list[dict]] = {}
    for a in articles:
        by_section.setdefault(a["section"], []).append(a)

    for section, items in sorted(by_section.items()):
        if len(items) > rules["max_section_articles"]:
            # The digest is where the tail goes, so it is never the thing to fold away.
            stories = [a for a in items if "digest" not in a["file"].lower()] or items
            weakest = sorted(stories, key=lambda a: a["words"])[0]
            findings.append({
                "code": "section_crowded", "scope": f"section:{section}",
                "message": f"{len(items)} articles, cap is {rules['max_section_articles']} "
                           f"(three stories and a digest). Fold the weakest into the digest — "
                           f"{weakest['file']} is the smallest at {weakest['words']} words.",
            })

    for pillar, sections in (rules.get("pillars") or {}).items():
        words = sum(a["words"] for a in articles if a["section"] in sections)
        if words > rules["max_pillar_words"]:
            findings.append({
                "code": "pillar_heavy", "scope": f"pillar:{pillar}",
                "message": f"{words} words against a {rules['max_pillar_words']} cap — it has taken "
                           f"another pillar's room. Cut about {words - rules['max_pillar_words']} "
                           f"from {', '.join(sections)}.",
            })
    return findings


def summarise(articles: list[dict], rules: dict) -> dict:
    by_section: dict[str, dict] = {}
    for a in articles:
        entry = by_section.setdefault(a["section"], {"articles": 0, "words": 0})
        entry["articles"] += 1
        entry["words"] += a["words"]
    pillars = {
        name: sum(a["words"] for a in articles if a["section"] in sections)
        for name, sections in (rules.get("pillars") or {}).items()
    }
    return {"total_words": sum(a["words"] for a in articles),
            "articles": len(articles), "sections": by_section, "pillars": pillars}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edition_dir", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    edition = args.edition_dir.expanduser().resolve()
    paper_file = edition.parent / "paper.json"
    paper = json.loads(paper_file.read_text()) if paper_file.is_file() else {}
    rules = {**DEFAULTS, **(paper.get("house") or {})}

    articles = read_edition(edition)
    if not articles:
        print(f"no articles in {edition}", file=sys.stderr)
        return 1

    findings = audit(articles, rules)
    report = {**summarise(articles, rules), "findings": findings, "ok": not findings}

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        s = report
        print(f"{s['articles']} articles, {s['total_words']} words (cap {rules['max_words']})")
        for section, v in sorted(s["sections"].items()):
            print(f"  {section:<14} {v['articles']:>2} art  {v['words']:>5} w")
        for pillar, words in sorted(s["pillars"].items()):
            print(f"  pillar {pillar:<7} {words:>9} w  (cap {rules['max_pillar_words']})")
        if findings:
            print("\nover the house rules:")
            for f in findings:
                print(f"  [{f['code']}] {f['scope']}: {f['message']}")
        else:
            print("\nwithin the house rules.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
