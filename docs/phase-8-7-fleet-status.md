# Phase 8.7 — Fleet status API, freshness and local dashboard

## What is implemented

- In-memory aircraft/controller inventory and telemetry; each successful local
  `Inventory.update_telemetry()` records a **UTC receipt time** in AeroNexus.
- Status categories: `fresh`, `stale`, `missing`, `unknown_age`,
  `clock_skew`. Stale snapshots **do not claim that a device is currently
  online**; `reported_online` retains the original flag, explicitly historical.
- Atomic staging in `ingest_project_batch` includes arrival timestamps.
- An aggregated status endpoint and a separately authenticated, paginated
  device-detail endpoint.
- Responsive read-only web page with configurable **browser-side** refresh.
- An opt-in Python `ReadOnlyStatusPoller` for asynchronous refresh callbacks;
  overlapping refreshes are rejected and callback errors do not leak credentials.

**Critical distinction:** the web page polls the *local API*, not DJI. By default
there is no DJI background polling task, no service setup and no persisted
telemetry. To display real values continuously, an explicitly configured
read-only DJI refresh callback and live credentials are required. This phase
does not enable any such callback by default.

## Start on Raspberry Pi 5

```bash
cd ~/Projekte/AeroNexusAdvanced
git pull --ff-only
source .venv/bin/activate
python -m pip check
python -m pytest -q
```

Choose a strong **separate** 32+ character status access token; do **not** use
your DJI OpenAPI token as the dashboard token.

```bash
read -rsp "AeroNexus dashboard access token (32+ characters): " AERONEXUS_STATUS_TOKEN; echo
export AERONEXUS_STATUS_TOKEN
python -m uvicorn aeronexus.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/status` **on the Pi itself**. For remote
access, use an SSH tunnel or an authenticated HTTPS reverse proxy. A
local-only SSH tunnel, executed from your computer:

```bash
ssh -L 8000:127.0.0.1:8000 mason@<pi-lan-ip>
```

Then open `http://127.0.0.1:8000/status` on that computer.

**Note:** when no provider data have been imported into the running process,
the dashboard legitimately displays 0 registered devices. The in-memory
inventory is not a persistent database. A one-shot `probe_state` run in a
separate Python process does **not** fill the API's inventory.

The dashboard API requires its own `AERONEXUS_STATUS_TOKEN`. Keep the token
out of shell history (the interactive `read` above helps), source control,
screenshots and logs. Do not expose the service directly to the public
internet or use unencrypted HTTP over the LAN.

## HTTP API

- `GET /health` — service liveness only
- `GET /api/v1/status/summary` — anonymous **aggregate counts only**, no
  serial numbers, project names, GPS locations or credentials
- `GET /api/v1/status/devices` — **Bearer token required**; optional
  `provider` and `project_id` filters; `limit=1..200`, `offset>=0`
- `GET /status` — locally rendered HTML status page; authentication to load
  detailed telemetry is performed in the browser's API request
- `POST /api/v1/flight/command` — **always 403**

If the dashboard token is unconfigured or shorter than 32 characters,
`/api/v1/status/devices` fails closed with HTTP 503. Missing/incorrect
authorization returns HTTP 401. Device details include serial numbers, project
IDs, and possibly GPS positions: treat them as sensitive.

The browser holds the dashboard access token only in memory and does not put
it into a URL or persistent local storage. The HTTP responses are marked
`Cache-Control: no-store`.

## Configuration

All intervals are in seconds.

| Environment variable | Default | Allowed | Meaning |
|---|---:|---:|---|
| `AERONEXUS_STATUS_STALE_AFTER_SECONDS` | 90 | 5–86400 | Age threshold; stale if **strictly greater** |
| `AERONEXUS_STATUS_REFRESH_SECONDS` | 30 | 5–3600 | Browser polling interval |
| `AERONEXUS_STATUS_TOKEN` | unset | 32+ characters | Dashboard-detail bearer credential |

The first two settings are evaluated when the FastAPI app is imported.
Incorrect settings cause startup validation to fail instead of silently
falling back.

`received_at` is the time AeroNexus received a validated sample, **not the
time the drone produced the information**. DJI source timestamps, message age
and reliable stale telemetry metrics will require further verification.

## Optional read-only asynchronous scheduler

The `ReadOnlyStatusPoller` is an opt-in building block. It never creates
network connections by itself:

```python
import asyncio
from aeronexus.status_polling import ReadOnlyStatusPoller
from aeronexus.status_runtime import StatusRuntime

runtime = StatusRuntime()

async def read_only_refresh():
    # Insert an explicitly configured, authenticated read-only DJI sync.
    # Do not send DJI commands or return credentials in exception messages.
    pass

stop = asyncio.Event()
poller = ReadOnlyStatusPoller(runtime, read_only_refresh)

# In your application's managed async lifecycle:
# task = asyncio.create_task(poller.run(stop))
# ...
# stop.set()
# await task
```

The scheduler stores only sanitized state (`running`, `idle`, `error`,
`stopped`) and UTC attempt/success times. It does not schedule itself
automatically or change any DJI configuration.

## Security and limits

- Aircraft and remote controllers only. No DJI-Dock integration.
- No write access to DJI endpoints or flight commands.
- No MQTT/Cloud API websocket/webhook ingestion in this phase.
- The status view only reflects data already present in the same process.
- No persisted history, authentication users/roles, rate limiting or
  production HTTPS termination. Keep the process bound to localhost.
- Because the receive timestamp is local, the client must not interpret a
  recently fetched cached DJI state as proof that the aircraft produced new
  telemetry at the same instant.
