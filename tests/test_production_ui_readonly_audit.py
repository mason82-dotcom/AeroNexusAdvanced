"""Unit checks for production read-only HTTPS UI/API audit. Zero external calls."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pi/production_ui_readonly_audit.py"
spec = importlib.util.spec_from_file_location("readonly_ui_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def test_all_reviewed_endpoints_are_readonly_and_known():
    paths = [p for p, _ in audit.HTML_CHECKS] + [p for p, _, _ in audit.API_CHECKS]
    assert len(paths) == len(set(paths))
    assert all(x.startswith(("/health", "/studio", "/status", "/operations",
                              "/media", "/thermal", "/multispectral", "/results",
                              "/api/v1/")) for x in paths)
    assert not any("/command" in x or "/scan" in x or "/session" in x for x in paths)
    assert all(not x.endswith("/export.kmz") for x in paths)


def test_get_only_and_tls_ca_pinning_are_required():
    import inspect
    code = inspect.getsource(audit.ReadOnlyClient)
    assert 'method="GET"' in code
    assert "ssl.create_default_context" in code
    assert "ProxyHandler({})" in code
    assert "RejectRedirect()" in code
    assert '"/api/v1/studio/dji-media/{media_id}/file"' in code
    assert "max_bytes + 1" in code


def test_html_health_and_studio():
    out = audit.classify_html("health", 200, "application/json", b'{"status":"ok"}', False)
    assert out.state == "PASS"
    assert audit.classify_html("studio", 200, "text/html",
                               b'<html>' + b'X'*300 + b'id="point-action-add"',
                               False).state == "PASS"
    assert audit.classify_html("studio", 200, "text/html", b"missing", False).state == "FAIL"
    assert audit.classify_html("results", 403, "", b"", False).state == "FAIL"


def test_core_api_invalid_json_and_optional_skips():
    assert audit.classify_api("status_devices", 200, "application/json",
                              b'{"total":2,"devices":[]}', False, optional=False)[0].state == "PASS"
    assert audit.classify_api("status_devices", 200, "application/json",
                              b'{"total":2}', False, optional=False)[0].state == "FAIL"
    assert audit.classify_api("dji_media", 503, "", b"", False, optional=True)[0].state == "SKIP"
    assert audit.classify_api("studio_missions", 503, "", b"", False, optional=False)[0].state == "FAIL"
    assert audit.classify_api("raster_results", 200, "application/json",
                              b'{"items":[],"total":0}', True, optional=True)[0].state == "SKIP"


def test_preview_accepts_only_bounded_opaque_readable_images():
    id_ = "a"*64
    item = {"id": id_, "mime": "image/jpeg", "size_bytes": 240,
            "previewable": True}
    assert audit.choose_preview({"media": [item]}) == id_
    assert audit.choose_preview({"media": [{**item, "size_bytes": 8_000_000}]}) == id_
    assert audit.API_CHECKS[[x[1] for x in audit.API_CHECKS].index("photo_map")][0] == (
        "/api/v1/photos/map?limit=10"
    )
    assert len(audit.PREVIEW_SEARCH_PATHS) == 4
    assert all(path.startswith("/api/v1/studio/dji-media?q=.") for path in audit.PREVIEW_SEARCH_PATHS)
    for new in ({"id": "../file"}, {"size_bytes": 40_000_000},
                {"mime": "video/mp4"}, {"previewable": False}):
        assert audit.choose_preview({"media": [{**item, **new}]}) is None
    class FakeClient:
        def preview(self, item_id):
            assert item_id == id_
            return 200, "image/jpeg", b"\xff\xd8\xff", True
    assert audit.check_preview(FakeClient(), {"media": [item]}).state == "PASS"


def test_audit_does_not_allow_arbitrary_media_or_external_urls():
    import inspect
    source = inspect.getsource(audit.run)
    assert "POST" not in source
    assert "print(" not in source
    assert "media_id" in inspect.getsource(audit.ReadOnlyClient.preview)
    with pytest.raises(ValueError, match="redirect"):
        audit.RejectRedirect().redirect_request(None, None, 302,
                                                 "moved", {}, "https://example.com")
