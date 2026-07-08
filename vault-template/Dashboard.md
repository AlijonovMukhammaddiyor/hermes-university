# 📊 Dashboard

*Requires the **Dataview** plugin. Every number is computed by the engine (see `Registrar/status.md`) —
this note only displays what's there.*

- 🗂️ [[Board]] — your task board  ·  🗓️ [[Registrar/Schedule]]  ·  🎓 [[Registrar/DegreeProgress]]  ·  📄 [[Registrar/Transcript]]

## Open tasks
```dataview
TASK FROM "Daily" WHERE !completed
```

## Last 7 days
```dataview
TABLE file.mtime AS "Updated" FROM "Daily" SORT file.name DESC LIMIT 7
```
