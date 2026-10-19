# DJI Matrice 4E / 4T – Pilot-to-Cloud MQTT property audit

**Reference (DJI, Matrice 4 Series):**
https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/mqtt/m4-series/properties.html#device-property-list

**Date:** 2026-10-19. **Base:** isolated integration branch for draft PRs #83 and #84 (combined in #85).
**Safety scope:** passive receiver only. No MQTT publish, no property/set, no flight command, no changes to the deployed Raspberry Pi.

## Method and limitations

The linked official Matrice 4 Series property list is the normative source.
A fresh search confirms that the page exists (dated 2026-01-27) and includes
`current_rth_mode` and `rth_mode`, but its dynamic content was **not available
as a complete machine-readable table** during this audit. The coverage below
is a **field-specific source/code review**, not a claim of an exhaustive
property-by-property match or of validated firmware values. The existing
project's model-specific DJI property review (2026-10-17) and DJI's
Pilot-to-Cloud MQTT topic definition supplied additional reference context.

Never infer the actual `pushMode` of an individual M4 firmware property
from an isolated live observation: properties may appear on either channel
over time. `pushMode=0` uses `/osd`; `pushMode=1` uses `/state`.

## Current tested field mapping

| Wire properties / group | Canonical AeroNexusAdvanced fields | Review status |
| --- | --- | --- |
| `mode_code`, `mode_code_reason` | `flight_mode_code`, `cloud_details.flight_mode_reason_code` | Implemented; raw numeric code, no guessed label |
| `latitude`, `longitude`, `height`, `elevation` | Coordinates, `height_m`, `elevation_m` | Implemented; partial coordinate pairs rejected for display |
| `horizontal_speed`, `vertical_speed`, `attitude_head/roll/pitch` | m/s and `cloud_details.heading/roll/pitch_deg` | Implemented |
| `position_state.gps_number/rtk_number/is_fixed/quality` | Satellite counts, `rtk_state`, `position.quality_code` | Implemented; quality alone is **not** an RTK fix |
| `battery.capacity_percent/remain_flight_time/batteries` | Battery %, time, pack values | Implemented; no battery serials |
| `wind_speed`, `wind_direction` | `wind_speed_mps` (wire factor 0.1), `wind_direction_code` | Implemented; raw unit should be checked with a real M4T |
| `distance_limit_status.state/distance_limit/is_near_distance_limit` | `distance_limit.state_code/distance_limit_m/near_limit` | Implemented; observe only, never set |
| `obstacle_avoidance.horizon/upside/downside` | `obstacle_avoidance.*_enabled` | Implemented as true/false |
| `rth_mode`, `current_rth_mode`, `rth_altitude` | `rth_mode_code`, `current_rth_mode_code`, `rth_altitude_m` | Implemented; two modes remain distinct |
| `control_source`, `payloads[].control_source` | `control_source_category` | Implemented; no browser UUID |
| `firmware_version`, battery thresholds | `cloud_details.firmware_version`, percentages | Implemented |
| `cameras[]`, per-payload `89-0-0` | `cameras`, `payloads`, model hint `M4T` | Implemented; hint is **not** authenticated model identity |

## Explicit boundaries / remaining checks

- Neither top-level `dongle_infos` containing IMEI/eSIM identifiers nor
  raw serial numbers, `device_secret`, `nonce`, `track_id` nor unconstrained
  watermark configuration are imported by the passive allowlist.
  This is a deliberate privacy restriction, **not** proof that each is present
  in the latest M4 thing model.
- Validate exact M4E/M4T `pushMode` values, enum domains, bounds,
  gimbal/camera nesting, `rth_mode` semantics, and input units against an
  export of the **complete official M4 table** before labeling exhaustive
  conformance. Do not add unknown fields speculatively.
- In production, `/state` is change-triggered and may not appear during a
  short observation window. Distinguish missing from stale fields; do not
  let `state` renew `/osd` liveness.
- The test uses synthetic M4T payload indexes and identifier strings.
  It proves decoder behavior only, not a validated RC Plus 2 / Matrice 4T
  measurement, hardware model identity, drone readiness or flight safety.

## Safe offline regression

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_dji_m4_properties_contract.py \
  tests/test_dji_mqtt_empty_state_contract.py \
  tests/test_cloud_api_118.py \
  tests/test_cloud_api_osd.py
```

GitHub Actions runs the full suite with Python 3.12 and 3.13.
