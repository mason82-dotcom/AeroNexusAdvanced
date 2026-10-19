# DJI Pilot-to-Cloud MQTT: finite-number and envelope conformance

**Scope:** passive AeroNexusAdvanced MQTT observer for DJI Pilot 2, Matrice 4T and RC Plus 2.
**Source:** [DJI Pilot-to-Cloud MQTT topic definition](https://github.com/dji-sdk/Cloud-API-Doc/blob/master/docs/en/60.api-reference/10.pilot-to-cloud/00.mqtt/00.topic-definition.md).
This is an offline decoder hardening change, **not** a device or flight acceptance.

## Contract and ownership

| DJI topic family | Receiving role | AeroNexusAdvanced behavior |
| --- | --- | --- |
| `thing/product/{device_sn}/osd` | Periodic telemetry, pushMode=0 | Subscribe; validate and normalize known fields |
| `thing/product/{device_sn}/state` | Change-triggered state, pushMode=1 | Optional subscribe; known devices only |
| `thing/product/{gateway_sn}/events` | Device event notification | Optional, HMS-only passive observer; the separate cloud server retains any necessary protocol replies |
| `sys/product/{gateway_sn}/status` | Topology update | Not subscribed by the observer; may contain device_secret and nonce |
| `thing/product/{gateway_sn}/requests` | Device-originated requests | Handled by the independent cloud server, never by the passive observer |
| `thing/product/{gateway_sn}/services`, `property/set`, `drc/down` | Server-originated control | No publish capability in the observer |

DJI's common envelope fields include `tid`, `bid`, `timestamp`, `gateway`
and `data`. A gateway serial number in the envelope is **not** equivalent
to the device serial number in the telemetry topic. Neither should be logged
as part of diagnostics. `state` may be absent when a property has not changed;
missing `state` must not refresh OSD liveness or authorize a new device.

## Validation change

Python's `json.loads` accepts the non-JSON numeric tokens `NaN`,
`Infinity` and `-Infinity` by default. These are not permitted JSON numbers.
The MQTT OSD/state envelope decoder now rejects them, including inside
unknown vendor properties, before mapping anything to the inventory.
Valid JSON numeric literals with exponents so large that Python would parse
them as positive or negative infinity (for example `1e9999`) are rejected
as well, even in unknown fields or next to an empty `state.data` object.
Direct `normalize_osd()` calls also reject nonfinite Python floats.

Positive finite numbers, signed finite values and documented nullable
properties retain their existing behavior. The runtime's per-field source
clocks, device classification, output schema, subscription ACL and
no-publish policy are unchanged.

The combined draft PR #85 integrates the complementary fixes from PR #83
(valid empty `state.data={}` as a no-op) and PR #84 (strict JSON decoding).
It is not a hardware acceptance or an authorization to deploy.

## Verification

Run in a nonproduction checkout:

```bash
python -m pytest -q tests/test_cloud_api_osd.py tests/test_cloud_api_mqtt.py tests/test_cloud_api_118.py
```

Regression coverage checks malformed nonfinite JSON in both mapped and
unmapped properties, direct numeric normalization, unchanged inventory,
unchanged source clocks and rejection counts.

**Not validated by these tests:** broker delivery, deployed version on
Raspberry Pi, firmware-dependent RC Plus 2/Matrice 4T property completeness,
operational `need_reply` handling by the separate cloud server, and DJI Pilot 2
or flight behavior. No MQTT settings, aircraft controls, EMQX ACLs, `.env`,
systemd services or production resources are changed.
