---
version: alpha
name: AeroNexus Mission Studio
description: German-language flight planning console with a map and dense technical controls.
colors:
  primary: "#48a8f5"
  background: "#0a111f"
  pane: "#111e31"
  surface: "#172740"
  ink: "#eaf3ff"
  muted: "#97aec7"
  line: "#2c425c"
typography:
  sans:
    fontFamily: 'Inter, ui-sans-serif, system-ui, "Segoe UI", sans-serif'
rounded:
  control: "9px"
  dialog: "15px"
omitted:
  - section: spacing
    reason: Existing screen-specific layout rules remain canonical; no spacing-system migration.
---

# Mission Studio design context

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
