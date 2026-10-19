"""FlightHub 2 native component tokens must never be entered on HTTP."""
from fastapi.testclient import TestClient

from aeronexus.app import app


def test_http_native_components_denied():
    client = TestClient(app, base_url="http://testserver")
    response = client.get("/fh2-components")
    assert response.status_code == 403
    assert "HTTPS required" in response.text


def test_https_native_component_shell_is_uninitialized_and_nocache():
    client = TestClient(app, base_url="https://testserver")
    response = client.get("/fh2-components")
    assert response.status_code == 200
    assert "window.FH2.initConfig" in response.text
    assert 'id="consent" type="checkbox" required' in response.text
    assert "script.src=new URL(\"/paas.js\",host).href" in response.text
    assert "HTTPS erforderlich" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "DJI_APP_KEY" not in response.text
