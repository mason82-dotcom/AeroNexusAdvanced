# Phase 9: read-only DJI Cloud API live feed (MQTT OSD)

AeroNexus (the sibling project) runs a self-hosted DJI Cloud API server:
DJI Pilot 2 on the remote controller (RC Plus 2 / RC Pro) connects to its EMQX
broker and pushes telemetry ("OSD") about once per second. AeroNexusAdvanced
can subscribe to that telemetry and show it in the status dashboard.

Historical status at the 2026-10-16 Pi setup: disabled on the dev Pi
(`AERONEXUS_CLOUD_MQTT_ENABLED=0`); FlightHub 2 (phase 10) is the
active source. Do not infer that an EMQX broker or Pilot 2 Cloud API workspace
is running merely because the MQTT consumer is implemented. For newer recorded
deployment evidence see `PROJECT_STATUS.md`; this implementation does not
change the running Pi configuration.

## What it does

- Connects to EMQX with the dedicated `aeronexus_osd` account. The AeroNexus
  ACL (`telemetry/emqx/acl.conf`) only allows it to **subscribe**
  `thing/product/+/osd`; publishing is denied by the broker.
- Subscribes to exactly `thing/product/+/osd`, QoS 0, by default.
  Opt-in `AERONEXUS_OSD_STATE_ENABLED=1` also subscribes to
  `thing/product/+/state`, the DJI change-driven properties topic.
  The broker must grant **both** subscriptions to the same dedicated
  non-superuser read-only account; a denied topic makes the client fail closed.
  The paho client's `publish` method is replaced by a function that raises:
  neither setting can send anything to the drone.
- `sys/product/+/status` (topology) is not read: it carries `device_secret`
  and `nonce`.
- The device type is derived from the OSD properties (aircraft: `mode_code`,
  `elevation`, `position_state`, `battery{}`; remote controller:
  `capacity_percent` / `wireless_link` / live status). Known devices can also
  send partial property-only OSD packets; documented camera payload indexes
  can establish an aircraft. Unrecognized messages are ignored.
- Every message is validated with the same strict canonical schema as
  FlightHub telemetry. An invalid message is dropped completely and never
  partially applied. Partial OSD pushes keep previously received values.
  Optional `state` packets update only **already registered OSD devices**
  and only an allowlist of canonical telemetry fields. Unknown state-only
  serials and unrelated DJI data are ignored. Additional properties use the
  strict `cloud_details` allowlist, never raw payload storage. Secrets,
  credentials, IMEI, SIM identifiers, battery serials, `device_secret` and
  `nonce` are never stored.
  RTK `is_fixed` allows documented numeric codes and bounded string enums
  such as `not_started`, without interpreting them as a fix confirmation.
- Position `0/0` (DJI's "no position") is shown as "no location".
- Devices land in the local inventory under provider `dji-cloud-api`,
  project `aeronexus` (limit: 50 devices).
- Anonymous counters (`live_feed` in `/api/v1/status/summary`):
  state, accepted, rejected, ignored, outdated, last message time. No serial numbers.

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


## Cloud API 1.18 protocol audit (2026-10-17)

DJI's [official Chinese release notes](https://developer.dji.com/doc/cloud-api-tutorial/cn/)
confirm **v1.18, dated 2026-10-13**. That release mainly adds O4 Ground
Station device capabilities and Dock 3 flight-termination protocols, and
expands Dock 2/3 camera configuration. Those **are not Matrice 4T / DJI
Pilot 2 features to activate** and are not implemented here. Matrice 4T Pilot 2
cloud support was introduced in v1.12. DJI's general developer landing page
may still show the older v1.14 number.

The current DJI
[topic specification](https://github.com/dji-sdk/Cloud-API-Doc/blob/master/docs/en/60.api-reference/10.pilot-to-cloud/00.mqtt/00.topic-definition.md)
defines `osd` (periodic) and `state` (changed properties).
This phase adds compatible, **read-only** handling for those messages, not
a versioned client library update. It does not implement the new O4, Dock,
control, firmware-write or camera-configuration APIs.

### Activate only after the Pi broker and Pilot 2 workspace are verified

1. Keep `AERONEXUS_FH_POLL_ENABLED=1` and the Public Cloud settings intact
   while testing; this is an independent provider and a fallback.
2. Check whether the **separate DJI Cloud API server** (AeroNexus edge,
   EMQX, Pilot 2 login/workspace and own DJI developer app licence) actually
   runs on this Pi. AeroNexusAdvanced is **only a subscriber**, not a
   full Pilot 2 third-party cloud backend. FlightHub OpenAPI credentials
   do not authenticate the Cloud API workspace.
3. On the broker grant a dedicated user ONLY MQTT `subscribe` to
   `thing/product/+/osd`. For opt-in state also grant `subscribe` to
   `thing/product/+/state`. Do **not** give it publish permissions and do not
   subscribe to `sys/product/+/status` (may include secrets).
4. Set `AERONEXUS_CLOUD_MQTT_ENABLED=1` with correct
   `AERONEXUS_OSD_HOST`, `AERONEXUS_OSD_PORT`,
   `AERONEXUS_OSD_USERNAME` and `AERONEXUS_OSD_PASSWORD` in
   the **private, mode 0600** `.env`; for state, optionally set
   `AERONEXUS_OSD_STATE_ENABLED=1`. The subscriber defaults to loopback
   plaintext; for non-loopback brokers use valid TLS unless explicitly
   opting into unencrypted LAN traffic.
5. Restart only `aeronexusadvanced.service`; verify
   `GET /api/v1/status/summary` shows
   `live_feed.state=subscribed`, plus `state_topic_enabled=true`
   if requested. Successful subscription alone does **not** prove a
   drone is sending telemetry: check increasing `accepted` counters with
   a controller connected via Pilot 2 to **this third-party platform**.
6. Compare the separate `dji-cloud-api` inventory with the still-active
   `flighthub-public-v2` provider in `/status`. No automatic source
   selection, DJI pairing, mission upload or flight control is done.

The current implementation tracks receive and source age per property.
State updates never renew OSD liveness or unrelated fields. See the explicit
ordering, compatibility and expiry rules in
[Cloud API 1.18 telemetry](cloud-api-118-telemetry.md). State remains opt-in;
this change does not grant broker permissions or activate subscriptions.

This is **not** an official FlightHub 2 On-Premises deployment. DJI Pilot 2
third-party Cloud API onboarding requires its own workspace, app ID/key,
and licence validation. The official discontinued Cloud API demo is not a
secure out-of-the-box production server.
