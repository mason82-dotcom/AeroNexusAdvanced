"""Pilot 2 KMZ preview: safe redirect handling, bounded XML/ZIP, read-only HTTP."""
import asyncio
from io import BytesIO
import json
from uuid import UUID
from zipfile import ZipFile, ZIP_DEFLATED

import httpx
import pytest
from fastapi.testclient import TestClient

from aeronexus import pilot2_wayline_preview as pv
from aeronexus import local_waylines as lw
import importlib

webapp = importlib.import_module("aeronexus.app")

WORKSPACE = "12345678-1234-4234-8234-123456789012"
WAYLINE = str(UUID(int=15))
CREDS = lw.Credentials(WORKSPACE, "preview-only-test-token-123456789")
SIGNED_URL = "http://192.168.178.63:9000/dji-cloud/wayline/demo.kmz?X-Amz-Signature=secret"


def kmz(*, route=True, xml=None):
    payload = xml or (
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Folder>'
        '<Placemark><Point><coordinates>8.58,49.15,30</coordinates></Point></Placemark>'
        '<Placemark><Point><coordinates>8.59,49.16,30</coordinates></Point></Placemark>'
        '</Folder></Document></kml>'
    )
    body = BytesIO()
    with ZipFile(body, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("wpmz/waylines.wpml" if route else "wpmz/template.kml", payload)
    return body.getvalue()


def read_mock(handler):
    return asyncio.run(pv.read_preview(CREDS, WAYLINE, transport=httpx.MockTransport(handler)))


def test_signed_minio_download_uses_loopback_but_preserves_signed_host(monkeypatch):
    monkeypatch.setenv("AERONEXUS_MINIO_BUCKET", "dji-cloud")
    seen = []
    def handler(request):
        seen.append((request.method, request.url.host, request.headers.get("host")))
        assert request.method == "GET"
        if len(seen) == 1:
            assert request.url.path.endswith("/" + WAYLINE + "/url")
            assert request.headers["x-auth-token"] == CREDS.access_token
            return httpx.Response(302, headers={"Location": SIGNED_URL})
        assert request.url.host == "127.0.0.1"
        assert request.url.port == 9000
        assert request.headers["Host"] == "192.168.178.63:9000"
        assert "x-auth-token" not in request.headers
        return httpx.Response(200, content=kmz())
    data = read_mock(handler)
    assert [item[0] for item in seen] == ["GET", "GET"]
    assert data["source"] == "waylines.wpml"
    assert data["point_count"] == 2
    assert data["features"] == [
        {"geometry": {"type": "LineString", "coordinates": [[8.58, 49.15], [8.59, 49.16]]}}]
    assert "secret" not in json.dumps(data)


@pytest.mark.parametrize("location", [
    "http://evil.example:9000/dji-cloud/a.kmz?sig=1",
    "http://8.8.8.8:9000/dji-cloud/a.kmz?sig=1",
    "http://127.0.0.1:9999/dji-cloud/a.kmz?sig=1",
    "https://127.0.0.1:9000/dji-cloud/a.kmz?sig=1",
    "http://127.0.0.1:9000/other-bucket/a.kmz?sig=1",
    "http://127.0.0.1:9000/dji-cloud/../other/a.kmz?sig=1",
    "http://127.0.0.1:9000/dji-cloud/a.kmz",
    "http://user:pass@127.0.0.1:9000/dji-cloud/a.kmz?sig=1",
    "http://127.0.0.1:9000/dji-cloud/a.kmz?sig=1#fragment",
])
def test_untrusted_storage_redirect_is_rejected_without_second_request(location, monkeypatch):
    monkeypatch.setenv("AERONEXUS_MINIO_BUCKET", "dji-cloud")
    seen = []
    def handler(request):
        seen.append(request.url)
        return httpx.Response(302, headers={"Location": location})
    with pytest.raises(lw.LocalWaylineError, match="^storage_origin_rejected$"):
        read_mock(handler)
    assert len(seen) == 1


def test_signed_link_redirect_chain_not_followed():
    seen = []
    def handler(request):
        seen.append(request.url)
        return httpx.Response(302, headers={"Location": SIGNED_URL})
    with pytest.raises(lw.LocalWaylineError, match="^storage_unavailable$"):
        read_mock(handler)
    assert len(seen) == 2


def test_kmz_damaged_decompression_and_doctype_refused():
    with pytest.raises(lw.LocalWaylineError, match="^invalid_archive$"):
        pv.parse_preview_kmz(b"bad zip")
    with pytest.raises(lw.LocalWaylineError, match="^invalid_archive$"):
        pv.parse_preview_kmz(kmz(xml="<!DOCTYPE kml><kml></kml>"))
    with pytest.raises(lw.LocalWaylineError, match="^invalid_archive$"):
        pv.parse_preview_kmz(kmz(xml="<kml><broken"))


def test_kmz_unsupported_actions_are_not_exposed():
    payload = ('<kml><Document><Folder><Placemark><Point><coordinates>8.6,49.1</coordinates>'
               '</Point><actionGroup><actionActuatorFunc>takePhoto</actionActuatorFunc>'
               '</actionGroup></Placemark></Folder></Document></kml>')
    response = pv.parse_preview_kmz(kmz(xml=payload))
    assert response["features"] == [
        {"geometry": {"type": "Point", "coordinates": [8.6, 49.1]}}]
    assert "takePhoto" not in json.dumps(response)


def test_template_polygon_preview_fallback():
    source = ("<kml><Document><Folder><Placemark><Polygon><outerBoundaryIs>"
              "<LinearRing><coordinates>8,49 8.1,49 8.1,49.1 8,49</coordinates>"
              "</LinearRing></outerBoundaryIs></Polygon></Placemark></Folder></Document></kml>")
    result = pv.parse_preview_kmz(kmz(route=False, xml=source))
    assert result["source"] == "template.kml"
    assert result["features"][0]["geometry"]["type"] == "Polygon"


def test_api_requires_viewer_and_known_full_inventory(monkeypatch):
    token = "test-wayline-preview-viewer-token-123456789"
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", token)
    seen = []
    async def inventory(self):
        return {"state": "connected", "workspace_id": WORKSPACE,
                "pagination_complete": True,
                "waylines": [{"wayline_id": WAYLINE, "name": "Testkarte"}]}
    async def preview(credentials, ident):
        seen.append(ident)
        return {"features": [{"geometry": {"type": "Point", "coordinates": [8, 49]}}],
                "source": "waylines.wpml", "point_count": 1}
    monkeypatch.setattr(lw.LocalWaylineReader, "read", inventory)
    monkeypatch.setattr(webapp, "load_credentials", lambda _: CREDS)
    monkeypatch.setattr(webapp, "read_preview", preview)
    with TestClient(webapp.app) as client:
        base = "/api/v1/local-cloud/waylines/"
        assert client.get(base + WAYLINE + "/preview").status_code == 401
        assert client.get(base + str(UUID(int=17)) + "/preview",
                          headers={"Authorization": "Bearer " + token}).status_code == 404
        assert seen == []
        r = client.get(base + WAYLINE + "/preview",
                       headers={"Authorization": "Bearer " + token})
        assert r.status_code == 200 and r.json()["state"] == "connected"
        assert r.headers["Cache-Control"] == "no-store"
        assert r.json()["name"] == "Testkarte"
        assert seen == [WAYLINE]


def test_api_loads_known_route_in_partial_inventory_and_rejects_unknown(monkeypatch):
    async def partial(self):
        return {"state": "connected", "workspace_id": WORKSPACE,
                "pagination_complete": False,
                "waylines": [{"wayline_id": WAYLINE, "name": "Partial"}]}
    monkeypatch.setattr(lw.LocalWaylineReader, "read", partial)
    token = "test-wayline-preview-viewer-token-123456789"
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", token)
    monkeypatch.setattr(webapp, "load_credentials", lambda _: CREDS)
    seen = []
    async def preview(credentials, ident):
        seen.append(ident)
        return {"features": [{"geometry": {"type": "Point", "coordinates": [8, 49]}}],
                "source": "waylines.wpml", "point_count": 1}
    monkeypatch.setattr(webapp, "read_preview", preview)
    with TestClient(webapp.app) as client:
        r = client.get("/api/v1/local-cloud/waylines/" + WAYLINE + "/preview",
                       headers={"Authorization": "Bearer " + token})
        assert r.status_code == 200
        assert r.json()["state"] == "connected"
        assert seen == [WAYLINE]
        r = client.get("/api/v1/local-cloud/waylines/" + str(UUID(int=17)) + "/preview",
                       headers={"Authorization": "Bearer " + token})
        assert r.status_code == 404
        assert seen == [WAYLINE]


def test_studio_preview_never_mutates_local_mission():
    from aeronexus.studio_page import render_studio
    page = render_studio()
    assert 'id="wayline-preview-clear"' in page
    assert 'async function previewCloudWayline(route,button)' in page
    section = page[page.index("function clearCloudWaylinePreview()"):page.index("function waylineSourceState(")]
    assert 'api("/api/v1/local-cloud/waylines/"' in section
    assert 'interactive:false' in section
    assert "saveMission" not in section
    assert "mission.waypoints" not in section
    assert "innerHTML" not in section
    assert '(waylinePreviewLayer&&map.hasLayer(waylinePreviewLayer))' in page
    assert '(cloudOverviewLayer&&map.hasLayer(cloudOverviewLayer))' in page
    assert 'waylinePreviewLayer=L.layerGroup()' in page
    assert 'id="wayline-preview-fit"' in page
    assert 'function centerCloudWaylinePreview()' in page
    assert 'fitWaylineMapBounds(merged,()=>request===waylinePreviewRequest' in page
    assert 'map.invalidateSize({pan:false})' in page



def test_archive_declared_and_actual_decompression_are_bounded():
    content = BytesIO()
    with ZipFile(content, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("wpmz/waylines.wpml", b"x" * (pv.MAX_MEMBER + 1))
    with pytest.raises(lw.LocalWaylineError, match="^invalid_archive$"):
        pv.parse_preview_kmz(content.getvalue())


def test_cli_probe_success_is_sanitized(monkeypatch, capsys):
    monkeypatch.setattr(pv, "load_credentials", lambda _: CREDS)
    async def inventory(credentials):
        assert credentials == CREDS
        return {"waylines": [{"wayline_id": WAYLINE, "name": "Private wayline"}],
                "reported_total": 1, "pagination_complete": True}
    async def preview(credentials, route):
        assert route == WAYLINE
        return {"features": [{"geometry": {"type": "Point",
                                          "coordinates": [8.6, 49.1]}}],
                "source": "waylines.wpml", "point_count": 1}
    result = asyncio.run(pv.diagnose_previews(
        1, preview_reader=preview, inventory_reader=inventory))
    assert result == {"inventory_state": "connected", "reported_total": 1,
                      "pagination_complete": True,
                      "results": [{"index": 1, "state": "connected",
                                   "feature_count": 1, "point_count": 1,
                                   "source": "waylines.wpml"}]}
    assert CREDS.access_token not in json.dumps(result)
    assert WAYLINE not in json.dumps(result)
    assert "Private wayline" not in json.dumps(result)


def test_cli_probe_errors_are_coded_without_sensitive_strings(monkeypatch):
    monkeypatch.setattr(pv, "load_credentials", lambda _: CREDS)
    async def inventory(_):
        return {"waylines": [{"wayline_id": WAYLINE, "name": "private route"}],
                "reported_total": 1, "pagination_complete": True}
    async def failed(_, __):
        raise lw.LocalWaylineError("storage_origin_rejected")
    result = asyncio.run(pv.diagnose_previews(
        1, preview_reader=failed, inventory_reader=inventory))
    assert result["results"] == [{"index": 1, "state": "storage_origin_rejected"}]
    assert WAYLINE not in json.dumps(result)


def test_cli_probe_refuses_incomplete_inventory_and_missing_credentials(monkeypatch):
    monkeypatch.setattr(pv, "load_credentials", lambda _: CREDS)
    async def inventory(_):
        return {"waylines": [{"wayline_id": WAYLINE}],
                "reported_total": 9, "pagination_complete": False}
    assert asyncio.run(pv.diagnose_previews(
        inventory_reader=inventory)) == {"inventory_state": "incomplete_inventory",
                                         "results": []}
    monkeypatch.setattr(pv, "load_credentials", lambda _: None)
    assert asyncio.run(pv.diagnose_previews()) == {
        "inventory_state": "not_configured", "results": []}
    for bad in (0, 9, True, "2"):
        with pytest.raises(ValueError):
            asyncio.run(pv.diagnose_previews(bad))
