"""Opt-in, read-only, privacy-preserving cross-wayline WPML action correlation.

Unknown actuator names remain only in ephemeral local process memory, never
returned, printed, logged, hashed, uploaded or stored. Anonymous A01/A02
labels are assigned per invocation and MUST NOT be treated as DJI enums.
"""
import argparse
import asyncio
from collections import Counter
import json

import httpx

from .local_waylines import LocalWaylineError, credentials_path, load_credentials, read_waylines
from .pilot2_wayline_parameters import (
    DOCUMENTED_ACTION_TRIGGERS, DOCUMENTED_ACTION_TYPES, K,
    KNOWN_WPML_SCHEMAS, MAX_ACTIONS, MAX_ELEMENTS, MAX_FEATURES, _read_xml,
)
from .pilot2_wayline_preview import _download_kmz


MAX_ENUM_LENGTH = 120
MAX_ALIASES = 128


def _text_or_missing(element):
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    if len(value) > MAX_ENUM_LENGTH:
        raise LocalWaylineError("unsupported_geometry")
    return value or None


def _archive_action_records(kmz):
    """Read allowlisted namespace and executable Folder action groups only.

    Raw strings returned internally by this private helper are never exposed
    by the public CLI, JSON report or a callable report function.
    """
    doc = _read_xml(kmz)
    versions = [
        version for version, namespace in KNOWN_WPML_SCHEMAS.items()
        if doc.find("{" + namespace + "}missionConfig") is not None
    ]
    if len(versions) != 1:
        raise LocalWaylineError("unsupported_geometry")
    version = versions[0]
    W = "{" + KNOWN_WPML_SCHEMAS[version] + "}"
    folders = doc.findall(K + "Folder")
    if not 1 <= len(folders) <= MAX_FEATURES:
        raise LocalWaylineError("unsupported_geometry")
    if sum(1 for _ in doc.iter()) > 25000:
        raise LocalWaylineError("invalid_archive")

    records_by_route = []
    seen_actions, waypoints = 0, 0
    for folder in folders:
        records = []
        for group in folder.findall(W + "startActionGroup"):
            trigger = "start"
            actions = group.findall(".//" + W + "action")
            for action in actions:
                seen_actions += 1
                records.append(("start", trigger, _text_or_missing(
                    action.find(W + "actionActuatorFunc"))))
        for waypoint in folder.findall(K + "Placemark"):
            waypoints += 1
            if waypoints > MAX_ELEMENTS:
                raise LocalWaylineError("invalid_archive")
            for group in waypoint.findall(".//" + W + "actionGroup"):
                trigger_elem = group.find(W + "actionTrigger/" + W + "actionTriggerType")
                raw_trigger = _text_or_missing(trigger_elem)
                trigger = (raw_trigger if raw_trigger in DOCUMENTED_ACTION_TRIGGERS
                           else "unknown_trigger")
                actions = group.findall(".//" + W + "action")
                for action in actions:
                    seen_actions += 1
                    records.append(("waypoint", trigger, _text_or_missing(
                        action.find(W + "actionActuatorFunc"))))
        if seen_actions > MAX_ACTIONS:
            raise LocalWaylineError("invalid_archive")
        records_by_route.append(records)
    return version, records_by_route


def _aggregate_action_records(archives):
    """Use per-call labels, not hashes, to correlate identical unknown enums.

    archives: list of (1-based inventory index, KMZ bytes) tuples. Does not
    materialize raw strings in returned or serializable structures.
    """
    aliases = {}  # Raw strings confined to this stack frame and never serialized.
    totals = {}
    results = []
    for index, kmz in archives:
        version, routes = _archive_action_records(kmz)
        route_counts = []
        unknown_total = 0
        known_total = 0
        for route in routes:
            unknown_by_alias = Counter()
            recognized = Counter()
            for location, trigger, raw_name in route:
                if raw_name in DOCUMENTED_ACTION_TYPES:
                    recognized[raw_name] += 1
                    known_total += 1
                    continue
                # None is not a secret; still use a neutral alias.
                if raw_name not in aliases:
                    if len(aliases) >= MAX_ALIASES:
                        raise LocalWaylineError("unsupported_geometry")
                    aliases[raw_name] = "A" + str(len(aliases) + 1).zfill(2)
                alias = aliases[raw_name]
                unknown_total += 1
                unknown_by_alias[alias] += 1
                if alias not in totals:
                    totals[alias] = {
                        "id": alias, "occurrences": 0, "files": set(),
                        "location_counts": Counter(), "trigger_counts": Counter(),
                    }
                item = totals[alias]
                item["occurrences"] += 1
                item["files"].add(index)
                item["location_counts"][location] += 1
                item["trigger_counts"][trigger] += 1
            route_counts.append(dict(sorted(unknown_by_alias.items())))
        results.append({
            "index": index,
            "state": "connected",
            "wpml_schema_version": version,
            "route_count": len(routes),
            "unknown_action_count": unknown_total,
            "recognized_action_count": known_total,
            "unknown_alias_counts_by_route": route_counts,
        })
    safe_totals = []
    for alias in aliases.values():
        item = totals[alias]
        safe_totals.append({
            "id": alias, "occurrences": item["occurrences"],
            "file_count": len(item["files"]),
            "location_counts": dict(sorted(item["location_counts"].items())),
            "trigger_counts": dict(sorted(item["trigger_counts"].items())),
        })
    return {"anonymous_types": safe_totals, "results": results,
            "unknown_action_total": sum(x["unknown_action_count"] for x in results),
            "recognized_action_total": sum(x["recognized_action_count"] for x in results),
            "alias_scope": "single_invocation_only",
            "full_content_verified": False,
            "flight_compatibility_verified": False}


async def diagnose_action_vocabulary(*, limit=8, inventory_reader=None,
                                     kmz_reader=None, credentials_loader=None):
    if type(limit) is not int or not 1 <= limit <= 8:
        raise ValueError("invalid limit")
    reader = inventory_reader or read_waylines
    downloader = kmz_reader or _download_kmz
    loader = credentials_loader or load_credentials
    credentials = loader(credentials_path())
    if credentials is None:
        return {"inventory_state": "not_configured", "results": []}
    try:
        inventory = await asyncio.wait_for(reader(credentials), timeout=15)
    except (LocalWaylineError, httpx.HTTPError, OSError, TimeoutError):
        return {"inventory_state": "unavailable", "results": []}
    if (inventory.get("state") != "connected" or not inventory.get("pagination_complete")
            or inventory.get("workspace_id") != credentials.workspace_id):
        return {"inventory_state": "incomplete_inventory", "results": []}
    results, seen = [], []
    for index, route in enumerate(inventory["waylines"][:limit], start=1):
        try:
            kmz = await asyncio.wait_for(
                downloader(credentials, route["wayline_id"]), timeout=22)
            # Fail closed and do not dump raw actuator names on parse errors.
            _archive_action_records(kmz)
            seen.append((index, kmz))
        except (LocalWaylineError, httpx.HTTPError, OSError, TimeoutError, ValueError, KeyError, TypeError):
            results.append({"index": index, "state": "unavailable_or_unsupported"})
    try:
        report = _aggregate_action_records(seen)
    except (LocalWaylineError, ValueError, KeyError, TypeError):
        return {"inventory_state": "unsupported_geometry", "results": results}
    # Index is intentionally only the index in the verified inventory.
    return {
        "inventory_state": "connected",
        "reported_total": inventory.get("reported_total"),
        "checked": len(seen) + len(results),
        "anonymous_types": report["anonymous_types"],
        "unknown_action_total": report["unknown_action_total"],
        "recognized_action_total": report["recognized_action_total"],
        "alias_scope": report["alias_scope"],
        "results": sorted(report["results"] + results, key=lambda item: item["index"]),
        "full_content_verified": False,
        "flight_compatibility_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=(
        "Opt-in local Pilot 2 action correlation; no actuator names, "
        "coordinates, UUIDs, KMZ, tokens or hashes in output. GET-only."))
    parser.add_argument("--limit", type=int, choices=range(1, 9), default=8)
    args = parser.parse_args()
    try:
        report = asyncio.run(diagnose_action_vocabulary(limit=args.limit))
    except KeyboardInterrupt:
        return 130
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["inventory_state"] == "connected" and all(
        item["state"] == "connected" for item in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
