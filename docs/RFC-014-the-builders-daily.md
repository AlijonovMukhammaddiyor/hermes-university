# RFC-014 — The Builder's Daily (a newspaper, not a digest)

Status: **ACCEPTED — implementing** · Date: 2026-09-13
Related: [RFC-010](RFC-010-daily-briefing.md) (the university's own briefing, unchanged by this).

## 0. Why

The standalone startup briefing produced a 24 KB Obsidian note every morning: a wall of headlines,
correct and unread. Three things were wrong with it, and only the first is about presentation.

1. **A list is the weakest rendering of the material.** The same content, set as a paper — a front
   page, sections, a running order — is skimmable in minutes and finishable, which a scrolling note
   never is.
2. **Numbers written by a model drift.** TrustMRR returns `last30Days`, `mrr` and `total` under one
   `revenue` object, and prose that calls an all-time figure "MRR" is a factual error the reader
   cannot catch. Whoever owns the number decides whether it is right.
3. **Being informed is not the goal.** The reader is building cash flow and sellable assets from one
   person in Tashkent. An item that changes nothing he does next month is a cost, not a benefit,
   however true it is.

## 1. Shape

An edition is a folder of markdown, in the [vael-paper](https://github.com/vaelkeep/vael-paper)
format. That project paginates and prints; it has no opinion about what wrote the folder, so the two
halves stay replaceable.

```
$VAULT/Papers/<name>/paper.json      masthead, section order, and the house rules
$VAULT/Papers/<name>/<date>/articles/  01-*.md … one file per story
```

Three kinds of writer fill it, in order:

- **Data desks** — code, never a model. `trustmrr_desk` (provider-verified indie revenue, banded to
  what one person could copy) and `showhn_desk` (launch attention, de-duplicated across relists).
  They own every figure they print and say what each metric measures — *points are attention, not
  adoption*; *30-day is not MRR is not all-time*. A desk that cannot source its board exits nonzero
  and the story is dropped rather than guessed.
- **Prose desks** — the model, one story at a time, over a handful of already-summarised items.
- **The lead desk** — last, seeing everything: the day's best opportunity written as a decision.

## 2. The entry test

An item earns its place by naming the move it enables — build it, copy it, buy it, sell into it,
price against it. If the honest answer is "now he knows", it is one line in a digest or it is
nothing. This is applied **while searching**, not as a filter afterwards: the job is not to find the
day's news but the day's openings, and the fetches should be spent where one exists.

An opportunity carries six things, compressed into 60–90 words as figures rather than prose: what it
earns now, what it costs to build and run, why *he* can win it, its ceiling and what that is worth at
the ~13× monthly these products trade at, the first step this week, and what kills it.

## 3. Enforcement

Two checks gate publication, and neither is a suggestion:

- `vael-paper-check` — will the edition **print**.
- `house_check.py` — is it the **paper it is meant to be**: the edition total, a per-pillar total, and
  a per-section article count, all read from `paper.json` under `house` so they are the owner's
  numbers rather than the script's.

The second exists because the three-story cap sat in the skill for two editions and the section came
back with six both times. A threshold the model must satisfy holds where a sentence does not — the
same reason the desks own the figures. **The skill deliberately does not restate those numbers**;
duplicated limits drift out of step with the ones actually checked.

## 4. Delivery

- **PDF** — `make_pdf.py` sets the edition for print: real sheet sizes (broadsheet through A4), the
  column count and body size chosen from the edition's own word count, one display face with rank
  carried by size, and a spacing scale derived from the body size. Headlines link to their source.
- **Telegram** — `send_edition.py` posts it with `sendDocument`. This exists because the agent has
  **no file-sending tool**: the skill was told to "attach the PDF" and could not, so editions were
  printing into a git-ignored directory nobody opened.
- **Screen** — `build_web.py` emits a self-contained page that reflows to one column on a phone,
  for publishing as a link.

Rendered output — the site, the chart plates, the PDF — is git-ignored. All of it is regenerated from
the markdown in about a second, and a repository can never reclaim what it once carried.

## 5. What this does not touch

The university. `registrar`, `examiner`, `professor` and `briefer` are unchanged, as are the
`uni-*` crons. The paper **reads** `Registrar/state.json`, `records/` and the university's own
`Briefing/sources.yaml` — that last one because the startup source list carries no AI-lab or
engineering feeds at all — and writes to none of them.

## 6. Notes for whoever rebuilds this

- The skill that drives the paper is **hand-authored on the host**, not rendered from
  `skills/*.template.md`, and carries personal detail. It lives in the private vault;
  `hermes_backup.sh` mirrors `~/.hermes/skills/hermes-university/` into `_source/skills/` so a
  rebuild recovers it. It is deliberately absent from this repository, which is public.
- A cron job pinned to a model is skipped when the global model config drifts (`drift_skip`), and
  **stays** skipped. Changing the model means re-pinning every job in the same breath.
- `git rm` before `rm` when clearing a tracked edition: vault-sync's `git pull` restores missing
  tracked files within two minutes, including underneath a run in progress.
