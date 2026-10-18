# DJI Mavic 3 Enterprise – read-only device model codes

The topology API may return `device_model` **without** `key`, but with
numeric `domain`, `type`, and `sub_type` fields. This is confirmed by
the local Pilot 2 GET response. The viewer now constructs a validated canonical
code when needed. The original `key` remains supported; any contradictory
fields fail closed and return `None` for the model key.

| Aircraft | Canonical aircraft code | WPML aircraft type/subtype | Camera/payload type/subtype |
| --- | --- | --- | --- |
| DJI Mavic 3 Enterprise (M3E) | `0-77-0` | `77/0` | `66/0` (`1-66-0`) |
| DJI Mavic 3 Thermal (M3T) | `0-77-1` | `77/1` | `67/0` (`1-67-0`) |
| DJI Mavic 3 Multispectral (M3M) | `0-77-2` | `77/2` | `68/0` (`1-68-0`) |
| DJI Mavic 3 Thermal Advanced (M3TA) | `0-77-3` | `77/3` | `129/0` (`1-129-0`) |

Controller identifiers (separate role/domain, not camera identifiers):

| Controller | Controller code |
| --- | --- |
| DJI RC Pro Enterprise | `2-144-0` |
| DJI RC Plus 2 | `2-174-0` |

## Sources and scope

- Official product support and device/payload enumeration (includes M3TA):
  https://developer.dji.com/doc/cloud-api-tutorial/en/overview/product-support.html
- Official DJI WPML drone and payload enumeration (includes M3M):
  https://github.com/dji-sdk/Cloud-API-Doc/blob/master/docs/en/60.api-reference/00.dji-wpml/40.common-element.md

The supported waypoint profiles in `wpml_export.MODELS` already list all
four models. This patch does not alter waypoint export, aircraft commands,
compatibility verification, or deployment settings.

**Important:** DJI model identification is not evidence of firmware support,
M3M multispectral camera actions, M3TA mission acceptance, operational flight
safety, or compatibility between a particular aircraft and controller.
The UI and API remain read-only and keep unknown model codes as codes,
rather than inventing product names. The documented Cloud API product list
may not enumerate M3M separately; its aircraft code is corroborated by WPML.
