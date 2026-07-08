"""Pull Anki review results back into the engine — the review-back half (RFC-009 §5).

Runs under the bundled Anki python (3.13). Downloads reviews from AnkiWeb (never uploads-overwrites),
reads new rows from the `revlog`, maps each reviewed card to its engine outcome via the `hu-o::<id>`
tag the professor attached, and hands the events to `hu-engine srs review`. A watermark (last revlog
id) prevents double-counting. GPA/transcript are untouched — a lapse only marks an outcome review-due.

Env: AW_USER, AW_PASS.  Args: <vault> <collection.anki2> <hu-engine path>.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/usr/local/share/anki/app_packages")
from anki.collection import Collection  # noqa: E402

TAG = "hu-o::"


def main(vault: str, coll_path: str, engine: str) -> int:
    srs = os.path.join(vault, "SRS")
    os.makedirs(srs, exist_ok=True)
    wm_path = os.path.join(srs, ".revlog_watermark")
    wm = int(open(wm_path).read().strip()) if os.path.exists(wm_path) else 0

    col = Collection(coll_path)
    try:
        auth = col.sync_login(os.environ["AW_USER"], os.environ["AW_PASS"], None)
        out = col.sync_collection(auth, False)
        if out.required in (2, 4):                     # never full-upload from here (data-loss guard)
            print("refusing full-upload sync (would overwrite AnkiWeb); seed the collection first",
                  file=sys.stderr); return 1
        if out.required == 3:                          # FULL_DOWNLOAD — safe
            if out.new_endpoint:
                auth.endpoint = out.new_endpoint
            col.full_upload_or_download(auth=auth, server_usn=out.server_media_usn, upload=False)
        rows = col.db.all(
            "select r.id, r.ease, n.tags from revlog r "
            "join cards c on r.cid = c.id join notes n on c.nid = n.id "
            "where r.id > ? order by r.id", wm)
    finally:
        col.close()

    events, maxid = [], wm
    for rid, ease, tags in rows:
        maxid = max(maxid, rid)
        for t in (tags or "").split():
            if t.startswith(TAG):
                events.append({"outcome": t[len(TAG):], "ease": int(ease),
                               "ts": datetime.fromtimestamp(rid / 1000, timezone.utc).isoformat()})
    if events:
        subprocess.run([engine, "srs", "review", "--vault", vault, "--events", json.dumps(events)],
                       check=True)
    with open(wm_path, "w") as f:
        f.write(str(maxid))
    print(f"pulled {len(events)} review events from {len(rows)} new revlog rows")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: anki_review_pull.py <vault> <collection.anki2> <hu-engine>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
