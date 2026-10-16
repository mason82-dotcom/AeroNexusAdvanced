"""Regression checks for the read-only, mobile-first FlightHub dashboard.

The page is a static shell: confidential telemetry comes from the separately guarded local device API,
never embedded in the static HTML or anonymous summary.
"""
from fastapi.testclient import TestClient

from aeronexus.app import app
from aeronexus.status_page import render_page


def test_card_layout_and_technical_table_are_present():
    page = render_page(5)
    assert 'id="device-cards"' in page
    assert 'class="device-grid"' in page
    assert 'class="raw-table"' in page
    assert 'id="devices"' in page
    assert 'id="poll-health"' in page
    assert "renderDeviceCards(data.devices)" in page
    assert "5000" in page


def test_telemetry_fields_and_freshness_are_labeled():
    page = render_page(15)
    for label in (
        "Akku (letzter Messwert)", "Höhe über Start", "Absolute Höhe",
        "Horizontale Geschwindigkeit", "Vertikale Geschwindigkeit",
        "GPS-Satelliten", "RTK-Satelliten", "RTK-Status",
        "Akkutemperatur", "Akkuspannung", "Flugmodus",
        "Position (GPS)", "Empfangsalter unbekannt",
        "Online-Zustand nicht aktuell", "Letzter erfolgreicher Abruf",
        "zuletzt gemeldete Meldung(en)",
    ):
        assert label in page


def test_device_content_is_inserted_as_text_not_html():
    page = render_page(30)
    assert "el.textContent=String(text)" in page
    assert 'pre.textContent=JSON.stringify(device.telemetry,null,2)' in page
    assert "innerHTML" not in page
    assert "localStorage" not in page[page.index("<script>"):]


def test_no_token_form_and_automatic_protected_api_refresh():
    page = render_page(30)
    assert 'id="token"' not in page
    assert 'id="connect"' not in page
    assert 'id="disconnect"' not in page
    assert "Authorization" not in page
    assert "Bearer " not in page
    assert "updateDevices();" in page
    assert "updateCatalog();" in page
    assert "epoch!==sessionEpoch||request!==devicesRequest" in page
    assert "epoch!==sessionEpoch||request!==catalogRequest" in page
    assert 'byId("device-cards").replaceChildren();' in page


def test_public_page_never_embeds_runtime_identifiers_or_tokens(monkeypatch):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", "A" * 40)
    with TestClient(app) as client:
        response = client.get("/status")
        assert response.status_code == 200
        assert "A" * 40 not in response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-frame-options"] == "DENY"
        assert "connect-src 'self'" in response.headers["content-security-policy"]
        assert client.post("/api/v1/flight/command").status_code == 403
