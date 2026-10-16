# Phase 15 – DJI FlightHub UI, Cloud API 2 and flighthub2-cli references

This phase integrates **patterns**, not vendor backends, on the Raspberry
Pi 5 (ARM64) running AeroNexusAdvanced (FastAPI/Python 3.13).

## Sources inspected

| Source | Actual implementation | Reused safely |
|---|---|---|
| [DJI FlightHub 2 Frontend Standalone Component](https://github.com/dji-sdk/FlightHub-2-Frontend-Standalone-Component) | Example HTML loads DJI's external `paas.js`; needs a running FlightHub 2 backend, project credentials and its notification WebSocket. It is not a standalone offline Leaflet/WPML engine. | Operations Center concept: project map, cockpit, route library and flight track timeline. **Not** embedding `paas.js` or tokens in the browser. |
| [DJI FlightHub 2 OpenAPI V2 Demo](https://github.com/dji-sdk/FlightHub-2-OpenAPI-V2-Demo) | Public and on-premises endpoints have different path/response contracts. The Public device list may require `device_model_class=drone`. | Existing strict V2 read-only transport and normalization; Public EU endpoint already verified on M4T. |
| [DJI Cloud API 2](https://github.com/dji-sdk/Cloud-API-2) | New PaaS with Java SDK **3.3.7**, SDK skeleton with `GET /api/v1/devices`, OSD/HMS cache, auth, Docker/MQTT infrastructure. Full server recommended 8 cores/64 GiB, and native SDK documentation specifies **amd64/x86_64**, not Raspberry Pi 5 ARM64. The skeleton device model includes DOCK, which must be filtered. | Optional, authenticated backend-to-backend, GET-only source for DRONE rows and normalized OSD/HMS. **No native DJI SDK or PaaS deployed to Pi.** |
| [flighthub2-cli (PyPI)](https://pypi.org/project/flighthub2-cli/) and [source](https://github.com/alecad/dji-flighthub2-cli) | Unofficial Apache-2.0 Python CLI/SDK, EU/US FlightHub 2 base URLs, typed read operations for projects, devices, waylines, models, tasks, task media and GeoJSON tracks; also contains live flight commands and MCP write tools. | Existing error classification/retry behaviour, GeoJSON track and catalog. **New: sanitized task media metadata endpoint and list in Operations Center.** No installation of command-capable CLI or MCP service. |

See [original upstream NOTICE](../NOTICE) for attribution where relevant.

## Operations Center (Chrome)

Open **`https://192.168.178.63:8000/operations`** after pulling and restarting
the existing AeroNexus service. It uses the same token-free, HTTPS-only LAN
guard as `/status` and `/studio` when Phase 14 mode is explicitly enabled.

- Overview of locally cached FlightHub projects and online aircraft.
- Leaflet satellite/OSM project map; always initially centred over
  **76694 Forst (Baden)**. Only known **fresh online aircraft with
  plausible non-zero GPS coordinates** get a live position marker.
- Selected-aircraft cockpit: battery, altitude, speed, satellites, RTK,
  received age, OSD and HMS; stale readings are explicitly marked.
- **Cockpit-Ergonomie nach Matrice-4T-Liveprüfung (Phase 16):** Geräteverbindung
  (online/offline/zuletzt online/unbekannt) und Alter der übermittelten Daten
  werden **unabhängig** angezeigt. Eine aktuelle Offline-Meldung ist kein
  vermeintlicher Telemetriefehler. Oben dauerhaft sichtbare kompakte Werte
  für Batterie, Flugmodus, Start-relative Höhe, horizontale Geschwindigkeit
  und den verständlichen RTK-Status; weiteres OSD, Spannung, Temperatur,
  GPS/RTK-Satellitenzahlen und Statistik in aufklappbaren technischen Details.
- Die vom Matrice-4T-Status übermittelten Enum-Werte
  `is_fixed:not_started`, `is_fixed:fixing`,
  `is_fixed:fixing_successful`, `is_fixed:fixing_failed` werden nur
  nach der im Projekt bereits bestätigten Zuordnung dargestellt.
  Unbekannte Werte bleiben im Rohdatenbereich erhalten. Ein Wert von
  null GPS-/RTK-Satelliten ist ein **vom Anbieter gemeldeter Wert**, keine
  gesicherte Aussage zum tatsächlichen Empfängerzustand.
- **Cockpit-Scroll-Korrektur nach Chrome-Praxistest:** Die teilweise
  außerhalb der Technikdarstellung sichtbaren Buchstaben des RTK-Rohwerts
  werden über eine vollbreite Technik-Kachel mit Monospace-Umbruch
  vermieden; der scrollbare Detailbereich erhält CSS-Paint-Containment
  und eine eigene Zeichenebene. Bei unverändertem Gerätedatensatz wird
  nur das Empfangsalter aktualisiert, nicht alle 15 Sekunden das
  gesamte HTML neu erzeugt. Ein DOM-Regressionstest prüft, dass
  Offen-/Geschlossen-Zustand, Scrollposition und DOM-Referenz über
  unveränderte Telemetrieabfragen hinweg erhalten bleiben; neue
  Telemetrie löst weiterhin ein Update aus.
- **Flugzeit gesamt und Flugstarts gesamt sind als API-Werte markiert.**
  Der bei eingeschalteter Matrice 4T beobachtete Wert 0 bedeutet nicht
  zwingend eine unbenutzte Drohne. Unbekannte HMS-Codes wie
  `0x16070042` erhalten keine erfundene DJI-Diagnose. Der aufgeklappte
  Detailbereich und seine Scrollposition bleiben bei den 15-Sekunden-
  Aktualisierungen erhalten.
- FlightHub task inbox: **active / completed / all**, latest known task
  status and waypoint progress, flight track as read-only GeoJSON.
- Local AeroNexus Mission Studio drafts can be previewed on the map,
  including a closed route's return segment, without uploading to DJI.
- Read-only FlightHub wayline/model list. FlightHub task media metadata is
  available on demand via `GET /api/v1/flighthub/projects/{project_id}/tasks/{task_uuid}/media`,
  **only when the project and UUID are already present in the cached task list**.
  Original/previews URLs, object-storage keys, tokens and DJI secrets are
  **intentionally removed**.
- A separate Cloud API 2 source status: disabled, connected or unavailable.
  Its aircraft appear only when no matching FlightHub aircraft is already
  present. The Cloud API 2 backend is NOT requested by the Chrome browser.

**Not present:** DJI Dock, BFF control endpoints, creating DJI flight
tasks, live streams, control authority, remote takeoff, mission execution,
open-model reconstruction or unattended uploads.

## Optional Cloud API 2 SDK BFF integration

The new server-side `CloudApi2Bridge` stays **disabled by default**.
It is a client of an *already running* official SDK skeleton
(`devkit/skeleton/feature/feature-device/DeviceRestController.java`) or
an equivalent independently managed BFF implementing exactly this
read-only response. It is not a substitute for installing the full Cloud
API 2 platform and does not make your existing DJI developer account or
FlightHub 2 organization key compatible with a BFF.

When you have **confirmed the server and backend token exist**, configure
only the private, gitignored Pi `.env` (chmod 600):

```dotenv
AERONEXUS_CLOUDAPI2_ENABLED=1
AERONEXUS_CLOUDAPI2_BFF_URL=https://<private-lan-x86_64-server>:8443
AERONEXUS_CLOUDAPI2_BFF_TOKEN=<backend-user-JWT>
AERONEXUS_CLOUDAPI2_STALE_SECONDS=45
```

The placeholders are documentation only; do not paste them unchanged into
`.env`. The connector enforces HTTPS for LAN servers, normal TLS
verification, a private destination address or `.lan/.local` name, a
short timeout, no redirects, no environment proxies, a maximum response
size and one request at most per 15 seconds.

Only an **outbound GET `/api/v1/devices`** is made. Nested, flat or
duplicate **DRONE** records are normalized; DOCK entries and non-aircraft
classes are not exposed. Responses include source, last OSD age, verified
GPS fix, limited battery/height/speed/mode fields and bounded HMS codes.
In particular, it does not attempt to manufacture a separate RC Plus 2
entry if the SDK has not actually reported one.

Unusable or down upstream source => `unavailable`, not fake
`online`. An enabled account alone is **not** a proven running BFF,
broker or compatible M4T Pilot 2 linkage. The full Cloud API 2 deployment
may be oriented around docks; actual Pilot 2 integration must be confirmed
with an eligible independent BFF and hardware before enabling this bridge.

The previous read-only DJI Cloud API MQTT feed remains independent and
disabled pending an actual broker. Do not reuse its MQTT credentials as
the BFF HTTP/JWT token.

## Checkpoints

```bash
cd ~/Projekte/AeroNexusAdvanced
git pull --ff-only
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
systemctl --user restart aeronexusadvanced
systemctl --user is-active aeronexusadvanced
```

Then open `/operations` on a trusted Chrome PC. No FlightHub tasks have
yet been seen in the user's real organization, so task media and track
functions remain **mock-tested only**. The WPML KMZ exports are still
**not acceptance-tested with DJI Pilot 2**. Never test flight commands
or mission execution without a separately reviewed workflow.

## Read-only API boundaries

- `/api/v1/status/devices`: normalised FlightHub/MQTT inventory.
- `/api/v1/flighthub/catalog`: cached project waylines/models/tasks.
- `/api/v1/flighthub/projects/{project_id}/tasks/{task_uuid}/track`:
  known task only, GeoJSON flown trajectory.
- `/api/v1/flighthub/projects/{project_id}/tasks/{task_uuid}/media`:
  known task only, sanitized filenames and metadata.
- `/api/v1/cloudapi2/devices`: optional separate SDK BFF, no DJI
  credentials exposed and no serials if disabled.

No arbitrary `fh2 call` forwarding, no `POST` to DJI, no path-selection
from client input, no Dock data. The 403 flight-command endpoint remains.
