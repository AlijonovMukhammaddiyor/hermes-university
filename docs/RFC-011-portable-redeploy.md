# RFC-011 — Portable redeploy / disaster recovery

Status: **ACCEPTED — implementing** · Date: 2026-07-08
Canonical description: [`ARCHITECTURE.md`](../ARCHITECTURE.md).

## 0. Why
A droplet can die. The system must come back on a **fresh droplet with one command and zero loss of
state or progress.** Audit of what exists today:

- **Durable already:** learner progress — `Registrar/state.json`, `records/grades.jsonl`,
  `learner_model.json` — lives in the **vault**, a private git repo auto-pushed every 2 min (RFC-009).
  Clone the vault → progress is back.
- **Lost on redeploy (gaps):**
  1. **Authored courses** — `courses/<CODE>/course.yaml` + `research/dossier.md` are git-ignored
     instance data on the droplet disk, backed up **nowhere**. Only the rendered `Syllabus.md` survives.
  2. **Config/secrets** — `profile.yaml`, `config.env`, `~/.hermes/.env`, `~/.hermes/config.yaml`,
     `~/.hermes/cron/jobs.json`, the Google-Calendar OAuth token — droplet-only.
  3. **`install.sh` is incomplete** — the Anki backend + sync/review timers + wrappers, the
     `uni-briefing` cron, and the durable-sync were set up manually and aren't in the install path.

## 1. Principle: the vault is the single durable store
Everything that must survive is either **already in the vault** (progress) or gets **backed up into the
vault** (course sources + an encrypted secrets bundle). Everything else is **reproducible** from the
code repo + `install.sh`. So a redeploy is: install agent → clone code → clone vault → restore from the
vault → `install.sh`. No external backup service.

## 2. Backup (`scripts/hermes_backup.sh`, on a daily timer + after authoring)
1. **Course sources → `vault/_source/courses/<CODE>/`** — mirror `course.yaml` + `research/` for every
   course. Rides the vault's git backup (closes Gap 1). `Uploads/` already lives in the vault.
2. **Secrets bundle → `vault/_source/secrets.tar.gz.enc`** — tar of `profile.yaml`, `config.env`,
   `~/.hermes/{.env,config.yaml,cron/jobs.json,auth.json}`, the Google-Calendar token; encrypted with
   **openssl AES-256** using a passphrase in `~/.hermes/backup.key` (git-ignored, droplet-only). The
   learner keeps **one copy of that passphrase** (their recovery key) — it is the only thing not
   recoverable from git. The Anki collection is **not** bundled (it re-syncs from AnkiWeb).
3. The vault-sync (RFC-009) then commits + pushes, so the backup is durable within ≤2 min.

Threat model: the encrypted bundle sits in a **private** GitHub repo; even if that repo leaks, the
secrets stay AES-encrypted. The passphrase lives only on the droplet + the learner's own store.

## 3. Reproducible install (`install.sh`, made complete)
Codify the manual steps so a fresh install recreates everything: engine venv · vault scaffold · state
init · rendered skills · systemd `hermes-gateway` · the **durable-sync** hook+timer · the **Anki**
push/review wrappers + timer · the **backup** timer · the crons. Wrappers move from `~/.hermes/bin/`
into `scripts/` (version-controlled), symlinked at install.

## 4. Restore (`bootstrap.sh` — one command on a fresh droplet)
```
bootstrap.sh <code-repo-url> <vault-repo-url>
```
1. Install prereqs (hermes-agent, Anki backend, git, openssl, uv).
2. Clone the code repo → `~/hermes-university`; clone the vault → `~/vault`.
3. **Decrypt** `vault/_source/secrets.tar.gz.enc` (prompt for the passphrase) → restore `profile.yaml`,
   `config.env`, `~/.hermes/{.env,config.yaml,cron/jobs.json,auth.json}`, the calendar token.
4. **Restore course sources** from `vault/_source/courses/` → `courses/`.
5. Run `install.sh` (venv, skills, systemd, timers, hooks).
6. Re-auth only what can't be restored: AnkiWeb login (collection re-syncs), Google OAuth refresh if the
   token expired. Start the gateway.
7. `hu-engine status` + a render should show the exact prior state.

## 5. Verification
`hermes_backup.sh` produces a decryptable bundle containing every listed file + a course mirror; a
**dry-run restore into a scratch dir** reconstructs `profile.yaml`, config, crons, and `courses/AG201`
byte-identical; the vault holds `_source/` after a sync. Full restore is validated on a real fresh
droplet before this is trusted (a redeploy runbook lives in the README).

## 6. Non-goals
Not a general backup service. Not backing up the Anki collection (AnkiWeb is its source of truth). Not
storing the passphrase anywhere the system controls — that's the learner's one responsibility.
