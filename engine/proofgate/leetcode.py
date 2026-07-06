"""LeetCode proof-gate (best-effort, RFC §7 / D9).

Proves an Accepted submission for a target problem after an assigned-since timestamp, using the
learner's recent-AC list. Network is injectable via `fetcher` for deterministic tests.

Caveat (from research): LeetCode has no official API and a public list can't prove account
ownership beyond the session cookie; treat as best-effort and swappable for Judge0 later.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable

from .base import ProofGate, ProofResult

# fetcher(username, session|None) -> list[{"titleSlug": str, "timestamp": int}]
Fetcher = Callable[[str, str | None], list[dict]]


_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _default_fetcher(username: str, session: str | None) -> list[dict]:
    # LeetCode 403s requests without a browser User-Agent; a session cookie also improves reliability.
    session = session or os.environ.get("LEETCODE_SESSION")
    query = ('{ recentAcSubmissionList(username: "%s", limit: 20) '
             '{ titleSlug timestamp } }') % username
    headers = {"Content-Type": "application/json", "Referer": "https://leetcode.com",
               "User-Agent": _UA}
    if session:
        headers["Cookie"] = f"LEETCODE_SESSION={session}"
    req = urllib.request.Request("https://leetcode.com/graphql",
                                 data=json.dumps({"query": query}).encode(),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    return data.get("data", {}).get("recentAcSubmissionList") or []


class LeetCodeGate(ProofGate):
    name = "leetcode"

    def __init__(self, fetcher: Fetcher = _default_fetcher):
        self._fetch = fetcher

    def verify(self, evidence: dict) -> ProofResult:
        """evidence: {username, slug, since_ts:int, session?:str}."""
        username = evidence["username"]
        slug = evidence["slug"]
        since_ts = int(evidence.get("since_ts", 0))
        try:
            subs = self._fetch(username, evidence.get("session"))
        except Exception as e:  # network/parse failure => not proven (fail loud in detail)
            return ProofResult(passed=False, score=0.0, source=self.name,
                               detail=f"fetch failed: {e!r}")
        for s in subs:
            if s.get("titleSlug") == slug and int(s.get("timestamp", 0)) >= since_ts:
                return ProofResult(passed=True, score=1.0, source=self.name,
                                   ref=slug, detail=f"AC at {s.get('timestamp')}")
        return ProofResult(passed=False, score=0.0, source=self.name, ref=slug,
                           detail="no Accepted submission for slug since assignment")
