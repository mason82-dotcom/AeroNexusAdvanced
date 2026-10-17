---
version: alpha
name: AeroNexusAdvanced Ergebnisraster
description: Local raster catalog extending the existing German flight inspection workspace.
colors:
  background: "#0b1323"
  surface: "#122139"
  border: "#334e69"
  text: "#eaf4ff"
  muted: "#a9bfd8"
  primary: "#75e3bd"
  danger: "#ff9ba8"
typography:
  sans:
    fontFamily: 'system-ui, "Segoe UI", sans-serif'
rounded:
  panel: "13px"
  control: "8px"
spacing:
  panel: "14px"
  gap: "12px"
omitted:
  - section: components
    reason: Existing native controls and panel styles are described in prose below.
---

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
