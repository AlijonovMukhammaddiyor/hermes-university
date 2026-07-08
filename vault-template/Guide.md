# 📖 How to use Hermes University

**One rule: message the bot to *do* things · open [[Home]] / [[Board]] to *see* things · open Anki to
*review*.** You never need a terminal.

## Start a course
Message the bot:
```
create course <your goal>
```
Then:
1. It asks a few quick questions.
2. 📎 It hands you a **research prompt** and pauses. Open it (a file in Telegram, or
   `Uploads/<CODE>/RESEARCH-PROMPT.md` here in the vault), run it in **Claude → Deep Research**, drop
   the report into `Uploads/<CODE>/`, and reply **`done`**.
3. It builds the full syllabus, runs a **placement** check (a "yes" is verified before it's skipped),
   and writes your personalized **MyPlan.md**. The daily loop begins.

A course waiting on your report shows **🔬 researching — waiting on you**.

## Your day
- **Morning** — the bot puts today's tasks in the **Today** column on [[Board]].
- **Do a task**, then drag its card to **Done** (or reply `done` in Telegram; answer quizzes by voice
  if you like).
- **Night** — it checks your proof. Verified → it counts. Not verified → the card moves to **Proof
  Pending** (never a fake pass). Proven concepts turn into Anki cards automatically.

Open **[[Home]]** anytime — courses + where you are + what's **blocked on you** + what's due + cards.

## Manage courses (in Telegram, by course name)
- `courses` · `status` · `profile` — list courses · where you are · view/edit your goals
- `create course <goal>` · `enroll <name>` — build a new one · enroll
- `archive <name>` (reversible) · `restore <name>` · `delete <name>` (permanent)
- `tailor <name>` · `pause` / `resume <name>` — adjust pace · stop/restart assignments

**Every destructive action asks first** — reply `yes` / `cancel`; a hard `delete` needs you to echo
`delete <name>`. Course lifecycle: `🔬 researching → ✍️ authoring → 🎯 placement → 🟢 active →
🗄️ archived`.

## Steer what it builds
Courses are designed backward from your **goal**. Change it: `set goal <…>`, `set daily cap <n>`,
`set level <…>`.

## Anki
Prove a concept → a card is queued → it syncs to your phone. Review as normal; if you lapse a card, that
concept comes back under **"To review"** on [[Home]]. (Your grades aren't touched by lapses — they
record what you *proved*.)

---
See also: [[Home]] · [[Board]] · [[Catalog]]
