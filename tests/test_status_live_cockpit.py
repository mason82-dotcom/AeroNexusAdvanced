"""Read-only DJI cockpit frontend contract and real embedded JS behavior."""
from __future__ import annotations

import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from aeronexus.app import app
from aeronexus.status_page import render_page


def test_status_is_live_cockpit_with_complete_modules():
    page = render_page(30)
    for label in (
        'id="cockpit"', 'id="cockpit-device"', 'id="cockpit-refresh"',
        'id="cockpit-live"', 'id="cockpit-track"', 'id="cockpit-trends"',
        'id="cockpit-fields"', 'id="cockpit-field-focus"', 'id="cockpit-camera"', 'id="cockpit-radio"',
        'id="cockpit-payload"', 'id="cockpit-safety"', 'id="cockpit-energy"',
        'id="cockpit-hms"', 'id="legacy-status"',
    ):
        assert label in page
    assert "Math.min(intervalMs,5000)" in page
    assert "renderCockpit(data.devices);" in page
    assert "cockpitUnavailable" in page
    assert 'id="catalog-panel" hidden' in page
    assert "Flugbefehle deaktiviert" in page


def test_cockpit_only_uses_protected_read_endpoints_and_text_content():
    page = render_page(30)
    assert "/api/v1/status/devices" in page
    assert "/api/v1/local-cloud/waylines" in page
    assert "innerHTML" not in page
    assert "localStorage" not in page
    assert "sessionStorage" not in page
    assert "createElementNS" in page
    assert "openstreetmap" not in page.lower()
    assert 'headers:{"Authorization"' not in page
    assert "Bearer " not in page
    with TestClient(app) as client:
        response = client.get("/status")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert "connect-src 'self'" in response.headers["content-security-policy"]
        assert client.post("/api/v1/flight/command").status_code == 403


_RUNTIME = r"""
const fs=require("node:fs"), assert=require("node:assert/strict");
const src=fs.readFileSync(0,"utf8");
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.textContent="";this.className="";
    this.value="";this.dataset={};this.hidden=false;this.style={};this.attributes={};}
  appendChild(child){this.children.push(child);return child;}
  replaceChildren(...children){this.children=children;}
  setAttribute(key,val){this.attributes[key]=val;}
  querySelector(key){if(key===".catalog-tags")
    return this.children.find(x=>x.className==="catalog-tags")||null;return null;}
}
const elements=new Map();
const document={
  hidden:false,
  getElementById(id){if(!elements.has(id))elements.set(id,new Element(id));
    return elements.get(id);},
  createElement(tag){return new Element(tag);},
  createElementNS(ns,tag){const element=new Element(tag);
    element.namespaceURI=ns;return element;}
};
const fetch=()=>new Promise(()=>{});
const setInterval=()=>0;
const api=new Function("document","fetch","setInterval",src+
  "\nreturn {renderCockpit,cockpitUnavailable,cockpitValidGps,cockpitHistory,cockpitKey};"
)(document,fetch,setInterval);
const el=id=>document.getElementById(id);
const bodyText=node=>node.textContent+" "+node.children.map(bodyText).join(" ");
const marker='\x3cimg src=x onerror=alert(1)\x3e';
const k='thing/product/SAMPLE/osd';
const first={
  provider:"dji-cloud-api",project_id:"local",device_id:"SAMPLE",kind:"aircraft",
  name:marker,online:true,freshness:"fresh",age_seconds:2,received_at:"2026-10-18T16:00:00Z",
  telemetry:{
    online:true,battery_percent:86,elevation_m:12,horizontal_speed_mps:5.5,
    flight_mode_code:3,rtk_state:"is_fixed:fixing_successful",
    latitude:49.1234,longitude:8.5678,
    cloud_details:{
      wind_speed_mps:3.5,heading_deg:120,
      battery:{remaining_flight_time_s:900},
      cameras:[{payload_index:"89-0-0",recording_state_code:1,
                ir_metering_point:{temperature_c:27.2}}],
      payloads:{"89-0-0":{gimbal_pitch_deg:-45}},
      control_source_category:"controller_a"
    }
  },
  field_status:{
    battery_percent:{freshness:"fresh",channel:"osd",source_timestamp_ms:1234,
      received_at:"2026-10-18T16:00:00Z",age_seconds:2,source_age_seconds:2},
    elevation_m:{freshness:"fresh",channel:"osd",source_timestamp_ms:1234,
      received_at:"2026-10-18T16:00:00Z",age_seconds:2},
    horizontal_speed_mps:{freshness:"fresh",channel:"osd",source_timestamp_ms:1234,
      received_at:"2026-10-18T16:00:00Z",age_seconds:2},
    latitude:{freshness:"fresh",channel:"osd",source_timestamp_ms:1234,
      received_at:"2026-10-18T16:00:00Z",age_seconds:2},
    longitude:{freshness:"fresh",channel:"osd",source_timestamp_ms:1234,
      received_at:"2026-10-18T16:00:00Z",age_seconds:2},
    'cloud_details.cameras':{freshness:"fresh",channel:"osd",source_timestamp_ms:1234,
      received_at:"2026-10-18T16:00:00Z",age_seconds:2}
  },health:[]
};
assert.equal(api.cockpitValidGps(0,0),false);
assert.equal(api.cockpitValidGps(49,8),true);
api.renderCockpit([first]);
assert.equal(el("cockpit-battery").textContent,"86 %");
assert.equal(el("cockpit-live").dataset.state,"live");
const findFocus=(label)=>el("cockpit-field-focus").children.find(r=>bodyText(r).includes(label));
assert.equal(el("cockpit-field-focus").children.length,4);
const neverRth=findFocus("RTH-Modus (Code)");
assert.equal(neverRth.dataset.state,"not-observed");
assert.ok(bodyText(neverRth).includes("Nicht beobachtet"));
assert.ok(bodyText(neverRth).includes("–"));
assert.equal(el("cockpit-mode").textContent,"Manueller Flug");
assert.equal(el("cockpit-rtk").textContent,"RTK-Fix");
assert.ok(el("cockpit-coordinates").textContent.includes("49.123400"));
assert.ok(bodyText(el("cockpit-camera")).includes("27.2"));
assert.ok(bodyText(el("cockpit-payload")).includes("-45.0"));
assert.equal(el("cockpit-device").children[0].textContent.includes(marker),true);
assert.equal(api.cockpitHistory.get(api.cockpitKey(first)).battery.length,1);
const batteryChart=el("cockpit-trends").children[0].children[1];
assert.equal(batteryChart.namespaceURI,"http://www.w3.org/2000/svg",
  "trend chart must use a real SVG element");
api.renderCockpit([{...first,age_seconds:3}]);
assert.equal(api.cockpitHistory.get(api.cockpitKey(first)).battery.length,1,
  "repeated source timestamp must not append artificial trend points");
api.renderCockpit([{...first,age_seconds:25,online:true,freshness:"fresh"}]);
assert.equal(el("cockpit-battery").textContent,"–",
  "backend freshness at 25 seconds cannot be called cockpit-live");
assert.notEqual(el("cockpit-live").dataset.state,"live");
const stale={...first,freshness:"stale",online:null,
  telemetry:{...first.telemetry,battery_percent:86}};
api.renderCockpit([stale]);
assert.equal(el("cockpit-battery").textContent,"–");
assert.notEqual(el("cockpit-live").dataset.state,"live");
assert.equal(api.cockpitHistory.has(api.cockpitKey(first)),false,
  "stale telemetry must break GNSS/trend continuity");
const oldBattery={...first,field_status:{...first.field_status,
  battery_percent:{...first.field_status.battery_percent,freshness:"stale"}}};
api.renderCockpit([oldBattery]);
assert.equal(el("cockpit-battery").textContent,"–",
  "fresh device cannot make an expired battery field live");
// A cached RTH value must remain explicitly non-live even when the
// aircraft is online and its other OSD fields are fresh.
const staleRth={...first,
  telemetry:{...first.telemetry,cloud_details:{...first.telemetry.cloud_details,
    rth_mode_code:null}},
  last_known_telemetry:{...first.telemetry,cloud_details:{...first.telemetry.cloud_details,
    rth_mode_code:7}},
  field_status:{...first.field_status,
    "cloud_details.rth_mode_code":{freshness:"stale",channel:"state",
      received_at:"2026-10-18T16:00:00Z",age_seconds:421,source_age_seconds:421}}};
api.renderCockpit([staleRth]);
const oldRth=findFocus("RTH-Modus (Code)");
assert.equal(oldRth.dataset.state,"last-known");
assert.ok(bodyText(oldRth).includes("Letzter bekannter Wert"));
assert.ok(bodyText(oldRth).includes("NICHT LIVE"));
assert.ok(bodyText(oldRth).includes("STATE"));
assert.ok(bodyText(oldRth).includes("421 s"));
assert.ok(bodyText(oldRth).includes("2026-10-18T16:00:00Z"));
assert.ok(bodyText(oldRth).includes("7"));
assert.ok(!bodyText(el("cockpit-safety")).includes("RTH-Modus (Code)"),
  "stale RTH must not appear in the live safety panel");
assert.equal(findFocus("Aktiver RTH-Modus (Code)").dataset.state,"not-observed",
  "an untransmitted optional field must be separate from historical values");
const liveRth={...staleRth,
  telemetry:{...staleRth.telemetry,cloud_details:{...staleRth.telemetry.cloud_details,
    rth_mode_code:7}},
  field_status:{...staleRth.field_status,
    "cloud_details.rth_mode_code":{...staleRth.field_status["cloud_details.rth_mode_code"],
      freshness:"fresh",age_seconds:2,source_age_seconds:2}}};
api.renderCockpit([liveRth]);
assert.equal(findFocus("RTH-Modus (Code)").dataset.state,"live");
assert.ok(bodyText(el("cockpit-safety")).includes("RTH-Modus (Code)"),
  "live RTH can appear in the live safety panel");
const slowRth={...liveRth,field_status:{...liveRth.field_status,
  "cloud_details.rth_mode_code":{...liveRth.field_status["cloud_details.rth_mode_code"],
    age_seconds:22,source_age_seconds:22}}};
api.renderCockpit([slowRth]);
assert.equal(findFocus("RTH-Modus (Code)").dataset.state,"last-known",
  "the 15-second cockpit threshold must not be loosened");
// Controller firmware and authorization data may be historical while
// its OSD feed and live-capacity State properties remain current.
const rc={...first,kind:"controller",device_id:"CONTROLLER",
  telemetry:{...first.telemetry,cloud_details:{
    firmware_version:null,cloud_control_authorization_count:null,
    live_capacity:{available_videos:2}}},
  last_known_telemetry:{...first.telemetry,cloud_details:{
    firmware_version:marker,cloud_control_authorization_count:4,
    live_capacity:{available_videos:2}}},
  field_status:{
    "cloud_details.firmware_version":{freshness:"stale",channel:"state",
      received_at:"2026-10-18T16:00:00Z",age_seconds:421,source_age_seconds:421},
    "cloud_details.cloud_control_authorization_count":{freshness:"stale",channel:"state",
      received_at:"2026-10-18T16:00:00Z",age_seconds:421,source_age_seconds:421},
    "cloud_details.live_capacity.available_videos":{freshness:"fresh",channel:"state",
      received_at:"2026-10-18T16:07:00Z",age_seconds:2,source_age_seconds:2}
  }};
api.renderCockpit([rc]);
assert.equal(findFocus("Firmwareversion (Fernsteuerung)").dataset.state,"last-known");
assert.ok(bodyText(findFocus("Firmwareversion (Fernsteuerung)")).includes(marker),
  "DJI text should be inserted safely as textContent");
assert.equal(findFocus("Cloud-Control-Autorisierungen (Anzahl)").dataset.state,"last-known");
assert.equal(findFocus("Verfügbare Livestreams").dataset.state,"live");
assert.equal(findFocus("Gleichzeitige Livestreams").dataset.state,"not-observed");
api.renderCockpit([{...first,online:false}]);
assert.equal(el("cockpit-battery").textContent,"–");
api.cockpitUnavailable("HTTP 401");
assert.equal(el("cockpit-battery").textContent,"–");
assert.equal(el("cockpit-live").dataset.state,"error");
assert.equal(el("cockpit-track").children.length,0);
assert.ok(!bodyText(el("cockpit-field-focus")).includes(marker),
  "historical fields must clear after an API authorization error");
api.renderCockpit([{...first,health:[{
  code:"0x16100083",level:"warning",module:"HMS",message:marker,
  source:"dji-cloud-hms",device_domain:"aircraft",
  message_source:"dji-hms-catalog-en",imminent:true,in_the_sky:true
}],hms_history:[{
  action:"reappeared",code:"0x16070042",observed_at:"2026-10-18T20:00:00Z",
  level:"reminder",message:marker
}]}]);
const hmsText=bodyText(el("cockpit-hms"));
assert.ok(hmsText.includes("DJI-Gateway-Meldung")&&hmsText.includes("Fluggerät"),
  "HMS source and reported device domain must be visible in live cockpit");
assert.ok(hmsText.includes("Englischer DJI-Katalogtext"));
assert.ok(hmsText.includes("Dringend laut DJI"));
assert.ok(hmsText.includes(marker),"HMS data is rendered as literal text");
assert.ok(hmsText.includes("Wiederaufgetreten") && hmsText.includes("2026-10-18T20:00:00Z"),
  "History must show real backend transitions, not browser-inferred changes");
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js required")
def test_embedded_cockpit_runs_with_live_and_stale_device_fixtures():
    scripts = re.findall(r"<script>(.*?)</script>", render_page(30), re.DOTALL)
    assert len(scripts) == 1
    result = subprocess.run(["node", "-e", _RUNTIME], input=scripts[0],
                            text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
