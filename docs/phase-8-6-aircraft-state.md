# Phase 8.6 — Detailed aircraft telemetry (FlightHub 2 V2, read-only)

## Source and scope

DJI's [official FlightHub 2 OpenAPI V2 demo](https://github.com/dji-sdk/FlightHub-2-OpenAPI-V2-Demo) documents two different read-only sources:

- **Public Cloud V2:** `GET /openapi/v2.0/device/{sn}/state` (the body can contain `data.device_state`).
- **On-Premises V2:** `GET /openapi/v2.0/manage/api/v1/organizations/{organization_uuid}/manage-devices` with `device_model_class=drone`, `page`, and `page_size`. Each result can include its own `device_state`.

References: `PublicCloud/DeviceList/main.ts`, `PublicCloud/DeviceList/README.en.md` and `Privatization/DeviceList/main.ts` in the DJI demo.

The decoder only accepts aircraft and explicitly rejects attempts to fetch arbitrary URL paths through the serial-number argument. It **does not import** dock, gateway, relay or base-station devices. Remote controllers remain part of the internal device model, but a controller-specific OpenAPI endpoint has not been verified.

## Supported status fields

| Local snapshot field | DJI source | Notes |
|---|---|---|
| `online` | `device_online_status` | bool, 0/1, or supported status string |
| `latitude`, `longitude` | `device_state.latitude/longitude` | Must be supplied together; validated ranges |
| `battery_percent` | `drone_battery_maintenance_info.batteries[0].capacity_percent`, `drone_charge_state.capacity_percent`, `battery.capacity_percent` | Priority follows DJI demo |
| `height_m` | `height` | Meters |
| `horizontal_speed_mps`, `vertical_speed_mps` | `horizontal_speed`, `vertical_speed` | m/s; vertical may be negative |
| `total_flight_time_s` | `total_flight_time` | Seconds |
| `total_flight_sorties` | `total_flight_sorties` | Count |
| `rtk_satellites`, `gps_satellites` | `position_state.rtk_number/gps_number` | Counts, **not** fix indicators |
| `rtk_state` | `position_state.is_fixed` | Preserved as `is_fixed:<raw value>`; no inferred RTK FIX |
| `battery_voltage_mv`, `battery_temperature_c` | `battery.voltage/temperature` or first battery | mV and Celsius |

Only known, validated fields are persisted in the canonical `DeviceSnapshot`. Missing fields remain `None`. Numeric values are not silently coerced from strings; unknown status encodings are rejected.

## Local test (no live DJI access)

```bash
cd ~/Projekte/AeroNexusAdvanced
git pull --ff-only
source .venv/bin/activate
python -m pip check
python -m pytest -v
```

## Optional live Public Cloud status check

Before testing, obtain a token with the appropriate FlightHub 2 permissions. **Do not share tokens, serial numbers, or location data in chat or commit them to Git.** The following input commands avoid storing these values in your shell command history.

```bash
cd ~/Projekte/AeroNexusAdvanced
source .venv/bin/activate
export AERONEXUS_DJI_BASE_URL="https://api-openapi.dji.com"
read -rp "Project UUID: " AERONEXUS_DJI_PROJECT_UUID
read -rp "Aircraft serial number: " AERONEXUS_DJI_DEVICE_SN
read -rsp "DJI access token: " AERONEXUS_DJI_TOKEN; echo
export AERONEXUS_DJI_PROJECT_UUID AERONEXUS_DJI_DEVICE_SN AERONEXUS_DJI_TOKEN
python -m aeronexus.probe_state
unset AERONEXUS_DJI_TOKEN AERONEXUS_DJI_DEVICE_SN AERONEXUS_DJI_PROJECT_UUID
```

The command prints only normalized flight metrics and whether coordinates exist. **Actual GPS coordinates, aircraft serial number and credentials are deliberately not printed.** It makes exactly one intended read-only GET request.

## Programmatic usage

- `read_public_aircraft_state(config, project_uuid, device_id)` retrieves a detailed snapshot without modifying the local inventory or DJI.
- `sync_public_aircraft_state(inventory, config, project_uuid, device_id)` updates **only a previously registered aircraft** in the local in-memory inventory. If the detail response omits `online`, the previously observed online value is retained.
- `read_onprem_aircraft_states(config, organization_uuid, page=1, page_size=20)` retrieves one organization's page of drone-class snapshots, but **does not assign a project**, since the official example does not establish a verified project UUID per entry.

All remote calls use HTTPS certificate verification, allowlisted GET paths and project-scoped authorization where required. Failed validations do not modify the inventory.

## Current limitations

- The new status decoders are tested using fixtures; they have **not yet been validated against your DJI account**.
- The read-only On-Premises list supports pages, not a full automatic pagination cycle.
- Location freshness, flight-state event timestamps, RTK fix semantics and advanced metrics require additional field-level verification in live responses before dashboard display.
- No connection to DJI Cloud API MQTT has been implemented in this phase.
- No DJI flight commands or remote configuration writes.
