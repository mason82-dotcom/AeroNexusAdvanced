# Phase 8.5 — FlightHub V2 aircraft discovery (read-only)

## Verified source

DJI's official [FlightHub 2 OpenAPI V2 demo](https://github.com/dji-sdk/FlightHub-2-OpenAPI-V2-Demo) is used as the field and route reference.

| Provider | Read-only GET | Response |
|---|---|---|
| Public Cloud V2 | `/openapi/v2.0/project/device` | `data.list: [{ gateway, drone }]` |
| On-Premises V2 | `/openapi/v2.0/manage/api/v1/organizations/{orgId}/manage-devices` | `data.list: [{ device_sn, device_model, device_state, ... }]` |

The On-Premises call requests `device_model_class=drone`, `page` and `page_size`. Public Cloud uses `X-Project-Uuid` and `X-User-Token`; the On-Premises list uses `X-User-Token`.

The code keeps **only aircraft** from these endpoints. It neither imports gateways, relay/base stations or other infrastructure, nor uses flight control endpoints. Remote controllers require their own verified class or route mapping and are not discovered by the above drone-only queries.

## Local, manual, read-only probe

Credentials must never be committed or pasted into chats or public issue trackers. The probe only displays counts, not tokens, raw HTTP bodies, or serial numbers.

Activate the existing Python virtual environment:

```bash
cd ~/Projekte/AeroNexusAdvanced
source .venv/bin/activate
```

For Public Cloud:

```bash
export AERONEXUS_DJI_BASE_URL="https://api-openapi.dji.com"
export AERONEXUS_DJI_PROJECT_UUID="<project UUID>"
read -rsp "DJI OpenAPI token: " AERONEXUS_DJI_TOKEN; echo
export AERONEXUS_DJI_TOKEN
python -m aeronexus.probe_devices --provider public
unset AERONEXUS_DJI_TOKEN
```

For On-Premises, use your actual *HTTPS* endpoint, and replace the project environment variable with an organization UUID:

```bash
export AERONEXUS_DJI_BASE_URL="https://your-onprem-host"
export AERONEXUS_DJI_ORGANIZATION_UUID="<organization UUID>"
read -rsp "DJI OpenAPI token: " AERONEXUS_DJI_TOKEN; echo
export AERONEXUS_DJI_TOKEN
python -m aeronexus.probe_devices --provider onprem --page 1 --page-size 20
unset AERONEXUS_DJI_TOKEN
```

**Safety:** TLS validation is always on, redirects and environment HTTP proxies are disabled. Self-signed On-Premises certificates must be trusted through normal OS/CA configuration rather than bypassing TLS verification. If the command fails, no credentials or response body are printed. Credentials are kept in the running process environment, which should be considered sensitive.

## Project association

Public Cloud: `sync_public_aircraft` requires an explicitly registered project UUID and atomically updates the in-memory inventory. It does not write to DJI.

On-Premises: the demo exposes `device_active_project_name` rather than a canonical project UUID. Accordingly, the read-only observation API **does not auto-import On-Premises results into a specific project**. Before enabling that step we must verify an authoritative UUID mapping.

## Known limitations

- No real DJI credentials or live endpoint have been tested by the development environment.
- The list endpoints expose only aircraft in this implementation; remote controllers are not yet included.
- Public Cloud richer telemetry can require a separate `GET /openapi/v2.0/device/{sn}/state` call, not implemented here.
- The On-Premises list is paginated; callers must request subsequent pages.
- No WebSocket, MQTT, RTK configuration, flight commands, or DJI-side mutations.
