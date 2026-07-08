"""Kanban board (RFC-008) — a two-way Obsidian surface (obsidian-kanban markdown).

The engine renders + parses the board deterministically; it is a **view**, never a source of truth.
Numbers (mastery/GPA/streak) always come from the gradebook — a card the learner marks Done without a
real proof bounces back, it never becomes mastery. Cards embed an invisible `<!--hu:…-->` metadata
comment mapping the card to its outcome/course/tier so the audit can reconcile against the engine.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

COLUMNS = ["This Week", "Today", "Doing", "Proof Pending", "Done"]

_META = re.compile(r"<!--hu:([^>]*)-->")
_CARD = re.compile(r"^- \[( |x|X)\]\s*(.*)$")
_TITLE = re.compile(r"\*\*(.+?)\*\*")


class Card(BaseModel):
    title: str
    line: str = ""                 # one-line description
    outcome: str | None = None     # engine outcome id (hidden metadata)
    course: str | None = None
    tier: str | None = None
    checked: bool = False


def _meta(c: Card) -> str:
    parts = [f"{k}={v}" for k, v in (("o", c.outcome), ("c", c.course), ("d", c.tier)) if v]
    return f" <!--hu:{';'.join(parts)}-->" if parts else ""


def render_card(c: Card) -> str:
    body = f"**{c.title}**" + (f" — {c.line}" if c.line else "")
    return f"- [{'x' if c.checked else ' '}] {body}{_meta(c)}"


def render_board(columns: dict[str, list[Card]]) -> str:
    """Always-valid obsidian-kanban markdown. Unknown extra columns are appended after the standard set."""
    order = COLUMNS + [c for c in columns if c not in COLUMNS]
    out = ["---", "", "kanban-plugin: board", "", "---", ""]
    for col in order:
        out.append(f"## {col}")
        out.append("")
        for card in columns.get(col, []):
            out.append(render_card(card))
        out.append("")
    out += ["%% kanban:settings", "```", '{"kanban-plugin":"board"}', "```", "%%"]
    return "\n".join(out) + "\n"


def _parse_card(line: str) -> Card | None:
    m = _CARD.match(line.strip())
    if not m:
        return None
    checked = m.group(1).lower() == "x"
    body = m.group(2)
    meta: dict[str, str] = {}
    mm = _META.search(body)
    if mm:
        for kv in mm.group(1).split(";"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                meta[k.strip()] = v.strip()
        body = _META.sub("", body).strip()
    tm = _TITLE.search(body)
    title = tm.group(1).strip() if tm else body.strip()
    line_txt = body.split("—", 1)[1].strip() if "—" in body else ""
    return Card(title=title, line=line_txt, outcome=meta.get("o"),
                course=meta.get("c"), tier=meta.get("d"), checked=checked)


def parse_board(md: str) -> dict[str, list[Card]]:
    cols: dict[str, list[Card]] = {c: [] for c in COLUMNS}
    cur: str | None = None
    for raw in md.splitlines():
        s = raw.strip()
        if s.startswith("## "):
            cur = s[3:].strip()
            cols.setdefault(cur, [])
        elif cur and s.startswith("- ["):
            card = _parse_card(raw)
            if card:
                cols[cur].append(card)
    return cols


def empty_board() -> str:
    return render_board({c: [] for c in COLUMNS})
