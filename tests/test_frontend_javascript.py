"""Parse *actual* embedded browser JS so a Chrome-wide syntax failure is caught.

This test would have caught the old missing parenthesis in the map longitude
calculation: Python endpoint tests cannot parse JavaScript.
"""
import re
import shutil
import subprocess

import pytest

from aeronexus.status_page import render_page
from aeronexus.studio_page import render_studio
from aeronexus.operations_page import render_operations


@pytest.mark.parametrize("page", ["studio", "status", "operations"])
def test_embedded_javascript_compiles_in_node(page):
    if shutil.which("node") is None:
        pytest.skip("Node.js is needed to validate embedded browser JavaScript")
    html = {"studio": render_studio, "status": lambda: render_page(30),
            "operations": render_operations}[page]()
    scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.DOTALL)
    assert len(scripts) == 1
    result = subprocess.run(
        ["node", "--check", "-"], input=scripts[0], text=True,
        capture_output=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr


def test_both_uis_have_no_login_forms_or_bearer_tokens():
    for html in (render_studio(), render_page(30), render_operations()):
        assert 'id="auth-token"' not in html
        assert 'id="token"' not in html
        assert 'id="login"' not in html
        assert 'id="connect"' not in html
        assert 'id="disconnect"' not in html
        assert "Authorization" not in html
        assert "Bearer " not in html


# Minimal browser DOM fake: tests the actual embedded cockpit script with Node,
# instead of relying only on finding literal strings in static HTML.
_COCKPIT_RUNTIME_TEST = r"""
const fs=require('node:fs');
const assert=require('node:assert/strict');
const script=fs.readFileSync(0,'utf8');
class Element {
  constructor(tag){
    this.tag=tag;this.children=[];this.id="";
    this.textContent="";this.className="";this.value="";
    this.scrollTop=0;this.open=false;this.listeners={};
    this.classList={toggle:(k,enabled)=>{
      this.className=this.className.split(" ").filter(x=>x!==k).join(" ")+
        (enabled?" "+k:"");
    }};
  }
  appendChild(x){this.children.push(x);return x;}
  replaceChildren(...xs){this.children=xs;}
  addEventListener(name,cb){this.listeners[name]=cb;}
  setAttribute(key,value){this[key]=value;}
  querySelector(q){
    if(q==="#cockpit-technical")
      return this.children.find(x=>x.id==="cockpit-technical")||null;
    return null;
  }
}
const cache=new Map();
const document={
  createElement(tag){return new Element(tag);},
  getElementById(id){
    if(!cache.has(id))cache.set(id,new Element(id));
    return cache.get(id);
  }
};
const window={setInterval(){},addEventListener(){}};
const fetch=()=>new Promise(()=>{});
const api=new Function("document","window","fetch",script+
  "\nreturn {rtkLabel,modeLabel,connectionStatus,freshnessStatus,renderCockpit,"+
  "setState(rows,id){devices=rows;currentDevice=id;}};"
)(document,window,fetch);

const base={
  device_id:"SYNTHETIC",name:"<script>unsafe</script>",
  project_id:"PROJECT",provider:"flighthub-public-v2",
  kind:"aircraft",freshness:"fresh",online:true,age_seconds:4,
  telemetry:{
    battery_percent:87,battery_voltage_mv:16365,
    battery_temperature_c:32.2,flight_mode_code:0,
    elevation_m:0,horizontal_speed_mps:0,rtk_state:"is_fixed:not_started",
    total_flight_time_s:0,total_flight_sorties:0,
    gps_satellites:0,rtk_satellites:0
  },
  health:[{level:"reminder",code:"0x16070042",message:null}]
};
const value=id=>document.getElementById(id).textContent;
const allText=node=>node.textContent+" "+node.children.map(allText).join(" ");
const summary=()=>allText(document.getElementById("cockpit-summary"));
const body=()=>document.getElementById("cockpit-content");

assert.equal(api.rtkLabel("is_fixed:not_started"),"RTK nicht gestartet");
assert.equal(api.rtkLabel("is_fixed:fixing"),"RTK-Fix läuft");
assert.equal(api.rtkLabel("is_fixed:fixing_successful"),"RTK-Fix erfolgreich");
assert.equal(api.rtkLabel("is_fixed:fixing_failed"),"RTK-Fix fehlgeschlagen");
assert.equal(api.rtkLabel("arbitrary:vendor_state"),"RTK-Status unbekannt");

api.setState([base],"SYNTHETIC");
api.renderCockpit();
assert.equal(value("cockpit-name"),"<script>unsafe</script>");
assert.equal(value("cockpit-connection"),"Online");
assert.equal(value("cockpit-freshness"),"Daten aktuell");
assert.equal(value("cockpit-received"),"Vor 4 s empfangen");
assert.ok(summary().includes("87 %"));
assert.ok(summary().includes("Standby"));
assert.ok(summary().includes("RTK nicht gestartet"));
assert.ok(!summary().includes("is_fixed:not_started"));
assert.ok(allText(body()).includes("Code: 0x16070042"));
assert.ok(allText(body()).includes("0 bedeutet nicht zwingend"));
assert.ok(allText(body()).includes("is_fixed:not_started"));

const previousDetails=body().querySelector("#cockpit-technical");
assert.equal(previousDetails.open,false);
previousDetails.open=true;
body().scrollTop=22;
api.renderCockpit();
assert.equal(body().querySelector("#cockpit-technical").open,true);
assert.equal(body().scrollTop,22);

api.setState([{...base,online:false}],"SYNTHETIC");
api.renderCockpit();
assert.equal(value("cockpit-connection"),"Offline");
assert.equal(value("cockpit-freshness"),"Daten aktuell");
assert.ok(summary().includes("gespeichert"));
assert.ok(allText(body()).includes("Keine bestätigte Live-Verbindung"));

api.setState([{...base,online:true,freshness:"stale",age_seconds:88}],"SYNTHETIC");
api.renderCockpit();
assert.equal(value("cockpit-connection"),"Zuletzt online");
assert.equal(value("cockpit-freshness"),"Daten veraltet");
assert.ok(summary().includes("gespeichert"));
assert.equal(value("cockpit-received"),"Vor 88 s empfangen");

api.setState([{
  ...base,online:null,freshness:"unknown_age",age_seconds:null,
  telemetry:{...base.telemetry,rtk_state:"custom:state",battery_percent:null}
}],"SYNTHETIC");
api.renderCockpit();
assert.equal(value("cockpit-connection"),"Verbindung unbekannt");
assert.equal(value("cockpit-freshness"),"Alter unbekannt");
assert.equal(value("cockpit-received"),"Empfangsalter unbekannt");
assert.ok(summary().includes("RTK-Status unbekannt"));
assert.ok(!summary().includes("custom:state"));
assert.ok(allText(body()).includes("custom:state"));
assert.ok(summary().includes("Akku (gespeichert)"));
"""


def test_operations_cockpit_behavior_in_simulated_browser():
    if shutil.which("node") is None:
        pytest.skip("Node.js is needed to evaluate cockpit JavaScript")
    page = render_operations()
    scripts = re.findall(r"<script>(.*?)</script>", page, flags=re.DOTALL)
    assert len(scripts) == 1
    result = subprocess.run(
        ["node", "-e", _COCKPIT_RUNTIME_TEST], input=scripts[0], text=True,
        capture_output=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr


# Evaluate the actual pure route-analysis functions from the browser bundle
# in Node.js, without replacing production logic with Python approximations.
_ROUTE_ANALYSIS_RUNTIME_TEST = r"""
const fs=require("node:fs");
const assert=require("node:assert/strict");
const script=fs.readFileSync(0,"utf8");
const start=script.indexOf("function geoDistanceMeters(");
const end=script.indexOf("function updateRouteStatus(){",start);
assert.ok(start>=0&&end>start,"route functions not found");
const utils=new Function(script.slice(start,end)+
  "\nreturn {geoDistanceMeters,routeMetrics,formatRouteDistance,formatRouteDuration};")();
const {geoDistanceMeters,routeMetrics,formatRouteDistance,formatRouteDuration}=utils;
const a={latitude:49.1,longitude:8.5,take_photo:true};
const b={latitude:49.11,longitude:8.5,take_photo:false};
const c={latitude:49.11,longitude:8.51,take_photo:false};
const points=[a,b,c];
const before=JSON.stringify(points);
const ab=geoDistanceMeters(a,b);
assert.ok(Math.abs(ab-1111.951)<0.5,"invalid haversine A-B: "+ab);
const open=routeMetrics(points,false,5);
assert.equal(open.valid,true);
assert.equal(open.segments.length,2);
assert.equal(open.executedPoints,3);
assert.equal(open.returnMeters,null);
assert.ok(Math.abs(open.segments[0].meters-ab)<0.00001);
assert.ok(Math.abs(open.seconds-open.distanceMeters/5)<0.00001);
const closed=routeMetrics(points,true,5);
assert.equal(closed.valid,true);
assert.equal(closed.segments.length,3);
assert.equal(closed.executedPoints,4);
assert.ok(closed.distanceMeters>open.distanceMeters);
assert.ok(Math.abs(closed.returnMeters-geoDistanceMeters(c,a))<0.00001);
assert.equal(JSON.stringify(points),before,"analysis must not modify the mission");
const preclosed=routeMetrics([...points,{...a,take_photo:false}],true,5);
assert.equal(preclosed.executedPoints,4,"explicit return must not be duplicated");
assert.equal(preclosed.segments.length,3);
assert.ok(Math.abs(preclosed.returnMeters-closed.returnMeters)<0.00001);
assert.ok(Math.abs(preclosed.distanceMeters-closed.distanceMeters)<0.00001);
const dateline=geoDistanceMeters({latitude:1,longitude:179.9},
  {latitude:1,longitude:-179.9});
assert.ok(dateline>22000&&dateline<22500,
  "antimeridian should use short path, not 360 degree wrap");
assert.equal(geoDistanceMeters({latitude:0,longitude:0},b),null);
assert.equal(geoDistanceMeters({latitude:Infinity,longitude:8},b),null);
assert.equal(routeMetrics([a,{latitude:91,longitude:8}],false,5).valid,false);
assert.equal(routeMetrics([],false,5).distanceMeters,null);
assert.equal(routeMetrics([a],false,5).seconds,null);
assert.equal(routeMetrics(points,false,0).seconds,null);
assert.equal(routeMetrics(points,false,NaN).seconds,null);
assert.equal(routeMetrics(points,false,16).seconds,null);
assert.equal(formatRouteDistance(null),"–");
assert.equal(formatRouteDuration(null),"–");
assert.equal(formatRouteDuration(59.1),"1 min 00 s");
assert.equal(formatRouteDuration(3661),"1 h 01 min");
assert.match(formatRouteDistance(1500),/km/);
"""


def test_studio_route_analysis_geometry_in_node():
    if shutil.which("node") is None:
        pytest.skip("Node.js is needed to validate mission route analysis")
    page = render_studio()
    scripts = re.findall(r"<script>(.*?)</script>", page, flags=re.DOTALL)
    assert len(scripts) == 1
    result = subprocess.run(
        ["node", "-e", _ROUTE_ANALYSIS_RUNTIME_TEST], input=scripts[0],
        text=True, capture_output=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
