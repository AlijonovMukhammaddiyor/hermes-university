#!/usr/bin/env python3
"""Fetch the paper's typefaces once, for a host that prints offline.

The print build named faces that were never installed, so every PDF came out in
DejaVu Serif — the Linux default — rather than the typography it specified. A
headless box has three serifs and none of them are newspaper faces, so the fonts
have to travel with the edition.

This keeps Google's own @font-face blocks (which carry the weight, style and
unicode-range for each subset) and only repoints `src` at the downloaded file, so
Cyrillic and Latin-ext subsets keep working.

The choices, and why:
  Old Standard TT   masthead and headlines. A revival of the late-19th-century
                    book and newspaper letter — high stroke contrast, sharp
                    serifs, the form a broadsheet nameplate is cut from.
  PT Serif          body. Drawn for news text at small sizes: sturdy serifs and
                    economical setting.
  PT Sans Narrow    labels, kickers, bylines, folios. Papers set their furniture
                    in a condensed sans against the serif text — it fits a label
                    into a column and gives the page a third voice.

PT Serif and PT Sans are one superfamily, drawn together by ParaType for Russian
public signage, so the pairing is designed rather than assembled — and all three
carry Cyrillic, which a paper covering Russian- and Uzbek-language plays needs.

Usage:
    fetch_fonts.py [--dir ~/.hermes/fonts]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import re
import urllib.error
import urllib.request
from pathlib import Path

# A browser UA, or Google serves the TrueType fallback instead of woff2.
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")
# Static faces only. Chromium's headless PDF path will not embed a variable-font
# instance — it silently prints the fallback serif, which is how the first pick
# (Bodoni Moda + Archivo, both variable) produced a paper set in Liberation.
FAMILIES = [
    "Old+Standard+TT:ital,wght@0,400;0,700;1,400",
    "PT+Serif:ital,wght@0,400;0,700;1,400",
    "PT+Sans+Narrow:wght@400;700",
]
TIMEOUT = 45


def get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"could not fetch {url}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=Path("~/.hermes/fonts"))
    args = parser.parse_args(argv)

    out = args.dir.expanduser()
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.woff2"):
        stale.unlink()

    blocks, files = [], 0
    for family in FAMILIES:
        css = get(f"https://fonts.googleapis.com/css2?family={family}&display=block").decode()
        for url in sorted(set(re.findall(r"https://fonts\.gstatic\.com/[^)]*\.woff2", css))):
            name = f"{hashlib.sha1(url.encode()).hexdigest()[:10]}.woff2"
            target = out / name
            if not target.is_file():
                target.write_bytes(get(url))
                files += 1
            # Inline as a data: URI rather than a file: one. Chromium refuses a
            # file:// subresource from a file:// page, which is how the first
            # attempt silently fell back to the host's default serif.
            encoded = base64.b64encode(target.read_bytes()).decode()
            css = css.replace(url, f"data:font/woff2;base64,{encoded}")
        blocks.append(css)

    sheet = out / "fonts.css"
    sheet.write_text("\n".join(blocks))
    faces = sum(b.count("@font-face") for b in blocks)
    print(f"fetched {files} files, {faces} @font-face rules "
          f"-> {sheet} ({sheet.stat().st_size // 1024} KB inlined)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
