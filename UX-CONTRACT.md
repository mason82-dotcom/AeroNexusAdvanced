# Mission Studio: CSV workflow contract

This records the CSV addition; existing unrelated workflows are not certified
or redesigned by this change. Visual context: [DESIGN.md](DESIGN.md).

## Sources and domain rules

- `src/aeronexus/wpml_export.py`: WGS84, Matrice 4T/4E, uniform mission height
  relative to start, maximum 500 executed waypoints, explicit return-point rule.
- `src/aeronexus/app.py`: existing bearer or explicit direct HTTPS-LAN access;
  local mission save API is the persistence owner; DJI flight commands blocked.
- `docs/phase-13-desktop-mission-studio.md`: offline drafts, volatile undo history,
  unsaved-change state and explicit saving.
- User-authorized scope: CSV import only; no WPML-action or PV-analysis changes.

## Canonical UI map

| Capability | Owner | CSV behavior | Verification |
|---|---|---|---|
| Select/Listbox | Native labeled select | Explicit delimiter and decimal selection; platform popup accepted | JS state tests; manual Chrome/Android checklist |
| Form | `mission_csv.preview_csv`, native file input | UTF-8, bounded file, complete server validation, line errors | `tests/test_mission_csv.py` |
| Table | Semantic CSV table | 50-row disclosure; bounded own scroller; no selection model | `tests/test_mission_csv_js.py` |
| Scrollbar | Existing browser baseline, CSV scoped table style | Visible internal table scroll; no shell height changes | Narrow-viewport manual checklist |
| Feedback | Existing `notice`, `errorMessage`, `.status` | Persistent modal validation feedback, successful editor notice | JS failure/success tests |
| CRUD | Existing mission API and editor history | Preview never saves; apply replaces current waypoints as one undo step | API round-trip and JS undo tests |

## Operation and recovery

Opening the dialog does not modify the mission. The user selects one file and
explicitly requests a preview. During checking, repeat checking is disabled,
status announces work and closing cancels the request. A 30-second timeout is
recoverable by retry. File or format changes cancel/invalidate prior results;
late responses cannot enable an old route. Errors preserve the selected file.

Only a completely valid preview enables replacing waypoints. The map and
table show file order; the map is optional if Leaflet or tiles fail. The current
editor snapshot must still match the preview baseline. Applying preserves
mission identity and settings, replaces waypoints and records one reversible
editor action. Existing saved data changes only through the existing Save flow.
CSV previews and files are never put into browser persistent storage.

Native dialog focus containment and Escape are used. Close returns focus to the
opener. Errors focus a textual status. All new controls and status text are
German, except explicit file column identifiers. No product flow introduced
here calls alert/confirm/prompt.
