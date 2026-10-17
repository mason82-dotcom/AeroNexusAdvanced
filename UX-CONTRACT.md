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
