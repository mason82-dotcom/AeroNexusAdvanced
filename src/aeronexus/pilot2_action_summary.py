"""On-demand viewer-only Pilot 2 action summary for Studio.

Never offers route editing, uploading, execution, DJI writes, or raw KMZ/XML.
A short, session-bound in-process cache throttles the expensive GET-only scan.
"""
import asyncio
import re
import time

import httpx

from .local_waylines import LocalWaylineError, credentials_path, load_credentials
from .pilot2_wayline_action_vocabulary import diagnose_action_vocabulary
from .pilot2_action_catalog import (
    PILOT2_OBSERVED_ACTIONS, DOCUMENTED_ACTION_LABELS,
)


CACHE_SECONDS = 90
MAX_REPORT_ITEMS = 8
_ALIAS = re.compile(r"A[0-9]{2,3}\Z")
_ALLOWED_TRIGGERS = frozenset({
    "start", "reachPoint", "betweenAdjacentPoints",
    "multipleTiming", "multipleDistance", "unknown_trigger",
})
_ALLOWED_LOCATIONS = frozenset({"start", "waypoint"})


def summarize_action_report(report):
    """Strict numeric/type allowlist; no freeform upstream/diagnostic fields."""
    if not isinstance(report, dict):
        return _empty("invalid_response")
    if report.get("inventory_state") != "connected":
        return _empty(report.get("inventory_state"))
    items = report.get("results")
    types = report.get("anonymous_types")
    if not isinstance(items, list) or not isinstance(types, list):
        return _empty("invalid_response")
    if len(items) > MAX_REPORT_ITEMS or len(types) > 128:
        return _empty("invalid_response")
    if any(not isinstance(item, dict) or item.get("state") != "connected" for item in items):
        return _empty("incomplete_inventory")
    if not 1 <= len(items) <= MAX_REPORT_ITEMS:
        return _empty("incomplete_inventory")
    if report.get("checked") != len(items):
        return _empty("incomplete_inventory")
    reported_total = report.get("reported_total")
    if (type(reported_total) is not int
            or reported_total < len(items) or reported_total > 10000000):
        return _empty("invalid_response")
    # The Studio summary must not present a bounded sample as a complete
    # compatible Cloud library. The CLI may examine a partial sample, but
    # this viewer endpoint is deliberately all-or-nothing.
    if reported_total != len(items):
        return _empty("incomplete_inventory")
    safe_types = []
    seen_aliases = set()
    unknown_sum = 0
    for item in types:
        if not isinstance(item, dict):
            return _empty("invalid_response")
        alias = item.get("id")
        count = item.get("occurrences")
        file_count = item.get("file_count")
        if (not isinstance(alias, str) or not _ALIAS.fullmatch(alias)
                or alias in seen_aliases
                or type(count) is not int or not 1 <= count <= 10000
                or type(file_count) is not int or not 1 <= file_count <= len(items)):
            return _empty("invalid_response")
        loc = item.get("location_counts")
        triggers = item.get("trigger_counts")
        if not isinstance(loc, dict) or not isinstance(triggers, dict):
            return _empty("invalid_response")
        if any(k not in _ALLOWED_LOCATIONS or type(v) is not int or not 0 <= v <= count
               for k, v in loc.items()):
            return _empty("invalid_response")
        if any(k not in _ALLOWED_TRIGGERS or type(v) is not int or not 0 <= v <= count
               for k, v in triggers.items()):
            return _empty("invalid_response")
        if sum(loc.values()) != count or sum(triggers.values()) != count:
            return _empty("invalid_response")
        seen_aliases.add(alias)
        unknown_sum += count
        safe_types.append({
            "alias": alias, "occurrences": count,
            "file_count": file_count,
            "locations": dict(sorted(loc.items())),
            "triggers": dict(sorted(triggers.items())),
        })
    # Optional backward-compatible extended diagnostics. Only exact local
    # allowlisted Pilot 2 enum names are ever forwarded to the browser.
    raw_identified = report.get("identified_types")
    identified = []
    aliases_identified = set()
    if raw_identified is not None:
        if not isinstance(raw_identified, list) or len(raw_identified) > len(PILOT2_OBSERVED_ACTIONS):
            return _empty("invalid_response")
        seen_names = set()
        for item in raw_identified:
            if not isinstance(item, dict):
                return _empty("invalid_response")
            name, alias = item.get("name"), item.get("alias")
            count, file_count = item.get("occurrences"), item.get("file_count")
            if (not isinstance(name, str) or name not in PILOT2_OBSERVED_ACTIONS
                    or name in seen_names or not isinstance(alias, str)
                    or alias not in seen_aliases or alias in aliases_identified
                    or type(count) is not int or not 1 <= count <= 10000
                    or type(file_count) is not int or not 1 <= file_count <= len(items)):
                return _empty("invalid_response")
            original = next((x for x in safe_types if x["alias"] == alias), None)
            if original is None or original["occurrences"] != count or original["file_count"] != file_count:
                return _empty("invalid_response")
            label, family = PILOT2_OBSERVED_ACTIONS[name]
            identified.append({"name": name, "label": label, "family": family,
                               "occurrences": count, "file_count": file_count,
                               "status": "pilot2_observed_unverified",
                               "export_supported": False})
            seen_names.add(name)
            aliases_identified.add(alias)
        identified_count = sum(x["occurrences"] for x in identified)
        if (report.get("identified_action_total") != identified_count
                or report.get("unresolved_action_total") != unknown_sum - identified_count):
            return _empty("invalid_response")
        safe_types = [x for x in safe_types if x["alias"] not in aliases_identified]
    else:
        identified_count = 0
    safe_files = []
    known_sum = 0
    total_unknown_files = 0
    for i, item in enumerate(items, start=1):
        idx = item.get("index")
        known = item.get("recognized_action_count")
        unknown = item.get("unknown_action_count")
        routes = item.get("route_count")
        version = item.get("wpml_schema_version")
        if (type(idx) is not int or idx != i
                or any(type(n) is not int or not 0 <= n <= 10000
                       for n in (known, unknown))
                or type(routes) is not int or not 1 <= routes <= 32
                or version not in ("1.0.2", "1.0.6")):
            return _empty("invalid_response")
        known_sum += known
        total_unknown_files += unknown
        safe_files.append({"index": idx, "route_count": routes,
                           "schema": version, "known_actions": known,
                           "unknown_actions": unknown})
    documented_types = []
    raw_documented = report.get("documented_type_counts")
    if raw_documented is not None:
        if (not isinstance(raw_documented, dict)
                or any(not isinstance(k, str) or k not in DOCUMENTED_ACTION_LABELS
                       or type(v) is not int or v < 0 for k, v in raw_documented.items())
                or sum(raw_documented.values()) != known_sum):
            return _empty("invalid_response")
        documented_types = [
            {"name": name, "label": label,
             "occurrences": raw_documented.get(name, 0),
             "status": "documented", "export_supported": name == "takePhoto"}
            for name, label in DOCUMENTED_ACTION_LABELS.items()
        ]
    if (unknown_sum != total_unknown_files
            or report.get("unknown_action_total") != unknown_sum
            or report.get("recognized_action_total") != known_sum):
        return _empty("invalid_response")
    if (report.get("flight_compatibility_verified") is not False
            or report.get("full_content_verified") is not False):
        return _empty("invalid_response")
    return {
        "state": "connected",
        "checked": len(items),
        "total": reported_total,
        "recognized_actions": known_sum,
        "unknown_actions": unknown_sum,
        "identified_actions": identified_count,
        "unresolved_actions": unknown_sum - identified_count,
        "identified_types": identified,
        "documented_types": documented_types,
        "anonymous_types": safe_types,
        "waylines": safe_files,
        "read_only": True,
        "wpml_semantics_verified": False,
        "flight_compatibility_verified": False,
        "full_content_verified": False,
    }


def _empty(state):
    # Do not forward arbitrary exception strings or upstream status names.
    known = {"not_configured", "awaiting_browser_session",
             "authentication_required", "configuration_error",
             "unavailable", "incomplete_inventory", "invalid_response",
             "unsupported_geometry"}
    return {
        "state": state if isinstance(state, str) and state in known else "unavailable",
        "checked": 0, "total": None,
        "recognized_actions": 0, "unknown_actions": 0,
        "identified_actions": 0, "unresolved_actions": 0,
        "identified_types": [], "documented_types": [],
        "anonymous_types": [], "waylines": [],
        "read_only": True, "wpml_semantics_verified": False,
        "flight_compatibility_verified": False,
        "full_content_verified": False,
    }


class Pilot2ActionSummaryReader:
    def __init__(self, inventory_reader, *, loader=load_credentials,
                 diagnosis=diagnose_action_vocabulary):
        self._inventory_reader = inventory_reader
        self._loader = loader
        self._diagnosis = diagnosis
        self._lock = asyncio.Lock()
        self._credentials = None
        self._cached = None
        self._until = 0

    async def read(self):
        async with self._lock:
            try:
                credentials = self._loader(credentials_path())
            except (LocalWaylineError, OSError):
                self._cached = self._credentials = None
                return _empty("configuration_error")
            if credentials is None:
                self._cached = self._credentials = None
                return _empty("not_configured")
            if (self._cached is not None and credentials == self._credentials
                    and time.monotonic() < self._until):
                return self._cached
            self._cached = None
            self._credentials = None
            try:
                report = await asyncio.wait_for(
                    self._diagnosis(
                        limit=MAX_REPORT_ITEMS,
                        inventory_reader=lambda _: self._inventory_reader.read(),
                        credentials_loader=lambda _: credentials),
                    timeout=90)
                # Protect same-workspace session rotations, including same Workspace ID.
                if self._loader(credentials_path()) != credentials:
                    return _empty("authentication_required")
                clean = summarize_action_report(report)
            except (LocalWaylineError, OSError, httpx.HTTPError,
                    TimeoutError, ValueError, TypeError, KeyError):
                return _empty("unavailable")
            if clean["state"] == "connected":
                self._credentials = credentials
                self._cached = clean
                self._until = time.monotonic() + CACHE_SECONDS
            return clean
