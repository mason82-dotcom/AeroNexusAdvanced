---
version: alpha
name: AeroNexusAdvanced Cockpit
description: Gemeinsamer Arbeitsbereich für DJI-Missionen und Auswertungen
colors:
  background: "#10151c"
  surface: "#171e28"
  border: "#344151"
  foreground: "#eaf3ff"
  muted: "#a6b4c5"
  primary: "#75e3bd"
  warning: "#e4bd78"
  danger: "#ff9ba8"
typography:
  sans:
    fontFamily: 'system-ui, "Segoe UI", sans-serif'
  mono:
    fontFamily: 'ui-monospace, Consolas, monospace'
rounded:
  control: "4px"
  panel: "4px"
spacing:
  panel: "14px"
  gap: "12px"
---

# Multispektral-Arbeitsplatz

## Overview

Produktoberfläche für Drohnenaufnahmen am Rechner und am Smartphone, deutschsprachig.
Dichte Messwertdarstellung wie ein technischer Auswerteplatz: die Indexkarte trägt
Farbe und Information; Bedienelemente bleiben zurückhaltend. Keine Marketingelemente
in den Fachbereichen. Quellen: `docs/multispectral.md`,
`src/aeronexus/multispectral_page.py`; Verhalten in `UX-CONTRACT.md`.

## Colors

`ui_theme.py` besitzt die gemeinsamen Oberflächen-Tokens;
`multispectral_page.py` besitzt die Analysefarben. Die Frontmatter spiegelt sie:
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

Gemeinsame 4px-Steuerelemente und Panels wiederverwenden.

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
  --bg: #10151c;
  --pane: #171e28;
  --line: #344151;
  --ink: #eaf3ff;
  --sub: #a6b4c5;
  --mint: #75e3bd;
  --red: #ff9ba8;
}
```

Use 14px / 1.45 system-ui body text; 17px panel titles, 12px supporting text.
Panels have 4px corners and 14px padding. The catalog occupies 300px beside a
flexible map; below 800px panels stack and the list remains scrollable. Controls
retain native keyboard behavior and a visible mint focus outline. Selection,
loading, empty, failed, unavailable and stale data states use explicit text.

The map itself has no decorative basemap or animations. Color legends must match
server palette stops. Values and units sit beside the legend, and NoData remains
transparent. Filenames and metadata are inserted as text, never HTML.

# Mission Studio design context

## Tokens

The shared cockpit palette is canonical in `src/aeronexus/ui_theme.py`.
Studio retains its blue interaction accent and its existing semantic states.

```css
:root {
  --accent: #48a8f5;
  --bg: #10151c;
  --pane: #171e28;
  --surface: #202b39;
  --ink: #eaf3ff;
  --muted: #a6b4c5;
  --line: #344151;
}
```

Font stack `Inter, ui-sans-serif, system-ui, "Segoe UI", sans-serif` (no new
font dependency); controls 4px, dialogs 15px corner radius. Spacing follows the
existing screen-specific layout rules.

## Overview

Product console for local drone mission planning on Raspberry Pi, used in
desktop Chrome and on Android. German interface; technical column keys stay
explicitly named. Preserve the existing dark map-and-instrument-panel identity;
this feature adds no rebrand, decorative animation or new font dependency.
Market-specific regulatory behavior is outside the CSV import scope.

## Colors

The canonical runtime owner of shared surfaces is `COCKPIT_CSS` in
`src/aeronexus/ui_theme.py`, applied after each module stylesheet. This file mirrors it: primary → `--accent`,
background → `--bg`, pane → `--pane`, surface → `--surface`, ink → `--ink`,
muted → `--muted`, line → `--line`. New CSV containers consume these variables.
Status panels reuse `.status`, `.status.error` and `.status.good`; status
meaning must also be written in text. There is no token generation pipeline.

## Typography

Use the existing sans stack and compact technical labels. Coordinate tables
use tabular numerals and seven decimal places. No external font download.

## Layout

Use route inventory / map / inspector on desktop; split the left column
on tablets and stack naturally on phones. The CSV dialog alone owns a bounded
scroll body and a table with internal scrolling; actions stay visible. At
narrow widths it fits within 95vw and 90vh. Other panels retain their existing
scroll ownership. CSV tables reveal 50 rows at a time, at most 500 in total.

## Elevation & Depth

Reuse native modal dialog semantics and the existing dark backdrop. Containers
use borders and tonal surfaces instead of new ornamental shadows.

## Shapes

Use the shared 4px controls and 15px dialog corners.

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
4px-Karten mit `--pane` und `--line`, 12px Abstand und 14px Innenabstand folgen
der vorhandenen technischen Dichte. Karten sind ausdrücklich keine klickbaren
Editoren. Lange Namen/Workspace-IDs umbrechen, statt Nachbarspalten zu verbreitern.
Unter schmalen Breiten bleibt eine Kartenspalte; höchstens zwölf Karten je Seite.
Die vorhandenen Scrollbereiche bleiben erhalten. Keine neuen Farben oder Fonts.

## Mission Manager: gemeinsame Routenauswahl

Der Mission Manager verwendet die bestehende native Auswahl `mission-list` mit
Quellgruppen für lokale Entwürfe, Pilot-2-Cloud und FlightHub. Betriebssystem-Popup,
Studio-Tokens, Sidebar-Scrollbereich und bestehende Buttons bleiben erhalten.
`mission-manager-state` besitzt die ausführlichen Quelleninformationen; die
sichtbare Zusammenfassung nennt den Bestand. Fehler und Teilbestände öffnen
die Details automatisch. Schreibgeschützte Cloud-Vorschauen bleiben benannt. Es gibt keine neuen Farben oder Fonts.

## Gemeinsame Navigation und vereinfachte Arbeitsabläufe

`src/aeronexus/ui_navigation.py` ist der kanonische Eigentümer der Navigation
aller sieben Fachmodule. `ui_theme.py` besitzt die gemeinsame Laufzeitpalette:
Text `#eaf3ff`, Hintergrund `#171e28`, Rahmen `#344151`, Fokus `#7ccaff` und
Auswahl `#1d344b`. Systemschrift, 13px Navigation und 3px-Navigationsradien folgen
den bisherigen Arbeitsbereichen. Die fachlichen Viewer behalten ihre Tokens.

Vier direkte Ziele (Live-Status, Missionen, Medien, Übersicht) und eine native
Disclosure für die drei Auswertungen ersetzen die wechselnden Linklisten.
Die aktuelle Seite trägt `aria-current="page"`. Auf schmalen Bildschirmen
öffnet die Auswertungsliste im Dokumentfluss. Studio-Werkzeuge stehen in einer
eigenen Zeile. Auf Desktop übernimmt ein flexibler Rahmen die tatsächliche
Headerhöhe; Seitenleiste und Karte behalten ihre eigenen Scrollbereiche.

Der Mission Manager zeigt Routenauswahl und Grunddaten zuerst. Start/Rückkehr,
Dateiimport, theoretische Routenanalyse und Erläuterungen sind über native
`details` erreichbar. Eingaben bleiben beim Zuklappen erhalten. Quellenzusammenfassung,
Fehler, Speicherzustand und schreibgeschützte Cloud-Vorschauen bleiben sichtbar.
Die Portalseite verwendet dieselbe aufgabenbezogene Sprache, vier tägliche
Einstiege und drei Analyseziele. Technische Einrichtung liegt in einer Disclosure.

## Cockpit nach OpenDroneKit als visueller Referenz

Nutzerauftrag: das Bedienkonzept von OpenDroneKit auf AeroNexus übertragen.
Geprüfte Referenz: `00PrabalK00/OpenDroneKit`, Commit
`1ef6351ba387aaace7e6907d10babc6feb2351d3`, insbesondere `docs/UI_GUIDE.md`.
Eigenständige Implementierung; kein Quellcode, Logo, Demo-Datensatz oder
Desktop-Bridge der Vorlage wird eingebunden. Die Referenz enthält im geprüften
Stand keine projektweite Lizenzdatei.

Die konkrete Anordnung ist nun Routenbestand links, Karte mittig, kontextueller
Inspektor rechts. Ab 1001px scrollen beide Seiten unabhängig. Auf 701–1000px
teilen sich Bestand und Inspektor die linke Spalte; der Canvas bleibt daneben.
Unter 701px entsteht ein natürlicher Dokumentfluss ohne verdeckte Formfelder.
Eine schmale Statusleiste unter der Arbeitsfläche zeigt den tatsächlichen
Missionsspeicherstatus. Andere Studio-Werkzeuge blenden den Missionsinspektor
aus und nutzen den Platz.
Eine Cloud-Vorschau zeigt ihren schreibgeschützten Kontext statt fremder lokaler
Formularwerte. Rückkehr zum lokalen Entwurf erhält alle Eingaben.
