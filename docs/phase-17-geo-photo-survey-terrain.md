# Phase 17 – Mission Studio P1/P2/P4 (lokale Planung, kein DJI-Flugkommando)

**Stand 17. Oktober 2026:** Phase 17 ist seit PR #4 in `main` integriert.
Die ergänzenden Pi-Bereitschaftsprüfungen und Geo-Editor-/DEM-Sicherungen
werden separat per Pull Request geprüft. **Nicht live auf dem Pi oder in
Chrome bestätigt**; keine realen GeoTIFF-/Matrice-Flugdaten verwendet.

Für die kontrollierte Pi-Installation und manuelle Abnahme siehe
[Phase-17-Pi-Validierung](phase-17-pi-validation.md).

## Module und Bedienung

Im Mission Studio unter `/studio` ist der neue Arbeitsbereich
**„Geo & Gelände“** vorhanden.

### P1 – Geo-Objekte und GeoPhoto

- Geo-Objekte als **Punkt, Linie, Polygon oder Kreis** direkt in der
  Leaflet-Karte skizzieren, benennen, speichern, bearbeiten, löschen.
  Separat vom WPML-Missionsentwurf in
  `~/.local/share/aeronexusadvanced/geo_objects/*.json` (0700-Verzeichnis,
  Dateien 0600). Maximal 200 Objekte mit je höchstens 128 Koordinaten.
- Strukturprüfung: WGS84-Breite/-Länge, maximale Ausdehnung, keine
  selbstschneidenden Polygone, Radius 1–5000 Meter bei Kreisen.
  Diese Plausibilitätsprüfung ist **keine** Luftraum-/Geländeprüfung.
- Bilder der lokalen Medienbibliothek können über **GeoPhoto** mit
  Breite/Länge, optionaler Höhe, Heading/Pitch/Roll und ISO-8601-Aufnahmezeit
  mit Zeitzone sowie Notizen versehen werden. Die Originaldatei wird nicht
  geändert; ausschließlich eine private JSON-Metadatendatei erhält die
  korrigierten Angaben. Aufnahmepositionen lassen sich als separate rosa
  Markierungen auf der Karte anzeigen.
- Kameraorientierung, tatsächlicher Aufnahmeort und Sichtkegel sind
  **manuell einzugebende** Metadaten. Keine automatische DJI-EXIF-Auswertung
  und keine physikalisch verifizierte Bildfußabdrucksberechnung. Dafür
  fehlen validierte Kamera-Kalibrierung und Gelände-Schnittpunktrechnung.
- Keinerlei Bilder-/Geo-Datenübertragung an FlightHub oder eine fremde
  OpenFlightHub-Instanz.

### P2 – Parallele Flugstreifen und lokaler Live-Kanal

- Gespeichertes Polygon auswählen, Spurabstand 2–200 m und Richtung
  0–359° einstellen. `POST /api/v1/studio/survey/preview` schneidet
  lokale parallele Strecken an der Polygonbegrenzung und liefert bis zu
  200 einzelne Streifen (höchstens 150 Scan-Linien). Anzeige als
  **gestrichelte Streifen** auf der Karte.
- Noch **keine** zusammenhängende Flugroute: Verbindungen und Kurven,
  Mindestabstände, Hindernisse, Höhenprofil, Missionsgeschwindigkeit,
  Batterieverbrauch, RTH oder DJI-Gerätekompatibilität sind nicht
  berechnet. Es gibt absichtlich keinen WPML-Export dieser Flugstreifen.
  Der existierende, separat gespeicherte Wegpunkt-KMZ-Export bleibt wie er ist.
- `AERONEXUS_STUDIO_EVENTS=1` aktiviert optional
  `wss://<LAN-Pi>:8000/api/v1/studio/events` im
  **bereits explizit eingeschalteten** `AERONEXUS_LAN_NO_TOKEN=1`-Modus.
  **Voraussetzung: direktes vertrauenswürdiges WSS/HTTPS-LAN** und
  passende `Origin`; gegen Fremd-IP, Fremd-Host, Cross-Origin und
  Proxy-Forwarding wird abgelehnt. Standard: aus.
- Im Flottenpanel „Live-Ereignisse verbinden“ wählen. Der WebSocket
  übermittelt nur `ready` und `fleet_changed`; keine Telemetrie,
  Zugangstoken, Befehle oder neuen DJI-Aufrufe. Die Browseransicht
  aktualisiert anschließend die bereits vorhandene lokale Status-API.
  Maximal vier parallele Clients; Prüfung alle 3 Sekunden **nur solange
  ein Browser verbunden ist**.
- Die Quelle bleibt die normale AeroNexus-StatusRuntime. Das Intervall
  des Upstream-FlightHub-Pollers wird **nicht** verändert. Bei
  nicht aktiviertem Token-freiem LAN-Modus wird die WSS-Verbindung
  grundsätzlich verweigert, damit keine Secrets in WebSocket-URLs
  übertragen werden.

### P4 – GeoTIFF-Höhenraster und Gelände-STL

- Maximal **8 MiB GeoTIFF** in die lokale API streamen, nur klassisches,
  einbandiges TIFF mit deklariertem räumlichen Bezug.
  GDAL lädt die Datei temporär im Speicher und erzeugt ein Raster bis
  **48 × 48 Höhenwerte**; die Originaldatei wird nicht gespeichert.
- Nur Projektionen mit bestimmbaren Metereinheiten bzw. geografische
  WGS84-artige Koordinaten als vereinfachte lokale Meterskalierung.
  NoData-Löcher und Raster ohne Georeferenzierung werden abgewiesen.
- Der Canvas zeigt eine **schematische isometrische Drahtgitter-Vorschau**
  mit zur Lesbarkeit normalisierter Höhenüberhöhung. Das ist
  keine exakte 3D-Karte, keine Sichtlinienrechnung.
- `POST /api/v1/studio/terrain/export.stl` liefert ein
  geschlossenes binäres STL (Dreiecke, Rückseite und Randwände)
  mit lokaler Meter-Skalierung und optionaler Sockeldicke.
  Es wird **nicht** in Missionshöhen oder DJI-Kameraaktionen übernommen.
  Höhenraster im JSON-Format können unabhängig von GDAL als STL exportiert werden.
- Die Python-Pakete der Pi-Installation enthalten GDAL nicht automatisch.
  `from osgeo import gdal` muss **in der tatsächlich verwendeten
  AeroNexus-`.venv`** funktionieren; die passende Bindung muss mit der
  installierten libgdal-Version kompatibel sein. Ist GDAL nicht
  verfügbar, liefert der GeoTIFF-Endpunkt `503` statt eine erfundene
  Höhenkarte. Vor Produktivnutzung erst mit einem echten GeoTIFF prüfen.

## API-Schnittstellen (alle außer WSS benötigen vorhandene Viewer-Authentifizierung)

| Methode | Pfad | Wirkung |
|---|---|---|
| GET/POST | `/api/v1/studio/geo-objects` | Lokale Geo-Objekte auflisten/erstellen |
| PUT/DELETE | `/api/v1/studio/geo-objects/{uuid}` | Nur lokale Geo-Objekte ändern/löschen |
| POST | `/api/v1/studio/survey/preview` | Unabhängige Flugstreifen als Vorschau |
| PATCH | `/api/v1/studio/media/{uuid}/geo` | GeoPhoto-Metadaten für ein privates Bild |
| POST | `/api/v1/studio/terrain/geotiff` | Transiente GDAL-Stichprobe |
| POST | `/api/v1/studio/terrain/export.stl` | Validiertes Höhenraster als STL |
| WSS | `/api/v1/studio/events` | Opt-in lokale Änderungsmeldungen |

## Architektur- und Sicherheitsgrenzen

- Aus OpenFlightHub wurden die Ideen für Geo-Objekt-, Medien- und
  Ereignisstrukturen verglichen, aber **kein OpenFlightHub-Client,
  keine OpenFlightHub-Cloud-Verbindung und kein Code mit DJI-Steuerbefehlen**
  eingebunden.
- Der Pi ist keine zusätzliche offene WebSocket-Quelle: bestehende feste
  LAN-Regeln und TLS gelten weiterhin.
- Bestehender DJI-WPML-Export nur für vorher unterstützte Matrice-4T/4E-
  Wegpunktmissionen, **nicht** für neue Survey-/Terrain-/GeoPhoto-Daten.
- Kein Dock, keine Flugmission-Uploads, keine Steuerungsübernahme,
  keine dynamischen Flugparameteränderungen.
- Live-Sichtprüfung in Chrome, Pi-TLS-WSS und GDAL-Höhenbezug sind
  vor einem produktiven Einsatz gesondert zu validieren.
