# Multispektral-Modul DJI Mavic 3M (`/multispectral`)

Stand: 17.10.2026 · Multispektral-Qualitätssicherung

Eigener Web-UI-Tab für die vier Multispektralbänder der Mavic 3M (Grün
560 nm, Rot 650 nm, RedEdge 730 nm, NIR 860 nm; 16-Bit-TIFF 2592×1944) aus
dem schreibgeschützten MinIO-Medienindex.

## Datenbasis und Katalog

- Bänder werden über die XMP-`CaptureUUID` zu Aufnahmen zusammengeführt –
  unabhängig vom Dateinamen. Damit passen auch FlightHub-Uploads
  (`org_*.tiff`) und SD-Importe in getrennten Ordnern zusammen. RGB-Foto
  (`_D.JPG`) und MS-Vorschau (`_F.JPG`) derselben Auslösung werden verknüpft.
- Privater Katalog `multispectral.sqlite3` (0600). Aufbau ausdrücklich auf
  dem Pi: `.venv/bin/python -m aeronexus.multispectral` – liest per Range nur
  die ersten 256 KiB je Datei, inkrementell per ETag, keine MinIO-Schreibzugriffe.
- Stand 17.10.2026: 4 vollständige 4-Band-Aufnahmen (3 × 15.10.2026 mit RTK
  und gültigem Sonnenlichtsensor, 1 Innenaufnahme vom 01.10.2026 ohne
  Einstrahlungswert – bleibt mit Warnung sichtbar, Berechnung gesperrt). Reine RGB-Aufnahmen ohne
  Bänder werden nicht gelistet.

## Verarbeitung (DJI *Mavic 3M Image Processing Guide* v1.0, 08/2023)

1. Kamerasignal: `(DN/2^bits − BlackLevel/2^bits) / (SensorGain · ExposureTime/1e6)` (Gl. 9)
2. Vignettierung: `· (k5·r⁶ + … + k0·r + 1)`, r ab `CalibratedOpticalCenter` (Gl. 7/8)
3. Objektiv-Entzerrung mit `DewarpData` (fx, fy, cx, cy, k1, k2, p1, p2, k3)
4. Bandausrichtung mit `CalibratedHMatrix` (realer → idealer Bildraum)
5. Relative Reflexion: `· SensorGainAdjustment / Irradiance` (Gl. 4–6)

Schritte 3 und 4 werden als inverse Abbildung mit bilinearer Abtastung in
numpy umgesetzt (kein OpenCV nötig). Ausgabe in 1296×972 (Standard),
648×486 oder voller Auflösung.

### Gültigkeit und Fehlerbehandlung

- Sonnenlichtsensor: ausschließlich `LS_status=1` oder `2` und eine
  `Irradiance > 1` werden zur Reflexionsberechnung zugelassen. Fehlende,
  ungültige oder Platzhalterwerte sperren die betroffenen Bänder mit HTTP 422;
  es wird kein künstlicher Ersatz für die Einstrahlung verwendet.
- Pixel am/unter dem Schwarzwert, gesättigte Pixel und nicht positive oder
  nicht endliche Reflexion werden als NaN ausgeschlossen. Indizes werden
  nicht nachträglich auf −1…1 begrenzt; insbesondere LCI kann aufgrund seiner
  anderen Nennerdefinition auch außerhalb dieses Bereichs liegen.
- Singuläre/ungültige HMatrix, ungültige Dewarp-Brennweiten und abweichende
  Bandrastergrößen ergeben kontrollierte Fehler statt interner Serverfehler.
- Beim Aufnahme-, Ebenen- oder Auflösungswechsel werden Raster, Messungen
  und Exportfreigaben sofort verworfen. Fehlgeschlagene Berechnungen können
  daher kein altes Bild unter einem neuen Aufnahmenamen exportieren.
  Verspätete Antworten überschreiben keine neuere Auswahl; CIR-Bänder sind
  während des gesamten Abrufs an dieselbe Aufnahme gebunden.
- Bereits gespeicherte NDVI-Übersichten werden durch eine neue
  Verarbeitungsversion ungültig und müssen neu berechnet werden. Der
  CLI-Bericht enthält `ndvi_failed`; einzelne fehlerhafte Aufnahmen verhindern
  die Berechnung anderer Aufnahmen nicht. Bei Fehlern liefert die CLI Exitcode 1.

**Grenzen:** Der gemeinsame Faktor ρ_NIR ist ohne Reflexions-Referenztafel
unbekannt → Bandwerte sind *relative* Reflexion. NDVI, GNDVI, NDRE und LCI
sind nach Gl. 6 davon unabhängig. DJIs optionaler Schritt 4 (ECC-/Merkmals-
ausrichtung bei schnellem Flug) ist nicht umgesetzt; die HMatrix gilt für
große Entfernungen – Nahaufnahmen zeigen Parallaxe zwischen den Bändern.

## Funktionen

- Ebenen: NDVI, GNDVI, NDRE, LCI, Falschfarben-CIR (NIR/Rot/Grün) und die
  vier Einzelbänder (relative Reflexion).
- Farbskalen Rot–Gelb–Grün, Viridis, Graustufen; Bereich P2–P98, −1…1,
  0…1 oder manuell; Wert unter dem Mauszeiger.
- Statistik (Min, P5, Median, Mittel, P95, Max) und NDVI-Klassenanteile
  (Richtwerte: < 0, 0–0,2, 0,2–0,4, 0,4–0,6, > 0,6).
- Punkt- und Bereichsmessung; Export PNG, Messungen CSV, Raster CSV, JSON-Bericht.
- Bandtabelle mit Wellenlänge, Sonnenlichtsensor-Irradiance und Belichtung;
  Seriennummern werden nicht angezeigt.

## Karte (Ansicht „Karte“)

- Aufnahmepunkte, eingefärbt nach NDVI-Median (Rot–Gelb–Grün, grau = noch
  nicht berechnet); Tooltip mit Zeit, NDVI, Höhe, Pitch und Bodenauflösung;
  Klick wählt die Aufnahme.
- Nadir-nahe Aufnahmen (Pitch −75…−105°, Höhe > 1 m): Footprint aus
  Strahl-Boden-Schnittpunkten unter Berücksichtigung von Pitch und Yaw und – optional –
  das NDVI-Bild auf allen vier Footprint-Ecken (projektives Dreiecksnetz, Leaflet-Overlay,
  max. 30 gleichzeitig). Schräg-/Bodenaufnahmen: Sichtkegel in Blickrichtung.
- Sichtfeld aus der kalibrierten Brennweite im XMP (M3M 2170 px bei
  2592×1944 → 61,7° × 48,3°, 73,5° diagonal); angezeigte Bodenauflösung ist
  die größere zentrale Pixelabmessung `Höhe / (Brennweite · cos(Pitch+90°)²)`.
  Annahme: ebenes Gelände auf Startpunkthöhe, kein Gimbal-Roll. Die Überlagerung
  ist keine vermessungstaugliche Orthorektifizierung. Seit PR #26 nutzt die
  Thermal-Karte dieselbe Projektion geneigter Kameras.
- NDVI-Übersichten werden als lokaler Cache im Katalog gespeichert, sobald
  der NDVI einer Aufnahme berechnet wurde; ändern sich Bänder (ETag), wird der
  Wert verworfen. Fehlende Übersichten: Schaltfläche „NDVI-Übersicht
  berechnen“ oder auf dem Pi `.venv/bin/python -m aeronexus.multispectral --ndvi`.
- Der Katalog versioniert seine Metadaten (`META_VERSION`); nach
  Formaterweiterungen werden die Dateiköpfe beim nächsten Scan neu gelesen.
- Live (17.10.2026): 3 Aufnahmen mit RTK-Position (Bodenaufnahmen, Kamera
  horizontal → Sichtkegel), NDVI-Median 0,56–0,57; 1 Innenaufnahme ohne GNSS.

## API (Viewer-Zugriff wie Mission Studio)

| Route | Inhalt |
|---|---|
| `GET /multispectral` | Web-UI-Tab |
| `GET /api/v1/multispectral/captures` | Aufnahmen mit Bändern, Ebenen, Warnungen |
| `GET /api/v1/multispectral/map` | Positionen, Footprints/Sichtkegel, NDVI-Übersicht |
| `GET /api/v1/multispectral/captures/{uuid}/layers/{layer}?scale=` | Statistik, Formel, Methode |
| `GET /api/v1/multispectral/captures/{uuid}/layers/{layer}/grid?scale=` | float32-LE-Raster (NaN = ungültig), `X-Grid-Width/Height` |

Abhängigkeit: optionales Extra `pip install -e '.[multispectral]'` (numpy).

## Live-Abnahme auf dem Pi (17.10.2026)

- Katalog: 30 Dateien gelesen, 4 Aufnahmen mit allen vier Bändern.
- Aufnahme 15.10.2026 14:02: NDVI-Median 0,57; 46 % dichter Bewuchs.
  Erstberechnung inkl. MinIO-Lesen ca. 2 s, weitere Ebenen aus dem Cache < 1 s.
- Sichtprüfung NDVI/CIR: Kanten der Bänder deckungsgleich, Vegetation hoch,
  Wand/Boden niedrig; leichte Farbsäume an nahen Ästen (Parallaxe).
- Browser-UI: vom Anwender im Browser bestätigt (Bildansicht); Kartenansicht per Node geprüft.

Die Live-Abnahme oben beschreibt den Stand vor der Qualitätssicherung.
Die neuen Fehlerfälle sind mit synthetischen TIFFs, API-Tests und dem tatsächlich
eingebetteten Viewer-JavaScript regressionsgetestet. Nach dem Update auf dem Pi
den Katalog mit `.venv/bin/python -m aeronexus.multispectral --ndvi` aktualisieren,
um gespeicherte Übersichten nach den neuen Regeln neu zu berechnen.

## Vorschläge

- Reflexions-Referenztafel (Kalibrierpanel) zur absoluten Reflexion.
- Mosaik/Orthofoto aus Flugserien (z. B. über OpenDroneMap) und Indexkarten
  auf der Operations-Karte.
- Zonierung (Applikationskarten) aus NDVI-Klassen mit Export als Shapefile/GeoJSON.

