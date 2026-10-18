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
from .pilot2_action_catalog import PILOT2_OBSERVED_ACTIONS


MAX_ENUM_LENGTH = 120
MAX_ALIASES = 128
MAX_FIELD_ALIASES = 64
# Allowlisted WPML field names from DJI's common-element documentation.
# Existence only, NOT actual contents, semantic meaning or 1.0.6 support.
# A field may occur in multiple action types.
PARAMETER_FIELD_CATEGORIES = {
    # The mapping classifies presence only; never XML values or action semantics.
    # Field names below appear in the DJI WPML Common Elements specification.
    "payloadPositionIndex": "payload",
    "gimbalPort": "payload",
    "payloadLensIndex": "camera_lens",
    "useGlobalPayloadLensIndex": "camera_lens",
    "orientedCameraType": "camera_model",
    "fileSuffix": "media_naming",
    "orientedFileSuffix": "media_naming",
    "orientedFilePath": "media_reference",
    "actionUUID": "action_tracking",
    "imageWidth": "image_dimensions",
    "imageHeight": "image_dimensions",
    "gimbalPitchRotateAngle": "gimbal",
    "gimbalYawRotateAngle": "gimbal",
    "gimbalRollRotateAngle": "gimbal",
    "gimbalRotateMode": "gimbal",
    "gimbalPitchRotateEnable": "gimbal",
    "gimbalYawRotateEnable": "gimbal",
    "gimbalRollRotateEnable": "gimbal",
    "gimbalRotateTimeEnable": "gimbal",
    "gimbalRotateTime": "gimbal",
    "focusX": "focus",
    "focusY": "focus",
    "AFPos": "focus",
    "focalLength": "zoom",
    "zoomFocalLength": "zoom",
    "hoverTime": "hover",
    "aircraftHeading": "aircraft",
    "aircraftPathMode": "aircraft",
    # Pilot 2 WPML 1.0.6 fields observed in genuine waylines. These are
    # presence-only labels, NOT DJI-documented schema or safe parameter enums.
    "cameraFocusType": "pilot2_focus_type_unverified",
    "smartObliqueCycleMode": "pilot2_smart_oblique_unverified",
    "smartObliquePoint": "pilot2_smart_oblique_unverified",
    "minShootInterval": "pilot2_interval_unverified",
}
MAX_PARAM_FIELDS_PER_ACTION = 64


def _text_or_missing(element):
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    if len(value) > MAX_ENUM_LENGTH:
        raise LocalWaylineError("unsupported_geometry")
    return value or None


def _action_param_hints(action, wpml_prefix):
    """Allowlisted field presence and ephemeral unknown names; NO parameter values.

    Unknown XML field names are private and never returned by the public CLI.
    Foreign namespaces cannot be correlated as if they were DJI WPML tags.
    """
    containers = action.findall(wpml_prefix + "actionActuatorFuncParam")
    if not containers:
        return ("absent", (), (), 0)
    if len(containers) != 1:
        return ("ambiguous", (), (), 0)
    children = list(containers[0])
    if len(children) > MAX_PARAM_FIELDS_PER_ACTION:
        raise LocalWaylineError("invalid_archive")
    if not children:
        return ("empty", (), (), 0)
    categories = set()
    unknown_fields = []
    foreign_count = 0
    for child in children:
        if not isinstance(child.tag, str) or not child.tag.startswith(wpml_prefix):
            foreign_count += 1
            continue
        key = child.tag[len(wpml_prefix):]
        label = PARAMETER_FIELD_CATEGORIES.get(key)
        if label is None:
            # Local names remain private even if they contain arbitrary data.
            if not key or len(key) > MAX_ENUM_LENGTH:
                raise LocalWaylineError("unsupported_geometry")
            unknown_fields.append(key)
        else:
            categories.add(label)
    if unknown_fields or foreign_count:
        categories.add("unclassified_fields_present")
    return ("present", tuple(sorted(categories)), tuple(unknown_fields), foreign_count)


def _xml_placement_bucket(ordinal, count):
    """Coarse ordinal bucket of the containing XML Placemark, NOT flight execution.

    DJI actionGroupStartIndex/EndIndex may specify an execution span that
    differs from the Placemark containing the actionGroup.
    """
    if count < 1 or ordinal < 0 or ordinal >= count:
        raise LocalWaylineError("unsupported_geometry")
    if count == 1:
        return "first"
    if count == 2:
        return "first" if ordinal == 0 else "last"
    return ("first", "middle", "last")[min(2, 3 * ordinal // count)]


def _uint16_element(parent, tag):
    """Internal bounded index only. Never expose indices, waypoints or values."""
    items = parent.findall(tag)
    if len(items) != 1 or items[0].text is None:
        return None
    raw = items[0].text.strip()
    if not raw or len(raw) > 5 or not raw.isascii() or not raw.isdecimal():
        return None
    value = int(raw)
    return value if 0 <= value <= 65535 else None


def _group_xml_span_relation(group, waypoint, prefix):
    """Classify source XML indices only; not actual aircraft execution spans."""
    start = _uint16_element(group, prefix + "actionGroupStartIndex")
    end = _uint16_element(group, prefix + "actionGroupEndIndex")
    if start is None or end is None:
        return "missing_or_invalid_span"
    if end < start:
        return "reversed_span"
    anchor = _uint16_element(waypoint, prefix + "index")
    if anchor is None:
        return "unresolved_placemark_index"
    if start == anchor:
        return "single_at_anchor" if start == end else "range_starts_at_anchor"
    return "single_elsewhere" if start == end else "range_starts_elsewhere"


def _group_xml_index_delta_bucket(group, waypoint, prefix, route_indices):
    """Only a coarse difference of source WPML indices, never flight distance.

    Requires a unique, consecutive set of declared wpml:index elements in the
    same Folder, with both actionGroup endpoints contained in that set.
    """
    start = _uint16_element(group, prefix + "actionGroupStartIndex")
    end = _uint16_element(group, prefix + "actionGroupEndIndex")
    anchor = _uint16_element(waypoint, prefix + "index")
    if start is None or end is None or anchor is None:
        return "missing_or_invalid_index"
    if end < start:
        return "reversed_span"
    if route_indices is None:
        return "unreliable_folder_indices"
    if start not in route_indices or end not in route_indices:
        return "endpoint_outside_folder"
    if start != anchor:
        return "starts_elsewhere"
    delta = end - start
    if delta == 0:
        return "same_index"
    if delta == 1:
        return "one_index_step"
    if delta <= 4:
        return "two_to_four_index_steps"
    if delta <= 16:
        return "five_to_sixteen_index_steps"
    return "over_sixteen_index_steps"


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
                    action.find(W + "actionActuatorFunc")), _action_param_hints(action, W),
                    "start_group", "start_group_not_applicable",
                    "start_group_not_applicable"))
        placemarks = folder.findall(K + "Placemark")
        indexes = [_uint16_element(place, W + "index") for place in placemarks]
        route_indices = (
            set(indexes) if (
                indexes and all(i is not None for i in indexes)
                and len(set(indexes)) == len(indexes)
                and max(indexes) - min(indexes) + 1 == len(indexes)
            ) else None
        )
        for position, waypoint in enumerate(placemarks):
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
                        action.find(W + "actionActuatorFunc")), _action_param_hints(action, W),
                        _xml_placement_bucket(position, len(placemarks)),
                        _group_xml_span_relation(group, waypoint, W),
                        _group_xml_index_delta_bucket(group, waypoint, W, route_indices)))
        if seen_actions > MAX_ACTIONS:
            raise LocalWaylineError("invalid_archive")
        records_by_route.append(records)
    return version, records_by_route


def _aggregate_action_records(archives, *, parameter_hints=False,
                              field_aliases=False, position_buckets=False,
                              span_audit=False, span_length_buckets=False):
    """Aggregate only anonymous enums, field occurrence counts and opt-in XML position buckets."""
    if field_aliases and not parameter_hints:
        raise ValueError("field aliases require parameter hints")
    if position_buckets and not field_aliases:
        raise ValueError("position buckets require field aliases")
    if span_audit and not field_aliases:
        raise ValueError("span audit requires field aliases")
    if span_length_buckets and not span_audit:
        raise ValueError("span length buckets require span audit")
    aliases = {}  # Raw strings confined to this stack frame and never serialized.
    # Per-invocation names only. Neither mapping is serialized, hashed or persisted.
    field_names_to_aliases = {}
    field_totals = {}
    # Static-name Pilot 2 catalogue and per-KMZ occurrence counts. These are
    # separate from the legacy anonymous/non-documented diagnostics.
    identified_counts = Counter()
    documented_counts = Counter()
    identified_files = {}
    identified_aliases = {}
    totals = {}
    results = []
    for index, kmz in archives:
        version, routes = _archive_action_records(kmz)
        route_counts = []
        route_field_multiplicities = []
        route_field_position_buckets = []
        route_field_span_statuses = []
        route_field_index_deltas = []
        unknown_total = 0
        known_total = 0
        for route in routes:
            unknown_by_alias = Counter()
            field_multiplicity_by_alias = {}
            field_positions_by_alias = {}
            field_spans_by_alias = {}
            field_index_deltas_by_alias = {}
            recognized = Counter()
            for (location, trigger, raw_name, hints, xml_bucket,
                 xml_span, xml_index_delta) in route:
                if raw_name in DOCUMENTED_ACTION_TYPES:
                    recognized[raw_name] += 1
                    documented_counts[raw_name] += 1
                    known_total += 1
                    continue
                # None is not a secret; still use a neutral alias.
                if raw_name not in aliases:
                    if len(aliases) >= MAX_ALIASES:
                        raise LocalWaylineError("unsupported_geometry")
                    aliases[raw_name] = "A" + str(len(aliases) + 1).zfill(2)
                alias = aliases[raw_name]
                if raw_name in PILOT2_OBSERVED_ACTIONS:
                    identified_counts[raw_name] += 1
                    identified_files.setdefault(raw_name, set()).add(index)
                    identified_aliases[raw_name] = alias
                unknown_total += 1
                unknown_by_alias[alias] += 1
                if alias not in totals:
                    totals[alias] = {
                        "id": alias, "occurrences": 0, "files": set(),
                        "location_counts": Counter(), "trigger_counts": Counter(),
                        "parameter_container_counts": Counter(),
                        "parameter_category_counts": Counter(),
                        "unknown_field_alias_counts": Counter(),
                        "foreign_namespace_field_count": 0,
                    }
                item = totals[alias]
                item["occurrences"] += 1
                item["files"].add(index)
                item["location_counts"][location] += 1
                item["trigger_counts"][trigger] += 1
                if parameter_hints:
                    container_state, categories, unknown_names, foreign_count = hints
                    item["parameter_container_counts"][container_state] += 1
                    for category in categories:
                        item["parameter_category_counts"][category] += 1
                    if field_aliases:
                        item["foreign_namespace_field_count"] += foreign_count
                        action_field_counts = Counter()
                        for field_name in unknown_names:
                            if field_name not in field_names_to_aliases:
                                if len(field_names_to_aliases) >= MAX_FIELD_ALIASES:
                                    raise LocalWaylineError("unsupported_geometry")
                                fid = "P" + str(len(field_names_to_aliases) + 1).zfill(2)
                                field_names_to_aliases[field_name] = fid
                                field_totals[fid] = {
                                    "id": fid, "occurrences": 0,
                                    "files": set(), "action_aliases": set(),
                                    "action_count": 0,
                                    "per_action_multiplicity": Counter(),
                                }
                            fid = field_names_to_aliases[field_name]
                            item["unknown_field_alias_counts"][fid] += 1
                            field_totals[fid]["occurrences"] += 1
                            field_totals[fid]["files"].add(index)
                            field_totals[fid]["action_aliases"].add(alias)
                            action_field_counts[fid] += 1
                        # One action can contain a field more than once. Count
                        # that multiplicity without retaining values or names.
                        for fid, count in action_field_counts.items():
                            field_totals[fid]["action_count"] += 1
                            field_totals[fid]["per_action_multiplicity"][str(count)] += 1
                            # Scope every histogram to the current KMZ and
                            # executable Folder, not only the entire library.
                            if fid not in field_multiplicity_by_alias:
                                field_multiplicity_by_alias[fid] = Counter()
                            field_multiplicity_by_alias[fid][str(count)] += 1
                            if position_buckets:
                                if fid not in field_positions_by_alias:
                                    field_positions_by_alias[fid] = {}
                                if xml_bucket not in field_positions_by_alias[fid]:
                                    field_positions_by_alias[fid][xml_bucket] = Counter()
                                field_positions_by_alias[fid][xml_bucket][str(count)] += 1
                            if span_audit:
                                if fid not in field_spans_by_alias:
                                    field_spans_by_alias[fid] = Counter()
                                # Per action, not per occurrence of a repeated field.
                                field_spans_by_alias[fid][xml_span] += 1
                            if span_length_buckets:
                                if fid not in field_index_deltas_by_alias:
                                    field_index_deltas_by_alias[fid] = {}
                                if xml_index_delta not in field_index_deltas_by_alias[fid]:
                                    field_index_deltas_by_alias[fid][xml_index_delta] = Counter()
                                # Cross-tabulate action-group index delta
                                # with per-action Pxx multiplicity, not raw positions.
                                field_index_deltas_by_alias[fid][xml_index_delta][str(count)] += 1
            route_counts.append(dict(sorted(unknown_by_alias.items())))
            if field_aliases:
                route_field_multiplicities.append({
                    fid: dict(sorted(counts.items(), key=lambda pair: int(pair[0])))
                    for fid, counts in sorted(field_multiplicity_by_alias.items())
                })
            if position_buckets:
                route_field_position_buckets.append({
                    fid: {
                        bucket: dict(sorted(mults.items(), key=lambda pair: int(pair[0])))
                        for bucket, mults in sorted(buckets.items())
                    }
                    for fid, buckets in sorted(field_positions_by_alias.items())
                })
            if span_audit:
                route_field_span_statuses.append({
                    fid: dict(sorted(statuses.items()))
                    for fid, statuses in sorted(field_spans_by_alias.items())
                })
            if span_length_buckets:
                route_field_index_deltas.append({
                    fid: {
                        size: dict(sorted(multiplicities.items(),
                                          key=lambda item: int(item[0])))
                        for size, multiplicities in sorted(deltas.items())
                    }
                    for fid, deltas in sorted(field_index_deltas_by_alias.items())
                })
        result_item = {
            "index": index,
            "state": "connected",
            "wpml_schema_version": version,
            "route_count": len(routes),
            "unknown_action_count": unknown_total,
            "recognized_action_count": known_total,
            "unknown_alias_counts_by_route": route_counts,
        }
        if field_aliases:
            result_item["unknown_field_multiplicity_by_route"] = route_field_multiplicities
        if position_buckets:
            result_item["unknown_field_xml_placement_by_route"] = route_field_position_buckets
        if span_audit:
            result_item["unknown_field_xml_span_by_route"] = route_field_span_statuses
        if span_length_buckets:
            result_item["unknown_field_xml_index_delta_by_route"] = route_field_index_deltas
        results.append(result_item)
    safe_totals = []
    for alias in aliases.values():
        item = totals[alias]
        entry = {
            "id": alias, "occurrences": item["occurrences"],
            "file_count": len(item["files"]),
            "location_counts": dict(sorted(item["location_counts"].items())),
            "trigger_counts": dict(sorted(item["trigger_counts"].items())),
        }
        if parameter_hints:
            entry["parameter_container_counts"] = dict(
                sorted(item["parameter_container_counts"].items()))
            entry["parameter_category_counts"] = dict(
                sorted(item["parameter_category_counts"].items()))
        if field_aliases:
            entry["unknown_field_alias_counts"] = dict(
                sorted(item["unknown_field_alias_counts"].items()))
            entry["foreign_namespace_field_count"] = item["foreign_namespace_field_count"]
        safe_totals.append(entry)
    identified_types = [
        {"name": name, "alias": identified_aliases[name],
         "occurrences": count, "file_count": len(identified_files[name])}
        for name, count in sorted(identified_counts.items())
    ]
    output = {"anonymous_types": safe_totals, "results": results,
              "documented_type_counts": dict(sorted(documented_counts.items())),
              "identified_types": identified_types,
              "identified_action_total": sum(identified_counts.values()),
              "unresolved_action_total": (
                  sum(x["unknown_action_count"] for x in results)
                  - sum(identified_counts.values())
              ),
              "unknown_action_total": sum(x["unknown_action_count"] for x in results),
              "recognized_action_total": sum(x["recognized_action_count"] for x in results),
              "alias_scope": "single_invocation_only",
              "full_content_verified": False,
              "flight_compatibility_verified": False}
    if field_aliases:
        output["unknown_field_aliases"] = [
            {"id": fid, "occurrences": data["occurrences"],
             "file_count": len(data["files"]),
             "action_aliases": sorted(data["action_aliases"]),
             "actions_with_field": data["action_count"],
             "multiplicity_per_action": dict(sorted(
                 data["per_action_multiplicity"].items(),
                 key=lambda pair: int(pair[0]))),}
            for fid, data in field_totals.items()
        ]
        output["field_alias_scope"] = "single_invocation_only"
    return output


async def diagnose_action_vocabulary(*, limit=8, parameter_hints=False,
                                     field_aliases=False, position_buckets=False,
                                     span_audit=False, span_length_buckets=False,
                                     inventory_reader=None,
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
        report = _aggregate_action_records(
            seen, parameter_hints=parameter_hints, field_aliases=field_aliases,
            position_buckets=position_buckets, span_audit=span_audit,
            span_length_buckets=span_length_buckets)
    except (LocalWaylineError, ValueError, KeyError, TypeError):
        return {"inventory_state": "unsupported_geometry", "results": results}
    # Index is intentionally only the index in the verified inventory.
    response = {
        "inventory_state": "connected",
        "reported_total": inventory.get("reported_total"),
        "checked": len(seen) + len(results),
        "anonymous_types": report["anonymous_types"],
        "identified_types": report["identified_types"],
        "documented_type_counts": report["documented_type_counts"],
        "identified_action_total": report["identified_action_total"],
        "unresolved_action_total": report["unresolved_action_total"],
        "unknown_action_total": report["unknown_action_total"],
        "recognized_action_total": report["recognized_action_total"],
        "alias_scope": report["alias_scope"],
        "results": sorted(report["results"] + results, key=lambda item: item["index"]),
        "full_content_verified": False,
        "flight_compatibility_verified": False,
    }
    if field_aliases:
        response["unknown_field_aliases"] = report["unknown_field_aliases"]
        response["field_alias_scope"] = report["field_alias_scope"]
    return response


def main():
    parser = argparse.ArgumentParser(description=(
        "Opt-in local Pilot 2 action correlation; no actuator names, "
        "coordinates, UUIDs, KMZ, tokens or hashes in output. GET-only."))
    parser.add_argument("--limit", type=int, choices=range(1, 9), default=8)
    parser.add_argument("--parameter-hints", action="store_true",
                        help="Nur statische XML-Feldkategorien der unbekannten Aktionen zählen")
    parser.add_argument("--field-aliases", action="store_true",
                        help="Unbekannte DJI-Feldnamen nur als flüchtige P01/P02-Aliase korrelieren")
    parser.add_argument("--position-buckets", action="store_true",
                        help="Grobe XML-Verankerung (erstes/mittleres/letztes Routendrittel)")
    parser.add_argument("--span-audit", action="store_true",
                        help="Nur Status der XML-actionGroup-Start-/End-Indizes zählen")
    parser.add_argument("--span-length-buckets", action="store_true",
                        help="Grobe Differenz der XML-Start-/End-Indizes ohne Rohwerte")
    args = parser.parse_args()
    if args.field_aliases and not args.parameter_hints:
        parser.error("--field-aliases erfordert --parameter-hints")
    if args.position_buckets and not args.field_aliases:
        parser.error("--position-buckets erfordert --parameter-hints --field-aliases")
    if args.span_audit and not args.field_aliases:
        parser.error("--span-audit erfordert --parameter-hints --field-aliases")
    if args.span_length_buckets and not args.span_audit:
        parser.error("--span-length-buckets erfordert --span-audit")
    try:
        report = asyncio.run(diagnose_action_vocabulary(
            limit=args.limit, parameter_hints=args.parameter_hints,
            field_aliases=args.field_aliases, position_buckets=args.position_buckets,
            span_audit=args.span_audit,
            span_length_buckets=args.span_length_buckets))
    except KeyboardInterrupt:
        return 130
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["inventory_state"] == "connected" and all(
        item["state"] == "connected" for item in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
