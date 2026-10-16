# AeroNexusAdvanced

Python/FastAPI integration gateway for DJI enterprise data on Raspberry Pi 5.

## Providers and implementation status

| Provider | Current read-only capabilities |
|---|---|
| FlightHub 2 Public Cloud OpenAPI V2 | Project listing, project fleet (aircraft + remote controllers), thing model state, opt-in polling |
| FlightHub 2 On-Premises OpenAPI V2 | Project listing, project topology (aircraft + remote controllers) with embedded state, opt-in polling |
| DJI Cloud API (AeroNexus EMQX, Pilot 2) | Opt-in read-only MQTT OSD live feed for aircraft and remote controllers |

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
telemetry that DJI Pilot 2 pushes to the AeroNexus MQTT broker:
[Phase 9 live feed](docs/phase-9-cloud-api-live-feed.md).

## Development

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,mqtt]'
python -m pip check
python -m pytest -q
```

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
- `GET /api/v1/status/devices` — authenticated device details and telemetry
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
These use the existing authenticated local API; the detailed legacy table and
FlightHub library remain available. The browser clears protected information
on disconnect, including results from late requests.

## Desktop Mission Studio (phase 13)

A dedicated Chrome/desktop workspace is available at
**`https://192.168.178.63:8000/studio`** once the current code is installed
and the existing user service has been restarted. Use the same independent
AeroNexus status token as for the dashboard (never the DJI organization key).

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

## Security limitations

- No DJI flight commands or remote configuration writes.
- No DJI Dock integration.
- HTTPS is mandatory for DJI provider origins.
- Dashboard details are fail-closed unless a strong, separate status token
  is configured; bind the service to localhost and use SSH tunnel or
  authenticated TLS reverse proxy for remote viewing.
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
