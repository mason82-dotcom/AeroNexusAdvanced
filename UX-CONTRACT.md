# Multispektral: Verhaltensvertrag für Serienberichte

Visuelle Quelle: `DESIGN.md`. Geltungsbereich: neuer Serienbericht in `/multispectral`;
keine nachträgliche Behauptung einer projektweiten UI-Migration.

| Fähigkeit | Kanonischer Eigentümer | Quelle / Variante | Verifikation |
|---|---|---|---|
| Select/Listbox | Native `select` im Viewer | Betriebssystem-Popup, Mehrfachauswahl der Aufnahmen | Browser-Test, schmale Ansicht |
| Form | `report-settings` / `runReport` | Beschriftete Felder, eigene Validierung, kein HTML-Form-Submit | Browser-Test für Schwelle/Auswahl |
| Scrollbar | Globale CSS in `multispectral_page.py` | Dokument und Ergebniscontainer | CSS und 390px-Browserprüfung |
| Toast | Inline `report-state` / `report-validation` | Status-Live-Region und Validierungsfehler | Browser-Test |

## Fachliche Quellen

- Viewer-Zugriff: `_studio_workspace` / `_ms_service` in `app.py`; dieselbe
  LAN-/Token-Regel wie bei bestehenden Multispektral-APIs.
- Datenlebenszyklus: `docs/multispectral.md`, `MultispectralService.layer`; nur
  bestehende kalibrierte Raster lesen. Kein MinIO-Schreiben, kein Flugkommando.
- Quelldatenänderung: `DjiMediaChanged` und Katalog-`source_key`; betroffene
  Aufnahme vollständig als Fehler ausweisen, keine alten Masken weiterverwenden.
- Berichte sind flüchtige Berechnungsergebnisse und explizite Browserdownloads.
  Keine neue serverseitige Aufbewahrung, Löschung, Abrechnung oder Rechteverwaltung.

## Ablauf

Auswahl von 1–20 Aufnahmen und 1–4 vorhandenen Indizes → berechnen → Einstellungen
und Exporte sperren → Aufnahmen nacheinander verarbeiten → Anzahl und Teilfehler
anzeigen → CSV/JSON freigeben. Verarbeitungsmaßstab und Maskenschwelle stehen im Export.
Die Maske verwendet endliche NDVI-Werte ab der eingegebenen Schwelle; jede Statistik
verwendet zusätzlich die gültigen Pixel der jeweiligen Ebene. Kein implizites Gruppieren
nach Flug oder Summieren überlappender Bildflächen.

Stoppen beendet die Serie nach der laufenden Aufnahme; vollständige Teilergebnisse
bleiben exportierbar und heißen Teilbericht. Transportfehler beenden die Serie sichtbar,
fachliche Fehler einzelner Ebenen stehen in eigenen Ergebniszeilen. Eine leere Auswahl
nach Maskierung hat null ausgewählte Pixel und keine numerischen Statistiken.

Geänderte Einstellungen verwerfen die bisherigen Exportfreigaben. Auswahl der aktuellen
Bildaufnahme oder Wechsel zwischen Bild und Karte verändert den separat gewählten
Serienbericht nicht. Erneutes Berechnen startet einen neuen, klar begrenzten Lauf.
Ergebnisse, Fehler und Histogramme werden über `textContent` ausgegeben.


# Result raster UX contract

Owner: AeroNexusAdvanced result catalog, route `/results`.

Primary workflow: place completed local GeoTIFFs → explicitly scan → search and
select → inspect metadata → view tiles → adjust display without altering sources.
The scan button explains the local folder workflow; refresh reads only the catalog.
Search has a clear action, empty result feedback and 50-item pagination. Every
control has a visible label; repeated filename buttons expose selection state.

No previous layer survives selection changes or failed statistics. Superseded
catalog/statistics/tile callbacks cannot replace the newest selection. A failed
catalog request clears selection. Invalid display bounds leave the current layer
visible and report the validation error. Tile failures offer retry and explain
rescanning changed files. Missing optional dependencies leave the catalog usable.

Scans are explicit, read source files only, replace metadata atomically, report
rejections and preserve the old catalog on directory/limit failure. No upload,
remote URL, source deletion, automatic conversion, mission or drone commands.
No source filesystem paths or credentials appear in the browser.

Verification: actual raster fixtures and API policy tests; Node runtime tests for
response ordering, failed loads, tile settings and text insertion. Actual browser
layout and Pi dataset performance must be checked on the target deployment.

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
