#!/usr/bin/env python3
"""Data desk: provider-verified indie revenue, from TrustMRR's public discovery API.

The startup briefing's sharpest failure mode is quoting the wrong revenue metric —
30-day revenue, current MRR and all-time total are three different numbers and the
API returns all three under one `revenue` object. This desk renders them as three
separately labelled columns by code, so they cannot be conflated in prose.

Needs network. If the fetch fails or returns nothing usable, the desk exits nonzero
and the story is dropped — it never prints a revenue figure it did not read.

Data desk, deliberately code, never a model.

Usage:
    trustmrr_desk.py <edition_dir> [--limit 8] [--min-30d 100] [--feed both]

Writes <edition_dir>/articles/02-the-revenue-board.md
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import DeskError, clip, write_article  # noqa: E402

FILENAME = "02-the-revenue-board.md"
API = "https://trustmrr.com/api/ai/discovery"
TIMEOUT = 30
LABEL_LIMIT = 12

FEEDS = {
    "recent": ["recentlyAddedStartups"],
    "growing": ["fastestGrowingStartups"],
    "both": ["fastestGrowingStartups", "recentlyAddedStartups"],
}


def fetch(url: str = API) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "hermes-daily-desk/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DeskError(f"TrustMRR discovery unreachable: {exc}") from exc


def rows_from(payload: dict, feeds: list[str], min_30d: float, max_30d: float | None,
              limit: int) -> list[dict]:
    """Verified 30-day revenue inside the band, best first, de-duplicated.

    The band matters more than the floor: the point of this board is products one
    person could plausibly copy, so a $100k/month rocketship is noise here.
    """
    seen, out = set(), []
    for feed in feeds:
        for item in payload.get(feed) or []:
            slug = item.get("slug")
            revenue = item.get("revenue") or {}
            last30 = revenue.get("last30Days") or 0
            if not slug or slug in seen or last30 < min_30d:
                continue
            if max_30d is not None and last30 > max_30d:
                continue
            seen.add(slug)
            out.append({
                "name": str(item.get("name") or slug),
                "slug": slug,
                "url": str(item.get("url") or ""),
                "website": str(item.get("website") or ""),
                "category": str(item.get("category") or "").strip(),
                "provider": str(item.get("paymentProvider") or "—"),
                "on_sale": bool(item.get("onSale")),
                "last30": float(last30),
                "mrr": float(revenue.get("mrr") or 0),
                "total": float(revenue.get("total") or 0),
                "feed": "growing" if feed == "fastestGrowingStartups" else "recent",
            })
    out.sort(key=lambda row: row["last30"], reverse=True)
    return out[:limit]


def money(value: float) -> str:
    return f"${value:,.0f}"


def build_body(rows: list[dict], min_30d: float, max_30d: float) -> str:
    providers = sorted({row["provider"] for row in rows})
    for_sale = [row for row in rows if row["on_sale"]]

    paras = [
        f"{len(rows)} products on TrustMRR took between {money(min_30d)} and {money(max_30d)} over "
        f"the last thirty days, each figure read from the provider that processes it "
        f"({', '.join(providers)}) rather than claimed by its founder.",
        "**The three numbers below are not the same number.** *30-day* is what the product took in "
        "over the last thirty days. *MRR* is what is recurring right now, so a product selling "
        "one-off licences can show strong 30-day revenue and no MRR at all. *All-time* is every "
        "dollar since the product connected its provider. Only the first two say anything about "
        "what it earns today.",
    ]
    if for_sale:
        shown = for_sale[:3]
        names = ", ".join(row["name"] for row in shown)
        if len(for_sale) > len(shown):
            names = "including " + names
        paras.append(
            f"{len(for_sale)} of them {'is' if len(for_sale) == 1 else 'are'} listed for sale "
            f"({names}) — these products trade around thirteen times monthly revenue."
        )

    rows_out = [
        "### Verified revenue",
        "",
        "| Product | 30-day | MRR | All-time |",
        "|:---|---:|---:|---:|",
    ]
    for row in rows:
        rows_out.append(
            f"| {clip(row['name'], 18)} | {money(row['last30'])} "
            f"| {money(row['mrr'])} | {money(row['total'])} |"
        )

    rows_out += ["", "### What they are", ""]
    for row in rows:
        link = row["url"] or row["website"]
        sale = " · for sale" if row["on_sale"] else ""
        what = f"{row['category']}, via {row['provider']}" if row["category"] else f"via {row['provider']}"
        rows_out.append(f"- **[{row['name']}]({link})** — {what}{sale}.")

    return "\n\n".join(paras) + "\n\n" + "\n".join(rows_out)


def build_article(edition_dir: Path, limit: int, min_30d: float,
                  max_30d: float | None, feed: str) -> Path:
    rows = rows_from(fetch(), FEEDS[feed], min_30d, max_30d, limit)
    if not rows:
        band = money(min_30d) + (f"–{money(max_30d)}" if max_30d else " and up")
        raise DeskError(f"no product landed in the {band} band of 30-day revenue")

    fields = {
        "id": FILENAME[:-3],
        "headline": "The Revenue Board",
        "deck": f"{len(rows)} products, provider-verified, best thirty days first",
        "section": "projects",
        "byline": "The Revenue Desk",
        "priority": 2,
        "span": "2col",
    }

    charted = [row for row in rows if row["last30"] > 0][:8]
    if len(charted) >= 2:
        fields["chart"] = {
            "kind": "bars",
            "values": [round(row["last30"]) for row in charted],
            "labels": [clip(row["name"], LABEL_LIMIT) for row in charted],
            "show_values": True,
        }
        fields["caption"] = (
            "Revenue over the last thirty days, in US dollars, as reported by each "
            "product's own payment provider. Not MRR."
        )

    ceiling = max_30d if max_30d else max(row["last30"] for row in rows)
    return write_article(edition_dir, FILENAME, fields, build_body(rows, min_30d, ceiling))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edition_dir", type=Path)
    parser.add_argument("--limit", type=int, default=8)
    # the band one person can realistically copy; the skill may widen it
    parser.add_argument("--min-30d", type=float, default=500.0)
    parser.add_argument("--max-30d", type=float, default=25000.0,
                        help="0 for no ceiling")
    parser.add_argument("--feed", choices=sorted(FEEDS), default="both")
    args = parser.parse_args(argv)

    try:
        ceiling = args.max_30d if args.max_30d and args.max_30d > 0 else None
        target = build_article(args.edition_dir, args.limit, args.min_30d, ceiling, args.feed)
    except DeskError as exc:
        print(f"trustmrr desk: {exc} — dropping the story", file=sys.stderr)
        return 1
    print(f"wrote {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
