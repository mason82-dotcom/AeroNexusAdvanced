---
version: alpha
name: AeroNexusAdvanced Multispektral
description: Technischer Auswerteplatz für DJI-Multispektralaufnahmen
colors:
  background: "#0b1323"
  surface: "#122139"
  border: "#334e69"
  foreground: "#eaf4ff"
  muted: "#a9bfd8"
  primary: "#75e3bd"
  warning: "#e4bd78"
  danger: "#ff9ba8"
typography:
  sans:
    fontFamily: 'system-ui, "Segoe UI", sans-serif'
  mono:
    fontFamily: 'ui-monospace, Consolas, monospace'
rounded:
  control: "8px"
  panel: "13px"
spacing:
  panel: "14px"
  gap: "12px"
---

# Multispektral-Arbeitsplatz

## Overview

Produktoberfläche für Drohnenaufnahmen am Rechner und am Smartphone, deutschsprachig.
Dichte Messwertdarstellung wie ein technischer Auswerteplatz: die Indexkarte trägt
Farbe und Information; Bedienelemente bleiben zurückhaltend. Keine Marketingelemente
oder Neugestaltung anderer Projektbereiche. Quellen: `docs/multispectral.md`,
`src/aeronexus/multispectral_page.py`; Verhalten in `UX-CONTRACT.md`.

## Colors

Die bestehenden CSS-Variablen in `multispectral_page.py` sind die kanonische
Laufzeitquelle (keine generierten Tokens). Die Frontmatter spiegelt sie:
background → `--bg`, surface → `--pane`, border → `--line`, foreground → `--ink`,
muted → `--sub`, primary → `--mint`, warning → `--amber`, danger → `--red`.
Neue Berichtselemente verwenden diese Variablen. Mint markiert Histogrammbalken,
Fokus und Auswahl; Fehler werden zusätzlich als Text bezeichnet.

## Typography

Systemschrift für UI, Beschriftungen und Tabellen. Monospace für Bildkoordinaten.
Basis 14px/1,45, bestehende Tabellen 12px. Zahlen in der Oberfläche deutsch formatiert;
CSV verwendet Semikolon und maschinenlesbare Dezimalpunkte.

## Layout

Vorhandene Bild-/Kartenansicht mit Seitenbereichen bleibt bestehen. Der Serienbericht
steht als eigener Abschnitt darunter im normalen Dokumentfluss. Zwei Spalten für die
Einstellungen, eine unter 760px; keine zusätzliche feste Seitenhöhe. Die Ergebnistabelle
hat eigenen sichtbaren horizontalen und vertikalen Scrollbereich (maximal 80 Zeilen).
Histogramme haben feste Höhe; ihre Werte sind zusätzlich als Tabelle zugänglich.

## Elevation & Depth

Flache Flächen mit feinen Rahmen; keine neuen Schatten oder Animationen.

## Shapes

Bestehende 8px-Steuerelemente und 13px-Panels wiederverwenden.

## Components

Native Plattform-Auswahllisten sind bewusst akzeptiert, einschließlich der mobilen
Mehrfachauswahl. Buttons, Labels, Status und Fokus folgen dem vorhandenen Viewer.
Scrollbar: globale Baseline in derselben eingebetteten CSS, Track `--bg`, Thumb
`--line`, Hover `--sub`, Forced Colors systemgesteuert. Kein gesonderter Opt-in nötig.
Neue async-Aktionen verwenden deaktivierte Einstellungen, stabilen Statusbereich und
sichtbaren Stop-Zustand; Exporte bleiben während der Berechnung gesperrt.

## Do's and Don'ts

Ungültige Messungen nicht durch Null ersetzen. Überlappende Bilder nicht als Feldfläche
addieren. Die Farbstreckung dient nur der Ansicht, nie der Indexberechnung. Fehlende
oder ungültige Quelldaten sichtbar melden. Bestehende Bild-, Karten- und Stack-Exporte
beim Ergänzen eines Berichts erhalten.




# AeroNexusAdvanced Ergebnisraster

The existing multispectral workspace owns the visual language. The result catalog
extends that application, retaining its navigation, German wording, navy panels,
compact system typography, mint selection and explicit operational states.

## Tokens

```css
:root {
  --bg: #0b1323;
  --pane: #122139;
  --line: #334e69;
  --ink: #eaf4ff;
  --sub: #a9bfd8;
  --mint: #75e3bd;
  --red: #ff9ba8;
}
```

Use 14px / 1.45 system-ui body text; 17px panel titles, 12px supporting text.
Panels have 13px corners and 14px padding. The catalog occupies 300px beside a
flexible map; below 800px panels stack and the list remains scrollable. Controls
retain native keyboard behavior and a visible mint focus outline. Selection,
loading, empty, failed, unavailable and stale data states use explicit text.

The map itself has no decorative basemap or animations. Color legends must match
server palette stops. Values and units sit beside the legend, and NoData remains
transparent. Filenames and metadata are inserted as text, never HTML.

# Mission Studio design context

## Tokens

Mission Studio keeps its own palette (canonical in the `:root` CSS of
`src/aeronexus/studio_page.py`); the multispectral front matter above does not
apply here.

```css
:root {
  --accent: #48a8f5;
  --bg: #0a111f;
  --pane: #111e31;
  --surface: #172740;
  --ink: #eaf3ff;
  --muted: #97aec7;
  --line: #2c425c;
}
```

Font stack `Inter, ui-sans-serif, system-ui, "Segoe UI", sans-serif` (no new
font dependency); controls 9px, dialogs 15px corner radius. Spacing follows the
existing screen-specific layout rules.

## Overview

Product console for local drone mission planning on Raspberry Pi, used in
desktop Chrome and on Android. German interface; technical column keys stay
explicitly named. Preserve the existing dark map-and-instrument-panel identity;
this feature adds no rebrand, decorative animation or new font dependency.
Market-specific regulatory behavior is outside the CSV import scope.

## Colors

The canonical runtime owner is the `:root` CSS in
`src/aeronexus/studio_page.py`. This file mirrors it: primary → `--accent`,
background → `--bg`, pane → `--pane`, surface → `--surface`, ink → `--ink`,
muted → `--muted`, line → `--line`. New CSV containers consume these variables.
Status panels reuse `.status`, `.status.error` and `.status.good`; status
meaning must also be written in text. There is no token generation pipeline.

## Typography

Use the existing sans stack and compact technical labels. Coordinate tables
use tabular numerals and seven decimal places. No external font download.

## Layout

Preserve the editor/sidebar and map layout. The CSV dialog alone owns a bounded
scroll body and a table with internal scrolling; actions stay visible. At
narrow widths it fits within 95vw and 90vh. Other panels retain their existing
scroll ownership. CSV tables reveal 50 rows at a time, at most 500 in total.

## Elevation & Depth

Reuse native modal dialog semantics and the existing dark backdrop. Containers
use borders and tonal surfaces instead of new ornamental shadows.

## Shapes

Preserve the existing 9px controls and 15px dialog corners.

## Components

Native buttons, labeled file input and platform-owned selects are intentional;
the operating system owns popup appearance and keyboard behavior. Native
`dialog.showModal()` supplies focus isolation and Escape; close restores focus
to the CSV opener. Shared `api`, `errorMessage`, `els`, `notice` and editor
history remain the behavior owners. See `UX-CONTRACT.md` for the CSV workflow.

## Do's and Don'ts

- Show explicit coordinate column names; do not guess whether plausible values
  are swapped.
- Render file-derived content through text nodes; never interpolate CSV into HTML.
- Keep route import reversible and persistence explicit.
- Do not add DJI commands or change unrelated screens as part of CSV import.

## Cloud-Routen im Mission Studio

Der lesende Bibliotheksbereich verwendet dieselben Studio-Tokens und das
bestehende Tab-/Sidebar-/Pane-Muster. Native beschriftete Such- und Quellenfelder,
9px-Karten mit `--pane` und `--line`, 12px Abstand und 14px Innenabstand folgen
der vorhandenen technischen Dichte. Karten sind ausdrücklich keine klickbaren
Editoren. Lange Namen/Workspace-IDs umbrechen, statt Nachbarspalten zu verbreitern.
Unter schmalen Breiten bleibt eine Kartenspalte; höchstens zwölf Karten je Seite.
Die vorhandenen Scrollbereiche bleiben erhalten. Keine neuen Farben oder Fonts.

## Mission Manager: gemeinsame Routenauswahl

Der Mission Manager verwendet die bestehende native Auswahl `mission-list` mit
Quellgruppen für lokale Entwürfe, Pilot-2-Cloud und FlightHub. Betriebssystem-Popup,
Studio-Tokens, Sidebar-Scrollbereich und bestehende Buttons bleiben erhalten.
`mission-manager-state` ist die sichtbare Statusregion für Laden, Quellenfehler
und schreibgeschützte Cloud-Vorschauen. Es gibt keine neuen Farben oder Fonts.
