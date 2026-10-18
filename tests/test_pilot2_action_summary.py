"""Read-only Studio Pilot 2 action summary: authentication, cache and privacy."""
import asyncio
import importlib
import json

from fastapi.testclient import TestClient
import pytest

from aeronexus.local_waylines import Credentials, LocalWaylineError
from aeronexus.pilot2_action_summary import (
    Pilot2ActionSummaryReader, summarize_action_report,
    CACHE_SECONDS,
)
from aeronexus.studio_page import render_studio

appmod = importlib.import_module("aeronexus.app")
WORKSPACE = "12345678-1234-4234-8234-123456789012"
TOKEN = "studio-pilot2-test-bearer-token-adequate-size-12345"
FIRST = Credentials(WORKSPACE, "pilot2-local-secret-token-this-is-not-the-bearer")
SECOND = Credentials(WORKSPACE, "changed-pilot2-local-session-this-is-not-the-bearer")


def fixture_report():
    return {
        "inventory_state": "connected",
        "reported_total": 2,
        "checked": 2,
        "results": [
            {"index": 1, "state": "connected", "route_count": 2,
             "wpml_schema_version": "1.0.6", "recognized_action_count": 4,
             "unknown_action_count": 3, "wayline_id": "PRIVATE-CLOUD-UUID"},
            {"index": 2, "state": "connected", "route_count": 1,
             "wpml_schema_version": "1.0.6", "recognized_action_count": 5,
             "unknown_action_count": 2, "name": "PRIVATE-CLOUD-MISSION"},
        ],
        "anonymous_types": [
            {"id": "A01", "occurrences": 3, "file_count": 2,
             "location_counts": {"start": 1, "waypoint": 2},
             "trigger_counts": {"start": 1, "reachPoint": 2},
             "sensitive_upstream": "NEVER-RETURN-THIS-SECRET"},
            {"id": "A02", "occurrences": 2, "file_count": 1,
             "location_counts": {"waypoint": 2},
             "trigger_counts": {"betweenAdjacentPoints": 2}},
        ],
        "unknown_action_total": 5,
        "recognized_action_total": 9,
        "full_content_verified": False,
        "flight_compatibility_verified": False,
        "workspace_id": WORKSPACE,
        "signed_url": "https://private.invalid/?token=PRIVATE",
    }


def test_summary_strict_allowlist_drops_raw_data_and_marks_nonflight():
    result = summarize_action_report(fixture_report())
    assert result["state"] == "connected"
    assert result["recognized_actions"] == 9
    assert result["unknown_actions"] == 5
    assert result["waylines"][0]["route_count"] == 2
    assert result["anonymous_types"][0]["alias"] == "A01"
    assert result["flight_compatibility_verified"] is False
    assert result["wpml_semantics_verified"] is False
    assert result["read_only"] is True
    encoded = json.dumps(result)
    for secret in ("PRIVATE-CLOUD-UUID", "PRIVATE-CLOUD-MISSION",
                   "NEVER-RETURN-THIS-SECRET", WORKSPACE,
                   "https://private.invalid"):
        assert secret not in encoded
    assert "actionGroupStartIndex" not in encoded
    assert "coordinates" not in encoded


@pytest.mark.parametrize("mutation", [
    lambda x: x["anonymous_types"][0].update(id="privateScript"),
    lambda x: x["anonymous_types"][0].update(occurrences=True),
    lambda x: x["anonymous_types"][0]["trigger_counts"].update({"private-value": 2}),
    lambda x: x["results"][1].update(index=7),
    lambda x: x["results"][0].update(state="unavailable"),
    lambda x: x.update(flight_compatibility_verified=True),
    lambda x: x.update(unknown_action_total=999),
])
def test_summary_fails_closed_on_invalid_payload(mutation):
    report = fixture_report()
    mutation(report)
    assert summarize_action_report(report)["state"] in (
        "invalid_response", "incomplete_inventory")


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(reported_total=None),
    lambda x: x.update(reported_total=1),
    lambda x: x.update(reported_total=-1),
    lambda x: x.update(reported_total=True),
    lambda x: x.update(reported_total=10000001),
    lambda x: x["anonymous_types"][1].update(id="A01"),
    lambda x: x.update(full_content_verified=True),
    lambda x: x.update(full_content_verified=None),
])
def test_summary_rejects_invalid_total_duplicate_alias_and_verification(mutation):
    value = fixture_report()
    mutation(value)
    assert summarize_action_report(value)["state"] == "invalid_response"


def test_viewer_summary_rejects_partial_library_even_when_bounded_cli_succeeded():
    report = fixture_report()
    report["reported_total"] = 8
    result = summarize_action_report(report)
    assert result["state"] == "incomplete_inventory"
    assert result["checked"] == 0
    assert result["flight_compatibility_verified"] is False


def test_summary_rejects_non_object_and_unhashable_state():
    assert summarize_action_report([])["state"] == "invalid_response"
    assert summarize_action_report({"inventory_state": []})["state"] == "unavailable"
    assert summarize_action_report({"inventory_state": {"secret": "value"}})["state"] == "unavailable"


def test_reader_parallel_requests_use_single_scan():
    calls = []
    async def diagnosis(**_):
        calls.append(True)
        await asyncio.sleep(0.01)
        return fixture_report()
    async def run():
        reader = Pilot2ActionSummaryReader(
            FakeInventory(), loader=lambda _: FIRST, diagnosis=diagnosis)
        return await asyncio.gather(reader.read(), reader.read(), reader.read())
    result = asyncio.run(run())
    assert len(calls) == 1
    assert all(x["state"] == "connected" for x in result)


def test_reader_expired_cache_triggers_new_scan():
    calls = []
    async def diagnosis(**_):
        calls.append(True)
        return fixture_report()
    async def run():
        reader = Pilot2ActionSummaryReader(
            FakeInventory(), loader=lambda _: FIRST, diagnosis=diagnosis)
        first = await reader.read()
        reader._until = 0
        second = await reader.read()
        return first, second
    first, second = asyncio.run(run())
    assert first == second and len(calls) == 2


class FakeInventory:
    async def read(self):
        return {"state": "connected", "workspace_id": WORKSPACE,
                "pagination_complete": True, "reported_total": 2,
                "waylines": []}


def test_reader_session_bound_cache_and_credential_rotation():
    calls = []
    current = [FIRST]
    async def diagnosis(**kwargs):
        calls.append(kwargs)
        return fixture_report()
    reader = Pilot2ActionSummaryReader(
        FakeInventory(), loader=lambda _: current[0], diagnosis=diagnosis)
    a = asyncio.run(reader.read())
    assert a["state"] == "connected"
    assert asyncio.run(reader.read()) == a
    assert len(calls) == 1
    assert calls[0]["limit"] == 8
    assert callable(calls[0]["inventory_reader"])
    current[0] = SECOND
    result = asyncio.run(reader.read())
    assert result == a
    assert len(calls) == 2
    current[0] = None
    assert asyncio.run(reader.read())["state"] == "not_configured"
    assert reader._cached is None


def test_reader_error_has_no_upstream_details():
    async def diagnosis(**_):
        raise LocalWaylineError("super-secret-private-upstream")
    reader = Pilot2ActionSummaryReader(
        FakeInventory(), loader=lambda _: FIRST, diagnosis=diagnosis)
    result = asyncio.run(reader.read())
    assert result["state"] == "unavailable"
    assert "super-secret" not in json.dumps(result)


def test_reader_session_changing_during_get_fails_closed():
    calls = [FIRST, SECOND]
    async def diagnosis(**_):
        return fixture_report()
    reader = Pilot2ActionSummaryReader(
        FakeInventory(), loader=lambda _: calls.pop(0), diagnosis=diagnosis)
    result = asyncio.run(reader.read())
    assert result["state"] == "authentication_required"
    assert reader._cached is None


def test_studio_action_summary_requires_authorization_and_no_cache(monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    monkeypatch.setattr(appmod, "lan_mode_enabled", lambda: False)
    hits = []
    class Reader:
        async def read(self):
            hits.append(True)
            return summarize_action_report(fixture_report())
    with TestClient(appmod.app) as client:
        appmod.app.state.pilot2_action_summary = Reader()
        uri = "/api/v1/studio/pilot2/action-summary"
        unauth = client.get(uri)
        assert unauth.status_code == 401
        assert hits == []
        authenticated = client.get(uri, headers={"Authorization": "Bearer " + TOKEN})
        assert authenticated.status_code == 200
        assert authenticated.headers["cache-control"] == "no-store"
        data = authenticated.json()
        assert data["read_only"] and data["flight_compatibility_verified"] is False
        assert data["unknown_actions"] == 5
        assert len(hits) == 1
        assert "PRIVATE-CLOUD-UUID" not in authenticated.text


def test_studio_ui_is_opt_in_get_only_and_uses_text_content():
    page = render_studio()
    assert 'id="pilot2-action-load"' in page
    assert 'id="pilot2-action-status"' in page
    assert 'id="pilot2-action-results"' in page
    assert '"/api/v1/studio/pilot2/action-summary"' in page
    block = page[page.index("async function loadPilot2ActionSummary()"):page.index("function waylineSourceState(")]
    assert 'await api("/api/v1/studio/pilot2/action-summary"' in block
    assert ".replaceChildren()" in block
    assert "cardText(" in block
    assert 'method:"POST"' not in block
    assert "innerHTML" not in block
    assert "Flugkompatibilität nicht bestätigt" in block
    assert "serial!==pilot2ActionRequest||controller.signal.aborted" in block
    assert "data.read_only!==true" in block
    assert "innerHTML" not in block
    assert 'if(id!=="waylines-pane")clearPilot2ActionSummary();' in page
    clear = page[page.index("function clearPilot2ActionSummary()"):page.index("async function loadPilot2ActionSummary()")]
    assert "pilot2ActionController?.abort()" in clear
    assert '("pilot2-action-results").replaceChildren()' in clear




def test_summary_presents_only_fixed_observed_names_without_export_permission():
    report = fixture_report()
    report["identified_types"] = [{
        "name": "startSmartOblique", "alias": "A02",
        "occurrences": 2, "file_count": 1,
    }]
    report["identified_action_total"] = 2
    report["unresolved_action_total"] = 3
    clean = summarize_action_report(report)
    assert clean["state"] == "connected"
    assert clean["recognized_actions"] == 9
    assert clean["unknown_actions"] == 5  # deprecated non-documented count
    assert clean["identified_actions"] == 2
    assert clean["unresolved_actions"] == 3
    assert clean["anonymous_types"] == [{
        "alias": "A01", "occurrences": 3, "file_count": 2,
        "locations": {"start": 1, "waypoint": 2},
        "triggers": {"reachPoint": 2, "start": 1},
    }]
    assert clean["identified_types"] == [{
        "name": "startSmartOblique", "label": "Smart Oblique starten",
        "family": "smart_oblique", "occurrences": 2, "file_count": 1,
        "status": "pilot2_observed_unverified",
        "export_supported": False,
    }]
    assert clean["flight_compatibility_verified"] is False


@pytest.mark.parametrize("mutation", [
    lambda p: p["identified_types"][0].update(name="secretInjectedActuator"),
    lambda p: p["identified_types"][0].update(name="<script>alert(1)</script>"),
    lambda p: p["identified_types"][0].update(occurrences=3),
    lambda p: p["identified_types"][0].update(alias="A99"),
    lambda p: p.update(unresolved_action_total=2),
    lambda p: p.update(identified_action_total=True),
])
def test_summary_rejects_invalid_observed_dji_mapping(mutation):
    report = fixture_report()
    report["identified_types"] = [{
        "name": "startSmartOblique", "alias": "A02",
        "occurrences": 2, "file_count": 1,
    }]
    report["identified_action_total"] = 2
    report["unresolved_action_total"] = 3
    mutation(report)
    assert summarize_action_report(report)["state"] == "invalid_response"



def test_documented_catalog_counts_are_allowlisted_and_complete():
    report = fixture_report()
    report["documented_type_counts"] = {"takePhoto": 7, "startRecord": 2}
    clean = summarize_action_report(report)
    assert clean["state"] == "connected"
    assert len(clean["documented_types"]) == 14
    assert sum(x["occurrences"] for x in clean["documented_types"]) == 9
    assert {x["name"] for x in clean["documented_types"] if x["export_supported"]} == {
        "takePhoto", "startRecord", "stopRecord", "focus", "zoom",
        "gimbalRotate", "gimbalEvenlyRotate",
    }
    for entry in clean["documented_types"]:
        assert entry["status"] == "documented"
    report["documented_type_counts"] = {"totallyPrivateAction": 9}
    assert summarize_action_report(report)["state"] == "invalid_response"
    report["documented_type_counts"] = {"takePhoto": 10}
    assert summarize_action_report(report)["state"] == "invalid_response"
