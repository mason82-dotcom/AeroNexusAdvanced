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
