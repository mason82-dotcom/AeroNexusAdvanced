"""Phase 12: mobile library and honest HMS presentation.

The HTML is a static shell. Provider text must only arrive through the
LAN-restricted read-only APIs and be inserted as text, not interpreted as HTML.
"""
from html.parser import HTMLParser

from fastapi.testclient import TestClient

from aeronexus.app import app
from aeronexus.status_page import render_page


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_local_cloud_library_is_hidden_until_authenticated_fetch():
    page = render_page(5)
    parser = _Tags()
    parser.feed(page)
    panels = [attrs for tag, attrs in parser.tags
              if tag == "section" and attrs.get("id") == "catalog-panel"]
    assert len(panels) == 1 and "hidden" in panels[0]
    assert 'byId("catalog-panel").hidden=false' in page
    assert "/api/v1/local-cloud/waylines" in page
    assert "/api/v1/flighthub/catalog" not in page
    assert "FlightHub-Bibliothek" not in page


def test_local_waylines_mobile_cards_and_collapsed_technical_table():
    page = render_page(5)
    assert 'id="wayline-cards"' in page
    assert 'id="wayline-count"' in page
    assert 'id="waylines"' in page
    assert 'class="catalog-grid"' in page
    assert page.count('class="catalog-raw"') == 1
    assert 'id="model-cards"' not in page
    assert 'id="task-cards"' not in page
    assert "renderLocalWaylines(data)" in page
    assert "repeat(auto-fit,minmax(min(100%,300px),1fr))" in page


def test_local_wayline_cards_preserve_read_only_metadata_and_states():
    page = render_page(5)
    assert 'catalogTag(card,"Typ",kinds)' in page
    assert 'catalogTag(card,"Geändert",changed)' in page
    assert 'const model=modelNames[route.device_model_key]' in page
    assert "data.pagination_complete===false" in page
    assert "authentication_required" in page
    assert "awaiting_browser_session" in page
    assert 'downloadTrack(' not in page
    assert "/api/v1/flighthub/projects/" not in page


def test_local_cloud_auto_load_and_ignores_superseded_fetches():
    page = render_page(5)
    assert "epoch!==sessionEpoch||request!==catalogRequest" in page
    assert "epoch!==sessionEpoch||request!==devicesRequest" in page
    assert 'byId("catalog-panel").hidden=false' in page
    assert "updateCatalog();" in page
    assert "updateDevices();" in page
    assert 'id="token"' not in page


def test_hms_unknown_code_has_no_fabricated_diagnosis():
    page = render_page(5)
    assert 'cardEl(entry,"code","hms-code","Code: "+alert.code)' in page
    assert "DJI hat für diesen HMS-Code keinen Beschreibungstext übermittelt." in page
    assert "alert.message&&alert.message!==alert.code" in page
    assert "0x16070042" not in page  # do not encode unsupported explanation


def test_hms_severity_and_age_are_marked():
    page = render_page(5)
    assert 'entry.dataset.level=alert.level||"unknown"' in page
    assert '"Warnung"' in page and '"Hinweis"' in page
    assert 'alert.imminent===true' in page
    assert 'alert.in_the_sky===true' in page
    assert "HMS-Stand möglicherweise veraltet" in page
    assert "DJI-Ereigniszeit unbekannt" in page


def test_anonymous_page_stays_read_only_and_privacy_safe(monkeypatch):
    token = "separate-status-token-012345678901234567890"
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", token)
    with TestClient(app) as client:
        page = client.get("/status")
        assert page.status_code == 200
        assert token not in page.text
        assert 'id="catalog-panel" hidden' in page.text
        assert "innerHTML" not in page.text
        assert "localStorage" not in page.text[page.text.index("<script>"):]
        assert page.headers["cache-control"] == "no-store"
        assert client.get("/api/v1/local-cloud/waylines").status_code == 401
        assert client.post("/api/v1/flight/command").status_code == 403
