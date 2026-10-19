# DJI Pilot-to-Cloud MQTT: empty `state` envelope conformance

**Scope:** AeroNexusAdvanced, offline decoder regression, independent of the
productive Pi service, broker and aircraft. No firmware, .env, ACL, deployment,
Cloud Server or flight-control change.

## DJI primary contract

DJI distinguishes periodic `thing/product/{device_sn}/osd` (`pushmode=0`)
from on-change `thing/product/{device_sn}/state` (`pushmode=1`).
DJI's **state message struct example explicitly contains `"data": {}`**.
The shared envelope has `tid`, `bid`, `timestamp` (milliseconds),
`gateway` and `data`.

Primary source:
https://github.com/dji-sdk/Cloud-API-Doc/blob/master/docs/en/60.api-reference/10.pilot-to-cloud/00.mqtt/00.topic-definition.md

## Behavior of the read-only consumer

| Received input | Behavior | Existing telemetry / liveness |
| --- | --- | --- |
| Authorized `/state`, `data={}` | Count **ignored**, not rejected | Unchanged |
| Unauthorized/disabled `/state`, `data={}` | Rejected | Unchanged |
| `/osd`, `data={}` | Rejected (OSD policy unchanged) | Unchanged |
| `/state` with missing/non-object `data` | Rejected | Unchanged |
| `/state` with malformed / far-future timestamp | Rejected | Unchanged |
| `/state` with nonempty supported data, known device | Existing opt-in normalizer | Per-field freshness preserved |
| MQTT services, property set, DRC down, topology | Not an allowed telemetry topic | No ingest / no publish |

Only the optional `allow_empty_data` argument of `osd_envelope` changes
the envelope parsing policy. It is passed **only** after recognizing and
authorizing a `/state` topic. Empty packets do not register devices,
set `online`, renew `cloud_osd_clocks`, change field timestamps,
or claim a successfully accepted telemetry sample.

The read-only account, explicit state subscription opt-in, and the
MQTT client-side publish prohibition are unchanged. Do **not**
treat an empty state event as an anomaly or evidence that state
property coverage is complete.

## Offline regression

```bash
cd ~/Projekte/AeroNexusAdvanced
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_dji_mqtt_empty_state_contract.py \
  tests/test_cloud_api_osd.py \
  tests/test_cloud_api_mqtt.py \
  tests/test_dji_state_conformance.py
```

These tests use synthetic identifiers and in-memory state; no broker,
drone, RC or cloud credentials are contacted. The command is intended
to run in a checkout of the **feature branch**, not in a production deploy.

## Separate responsibilities and open acceptance work

AeroNexusAdvanced's observer does **not** take over DJI's reply-required
`events`, `requests`, `services`, or topology transactions. The
existing Cloud Server is responsible for its own MQTT protocol exchanges.
Do not subscribe to `sys/product/+/status` inside the read-only decoder;
`update_topo` can carry device secrets and nonces.

Real M4T / RC Plus 2 conformance still requires
documented field-by-field comparison, valid SUBACK and accepted deltas,
stale/online negative tests, and independent verification of properties
delivered by the installed DJI firmware. An offline regression is not
hardware verification or authorization to fly.
