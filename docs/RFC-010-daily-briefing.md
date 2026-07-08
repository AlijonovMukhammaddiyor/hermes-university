# RFC-010 — Daily Tech Briefing (a recurring digest, not a course)

Status: **ACCEPTED — implementing** · Date: 2026-07-08
Canonical description: [`ARCHITECTURE.md`](../ARCHITECTURE.md).

## 0. Why
The learner wants a daily, curated summary of the tech/AI/engineering blogs and news worth reading.
That is **not a course**: a course is a mastery-gated curriculum (units → proofs → finals → GPA →
graduation), and daily news has no mastery, no finals, nothing to complete. Forcing it into
`course.yaml` would fight the authored gate (units/outcomes/dossier that don't apply) and produce a
broken half-course. So the Briefing is its own lightweight subsystem on the **same surfaces**
(Telegram + Obsidian + Home), with a different engine.

## 1. Shape
- **Sources are data, in the vault** — `<vault>/Briefing/sources.yaml` (seeded from
  `vault-template/Briefing/`), editable in Obsidian or via the bot (`add source`/`remove source`) and
  auto-synced. `rss`/`api` preferred (reliable); `paid: true` = titles/teasers only; `weight: high` =
  always scanned.
- **A daily cron** (`uni-briefing`) runs the **briefer** skill: gather recent items (RSS/HN-API first,
  then fetch/web-search), summarize, then **curate** — the **3–5 genuinely worth-reading** items with a
  one-line *why* + a short summary (**top picks**), then quick **headlines** for the rest by category.
- **Delivered** as: a Telegram morning digest (plain, digest-voice) · a searchable vault note
  `Briefing/YYYY-MM-DD.md` (Obsidian callouts + links) · a "Today's reads" link on `Home.md`.
- **Interactive**: `briefing` / `what should I read` sends today's (or generates it on demand).

## 2. Curation rule
Signal over noise. A "top pick" is novel, important, or unusually well-argued — not just recent. Group
headlines by category so the long tail is skimmable. Avoid repeating an item picked in a recent
briefing (check the last note). Never fabricate a summary for a source that couldn't be fetched — say
"titles only" for paywalled/failed sources.

## 3. Boundaries (honest)
- Paywalled sources (Pragmatic Engineer, Lenny's, Stratechery, most Medium) → titles/teasers only.
- `medium.com`/`news.ycombinator.com` raw are too broad — follow specific Medium publications; use the
  **HN Algolia front-page API**.
- Fetch reliability varies (RSS reliable; scraped homepages less so). "Worth reading" is model
  judgment — good, tunable, not perfect.

## 4. Not
Not a course (no mastery/GPA/finals). Not a schema change to `course.yaml`. Not full-text scraping of
paywalled content. Not a replacement for the daily learning loop — it runs alongside it.

## 5. Verification
`uni-briefing` produces a dated `Briefing/` note with a Top-picks callout + category headlines + a
sources-covered line; a Telegram digest with the top picks + a link; `Home` links the latest briefing;
paid/failed sources are shown as titles-only, never invented.
