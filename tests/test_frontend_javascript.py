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
// Two refresh cycles with identical content, only received-age changing,
// must retain the exact DOM nodes and scroll offsets (no Chrome repaint).
api.setState([{...base,age_seconds:5}],"SYNTHETIC");
api.renderCockpit();
assert.strictEqual(body().querySelector("#cockpit-technical"),previousDetails);
assert.equal(value("cockpit-received"),"Vor 5 s empfangen");
assert.equal(body().scrollTop,22);
api.setState([{...base,age_seconds:7}],"SYNTHETIC");
api.renderCockpit();
assert.strictEqual(body().querySelector("#cockpit-technical"),previousDetails);
assert.equal(body().scrollTop,22);
assert.equal(value("cockpit-received"),"Vor 7 s empfangen");
// A changed real telemetry sample must repaint but preserve expansion/scroll.
api.setState([{...base,telemetry:{...base.telemetry,battery_percent:86}}],"SYNTHETIC");
api.renderCockpit();
assert.notStrictEqual(body().querySelector("#cockpit-technical"),previousDetails);
assert.equal(body().querySelector("#cockpit-technical").open,true);
assert.equal(body().scrollTop,22);
assert.ok(summary().includes("86 %"));
const rawCards=body().querySelector("#cockpit-technical")
  .children.find(x=>x.className==="cockpit")
  .children.filter(x=>x.className.includes("cockpit-raw"));
assert.equal(rawCards.length,1);
assert.ok(allText(rawCards[0]).includes("is_fixed:not_started"));

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
assert.equal(routeMetrics(points,false,0.05).seconds,null);
assert.equal(routeMetrics(points,false,0.1).valid,true);
assert.equal(routeMetrics(points,false,NaN).seconds,null);
assert.equal(routeMetrics(points,false,16).seconds,null);
assert.equal(formatRouteDistance(null),"–");
assert.equal(formatRouteDuration(null),"–");
assert.equal(formatRouteDuration(59.1),"1 min 00 s");
assert.equal(formatRouteDuration(3661),"1 h 01 min");
assert.match(formatRouteDistance(1500),/km/);

// Render via the production DOM function without Leaflet or a network.
// The speed field is the active unsaved form value, not stale mission.speed_mps.
const values=new Map();
const el=id=>{
  if(!values.has(id))values.set(id,{value:"",textContent:""});
  return values.get(id);
};
const editor=new Function("mission","$",script.slice(start,end)+
  "\nreturn updateRouteAnalysis;")({
    waypoints:points,close_route:true,speed_mps:5
  },el);
el("mission-speed").value="5";
const first=editor();
assert.equal(first.segments.length,3);
assert.equal(el("route-legs").textContent,"3");
assert.ok(el("route-distance").textContent.includes("km"));
assert.ok(el("route-return").textContent.includes("km"));
const previous=el("route-duration").textContent;
el("mission-speed").value="10";
const faster=editor();
assert.ok(faster.seconds<first.seconds);
assert.notEqual(el("route-duration").textContent,previous);
el("mission-speed").value="";
editor();
assert.equal(el("route-duration").textContent,"–");
assert.ok(el("route-analysis-warning").textContent.includes("0,1 bis 15"));
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


# Real Mission Studio browser editor logic evaluated inside Node, with a
# minimal mocked DOM and no external network calls or DJI devices.
_STUDIO_HISTORY_RUNTIME_TEST = r"""
const fs=require("node:fs");
const assert=require("node:assert/strict");
const script=fs.readFileSync(0,"utf8");
const start=script.indexOf("function editorSnapshot(){");
const stop=script.indexOf("function getForm(){",start);
const navStart=script.indexOf("async function loadMission(id,{skipConfirm=false}={}){");
const navStop=script.indexOf("async function saveMission(){",navStart);
assert.ok(start>=0&&stop>start&&navStart>stop&&navStop>navStart);
const logic=script.slice(start,stop)+"\n"+script.slice(navStart,navStop);
const setup=[
  'const FORM_IDS=["mission-name","mission-description","mission-model",',
  '"mission-altitude","mission-speed","mission-takeoff","mission-rth","mission-finish"];',
  'const HISTORY_LIMIT=60;',
  'const EMPTY=()=>({name:"Neue Wegpunktmission",description:"",drone_model:"matrice4t",',
  'altitude_m:50,speed_mps:5,takeoff_security_height_m:20,rth_height_m:60,',
  'finish_action:"goHome",close_route:false,waypoints:[]});',
  'let mission=EMPTY(),missionId=null,selected=-1,',
  'editHistory=[],editIndex=-1,editGroup=null,cleanSnapshot=null;',
  'const values=new Map(),notices=[];',
  'const window={confirmed:false,confirm(){return this.confirmed;}};',
  'function $(id){if(!values.has(id))values.set(id,{value:"",checked:false,disabled:false,',
  'textContent:"",classList:{toggle(){} }});return values.get(id);}',
  'function redraw(){};function fitMission(){};',
  'function notice(v){notices.push(v)};',
  'function syncForm(){const f={"mission-name":mission.name,',
  '"mission-description":mission.description,"mission-model":mission.drone_model,',
  '"mission-altitude":mission.altitude_m,"mission-speed":mission.speed_mps,',
  '"mission-takeoff":mission.takeoff_security_height_m,"mission-rth":mission.rth_height_m,',
  '"mission-finish":mission.finish_action};for(const [id,v] of Object.entries(f))',
  '$(id).value=String(v);$("close-route").checked=mission.close_route;}',
  'function updateMissionSelect(){$("mission-list").value=missionId||"";}',
  'function resolvedWaypoints(){return mission.waypoints;}',
  'let request=async()=>({json:async()=>({id:"saved-id",mission:EMPTY()})});',
  'async function api(){return request();}',
  logic,
  'syncForm();historyReset();',
  'return {editorDirty,historyReset,historyRecord,historySaved,undoEdit,redoEdit,',
  'allowDiscard,midpointCoordinates,insertMidpoint,newMission,loadMission,',
  'get mission(){return mission},get selected(){return selected},',
  'get length(){return editHistory.length},get index(){return editIndex},',
  'get values(){return values},get notices(){return notices},',
  'choose(n){selected=n},setMission(v){mission=v;syncForm();historyReset()},',
  'setConfirm(v){window.confirmed=v},setRequest(v){request=v},',
  'node(id){return $(id)}};'
].join("\n");
const studio=new Function(setup)();
const el=id=>studio.node(id);
(async()=>{
  assert.equal(studio.editorDirty(),false);
  assert.equal(el("undo-edit").disabled,true);
  el("mission-name").value="AB";
  studio.historyRecord("typing:mission-name");
  el("mission-name").value="ABC";
  studio.historyRecord("typing:mission-name");
  assert.equal(studio.length,2,"consecutive keystrokes must coalesce");
  assert.equal(studio.editorDirty(),true);
  assert.equal(el("redo-edit").disabled,true);
  assert.equal(studio.undoEdit(),true);
  assert.equal(el("mission-name").value,"Neue Wegpunktmission");
  assert.equal(studio.editorDirty(),false);
  assert.equal(studio.redoEdit(),true);
  assert.equal(el("mission-name").value,"ABC");
  assert.equal(studio.editorDirty(),true);
  studio.historySaved();
  assert.equal(studio.editorDirty(),false);
  const preSaveSteps=studio.length;
  // getForm() copies visible fields to the mission object on save;
  // this internal synchronization must not create an invisible undo step.
  studio.mission.name="ABC";
  studio.historyRecord();
  assert.equal(studio.length,preSaveSteps);
  studio.undoEdit();
  assert.equal(studio.editorDirty(),true,"undo after save is an unsaved revision");
  studio.redoEdit();
  assert.equal(studio.editorDirty(),false);
  el("mission-description").value="uncommitted";
  studio.historyRecord();
  assert.equal(studio.newMission(),false,"unsaved changes must block new mission");
  assert.equal(el("mission-description").value,"uncommitted");
  studio.setConfirm(true);
  assert.equal(studio.newMission(),true);
  assert.equal(studio.editorDirty(),false);

  const a={latitude:49.1234567,longitude:179.9,take_photo:true};
  const b={latitude:49.2234567,longitude:-179.9,take_photo:true};
  const c={latitude:49.3234567,longitude:-179.8,take_photo:false};
  studio.mission.waypoints=[a,b,c];
  studio.historyReset();
  studio.choose(0);
  assert.equal(studio.insertMidpoint(),true);
  assert.equal(studio.mission.waypoints.length,4);
  const midpoint=studio.mission.waypoints[1];
  assert.ok(Math.abs(midpoint.longitude-(-180))<0.000001,
    "midpoint across antimeridian must not jump to longitude 0");
  assert.equal(midpoint.latitude,49.1734567);
  assert.equal(midpoint.take_photo,false);
  assert.equal(studio.editorDirty(),true);
  studio.undoEdit();
  assert.equal(studio.mission.waypoints.length,3);
  studio.redoEdit();
  assert.equal(studio.mission.waypoints.length,4);
  assert.equal(studio.editorDirty(),true);
  assert.equal(studio.midpointCoordinates({latitude:100,longitude:1},b),null);
  assert.equal(studio.midpointCoordinates({latitude:1,longitude:1},null),null);

  // Switch to a saved mission cannot proceed without explicit confirmation.
  studio.setConfirm(false);
  assert.equal(await studio.loadMission("saved-id"),false);
  assert.equal(studio.editorDirty(),true);
  studio.setConfirm(true);
  assert.equal(await studio.loadMission("saved-id"),true);
  assert.equal(studio.editorDirty(),false);
  assert.equal(studio.mission.waypoints.length,0);

  // Late network completion must never discard edits started while fetching.
  let finish;
  studio.setRequest(()=>new Promise(resolve=>{finish=resolve;}));
  const delayed=studio.loadMission("second-id");
  el("mission-name").value="changed while loading";
  studio.historyRecord();
  finish({json:async()=>({id:"second-id",mission:{name:"Lost",waypoints:[]}})});
  await assert.rejects(delayed,/während des Ladens geändert/);
  assert.equal(el("mission-name").value,"changed while loading");
  assert.equal(studio.editorDirty(),true);
})().catch(e=>{console.error(e);process.exitCode=1;});
"""


def test_studio_undo_redo_dirty_navigation_in_node():
    if shutil.which("node") is None:
        pytest.skip("Node.js is needed to validate Mission Studio history")
    page = render_studio()
    scripts = re.findall(r"<script>(.*?)</script>", page, flags=re.DOTALL)
    assert len(scripts) == 1
    result = subprocess.run(
        ["node", "-e", _STUDIO_HISTORY_RUNTIME_TEST], input=scripts[0],
        text=True, capture_output=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
