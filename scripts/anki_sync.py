#!/usr/bin/env python3
"""Push queued spaced-repetition cards to AnkiWeb — headless, via the `anki` library (RFC §7, D8).

Reads <vault>/SRS/pending.jsonl (one card/line: {deck, front, back, tags}), adds them to the Anki
collection, syncs to AnkiWeb (→ the learner's phone), and clears the queue ONLY on a successful
sync (so no card is ever lost). No GUI / xvfb / addon — just the backend library.

Run under a python that can import `anki` (droplet: the bundled Anki python + app_packages).
Env: AW_USER, AW_PASS. Args: <vault> <collection.anki2 path>.
"""

import json
import os
import sys

# Droplet: make the bundled Anki backend importable.
for p in ("/usr/local/share/anki/app_packages",):
    if os.path.isdir(p):
        sys.path.insert(0, p)

from anki.collection import Collection  # noqa: E402


def main(vault: str, coll_path: str) -> int:
    pending = os.path.join(vault, "SRS", "pending.jsonl")
    if not os.path.exists(pending) or os.path.getsize(pending) == 0:
        print("no pending cards"); return 0
    cards = [json.loads(line) for line in open(pending) if line.strip()]

    col = Collection(coll_path)
    try:
        basic = col.models.by_name("Basic")
        added = 0
        for c in cards:
            did = col.decks.id(c["deck"])
            note = col.new_note(basic)
            note.fields[0] = c.get("front", "")
            note.fields[1] = c.get("back", "")
            for t in c.get("tags", []):
                note.add_tag(t)
            col.add_note(note, did)
            added += 1

        auth = col.sync_login(os.environ["AW_USER"], os.environ["AW_PASS"], None)
        out = col.sync_collection(auth, False)
        if out.required in (2, 3, 4):                 # FULL_SYNC/DOWNLOAD/UPLOAD
            if out.new_endpoint:
                auth.endpoint = out.new_endpoint
            col.full_upload_or_download(auth=auth, server_usn=out.server_media_usn,
                                        upload=(out.required != 3))
    finally:
        col.close()

    open(pending, "w").close()                        # clear queue only after a clean sync
    print(f"synced {added} cards to AnkiWeb")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: anki_sync.py <vault> <collection.anki2>", file=sys.stderr); sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
