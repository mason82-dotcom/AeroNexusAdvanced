# Phase 18 – Interaktive lokale 3D-Geländeansicht (MVP)

**Stand: 17. Oktober 2026.** Phase 17 wurde auf dem Raspberry Pi 5 mit
619 Tests, HTTPS, Geo-Polygonen, Flächenstreifen, GeoTIFF-Upload,
32×32-Höhenraster und heruntergeladenem STL anhand einer künstlichen
Testdatei praktisch bestätigt. Phase 18 ist eine **Browser-Erweiterung**,
nicht auf dem Pi oder in Chrome live abgenommen, solange der neue Commit
nicht ausdrücklich getestet wurde.

## Bedienung

1. Unter `/studio` im Bereich **Geo & Gelände** ein nordorientiertes,
   einbandiges GeoTIFF (höchstens 8 MiB; kein NoData) auswählen und
   **3D-Vorschau** drücken. Es gelten weiterhin die Grenzen der
   Phase-17-GDAL-Importprüfung (maximal vier Millionen Rasterpixel,
   maximal 48×48 Stichproben).
2. **Interaktive Großansicht öffnen** oder über die Navigation
   **3D Gelände** auswählen.
3. Mit linker Maustaste oder Finger über dem Canvas drehen bzw. neigen;
   mit dem Mausrad zoomen. Für präzise Eingaben stehen separate
   Schieberegler für **Rotation** (-180 bis 180°), **Neigung** (15–80°),
   **Zoom** (0,5–2,5×) und **Höhenüberhöhung** (1–6×) bereit.
4. Höhenfarben und Drahtgitter separat ein-/ausschalten; mit
   **Ansicht zurücksetzen** auf Anfangswerte zurückkehren.
5. **STL exportieren** bleibt auf der bisherigen Pi-API und verwendet
   ausschließlich die unveränderten Höhenwerte in Metern. Drehung,
   Zoom, Farbe und Überhöhung wirken **nicht** auf den Export.

## Technische Grenzen

- Der Viewer ist ein lokaler **Canvas-2D-Software-Renderer** mit
  orthografischer 3D-Projektion, einer zentrierten metrischen
  Geländefläche, Tiefensortierung der Rasterzellen und Höhenfarbverlauf.
  Kein WebGL, Three.js, zusätzlicher CDN-Dienst oder neues Datenformat.
- Die metrische X-/Y-Darstellung berücksichtigt `x_step_m` und
  `y_step_m`. Die Höhen werden für die Visualisierung relativ zum
  Minimalwert gezeichnet. Bei extrem steilen oder stark überhöhten
  Datensätzen begrenzt die Darstellung Ausreißer; dies **ändert
  niemals** die Höhenwerte im Originalraster oder STL.
- Der Phase-17-Importer gibt derzeit **kein** vollständiges CRS,
  Koordinatenursprung, Datum oder Geoid-/Höhenbezug an den Browser weiter.
  Der Viewer darf daher nicht als georeferenzierte 3D-Karte ausgegeben
  werden. Geo-Objekt-Overlays, verifizierte Höhenprofile und
  Flugfreigabe bleiben bewusst ausgespart.
- Bilder und Geländedaten bleiben auf dem lokalen Pi/Browser. Die
  Esri-/OSM-Kartenkacheln im getrennten Leaflet-Kartenpanel unterliegen
  weiterhin den bisherigen Hinweisen.
- Keine Kopplung an DJI-Flugsteuerung, automatische Waypoint-Höhen,
  Hindernisvermeidung, Cloud-Aufträge oder Flugmissionsexporte.
- Beim Wechsel der GeoTIFF-Datei werden beide Canvas-Ansichten geleert
  und der STL-Button deaktiviert, bis die neue Vorschau geladen wurde.

## Technische Prüfung

Im CI: `python -m pytest -q`, einschließlich neuem Node.js-Test,
der den **tatsächlichen eingebetteten Browser-JavaScript-Code**
auswertet und Projektionspunkte, Farben, Pointer-Rotation,
Zoom, Zurücksetzen, Mesh-Schalter und unveränderte Rasterwerte
überprüft.

Auf dem Pi:

```bash
cd ~/Projekte/AeroNexusAdvanced
git status --short
git pull --ff-only
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
systemctl --user restart aeronexusadvanced
PHASE17_CHECK_LIVE=1 bash scripts/pi/phase17-smoke.sh
```

Nur bei erfolgreichen Tests neu starten. Anschließend die bereits
getestete `terrain-browser-test.tif` über den Browser laden. Großansicht,
Maus-/Touchsteuerung, Höhenfarben und STL-Download im echten Chrome prüfen.
Ein erfolgreicher CI-Lauf allein ist noch **keine** Live-Browserbestätigung.
