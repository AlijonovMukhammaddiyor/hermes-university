# Using & managing Hermes University

A practical operator's manual. Everything here is a real command or surface — nothing is aspirational.
For the *why*, see [ARCHITECTURE.md](ARCHITECTURE.md) and `docs/RFC-00*.md`.

---

## The three surfaces (one brain, the right tool per job)

| Surface | Role | You use it to… |
|---|---|---|
| **Telegram** | control + coach | run *every* command, get daily nudges, answer by text/voice, receive files |
| **Obsidian** | read + track | see `Home.md` (control center), work the Kanban `Board.md`, read syllabi/transcript |
| **Anki** | retention | review spaced-repetition cards on your phone |

Rule of thumb: **talk to the bot to *do* things; open Obsidian to *see* things; open Anki to *review*.**
You never need a terminal for anything routine.

---

## Getting started: create your first course

Message the bot:

```
create course <your goal>          e.g. create course backend engineering
```

Then it runs a research-gated build — it will **never invent a course from memory**:

1. **Short intake** — a few questions about your goal and level (one per message).
2. **📎 Research handoff** — it hands you a **research prompt** and pauses. You:
   - open the prompt (a file in Telegram, or `Uploads/<CODE>/RESEARCH-PROMPT.md` in Obsidian),
   - run it in **[Claude](https://claude.ai) → Deep Research**,
   - drop the report into `Uploads/<CODE>/` in your vault (or paste it back),
   - reply **`done`**.
3. **It builds the full A–Z syllabus** from that report — units, best materials, a week-by-week plan
   with take-home assignments, and the quiz/midterm/finals calendar.
4. **Placement** — it asks what you already know; a "yes" is *verified* at ≥ B before it's skipped.
5. **`MyPlan.md`** — your personalized track (mastered units skipped) — and the daily loop begins.

While a course waits on your research report, its status is **🔬 researching — waiting on you**; the
bot re-nudges instead of guessing.

---

## Everyday use: the daily loop

You mostly just **do the work and mark it done**. The engine drives the rest:

- **Morning** — the bot assigns ≤ your daily cap of tasks (a concept-first lesson + a sized task),
  adds them to the **Today** column on your Board, and books study blocks on your calendar.
- **During the day** — do a task, then either drag its card to **Done** in Obsidian *or* reply
  **`done`** in Telegram. Answer quizzes/teach-backs by text or **voice memo**.
- **Night** — the audit verifies each Done item's **proof**. Verified → it counts. Not verified → it
  moves to **Proof Pending** (never a fake pass). Proven concepts become **Anki cards** automatically.

Ask anytime: **`status`** (or open `Home.md`) — courses + where you are + what's blocked on you +
what's due + streak.

---

## Managing courses (all in Telegram, by course **name**)

| Say this | It does |
|---|---|
| `courses` | list available + your enrolled courses with their status |
| `create course <goal>` | research → build a new course |
| `enroll <name>` | enroll (authors first if needed, then placement) |
| `archive <name>` (or `drop`) | **soft** — hides it, keeps everything, reversible |
| `restore <name>` | bring an archived course back |
| `delete <name>` | **hard** — removes the syllabus, resources, progress (permanent) |
| `tailor <name>` | re-run placement / adjust pace / depth |
| `pause` · `resume <name>` | stop/restart its daily assignments |

**Confirm convention (the one safety rule):** any destructive action asks first.
- *Soft* (archive, day off): reply **`yes`** or **`cancel`**.
- *Hard* (delete): you must **echo `delete <name>`** to confirm — and archive is always offered as the
  safer alternative.

**Lifecycle** (shown on `Home.md` and in `status`): `draft → 🔬 researching → ✍️ authoring →
🎯 placement → 🟢 active → 🗄️ archived`.

---

## Steering what it builds toward

- **`profile`** — show your goal · target level · timezone · daily task cap.
- **`set goal <…>` · `set daily cap <n>` · `set level <…>`** — edit them (the bot writes the profile;
  never hand-edit files). Courses are designed backward from your **goal**, so this matters.

---

## Anki (retention) — automatic

When you prove a concept, the engine queues a card. A background sync pushes queued cards to **AnkiWeb
→ your phone** (every 6h). Review on the phone as normal. If you **lapse** a card (rate *Again*), that
concept is pulled back into your rotation and shows under **"To review"** on `Home.md`. Your GPA is
**not** touched by lapses — grades record what you *proved*; lapses just resurface a concept.

---

## What runs automatically (for the self-hoster)

On the host, under `systemd --user`:

| Unit | Cadence | Job |
|---|---|---|
| `hermes-gateway` | always on | the Telegram bot + skill runtime |
| cron `uni-assign` / `uni-audit` | daily | morning assign · night audit |
| cron `uni-week` / `uni-monthly` | weekly / monthly | advance the calendar · course self-update |
| `hermes-anki-sync.timer` | every 6h | push SRS cards to AnkiWeb + pull reviews back |
| `hermes-vault-sync.timer` | every 2 min | keep the Obsidian vault committed **and pushed** |

The vault is also protected by a **git post-commit hook** that auto-pushes — so a vault change can
never be stranded (Obsidian always pulls a current remote).

Skills are **preloaded when the gateway starts** — after changing a skill, reinstall and
`systemctl --user restart hermes-gateway`.

---

## Golden rules

- **Talk to the bot; don't touch the shell** for anything routine. Deleting a course is a chat command,
  not `rm`.
- **Course sources are private.** `courses/<CODE>/course.yaml` + its dossier are git-ignored instance
  data the engine reads from disk — **never commit them to the code repo** (it ships an empty catalog).
- **Numbers are the engine's.** Never hand-edit GPA/mastery/state; the bot reads them, it doesn't invent
  them, and neither should you.
- **The research report is required.** A course can't reach `authored` from the model's memory — that's
  by design; upload the Claude report.

---

## Troubleshooting

- **Obsidian isn't updating** → it pulls the remote; the vault auto-pushes within ~2 min. If still
  stale, pull again; if your Obsidian has local edits, resolve them (Obsidian Git → pull).
- **A course is stuck "researching"** → it's waiting on your research upload. Open
  `Uploads/<CODE>/RESEARCH-PROMPT.md`, run it in Claude, drop the report, reply `done`.
- **Telegram is noisy** → only the final message should appear; interim narration is off by config
  (`display.interim_assistant_messages: false`).
- **No Anki cards on the phone** → cards only flow after you *prove* concepts; the sync runs every 6h.
