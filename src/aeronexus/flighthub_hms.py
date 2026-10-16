"""FlightHub 2 Public Cloud HMS (Health Management System) alerts, read-only.

GET /openapi/{v2.0|v0.1}/device/hms?device_sn_list=SN1,SN2 (project-scoped).
Only live alerts (status 1) are kept, reduced to display fields. The
endpoint and the {"list": null} quirk were validated live by
alecad/dji-flighthub2-cli (Apache-2.0).
"""
from collections.abc import Mapping, Sequence
import re
from uuid import UUID

from .providers import ProviderConfig, ProviderKind
from .read_only_transport import ReadOnlyTransport


class HmsError(ValueError):
    pass


LEVELS = ("notification", "reminder", "warning")
MAX_DEVICES_PER_CALL = 20
MAX_ALERTS_PER_DEVICE = 20
_SERIAL = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")


def _text(value, limit: int) -> str | None:
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def _alert(item) -> dict | None:
    if not isinstance(item, Mapping) or item.get("status", 1) != 1:
        return None
    level = item.get("level")
    return {
        "level": level if level in LEVELS else "unknown",
        "code": _text(item.get("code"), 64),
        "message": _text(item.get("message"), 300),
        "imminent": item.get("imminent") is True,
        "in_the_sky": item.get("in_the_sky") == "in_the_sky",
    }


def normalize_hms(payload, requested: Sequence[str]) -> dict[str, tuple[dict, ...]]:
    if not isinstance(payload, Mapping) or payload.get("code") != 0:
        raise HmsError("Unsuccessful HMS response")
    data = payload.get("data")
    rows = data.get("list", ...) if isinstance(data, Mapping) else ...
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise HmsError("Invalid HMS list")
    result = {sn: () for sn in requested}
    for row in rows:
        if not isinstance(row, Mapping):
            raise HmsError("Invalid HMS entry")
        sn = row.get("device_sn")
        if sn not in result:
            continue  # never accept alerts for devices that were not asked for
        hms = row.get("device_hms") or {}
        items = hms.get("list") if isinstance(hms, Mapping) else None
        alerts = [a for a in (_alert(i) for i in (items or [])) if a is not None]
        rank = {level: index for index, level in enumerate(reversed(LEVELS))}
        alerts.sort(key=lambda a: (rank.get(a["level"], len(LEVELS)), not a["imminent"]))
        result[sn] = tuple(alerts[:MAX_ALERTS_PER_DEVICE])
    return result


async def read_public_hms(config: ProviderConfig, project_uuid: str,
                          device_sns: Sequence[str]) -> dict[str, tuple[dict, ...]]:
    if config.kind != ProviderKind.PUBLIC_V2:
        raise HmsError("Public Cloud provider required")
    try:
        project_uuid = str(UUID(project_uuid))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HmsError("Invalid project UUID") from exc
    sns = list(dict.fromkeys(device_sns))
    if any(not isinstance(sn, str) or _SERIAL.fullmatch(sn) is None for sn in sns):
        raise HmsError("Invalid device serial number")
    path = config.path("/device/hms")
    transport = ReadOnlyTransport(config, frozenset({path}))
    result: dict[str, tuple[dict, ...]] = {}
    for start in range(0, len(sns), MAX_DEVICES_PER_CALL):
        chunk = sns[start:start + MAX_DEVICES_PER_CALL]
        payload = await transport.get(path, {"device_sn_list": ",".join(chunk)},
                                      project_uuid=project_uuid)
        result.update(normalize_hms(payload, chunk))
    return result
