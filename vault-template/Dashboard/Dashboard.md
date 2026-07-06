---
type: dashboard
title: Hermes University
---
# 🎓 Hermes University — Dashboard

> Numbers are precomputed by the engine into `Registrar/status.md` frontmatter and just displayed
> here (Dataview/Bases can't and shouldn't compute your GPA). Requires community plugins:
> **Dataview**, **Tasks**, and **Charts** (obsidian-charts). See RFC §9.

## Now
`= "**Semester** " + this.file.link` <!-- replaced by a Dataview query below -->
```dataview
TABLE WITHOUT ID semester AS "Semester", week AS "Week", gpa_semester AS "GPA (sem)",
      gpa_cumulative AS "GPA (cum)", standing AS "Standing", streak AS "🔥 Streak"
FROM "Registrar"
WHERE type = "status"
```

## Today's plan
```dataview
TASK
FROM "Daily"
WHERE !completed AND due = date(today)
```

## Upcoming exams (next 30 days)
```dataview
TABLE course AS "Course", kind AS "Kind", exam_date AS "When"
FROM "Exams"
WHERE type = "exam" AND exam_date >= date(today) AND exam_date <= date(today) + dur(30 days)
SORT exam_date ASC
```

## Transcript
```dataview
TABLE course AS "Course", unit AS "Unit", band AS "Grade", credits AS "Cr", semester AS "Sem"
FROM "Registrar"
WHERE type = "transcript-row"
SORT semester ASC, course ASC
```

## GPA over time
```dataviewjs
const pts = dv.pages('"Registrar"').where(p => p.type === "gpa_snapshot").sort(p => p.date);
const labels = pts.map(p => "" + p.date);
const data = pts.map(p => p.gpa_cumulative);
if (window.renderChart) {
  window.renderChart({ type: 'line',
    data: { labels, datasets: [{ label: 'Cumulative GPA', data }] },
    options: { scales: { y: { min: 0, max: 4 } } } }, this.container);
} else { dv.paragraph("_Install the Charts plugin to see the GPA graph._"); }
```
