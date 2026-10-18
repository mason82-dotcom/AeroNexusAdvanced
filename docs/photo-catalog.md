# DJI-Fotokatalog (`/media`)

Der Fotokatalog ordnet jedes JPEG aus dem schreibgeschützten MinIO-Index nach
**Drohnenmodell, Kamera und Flug**. Die Zuordnung stammt aus den Bild-Metadaten
selbst, nicht aus dem Dateinamen. Damit werden auch FlightHub-Uploads mit
Namen `org_*.jpg` erkannt, die kein `_W`/`_T`/`_Z`-Suffix tragen.

## Umfang

- **Modelle:** M3E (Mavic 3 Enterprise), M3T, M3M, M4T sowie weitere
  DJI-Modelle mit gleichem XMP-Schema.
- **Kameras:** XMP `drone-dji:ImageSource`, also `WideCamera`, `ZoomCamera`,
  `InfraredCamera` und `MS_CAMERA`. Bei M3M-RGB ohne Angabe wird `VisibleCamera`
  verwendet.
- **Je Bild:** Aufnahmezeit, Position, relative Höhe, Gimbal-Pitch und -Yaw,
  Bildgröße und EXIF-Brennweite in Kleinbild-Äquivalent.
  Seriennummern und NTRIP-Daten werden nicht gespeichert.
- **Geometrie:** Das Sichtfeld folgt aus der KB-Brennweite (Diagonale
  43,27 mm), daher ist keine Kameratabelle nötig. Footprint und GSD gibt es
  nur bei Nadir-Aufnahmen (±15°) über ebenem Gelände auf Starthöhe.
  - Beim M3E-Weitwinkel ergibt das 71,6° × 56,8° und 1,64 cm/px bei 60 m.
    Das entspricht DJIs Angabe H/36,5.
- **Flüge:** Eine Pause von mehr als 15 Minuten beginnt einen neuen Flug.
  Die Gruppierung ist dieselbe wie im Thermal-Modul.
- **Unplausible Positionen:** Manchmal schreibt DJI in die ersten Bilder nach
  dem Einschalten einen veralteten Fix, auch mit Status „RTK“.
  - Positionen, die mehr als 20 km vom Median ihres Flugs entfernt liegen,
    werden markiert (`position_outlier`). Auf der Karte erscheinen sie
    gestrichelt.
  - Die Kartenansicht richtet sich nur nach plausiblen Punkten.
  - Flüge mit weniger als drei Positionen werden nicht bewertet.

## Thermal-Integration

Infrarotbilder, die nur über die Metadaten erkannt werden (`org_*.jpg` von
M4T/M3T), fließen in Thermal-Liste, Thermal-Karte und Flugauswertung ein.

## Betrieb

- **Automatisch:** Der Medien-Sync führt den Schritt `photo_catalog` direkt
  nach dem Medienindex und vor dem Thermal-Geo-Index aus.
  - Inkrementell nach ETag: Pro neuem Bild wird nur der erste Teil der
    Datei gelesen (Range-Read, 256 KiB).
  - Gelöschte Objekte fallen aus dem Katalog.
- **Manuell:** `python -m aeronexus.photo_catalog`
- **Speicher:** private SQLite-Datei `photo_catalog.sqlite3` mit den Rechten
  0600 im Workspace.

## API (Lesezugriff wie die übrigen Medien-APIs)

| Endpunkt | Inhalt |
|---|---|
| `GET /api/v1/photos/summary` | Modelle mit Kameras und Anzahl, Scanzeit |
| `GET /api/v1/photos/flights?model=&camera=` | Flüge mit Zeitraum, Bildzahl, Medianhöhe |
| `GET /api/v1/photos?model=&camera=&flight=&limit=&offset=` | Bildliste (max. 200 je Seite) |
| `GET /api/v1/photos/map?model=&camera=&flight=` | Positionen, Footprints, GSD, Ausreißer-Markierung |

`model` und `camera` sind auf `[A-Za-z0-9_]{1,32}` begrenzt, `flight` ist eine
64-stellige Hex-ID. Antworten enthalten keine Objektschlüssel. Das Original
öffnet sich über `/api/v1/studio/dji-media/{id}/file`.

## Kleine, begrenzte Kartenabfrage für Diagnose

Für schreibgeschützte Abnahmen kann zusätzlich `limit` (1 bis 10000) an
`GET /api/v1/photos/map` angehängt werden. Ohne Parameter bleibt der
bisherige Standard von 10000 erhalten, sodass die UI keine neue
Paginierung braucht. Beispiel: `/api/v1/photos/map?limit=10`.

`total` meldet weiterhin die Gesamtanzahl der gefundenen Datensätze;
`items`, `without_position` und `position_outliers` beziehen sich
auf die ausgewählte Stichprobe. Die Ausreißerbewertung einer kleinen
Stichprobe kann von der kompletten Flugübersicht abweichen.
