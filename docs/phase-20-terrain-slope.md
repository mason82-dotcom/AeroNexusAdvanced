# Phase 20 – Lokale DEM-Hangneigungsanalyse im Mission Studio

**Stand: 17. Oktober 2026.** Umsetzung über GitHub-PR #16;
noch nicht auf Raspberry Pi 5 / Chrome live validiert.

## Funktion

- Im Tab **3D Gelände** gibt es den optionalen Schalter **Hangneigung einfärben**.
  Die Farbklassen sind Grün unter 8°, Gelb 8–15°, Orange 15–30°,
  Rot ab 30°. Der Schalter hat Vorrang vor den bisherigen Höhenfarben;
  Raster-Gitternetz, Rotation, Zoom, Überhöhung und WGS84-Geo-Objekte
  bleiben separat nutzbar.
- Beim GeoTIFF-Import zeigt der Viewer den **mittleren und maximalen
  Zellneigungswinkel** und die Anzahl der Zellen mit mindestens 30°
  Neigung an. Die Übersicht verwendet ausschließlich die bestehende
  lokal auf höchstens 48×48 Stützpunkte heruntergesampelte Höhenmatrix.
- Klick auf die 3D-Geländeoberfläche zeigt zusätzlich zur unveränderten
  Rasterhöhe und optionalen WGS84-Position die **lokale Neigung** in Grad.
- Berechnung: bilinearer DEM-Höhengradient aus den echten Höhenunterschieden
  pro X-/Y-Schritt in Metern, `atan(hypot(dz/dx,dz/dy))`, Ergebnis in Grad.
  Je Zelle wird der Mittelpunkt ausgewertet. **Die visuelle
  Höhenüberhöhung fließt nicht in den Messwert ein.**
- Umschalten, Neuladen und Reset verwenden ausschließlich temporären
  Browserzustand. Keine weiteren APIs, Speicherformate, externen Dienste,
  DJI-Lese-/Schreibrechte oder Abhängigkeiten erforderlich.

## Messgrenzen und Sicherheit

- Die Neigung stammt aus einem **resampelten** DEM, nicht aus dem
  vollständigen Quellraster. Sehr kleine Kanten/Objekte können fehlen.
  Bei EPSG:4326 werden lokale angenäherte Meterabstände benutzt.
- Der **vertikale Höhenbezug bleibt unbekannt**; es gibt keine Prüfung,
  ob der Datensatz überhaupt ein geeignetes DTM/DSM ist.
- Die Schwellwerte sind ausschließlich eine Kartenfarblegende und
  **keine** Sicherheitsgrenzwerte, Hindernisfreigabe, Start-/Landeprüfung
  oder Grundlage automatischer DJI-Missionshöhen.
- Georeferenzierung aus Phase 19 unverändert: nur geeignetes,
  nordorientiertes EPSG:4326; projizierte Raster weiterhin ohne WGS84-Overlay.
- Bestehende STL-Ausgabe verwendet das unveränderte `TerrainGrid`.

## Qualität und Pi-/Chrome-Abnahme

Die neuen Tests führen die **wirklich eingebetteten
JavaScript-Funktionen** mittels Node.js aus und prüfen: flaches Raster,
45°-Rampen in X/Y, diagonale Neigung, Zellstatistik, Farbklassifikation,
Schalter und Reset, unveränderte Originalhöhen.

Nach GitHub-CI-Erfolg auf dem Pi die Änderungen bewusst einspielen:

```bash
cd ~/Projekte/AeroNexusAdvanced
git status --short
git pull --ff-only
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
# Nur bei erfolgreichen Tests:
systemctl --user restart aeronexusadvanced
```

Anschließend in Chrome **Geo & Gelände** → DEM-GeoTIFF hochladen
→ **3D Gelände**: die Neigungslegende einschalten, durch Umschalten
Höhenfarben/Neigungsfarben vergleichen, bei einem geneigten Raster
einzelne Zellen anklicken; Zoom und Höhenüberhöhung dürfen den
angegebenen numerischen Neigungswert **nicht verändern**.
Nach Dateiwechsel muss die Neigungsstatistik wieder leer sein.
