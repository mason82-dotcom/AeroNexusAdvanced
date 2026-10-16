# Phase 9: read-only DJI Cloud API live feed (MQTT OSD)

AeroNexus (the sibling project) runs a self-hosted DJI Cloud API server:
DJI Pilot 2 on the remote controller (RC Plus 2 / RC Pro) connects to its EMQX
broker and pushes telemetry ("OSD") about once per second. AeroNexusAdvanced
can subscribe to that telemetry and show it in the status dashboard.

Status 2026-10-16: disabled on the dev Pi (`AERONEXUS_CLOUD_MQTT_ENABLED=0`);
FlightHub 2 (phase 10) is the active data source.

## What it does

- Connects to EMQX with the dedicated `aeronexus_osd` account. The AeroNexus
  ACL (`telemetry/emqx/acl.conf`) only allows it to **subscribe**
  `thing/product/+/osd`; publishing is denied by the broker.
- Subscribes to exactly `thing/product/+/osd`, QoS 0. The paho client's
  `publish` method is replaced by a function that raises, so the gateway
  cannot send anything to a device even by mistake.
- `sys/product/+/status` (topology) is not read: it carries `device_secret`
  and `nonce`.
- The device type is derived from the OSD properties (aircraft: `mode_code`,
  `elevation`, `position_state`, `battery{}`; remote controller:
  `capacity_percent` / `wireless_link`). Unrecognized messages are ignored.
- Every message is validated with the same strict canonical schema as
  FlightHub telemetry. An invalid message is dropped completely and never
  partially applied. Partial OSD pushes keep previously received values.
- Position `0/0` (DJI's "no position") is shown as "no location".
- Devices land in the local inventory under provider `dji-cloud-api`,
  project `aeronexus` (limit: 50 devices).
- Anonymous counters (`live_feed` in `/api/v1/status/summary`):
  state, accepted, rejected, ignored, last message time. No serial numbers.

Feed states: `connecting`, `connected`, `subscribed` (receiving),
`subscription_denied` (ACL), `auth_failed` (account missing/wrong password),
`unreachable` (broker down), `disconnected` (reconnects automatically,
1-30 s back-off), `stopped`.

## Setup

```bash
cd ~/Projekte/AeroNexusAdvanced
source .venv/bin/activate
python -m pip install -e '.[test,mqtt]'
cp .env.example .env && chmod 600 .env   # fill in, see comments
python -m uvicorn aeronexus.app:app --host 127.0.0.1 --port 8000 --env-file .env
```

The broker account must exist in EMQX as a **non-superuser**. AeroNexus
`edge/setup.sh` adds it to `runtime/emqx/auth-bootstrap.csv` when
`AERONEXUS_OSD_PASSWORD` is set in `edge/.env`; if EMQX already has a user
database, create it once in the EMQX dashboard (127.0.0.1:18083,
Authentication -> Built-in database -> Users, "Is superuser" off).

## Test with Matrice 4T + RC Plus 2

1. Start the AeroNexus edge stack (`edge/`, `docker compose up -d`).
2. Start AeroNexusAdvanced as above; `/api/v1/status/summary` must show
   `"live_feed": {"state": "subscribed", ...}`.
3. Switch on RC Plus 2, log in to the AeroNexus workspace in Pilot 2
   (Cloud Service). The RC appears as "Remote controller".
4. Switch on the Matrice 4T: an "Aircraft" row appears with battery,
   satellites, flight mode (Standby) and position.
5. Switch off the aircraft: its row turns "Veraltet" (stale) after
   `AERONEXUS_STATUS_STALE_AFTER_SECONDS` (15 s recommended for MQTT).

## Limits

- OSD has no model name or callsign; rows are named "Aircraft" /
  "Remote controller" with the serial number.
- `received_at` is the gateway receive time, not the DJI event time.
- Plain MQTT is used on the Pi's loopback interface; a remote broker needs
  `AERONEXUS_OSD_TLS=1` or an explicit `AERONEXUS_OSD_ALLOW_PLAINTEXT_LAN=1`.
