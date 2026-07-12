#!/usr/bin/env python3
"""Push queued SRS cards to AnkiWeb headless via the `anki` library (RFC §7, D8).

Reads <vault>/SRS/pending.jsonl, adds to the collection, syncs, and clears the queue ONLY on a
successful sync (so no card is lost). Run under a python that can import `anki`.
Env: AW_USER, AW_PASS. Args: <vault> <collection.anki2>.
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
        print("no pending cards")
        return 0
    cards = [json.loads(line) for line in open(pending) if line.strip()]

    col = Collection(coll_path)
    added_ids: list[int] = []
    # uploaded → our adds reached AnkiWeb; downloaded → remote replaced local (our adds gone)
    uploaded = downloaded = False
    try:
        basic = col.models.by_name("Basic")
        for c in cards:
            did = col.decks.id(c["deck"])
            note = col.new_note(basic)
            note.fields[0] = c.get("front", "")
            note.fields[1] = c.get("back", "")
            for t in c.get("tags", []):
                note.add_tag(t)
            col.add_note(note, did)
            added_ids.append(note.id)

        auth = col.sync_login(os.environ["AW_USER"], os.environ["AW_PASS"], None)
        out = col.sync_collection(auth, False)
        # Safety: never overwrite AnkiWeb (the phone's collection). Only a full DOWNLOAD is safe;
        # refuse a full UPLOAD and fail loud so a human seeds the collection instead of clobbering it.
        if out.required in (2, 4):  # FULL_SYNC (ambiguous) / FULL_UPLOAD
            raise SystemExit(
                "refusing a full-upload sync — it would overwrite AnkiWeb. Seed the "
                "droplet collection by syncing once from your Anki, then retry."
            )
        if out.required == 3:  # FULL_DOWNLOAD — safe (pulls remote in, discarding our local adds)
            if out.new_endpoint:
                auth.endpoint = out.new_endpoint
            col.full_upload_or_download(auth=auth, server_usn=out.server_media_usn, upload=False)
            downloaded = True
        else:
            uploaded = True  # normal sync pushed our new notes
    finally:
        # Atomicity: unless a normal sync pushed the notes, undo them so a failed/refused run leaves
        # the collection unchanged, never duplicated. A full DOWNLOAD already replaced local, so
        # there's nothing to undo.
        if not uploaded and not downloaded and added_ids:
            col.remove_notes(added_ids)
        col.close()

    if uploaded:
        open(pending, "w").close()  # clear the queue only once its cards are on AnkiWeb
        print(f"synced {len(added_ids)} cards to AnkiWeb")
        return 0
    print("seeded local collection from AnkiWeb; cards remain queued for the next sync")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: anki_sync.py <vault> <collection.anki2>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
