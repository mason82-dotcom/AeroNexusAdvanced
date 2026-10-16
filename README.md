# AeroNexusAdvanced

Python/FastAPI integration gateway for DJI enterprise data on Raspberry Pi 5.

## Providers and implementation status

| Provider | Current read-only capabilities |
|---|---|
| FlightHub 2 Public Cloud OpenAPI V2 | Project listing, aircraft topology, aircraft detailed state |
| FlightHub 2 On-Premises OpenAPI V2 | Project listing, paginated aircraft observations, embedded state |
| DJI Cloud API | Provider placeholder only; no MQTT live adapter |

The project has a validated local inventory for **aircraft and remote
controllers only**. The currently verified FlightHub OpenAPI device-list
endpoints discover *aircraft*; they do not establish a standalone
remote-controller mapping. Other infrastructure devices are not imported.

Canonical telemetry includes online status, GPS coordinates, battery,
height, horizontal/vertical speed, flight times and satellite counts.
Provider wire formats are converted to strict validated models. The code
uses allowlisted HTTPS GET operations against the documented endpoints.

**Important:** unit tests use mock DJI responses. A real FlightHub session
has not yet been verified in this project.

## Development

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
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

Visit `http://127.0.0.1:8000/status` on the Pi or through an SSH tunnel.
The responsive page refreshes its view of **local** in-memory telemetry
automatically. No DJI background polling or remote changes are enabled by
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

## DJI manual diagnostics

Read-only checks using separate environment variables and valid DJI
OpenAPI permissions are documented in:

- [Phase 8.5 aircraft discovery](docs/phase-8-5-device-discovery.md)
- [Phase 8.6 detailed aircraft state](docs/phase-8-6-aircraft-state.md)

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
  production-grade rate limiting, or automatic DJI polling yet.
- Starlette may emit a non-fatal `httpx2` migration warning in tests.

## References

- https://fh.dji.com/user-manual/en/custom-development/open-api/public-cloud-v2.html
- https://fh.dji.com/user-manual/en/custom-development/open-api/private-cloud-v2.html
- https://github.com/dji-sdk/FlightHub-2-OpenAPI-V2-Demo
