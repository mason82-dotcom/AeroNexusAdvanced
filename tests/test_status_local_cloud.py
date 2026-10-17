"""Local Pilot 2 Cloud status library: authorized, GET-only, fail-closed UI."""
import importlib
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from aeronexus.local_waylines import LocalWaylineReader
from aeronexus.status_page import render_page


app = importlib.import_module("aeronexus.app").app
TOKEN = "local-cloud-status-test-token-" + "x" * 32


@pytest.mark.parametrize("state", ["connected", "awaiting_browser_session",
                                   "authentication_required", "unavailable"])
def test_local_wayline_endpoint_enforces_viewer_access(monkeypatch, state):
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    calls = []

    async def fake_read(self):
        calls.append(True)
        if state != "connected":
            return {"state": state, "waylines": []}
        return {
            "state": "connected", "waylines": [
                {"wayline_id": "00000000-0000-0000-0000-000000000001",
                 "name": "M3M Wayline", "device_model_key": "0-77-2",
                 "template_types": ["waypoint"], "template_type_codes": [0],
                 "updated_at_ms": 1792250000123}],
            "workspace_id": "12345678-1234-4234-8234-123456789012",
            "reported_total": 1, "pagination_complete": True,
            "updated_at": "2026-10-17T20:00:00+00:00",
            "access_token": "MUST_NOT_LEAK",
        }

    monkeypatch.setattr(LocalWaylineReader, "read", fake_read)
    with TestClient(app) as client:
        assert client.get("/api/v1/local-cloud/waylines").status_code == 401
        assert calls == []
        response = client.get("/api/v1/local-cloud/waylines",
                              headers={"Authorization": "Bearer " + TOKEN})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert len(calls) == 1
        data = response.json()
        assert data["state"] == state
        assert len(data["waylines"]) == (1 if state == "connected" else 0)
        assert "MUST_NOT_LEAK" not in response.text
        assert "access_token" not in response.text
        assert "workspace_id" not in response.text


def test_status_shows_local_mqtt_and_not_flight_hub():
    page = render_page(15)
    assert "Lokale Pilot-2-Missionsbibliothek" in page
    assert "/api/v1/local-cloud/waylines" in page
    assert "/api/v1/cloud/stack" in page
    assert "Letzte gültige Nachricht" in page
    assert "FlightHub" not in page
    assert "innerHTML" not in page


_NODE = r"""
const fs=require('node:fs');
const assert=require('node:assert/strict');
let script=fs.readFileSync(0,'utf8');
script=script.slice(0,script.indexOf('// All dashboard sections load automatically'));
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.textContent='';this.className='';this.hidden=false}
  appendChild(x){this.children.push(x);return x}
  replaceChildren(...xs){this.children=xs}
  querySelector(s){return s==='.catalog-tags'?this.children.find(x=>x.className==='catalog-tags'):null}
}
const cache=new Map();
const document={
  createElement(tag){return new Element(tag)},
  getElementById(id){if(!cache.has(id))cache.set(id,new Element(id));return cache.get(id)}
};
const api=new Function('document',script+'\nreturn {renderLocalWaylines};')(document);
const value=id=>document.getElementById(id);
const malicious='<img src=x onerror=alert(1)>';
api.renderLocalWaylines({state:'connected',
  reported_total:1,pagination_complete:true,updated_at:'2026-10-17T20:00:00Z',
  waylines:[{name:malicious,device_model_key:'0-77-2',
    template_types:['waypoint'],template_type_codes:[0],updated_at_ms:1792250000123}]});
assert.equal(value('wayline-count').textContent,1);
assert.equal(value('wayline-cards').children[0].children[0].textContent,malicious);
assert.equal(value('waylines').children.length,1);
assert.equal(value('waylines').children[0].children[0].textContent,malicious);
assert.ok(value('catalog-info').textContent.includes('verbunden'));
api.renderLocalWaylines({state:'authentication_required',waylines:[]});
assert.equal(value('wayline-count').textContent,'–');
assert.equal(value('waylines').children.length,0);
assert.ok(value('catalog-info').textContent.includes('abgelaufen'));
assert.ok(value('wayline-cards').children[0].textContent.includes('Keine aktuellen Routen'));
"""


def test_real_browser_js_local_cloud_route_cards_are_text_only():
    if shutil.which("node") is None:
        pytest.skip("Node.js required")
    script, = re.findall(r"<script>(.*?)</script>", render_page(15), re.DOTALL)
    result = subprocess.run(["node", "-e", _NODE], input=script,
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
