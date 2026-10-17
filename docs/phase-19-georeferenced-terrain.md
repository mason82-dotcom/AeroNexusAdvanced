# Phase 19 – WGS84-Gelände, Geo-Objekte und Höhenprofile

**Stand: 17. Oktober 2026.** Neuer Entwicklungsstand, auf dem Pi/Chrome
noch nicht live geprüft. Phase 18 mit interaktivem 3D-Viewer, Phase 17
mit GeoTIFF/STL aus synthetischem 32×32-Raster wurden zuvor auf
Raspberry Pi 5/Chrome getestet.

## Neue Funktionen

- Der bereits bestehende GeoTIFF-Import liefert optional zusätzliche
  `geo`-Informationen in seiner JSON-Antwort. Nur **EPSG:4326 WGS84**
  mit nordorientiertem Raster, korrekten Breiten/Längen und einer für
  lokale Tangentialprojektion ausreichenden Ausdehnung (max. 0,45°
  je Achse) erhält geografische Werte. Projizierte CRS wie UTM liefern
  bewusst `geo: null`, statt sie fälschlich als GPS-Koordinaten zu
  interpretieren.
- Die Koordinaten sind **Rasterpunktmitten** der auf höchstens 48×48
  Punkte heruntergesampelten Daten. GDAL-Resampling benutzt die
  Mittelpositionen der entsprechenden Quellpixelintervalle. Deshalb
  beträgt der Abstand Quellpixelgröße mal Quellrasterbreite durch
  Zielrasterbreite (analog für Y). Kein Anspruch auf Vermessungsgenauigkeit.
- Im Tab **3D Gelände** zeigt ein Infofeld den tatsächlich gelieferten
  EPSG:4326-Bezug oder nennt eindeutig, dass kein WGS84-Overlay möglich
  ist. Gespeicherte Geo-Objekte (Punkt, Linie, Polygon, Kreis) werden
  bei eingeschaltetem Schalter nur dann schematisch über dem 3D-Gelände
  eingeblendet, wenn **alle** benötigten Koordinaten innerhalb
  des sichtbaren Rasterpunktmitten-Gebiets liegen.
- **Klick auf die Geländeoberfläche:** Dreiecks-Hit-Test in der
  dargestellten orthografischen Projektion, anschließende bilineare
  Interpolation des angezeigten Rasterwerts. Dazu WGS84-Breite/Länge,
  falls tatsächlich verfügbar. Bei nicht georeferenziertem Raster wird
  nur die Rasterhöhe ohne erfundene Position angezeigt.
- **Terrain-Draping (Korrektur nach Chrome-Abnahme):** Die rosa
  Geo-Objekt-Konturen werden im 3D-Viewer nicht mehr nur als direkte
  Geraden zwischen erhöhten Eckpunkten gezeichnet. Stattdessen
  werden ihre Segmente in maximal 1024 zusätzliche Teilabschnitte
  abgetastet und mit demselben bilinearen DEM-Höhenwert wie das
  Höhenprofil auf die sichtbare Oberfläche gelegt. Die Originalpunkte,
  das Raster und die STL-Ausgabe bleiben unverändert. Die gezeichneten
  Linien sind weiterhin rein visuell; keine echte Verdeckungsberechnung.
- **Höhenprofil:** Eine bereits **gespeicherte Geo-Linie**, die
  vollständig innerhalb des geeigneten EPSG:4326-Rasters liegt,
  lässt sich auswählen und entlang ihrer Segmentkette mit 129
  Stützstellen abtasten. Angezeigt werden horizontale Länge in
  lokalen Näherungsmetern, DEM-Minimum/Maximum und Profilkurve.
- Kein neuer Datenspeicher: Die GeoObjekte stammen aus der
  bestehenden privaten Studio-API; GeoTIFF-Proben werden nach
  Upload nur temporär im Browser gehalten.

## Wichtige fachliche Grenzen

- **Vertikaler Höhenbezug unbekannt.** EPSG:4326 beschreibt hier
  die **horizontale** Referenz. Die Rasterhöhen können je nach Quelle
  auf EGM96, EGM2008, Ellipsoid oder einem anderen Bezug beruhen.
  AeroNexus führt keine Geoid-Umrechnung durch.
- Abstände und interpolierte Höhen sind **Planungsillustrationen**,
  keine verifizierten Höhen über Grund, Hindernis-/Kollisionsfreigaben
  oder DJI-Missionshöhen. Die ursprünglichen Höhenwerte werden nicht
  an der STL-API verändert.
- Die Overlays werden als 2D-Zeichenpfade auf die gezeichnete
  Rasteroberfläche gelegt; die Darstellung ist keine verdeckungskorrekte
  GIS-3D-Szene. Außerhalb liegende Objekte erscheinen nicht.
- Keine automatische CRS-Transformation von UTM nach WGS84.
  Diese wäre erst nach gesonderter Prüfung der GDAL-/PROJ-Achsenreihenfolge
  und der metrischen Maßstäbe sinnvoll.
- Die ursprünglichen P1-/P2-Flächen-, Medien-, WPML- und DJI-Funktionen
  bleiben getrennt. Kein Flugauftrag, kein DJI-API-Schreibzugriff.

## Prüfung nach erfolgreichem GitHub-CI-Lauf

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

**Nur bei erfolgreichen Tests neu starten.** Im Browser die
synthetische `terrain-browser-test.tif` neu hochladen und
`3D Gelände` öffnen. Der Georeferenz-Hinweis muss EPSG:4326
und Rasterpunktmitten ausweisen. Eine zuvor gespeicherte Einsatzfläche
außerhalb des Test-GeoTIFFs darf **nicht** darüber projiziert werden.
Zum Profiltest eine lokale Linie **innerhalb** des Test-GeoTIFF-
Koordinatenbereichs 8,50005–8,50315° E / 49,19685–49,19995° N
erstellen und speichern; zwei Punkte genügen. Danach die Linie
in der 3D-Ansicht als Profil auswählen und den Graph prüfen.

Der synthetische Test hat keine verifizierte reale Geländereferenz.
Die vertikale Referenz bleibt auch dann unbekannt, wenn auf
dem Bildschirm metrische Zahlen ausgegeben werden.
