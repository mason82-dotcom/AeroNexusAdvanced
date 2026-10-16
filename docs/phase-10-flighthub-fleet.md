# Phase 10: FlightHub 2 fleet (aircraft + remote controllers), read-only

Reference: the official FlightHub 2 OpenAPI V2.0 documentation
([Public Cloud](https://fh.dji.com/user-manual/en/custom-development/open-api/public-cloud-v2.html),
[On-Premises](https://fh.dji.com/user-manual/en/custom-development/open-api/private-cloud-v2.html))
and the linked Apifox specifications (OpenAPI 3 YAML per endpoint).

## Authentication

- `X-User-Token` (On-Premises: `x-user-token`) is the **organization key**:
  FlightHub 2 -> My Organization -> Organization Settings -> Cloud Interconnect
  (Public) / OpenAPI (On-Premises) -> Organization Key. It is a JWT; refreshing
  it in FlightHub invalidates the old key immediately.
- `X-Project-Uuid` is `data.list[].uuid` of the project list.
- The short organization code shown in FlightHub (`organization_id` in
  `GET /openapi/v2.0/organizations`, an invite code) is not a credential.
  Set it as `AERONEXUS_DJI_ORGANIZATION_ID` to have the poller/probe verify
  once that the key belongs to that organization.
- Public Cloud gateways (`AERONEXUS_DJI_REGION`, default `eu`):
  `eu` `https://es-flight-api-eu.djigate.com`, `us`
  `https://es-flight-api-us.djigate.com`, `cn`
  `https://es-flight-api-cn.djigate.com`. DJI's pages only name cn/us; the
  EU gateway was verified live by
  [dji-flighthub2-cli](https://github.com/alecad/dji-flighthub2-cli). A key
  only works on the gateway of its region (the other answers 401).
  On-Premises: your own deployment domain (`AERONEXUS_DJI_BASE_URL`).
- `AERONEXUS_DJI_API_VERSION` (Public only): `v2.0` (default, current DJI
  reference) or `v0.1` (previous reference, same paths, live-validated on the
  EU gateway by dji-flighthub2-cli). Try `v0.1` if the probe reports 404.

## Endpoints used (all GET)

| Provider | Endpoint | Used for |
|---|---|---|
| Public | `/openapi/v2.0/project` | projects |
| Public | `/openapi/v2.0/project/device` | `{gateway, drone}` rows: RC + aircraft, call sign, model, online |
| Public | `/openapi/v2.0/device/{device_sn}/state` | thing model snapshot (only for online devices) |
| Public | `/openapi/v2.0/device/hms?device_sn_list=...` | live HMS health alerts (best effort) |
| On-Prem | `/openapi/v2.0/manage/api/v1/organizations/{uuid}/projects` | projects |
| On-Prem | `/openapi/v2.0/manage/api/v1/projects/{proj_uuid}/topologies` | `host` (aircraft) + `parents` (RC) incl. `device_state` |

Only `device_model.class` `drone` and `rc` are imported. Docks (`airport`),
relays, base stations and payloads are skipped. RC Plus 2 is model key
`2-174-0` (thing model `DeviceState_rc701`), Matrice 4T `0-99-1`
(`DeviceState_wa345`).

## Live behaviour (EU gateway, 2026-10-16, Matrice 4T + RC Plus 2 via Pilot 2)

- `project/device` and `device` return `{"list": null}` **unless**
  `device_model_class` is passed; `drone` and `airport` work, `rc` /
  `remote_controller` / `dock` are rejected with business code `210070`.
  AeroNexusAdvanced therefore always sends `device_model_class=drone`.
- The RC-connected aircraft is reported in the **`gateway`** slot with
  `device_model.class` `drone`, and `drone` is `null`. The RC Plus 2 itself
  is not listed, so FlightHub currently provides aircraft only.
- `device/{sn}/state` returns the `DeviceState_wa345` thing model as
  documented, with string enums (`mode_code: "standby"`, `is_fixed:
  "not_started"`). Without GPS fix latitude/longitude are `0`.
- `height` is the absolute altitude (about 66 m on the ground) and
  `elevation` the height above take-off (0 on the ground), like the Cloud
  API and unlike the wording of the FlightHub thing model reference.

## Mapping notes

- Empty collections arrive as `{"list": null}`, not `[]` (found live by
  dji-flighthub2-cli); this is treated as an empty list. A missing `data`
  or `list` is still rejected.
- HMS: only live alerts (status 1), at most 20 per device, sorted
  warning > reminder > notification. An HMS failure keeps the telemetry and
  clears the alerts; the summary reports `health_warnings` (device count).
  On-Premises HMS is organization-scoped and not wired yet.
- Errors: 401/403/404/429/5xx and non-zero business codes map to typed
  errors; business code 200401 (HTTP 200, missing or invalid key, observed on
  the eu/us gateways 2026-10-16) is treated as an authentication error. Typed
  errors with the X-Request-Id (for DJI support); bodies are never shown.
  GETs on 408/425/429/5xx are retried twice with backoff (Retry-After up to
  30 s).
- FlightHub thing models report enums as strings (`mode_code:
  "manual_flight"`, `is_fixed: "fixing_successful"`). `mode_code` is
  converted to the DJI integer code (same order as the Cloud API); an
  unknown future value becomes "unknown" instead of dropping the sample.
  `is_fixed` stays a raw, labelled value (`is_fixed:fixing_successful`).
- Position 0/0 means "no position" and is stored as no location.
- On-Premises `is_device_pending_offline` (5 minute grace period) counts
  as offline.
- `height` / `elevation` are passed through under their DJI names
  (`height_m` absolute, `elevation_m` above take-off, see live behaviour).
- A changed call sign in FlightHub renames the local device; a changed
  device type aborts the import. Every import is atomic.
- At most 10 projects and 50 devices per project are processed.

## Usage

```bash
# .env (see .env.example)
AERONEXUS_DJI_PROVIDER=public
AERONEXUS_DJI_REGION=eu
AERONEXUS_DJI_TOKEN=<organization key>
# optional: AERONEXUS_DJI_PROJECT_UUIDS=<uuid>[,<uuid>]

set -a; source .env; set +a
python -m aeronexus.probe_fleet          # counts only, no IDs/positions

AERONEXUS_FH_POLL_ENABLED=1              # in .env: dashboard polling
python -m uvicorn aeronexus.app:app --host 127.0.0.1 --port 8000 --env-file .env
```

The dashboard summary then reports `polling: idle|running|error` and the
time of the last successful refresh. Poll interval:
`AERONEXUS_FH_POLL_SECONDS` (10..3600, default 30). Polling errors never
expose exception text. Keep `AERONEXUS_STATUS_STALE_AFTER_SECONDS` at least
twice the poll interval (e.g. poll 15 s, stale 45 s), otherwise devices turn
"stale" between two polls. One cycle costs 2 + 2 x devices GETs per project
(projects, list, state per online device, HMS).

## Test with RC Plus 2 + Matrice 4T

1. Bind RC Plus 2 and Matrice 4T to a FlightHub 2 project (Pilot 2 ->
   Cloud Services -> FlightHub 2, log in, join the project).
2. Copy the organization key into `.env`, run `python -m aeronexus.probe_fleet`:
   expected `Aircraft: 1`, `Remote controllers: 1`.
3. Enable polling and open `/status`: the RC row shows battery, the M4T row
   battery, satellites, flight mode, height and speed, plus HMS alerts.

## Project library (waylines, models, flight tasks)

Public Cloud only, refreshed separately every `AERONEXUS_FH_CATALOG_SECONDS`
(default 600, `0` = off; one cycle = system status + 3 GETs per project):

| Endpoint | Shown |
|---|---|
| `GET /system_status` | `flighthub.system_status` in the summary |
| `GET /wayline` | name, template type, aircraft model, lenses, update time, size |
| `GET /model` | name, 2D/3D, shown on map, update time, size |
| `GET /flight-task/list` (last 30 days) | name, type, status, start, waypoint progress |
| `GET /flight-task/{uuid}/track` | GeoJSON LineString `[lon, lat, height]`, on demand |

- Authenticated API: `GET /api/v1/flighthub/catalog` and
  `GET /api/v1/flighthub/projects/{project_id}/tasks/{task_uuid}/track`
  (`application/geo+json`, cached 5 min). Tracks are fetched only for tasks
  listed in the local library, so the endpoint cannot probe arbitrary IDs.
- Wayline download URLs (signed links), dock/aircraft serials and operator
  accounts are not stored or forwarded. Each list is best effort: one failing
  list is shown as "not readable" without hiding the others.
- The anonymous summary only carries counts (`flighthub.waylines`, `models`,
  `tasks`).
- Live 2026-10-16: 5 waylines and 5 3D models read; flight task list empty
  (RC flights with Pilot 2 are not FlightHub flight tasks; tasks come from
  docks or tasks created in FlightHub). `flight-alerts` (200400) and
  `live-shares` (231011) answered business errors and are not used.
- Feature set and GeoJSON shape follow dji-flighthub2-cli (`fh2 wayline list`,
  `fh2 model list`, `fh2 task list`, `fh2 task track --geojson`).

## Not adopted from dji-flighthub2-cli

Flight commands, control acquisition, task creation and status changes,
live stream start, stream converters, uploads (wayline, open modeling),
annotations, member management and reconstruction are write, cost or
flight-control operations; wayline downloads hand out signed URLs.
AeroNexusAdvanced stays read-only.
