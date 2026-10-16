# Phase 11: Mobile Fleet Diagnostics (read-only)

## Goal

Provide a legible FlightHub 2 device view on Android phones as well as desktop
browsers. Uses only **existing local status APIs**; does not poll DJI from the
browser or introduce any new provider endpoints, flight commands or dock support.

## Dashboard: `/status`

The authenticated `/api/v1/status/devices?limit=200` response feeds responsive
cards for aircraft and remote controllers. Each card displays when available:

- Device name, ID, type and **freshness** (`fresh`, `stale`, `missing`,
  `unknown_age`, `clock_skew`).
- Last ingestion **age**, not DJI source timestamp. Online/offline claims are
  displayed only when freshness is `fresh`; for stale records the page explicitly
  says that the online state is not current.
- Battery percentage with a native progress bar; FlightHub flight mode; height
  above takeoff (`elevation_m`) **separately** from absolute height (`height_m`);
  horizontal and vertical speed; home distance; GPS and RTK satellites; RTK raw
  fix state; battery voltage/temperature; cumulative flight time/sorties.
- Coordinates only when the provider supplied valid nonzero GPS data. Positions
  are never present in anonymous summary responses.
- Most recently received HMS warnings/notifications (not guaranteed to be
  current after a failed HMS retrieval), up to five in the card. The full
  detail table remains accessible through an expandable section.

Above the cards, the anonymous summary includes a simple read-only diagnostic
line for the FlightHub polling state, the last **successful** local refresh
timestamp and the telemetry staleness threshold. An error does not imply that
the device itself is offline.

FlightHub library tables (waylines, mapping models, flight tasks) and manually
requested GeoJSON tracks remain available and require the same dashboard token.

## Authentication and browser session

- Dashboard bearer token is **never stored in browser localStorage, cookies or
  URL parameters**. It lives only in the JavaScript state of the current tab.
- All provider-originated text (name, ID, HMS, telemetry, catalog) is inserted
  using DOM `textContent`, not `innerHTML`.
- Disconnect clears the card and table containers and invalidates pending
  device/catalog/track requests through a session epoch. Late asynchronous
  responses may finish on the network but cannot repopulate a disconnected view.
- No new server endpoints or permissions. Read-only FlightHub access is
  unchanged. `POST /api/v1/flight/command` remains rejected with HTTP 403.
- Use only the existing **HTTPS** endpoint for entering the status token:
  `https://192.168.178.63:8000/status` (trusted local CA required).
  Do **not** use an old plaintext HTTP URL.

## Limitations

- Only the first 200 devices are currently shown (the API reports the total).
- HMS data is a snapshot of the last successful HMS read, not a separately
  time-stamped message stream.
- A refreshed browser tab requires the status token again.
- DJI RC Plus 2 does not currently appear as a distinct device in the tested
  FlightHub Public Cloud project; the page cannot conjure RC data if DJI does
  not supply it. The opt-in MQTT feed may cover RC telemetry later.

## Raspberry Pi smoke test

```bash
cd ~/Projekte/AeroNexusAdvanced
git pull --ff-only
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
systemctl --user restart aeronexusadvanced
systemctl --user is-active aeronexusadvanced
```

Open the HTTPS dashboard on your phone, connect with the **AeroNexus status
token**, expand the technical table and verify values against the DJI Pilot 2
display. Disconnect and confirm device cards, library rows and track controls
disappear. Expect **400 tests** (395 previously verified plus five new UI
regression tests); the updated code has not yet been run on the Pi.
