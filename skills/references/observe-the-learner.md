# Observing the learner (RFC-013)

As you work with the learner, notice what you learn about *how they learn* and record it. The engine
keeps a decaying, correctable model the learner can see and edit. Record with:

    {{ENGINE}} learner observe --vault {{VAULT}} --aspect <aspect> --value "<short>" \
      --evidence "<why you believe it>" --source <chat|calendar|timing> [--confidence 0.0-1.0]

Only these **aspects** (anything else is rejected — never force-fit):
- `format` — how they like to learn (worked examples, video, reading, problems-first)
- `energy_window` — when they're sharp or dead ("mornings are useless")
- `constraint` — a hard limit ("nothing after 22:00", "≤1h on weekdays")
- `interest` — what genuinely engages them (a topic, a domain, a goal)
- `motivation` — what drives them (shipping, competition, mastery, a deadline)
- `pace` — how much they can really take on

Rules:
- **Only record what they actually showed you** — something said, or a repeated behaviour. Never guess
  from a single data point. The real reason goes in `--evidence`; the learner audits it.
- **One clear thing per call**; keep `--value` short.
- `--confidence`: ~0.4 for one signal, higher when repeated. It decays if you stop seeing it.
- Never record identity, mood, or anything off-platform. If it isn't about *how they learn*, skip it.
- The learner can correct or delete any of it. **Read the model before you personalise; trust it over
  your memory.**

## From the calendar (`--source calendar`)
On the night audit, compare what you booked to what actually happened:
- Blocks they consistently **complete** at a time → `energy_window` (their real productive window).
- Blocks they consistently **skip or move** → a `constraint` or `pace` signal (wrong time, or too much).
  Record it, then book differently next time.

## From timing (`--source timing`)
If a task took much **longer or shorter** than booked, that's a `pace` signal — record it so tomorrow's
load fits. Reading speed and over/under-loading live here.
