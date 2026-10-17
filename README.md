# AeroNexusAdvanced

Python/FastAPI integration gateway for DJI enterprise data on Raspberry Pi 5.

## Providers and implementation status

| Provider | Current read-only capabilities |
|---|---|
| FlightHub 2 Public Cloud OpenAPI V2 | Project listing, project fleet (aircraft + remote controllers), thing model state, opt-in polling |
| FlightHub 2 On-Premises OpenAPI V2 | Project listing, project topology (aircraft + remote controllers) with embedded state, opt-in polling |
| DJI Cloud API (AeroNexus EMQX, Pilot 2) | Opt-in read-only MQTT OSD live feed; optional event-driven `/state` updates for already known aircraft and controllers |
| DJI Cloud API 2 (official SDK BFF) | Optional read-only GET of aircraft OSD/HMS snapshots via a separately deployed authenticated x86_64 backend; disabled by default |

The project has a validated local inventory for **aircraft and remote
controllers only** (FlightHub `device_model.class` `drone` and `rc`).
Docks, relays, base stations and payloads are not imported.
Endpoints follow the official OpenAPI V2.0 specifications:
[Phase 10 FlightHub fleet](docs/phase-10-flighthub-fleet.md).

Canonical telemetry includes online status, GPS coordinates, battery,
height, horizontal/vertical speed, flight times and satellite counts.
Provider wire formats are converted to strict validated models. The code
uses allowlisted HTTPS GET operations against the documented endpoints.

**Important:** unit tests use mock DJI responses. A live FlightHub 2 EU
session with a Matrice 4T has also been validated separately; RC Plus 2 did
not appear as a distinct FlightHub device. See
[confirmed project status](docs/PROJECT_STATUS.md) for the precise scope.

The DJI Cloud API live feed (phase 9) subscribes read-only to the OSD
telemetry that DJI Pilot 2 pushes to the AeroNexus MQTT broker; optional
`AERONEXUS_OSD_STATE_ENABLED=1` also reads approved change-driven
`thing/product/+/state` packets. The consumer **does not itself provide**
the Pilot 2 workspace, licence validation or MQTT broker; the legacy
FlightHub EU provider remains independent. DJI Cloud API 1.18 (2026-10-13)
adds mainly O4 Ground Station and Dock functions, not a new Matrice 4T
Pilot 2 API. See [Phase 9 live feed and 1.18 audit](docs/phase-9-cloud-api-live-feed.md).

The telemetry extension covers M3E, M3T, M3M, M3TA and M4E/M4T property
formats, RC Pro/RC Plus 2 link state, camera payloads and independent field
freshness. Existing source timestamps prevent late samples replacing newer
values. [Data contract and limits](docs/cloud-api-118-telemetry.md).

## DJI Cloud API server under AeroNexusAdvanced (Raspberry Pi 5)

The previously installed `~/Projekte/AeroNexus/edge` server can be staged,
with its stopped MySQL, Redis, EMQX and MinIO state, into the **gitignored**
`~/Projekte/AeroNexusAdvanced/cloud-server/` directory. An isolated seven-service
Compose template uses the existing Pi Docker images, excludes mapping/farming/PV,
and does not start or delete anything automatically.

```bash
python3 scripts/migrate_cloud_server.py           # read-only preflight
python3 scripts/migrate_cloud_server.py --stage   # checked cold copy; no start
```

Source data, DJI credentials and the prior stopped containers remain intact.
The copied `edge/.env` is private, distinct from the current FlightHub
`.env` at the repository root. See
[Pi migration guide](docs/local-cloud-server-migration.md); [Pilot 2 branding and safe web-only rebuild](docs/pilot2-web-branding.md); [RC Plus 2 einmalig koppeln und Sitzung automatisch wiederherstellen](docs/pilot2-auto-session.md) for conditions,
Compose validation, rollout and rollback. **No FlightHub 2 On-Premises
installation** is included or implied.

## GeoTIFF-/COG-Ergebnisraster

`/results` ergänzt einen lokalen Ergebniskatalog mit Band-/RGB-Kachelviewer,
NoData-Transparenz, reprojizierten XYZ-Kacheln und Kontrasteinstellungen.
Optionales Extra `[raster]`; [Einrichtung und Grenzen](docs/raster-results.md).

## Development

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,mqtt]'
python -m pip check
python -m pytest -q
```

## Tokenfreier HTTPS-LAN-Betrieb (Phase 14)

In `/status` und `/studio` gibt es **keine Token-Eingabefelder** mehr.
Beide Seiten laden Flottendaten, die FlightHub-Bibliothek und lokale
Studio-Daten automatisch.

Dieser Betrieb ist **ausdrücklich zu aktivieren**: in der privaten `.env`
`AERONEXUS_LAN_NO_TOKEN=1` und `AERONEXUS_LAN_HOST=192.168.178.63`
setzen, danach den bestehenden HTTPS-systemd-Dienst neu starten.
Der Server prüft direkte Client-IP im Heimnetz `192.168.178.0/24`,
HTTPS, Host und Origin; keine Router-Portweiterleitung.

**Warnung:** Alle Geräte im Heimnetz erhalten damit Zugriff auf
Seriennummern, Flugpositionen, Projektbibliothek und können lokale
Missionen/Medien speichern, ändern oder löschen. DJI-Flugbefehle
bleiben gesperrt. Weitere Details:
[Phase 14 – tokenfreier LAN-Modus](docs/phase-14-token-free-lan.md).

## Local read-only status dashboard (phase 8.7)

```bash
cd ~/Projekte/AeroNexusAdvanced
source .venv/bin/activate

# Dedicated dashboard bearer token, NOT your DJI access token.
read -rsp "Dashboard token (32+ characters): " AERONEXUS_STATUS_TOKEN; echo
export AERONEXUS_STATUS_TOKEN

python -m uvicorn aeronexus.app:app --host 127.0.0.1 --port 8000
```

Alternatively keep all settings in a gitignored `.env` (template:
`.env.example`) and start with `--env-file .env`.

Visit `http://127.0.0.1:8000/status` on the Pi or through an SSH tunnel.
The responsive page refreshes its view of **local** in-memory telemetry
automatically. No DJI background polling (opt-in, phase 10) or remote changes are enabled by
default. Initially, a newly started app correctly has zero registered
devices; running the separate `probe_state` command does not populate
the web server's memory.

- `GET /health` — liveness
- `GET /api/v1/status/summary` — anonymous, non-identifying counters
- `GET /api/v1/status/devices` — protected details; token-free for trusted LAN when Phase 14 is enabled
- `GET /status` — auto-updating local web dashboard
- `POST /api/v1/flight/command` — always forbidden (HTTP 403)

The separate status bearer token must have at least 32 characters and
should be protected like a password. Detailed telemetry can include
sensitive coordinates and serial numbers.

By default, telemetry older than 90 seconds is reported **stale**, not
online. Configure with `AERONEXUS_STATUS_STALE_AFTER_SECONDS` and
`AERONEXUS_STATUS_REFRESH_SECONDS` (browser refresh interval). Timestamp
`received_at` means the time the gateway received the sample, not the
DJI device event time.

Full setup: [Phase 8.7 status dashboard](docs/phase-8-7-fleet-status.md).
The mobile-first [Phase 11 device diagnostics](docs/phase-11-dashboard-diagnostics.md)
adds aircraft status cards, battery bars, GPS/RTK/flight-state diagnostics,
received-data age, HMS notifications and a visible last-successful-sync status.
These use the local API, which is protected either by the legacy bearer mode
or the opt-in HTTPS-LAN policy. The full technical table and FlightHub
library remain available; pages auto-load without a browser login.

## Desktop Mission Studio (phase 13)

A dedicated Chrome/desktop workspace is available at
**`https://192.168.178.63:8000/studio`** once the current code is installed
and the existing user service has been restarted. There is **no login form**.
Enable the Phase 14 HTTPS-LAN policy in `.env` before use.

- Desktop-sized interactive OpenStreetMap/Esri map with click/drag waypoints,
  mission metadata, point editing/reordering and optional photo actions.
- Create/save/reopen/edit/delete waypoint drafts locally on the Pi, including
  safe re-import of AeroNexus-generated KMZ waypoint files.
- Download DJI waypoint KMZ (`wpmz/template.kml`, `wpmz/waylines.wpml`)
  for **manual** review/import in DJI Pilot 2; initial aircraft profiles
  Matrice 4T and Matrice 4E, uniform height relative to takeoff.
- Local private media library: upload, search, preview and delete
  JPEG/PNG/WebP/MP4 (25 MiB maximum per file).
- Read-only fleet tab with optional map plotting of valid *fresh* GPS.
- Planned missions and media are stored under
  `~/.local/share/aeronexusadvanced` with private permissions, **outside Git**.
- Leaflet, OSM and Esri map tiles are third-party browser requests; the tile
  providers learn the selected map viewport, but no AeroNexus token is sent.
- **No** DJI mission upload or execution, Dock, flight command, live airspace
  or terrain validation. The WPML exporter implements an intentionally
  constrained waypoint subset and is **not yet acceptance-tested in Pilot 2**;
  check every exported mission before flying.

See [Phase 13 desktop studio and WPML scope](docs/phase-13-desktop-mission-studio.md).

## Operations Center – DJI Cloud API 2 und FlightHub 2 (Phase 15)

Auf dem Chrome-PC öffnet **`https://192.168.178.63:8000/operations`**
die zusätzliche FlightHub-inspirierte Leitstandansicht. Sie verwendet
ausschließlich unsere bestehenden lokal geschützten Lese-APIs und
startet die Karte automatisch über **76694 Forst**.

- Projekt-/Geräteübersicht, Matrice-4T-Cockpit, Akku/OSD/HMS/GPS und
  Flugaufträge nach Status, mit vorhandenen GeoJSON-Flugspuren.
- FlightHub-Bibliothek, lokale Missionsvorschau einschließlich
  **„Route schließen“** und **Flugauftrags-Medienliste**.
  Der Medienendpunkt zeigt nur Dateinamen, Typ, Größe und Zeitpunkte,
  **keine signierten DJI-Download-URLs**.
- Optionaler **DJI Cloud API 2**-Datenkanal mit eindeutiger Quellanzeige,
  rein lesend. Dazu wird **eine bereits laufende, unabhängig
  authentifizierte SDK-BFF-Instanz auf einem privaten x86_64-Server**
  benötigt; ein DJI-Entwicklerkonto oder eine Lizenz allein genügt nicht.
  Diese Anbindung ist standardmäßig **deaktiviert**.
- **Livestream** (Bereich „Kamerabild“): Streams, die DJI Pilot 2 an den
  lokalen MediaMTX sendet, lassen sich direkt ansehen (WebRTC, ca. 1 s
  Verzögerung, Vollbild, Auflösung/fps/Bitrate). Das Gateway leitet nur die
  WebRTC-Anmeldung weiter; das Video kommt per UDP direkt vom Pi. Der Browser
  sieht keine Streampfade oder Seriennummern. In Pilot 2 H.264 wählen.
  Details: [docs/livestream.md](docs/livestream.md).
- Keine Dock-Integration, Flugbefehle, DJI-Missionsausführung oder
  ungeprüfte Cloud-Uploads. Das FlightHub-2-Live-Polling läuft wie bisher.

Weitere Details und Quellenvergleich:
[Phase 15: DJI-Integrationen](docs/phase-15-dji-sources-operations.md).
Als zusätzliche technische Referenz wurde das
[flighthub2-cli-Paket](https://pypi.org/project/flighthub2-cli/)
geprüft. Sein Kommandozeilenprogramm/MCP-Server wird **nicht**
automatisch installiert oder mit DJI-Schreibberechtigungen gestartet.

## DJI-MinIO-Medienkatalog (Phase 21)

DJI-Medien aus dem lokalen MinIO-Bucket `dji-cloud` lassen sich ohne
Kopieren, Löschen oder DJI-Steuerbefehle **schreibgeschützt indizieren**.
Der transaktionale Metadatenkatalog erscheint separat in der
Mission-Studio-Medienbibliothek; JPEG/PNG/WebP sind bis 32 MiB als
Vorschau abrufbar, große DNG/Videoobjekte bleiben als Download verfügbar.

Einlesen auf dem Pi: `python -m aeronexus.minio_media_index` (manuell,
optional mit `--dry-run`). Erfordert einen eigenen MinIO-Lesezugang
und das optionale Paket-Extra `minio`.
Die bisherige Seite `/media` liest denselben Katalog; ihre Metadaten-API
bleibt kompatibel. Der alte Root-basierte Scanpfad ist entfernt. Bestehende
Phase-20-Indizes unter `var/` bleiben unangetastet; für deren Umstieg ist
ein expliziter Scan mit dem neuen Lesezugang erforderlich.
Details: [Phase 21 – DJI-MinIO-Medien](docs/phase-21-dji-minio-media.md).

**Fotokatalog auf `/media`:** Alle DJI-JPEGs sind nach Drohne (M3E, M3T, M4T,
M3M), Kamera und Flug geordnet. Grundlage sind die Bild-Metadaten, nicht der
Dateiname. Die Seite zeigt eine Karte mit Aufnahmepunkten, Footprints und GSD;
unplausible GNSS-Positionen sind markiert.
Details: [docs/photo-catalog.md](docs/photo-catalog.md).

## CSV-Wegpunkte im Mission Studio

Im Missionseditor lassen sich CSV-Dateien mit `latitude`, `longitude` und
optional `take_photo` prüfen und als neue Wegpunktliste übernehmen. Vorschau
mit Karte und Tabelle, Zeilenfehler, explizite Trenn-/Dezimalzeichen und
Rückgängig/Wiederherstellen; Missionswerte bleiben erhalten, Speichern bleibt
ein eigener Schritt. UTF-8, maximal 512 KiB und 500 ausführbare Wegpunkte.
Anleitung und Dateivertrag: [CSV-Import](docs/mission-csv-import.md).

## Thermal (`/thermal`)

Eigener Web-UI-Tab für radiometrische DJI-Wärmebilder (M3T/M4T R-JPEG) aus
dem MinIO-Index. Temperaturen nur über das DJI Thermal SDK (`dji_irp`,
auf dem Pi 5 via Box64): Paletten, Isotherme, Hot-/Coldspot, Punkt- und
Bereichsmessung, Emissionsgrad & Co., PNG/CSV/JSON-Export, Karte mit
Aufnahmepunkten und Footprints, Overlay mit dem Sichtbild sowie PV-Inspektion
(ΔT-Klassen und Messbedingungen, Orientierung an IEC TS 62446-3). Installation:
`deploy/pi/install-thermal-sdk.sh <dji_thermal_sdk_v1.8_*.zip>`.
Details: [docs/thermal.md](docs/thermal.md).

## Automatischer Medien-Sync (Pilot 2 Uploads)

Dienst `aeronexusadvanced-media-sync`: vollständiger Scan beim Start, danach
nach jedem Pilot-2-Upload (Bucket-Abfrage alle 2 min oder MinIO-Ereignisse)
Aktualisierung von Medienindex, Fotokatalog, Thermal-Geo-Index, Multispektral-Katalog,
NDVI-Übersichten und Thermal-Messungen – nur lesend. Status auf `/media`.
Details: [docs/media-auto-sync.md](docs/media-auto-sync.md).

## Multispektral DJI Mavic 3M (`/multispectral`)

Eigener Web-UI-Tab für M3M-Bänder (Grün, Rot, RedEdge, NIR) aus dem
MinIO-Index, über die CaptureUUID zu Aufnahmen gruppiert. Verarbeitung nach
DJIs *Mavic 3M Image Processing Guide* (Schwarzwert, Gain, Belichtung,
Vignettierung, Entzerrung, HMatrix-Ausrichtung, Sonnenlichtsensor); NDVI,
GNDVI, NDRE, LCI, CIR-Falschfarben, Messwerkzeuge und Export; 4-Band-GeoTIFF
für QGIS (NIR, G, R, RE; nach mirrormapper/m3m-image-stacking, plus
Feinausrichtung und Nadir-Georeferenz), auch für lokale Ordner:
`python -m aeronexus.m3m_stack ORDNER -o AUSGABE`. Katalog:
`.venv/bin/python -m aeronexus.multispectral`; Abhängigkeit
`pip install -e '.[multispectral]'`. Details: [docs/multispectral.md](docs/multispectral.md).

## DEM-Hangneigung im 3D-Geländeviewer (Phase 20)

Im Mission Studio lässt sich das importierte, auf maximal 48×48 Stützpunkte
resampelte Höhenmodell alternativ nach **lokaler Hangneigung** einfärben
(0–8°, 8–15°, 15–30°, ab 30°). Zellmittel/Maximum und ein Klick-Neigungswert
ergänzen die bestehenden WGS84-/Höhenprofilfunktionen. Die Berechnung
verwendet die **Originalhöhen ohne visuelle Überhöhung** und die lokalen
metrischen Rasterabstände. **Keine** DJI-Flugfreigabe, Hindernisprüfung
oder Änderung an WPML, STL und den lesenden DJI-Datenquellen.

Grenzen, Prüfungen und manuelle Pi-/Chrome-Abnahme:
[Phase 20 – DEM-Hangneigung](docs/phase-20-terrain-slope.md).

## Running on the Pi (systemd + HTTPS)

`deploy/pi/` contains a local-CA certificate script, a launcher that refuses
plain HTTP on LAN addresses, and a systemd user service. Live LAN usage is
via `https://192.168.178.63:8000/status` with the installed local CA. See
[Running on the Raspberry Pi](docs/deploy-pi.md).

## DJI manual diagnostics

Read-only checks using separate environment variables and valid DJI
OpenAPI permissions are documented in:

- [Phase 8.5 aircraft discovery](docs/phase-8-5-device-discovery.md)
- [Phase 8.6 detailed aircraft state](docs/phase-8-6-aircraft-state.md)
- [Phase 10 fleet probe and polling](docs/phase-10-flighthub-fleet.md):
  `python -m aeronexus.probe_fleet`; project library (waylines, models,
  flight tasks) and flight tracks as GeoJSON via the authenticated API

Never commit DJI tokens, serial numbers or location data. Do not disable TLS
certificate verification.

## Docker

```bash
docker build -t aeronexusadvanced:dev .
docker run --rm -p 127.0.0.1:8000:8000 aeronexusadvanced:dev
```

## Optional Metashape orthomosaic workflow

The Multispectral page can package 3–100 selected M3M captures for an external
Agisoft Metashape Professional worker. The Pi exports read-only copies; it does
not install Metashape or start reconstruction. RGB and independent MS raw-band
mosaics are supported. Raw-band outputs are not calibrated reflectance/NDVI
products and tiled GeoTIFFs are not automatically certified COGs.

See [Metashape integration](docs/metashape-integration.md) for the separately
installed GeoSense processor, license requirements, export limits and worker use.

## Security limitations

- No DJI flight commands or remote configuration writes.
- No DJI Dock integration.
- HTTPS is mandatory for DJI provider origins.
- Protected data requires either a separate strong bearer token (legacy
  backend) or the explicit Phase 14 direct HTTPS-LAN mode. The browser UIs
  have no token form, so LAN mode must be enabled for their automatic data
  loading. No reverse proxy or port-forwarding in passwordless mode.
- In-memory device inventory; no persistence, access-control roles,
  production-grade rate limiting; FlightHub polling is opt-in.
- The Cloud API MQTT feed is subscribe-only (OSD); it never publishes.
- Starlette may emit a non-fatal `httpx2` migration warning in tests.

## References

- https://fh.dji.com/user-manual/en/custom-development/open-api/public-cloud-v2.html
- https://fh.dji.com/user-manual/en/custom-development/open-api/private-cloud-v2.html
- https://github.com/dji-sdk/FlightHub-2-OpenAPI-V2-Demo
- https://github.com/alecad/dji-flighthub2-cli (Apache-2.0; EU gateway,
  error handling and live-validated API behaviour, see NOTICE)
