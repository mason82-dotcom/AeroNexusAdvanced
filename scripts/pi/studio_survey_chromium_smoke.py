#!/usr/bin/env python3
"""Headless Chromium DOM regression for the real Studio survey workflow.

Runs the entire production HTML/JS; replaces only remote Leaflet with a
deterministic map API double and only local workspace/survey HTTP with memory
fixtures. It tests frontend wiring, not actual Leaflet raster rendering.
Does not contact the Pi, DJI, MinIO or any backend, or write a real mission.
"""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile

from aeronexus.geo_planning import GeoObject, SurveyPlanRequest, generate_survey_preview
from aeronexus.studio_page import render_studio

# Load the existing sibling browser harness by path. Pytest doesn't always put
# the repository root on sys.path when collecting tests on GitHub Actions.
BASE_PATH = Path(__file__).with_name("studio_full_ui_chromium_smoke.py")
base_spec = importlib.util.spec_from_file_location("studio_full_ui_base", BASE_PATH)
base = importlib.util.module_from_spec(base_spec)
base_spec.loader.exec_module(base)

PASS = re.compile(r'<html\b[^>]*\bdata-survey-ui="PASS"', re.I)
ERROR = re.compile(r'data-survey-error="([^"]{0,180})"', re.I)
RECTANGLE = [
    {"latitude": 49.15330, "longitude": 8.58400},
    {"latitude": 49.15330, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58490},
    {"latitude": 49.15410, "longitude": 8.58400},
]

MAP_DOUBLE = r"""<script>
"use strict";
window.__fakeMap={
  _events:{},_layers:new Set(),fitted:false,
  setView(){return this;},getZoom(){return 15;},
  invalidateSize(){return this;},fitBounds(bounds){this.fitted=!!bounds;return this;},
  on(event,fn){this._events[event]=fn;return this;},
  fire(event,arg){if(!this._events[event])throw Error('No map event handler');this._events[event](arg)},
  addLayer(layer){this._layers.add(layer);return this;},
  removeLayer(layer){this._layers.delete(layer);return this;},
  hasLayer(layer){return this._layers.has(layer)}
};
function fakeShape(coords,options={}){
  return {coords,options,bindTooltip(){return this;},
    on(){return this;},getLatLng(){return {lat:coords[0],lng:coords[1]}},
    addTo(container){container.addLayer(this);return this}};
}
function fakeGroup(){
  return {layers:[],addLayer(item){this.layers.push(item);return this;},
    clearLayers(){this.layers=[];return this;},
    addTo(container){container.addLayer(this);return this;}};
}
window.L={
  map:()=>window.__fakeMap,
  layerGroup:fakeGroup,
  tileLayer:()=>({on(){return this;},addTo(map){map.addLayer(this);return this;}}),
  marker:(coords,options)=>fakeShape(coords,options),
  circleMarker:(coords,options)=>fakeShape(coords,options),
  circle:(coords,options)=>fakeShape(coords,options),
  polygon:(coords,options)=>fakeShape(coords,options),
  polyline:(coords,options)=>fakeShape(coords,options),
  divIcon:config=>config,
  latLngBounds:points=>({points})
};
</script>"""

API_DOUBLE = r"""<script>
"use strict";
// All live read paths are handled by the existing strict synthetic GET-only
// test fixture. These are the ONLY two allowed in-memory POST requests.
window.__surveyCalls=[];
window.__surveyObjects=[];
const surveyReadFetch=window.fetch;
window.fetch=async function(path,opts={}){
  const url=String(path), method=String(opts.method||'GET').toUpperCase();
  if(method==='POST'&&url==='/api/v1/studio/geo-objects'){
    const obj=JSON.parse(opts.body);
    if(obj.kind!=='polygon'||obj.vertices.length!==4)
      throw Error('Unexpected synthetic polygon content');
    const record={id:'00000000-0000-4000-8000-000000000001',object:obj};
    window.__surveyObjects.push(record);
    window.__surveyCalls.push('POST geo');
    return new Response(JSON.stringify(record),{
      status:201,headers:{'Content-Type':'application/json'}});
  }
  if(method==='GET'&&url==='/api/v1/studio/geo-objects'){
    return new Response(JSON.stringify({objects:window.__surveyObjects}),{
      status:200,headers:{'Content-Type':'application/json'}});
  }
  if(method==='POST'&&url==='/api/v1/studio/survey/preview'){
    const req=JSON.parse(opts.body);
    if(req.polygon.kind!=='polygon'||req.spacing_m!==20||req.bearing_deg!==0)
      throw Error('Survey request lost polygon or parameters');
    if(req.polygon.vertices.length!==4)
      throw Error('Survey request did not persist geometry');
    window.__surveyCalls.push('POST preview');
    return new Response(JSON.stringify(__PREVIEW__),{
      status:200,headers:{'Content-Type':'application/json'}});
  }
  return surveyReadFetch(path,opts);
};
</script>"""

CHECK = r"""<script>
"use strict";
const surveyCheck=(valid,why)=>{if(!valid)throw Error(why)};
const surveyTick=()=>new Promise(done=>setTimeout(done,0));
async function runSurveySmoke(){
  await surveyTick();await surveyTick();await surveyTick();
  surveyCheck(window.__uiErrors.length===0,
    'Boot JS error: '+window.__uiErrors.join('; '));
  surveyCheck(window.__fakeMap._events.click,'Map click event not installed');
  surveyCheck(map===window.__fakeMap,'Map double not initialized');
  document.querySelector('nav button[data-tab="geo-pane"]').click();
  document.getElementById('geo-kind').value='polygon';
  document.getElementById('geo-name').value='Synthetisches Rechteck';
  document.getElementById('geo-draw').click();
  surveyCheck(geoDraw===true,'Drawing mode not activated');
  for(const p of __RECTANGLE__){
    window.__fakeMap.fire('click',{latlng:{lat:p.latitude,lng:p.longitude}});
  }
  surveyCheck(geoDraft.length===4,'Four synthetic map clicks not recorded');
  surveyCheck(document.getElementById('geo-draft-points').children.length===4,
    'Polygon draft list not rendered');
  surveyCheck(geoLayer.layers.some(x=>x.options?.color==='#ffc878'),
    'Editable Leaflet polygon draw call missing');
  document.getElementById('geo-draw').click();
  surveyCheck(geoDraw===false,'Drawing mode not stopped');
  document.getElementById('geo-save').click();
  for(let i=0;i<8;i++)await surveyTick();
  surveyCheck(window.__surveyObjects.length===1,'Geo object not saved in synthetic backend');
  surveyCheck(geoDraft.length===0,'Draft not cleared after save');
  surveyCheck(geoObjects.length===1,'Saved geometry not reloaded into UI');
  surveyCheck(document.getElementById('survey-object').value===
    window.__surveyObjects[0].id,'New polygon not preselected for survey');
  surveyCheck(document.getElementById('geo-list').textContent.includes('Synthetisches Rechteck'),
    'Saved polygon missing from visible list');
  document.getElementById('survey-spacing').value='20';
  document.getElementById('survey-bearing').value='0';
  document.getElementById('survey-generate').click();
  for(let i=0;i<8;i++)await surveyTick();
  surveyCheck(surveyLayer.layers.length===4,
    'Expected four Leaflet survey polyline draw calls');
  surveyCheck(surveyLayer.layers.every(x=>x.options?.dashArray==='5 5'
    && x.coords.length===2),'Survey polyline style/geometry incorrect');
  surveyCheck(window.__fakeMap.fitted,'Map did not fit to survey flight strips');
  surveyCheck(document.getElementById('survey-message').textContent.includes('4 getrennte Flugstreifen'),
    'Survey metrics not rendered');
  surveyCheck(document.getElementById('survey-message').textContent.includes('355,6')
    ||document.getElementById('survey-message').textContent.includes('356'),
    'Survey distance not displayed');
  surveyCheck(window.__surveyCalls.join(',')==='POST geo,POST preview',
    'Unexpected write-like operation');
  surveyCheck(mission.waypoints.length===0,
    'Survey preview must not mutate editable DJI waypoint mission');
  surveyCheck(window.__uiErrors.length===0,
    'Browser errors after interactions: '+window.__uiErrors.join('; '));
  return surveyLayer.layers.length;
}
runSurveySmoke().then(n=>{
  document.documentElement.setAttribute('data-survey-ui','PASS');
  document.documentElement.setAttribute('data-survey-strips',String(n));
}).catch(err=>{
  document.documentElement.setAttribute('data-survey-ui','FAIL');
  document.documentElement.setAttribute('data-survey-error',
    String(err?.message||err).slice(0,180));
});
</script>"""


def build_fixture():
    source = render_studio()
    source, external = base.CDN.subn("", source)
    if external != 1 or source.count(base.SCRIPT_START) != 1 or source.count("</body>") != 1:
        raise ValueError("Unexpected rendered Studio HTML script structure")
    geometry = GeoObject(name="Synthetisches Rechteck", kind="polygon", vertices=RECTANGLE)
    preview = generate_survey_preview(
        SurveyPlanRequest(polygon=geometry, spacing_m=20, bearing_deg=0))
    if preview["leg_count"] != 4:
        raise ValueError("Baseline survey fixture changed")
    api = API_DOUBLE.replace("__PREVIEW__", json.dumps(preview))
    checks = CHECK.replace("__RECTANGLE__", json.dumps(RECTANGLE))
    return source.replace(base.SCRIPT_START,
                          base.PRELUDE + "\n" + MAP_DOUBLE + "\n" + api + "\n" + base.SCRIPT_START, 1
                          ).replace("</body>", checks + "\n</body>", 1)


def run_smoke(*, width=1440, height=900):
    chrome = base.browser_binary()
    if not chrome:
        return "not_run", "Chromium unavailable"
    try:
        with tempfile.TemporaryDirectory(prefix="aeronexus-survey-ui-") as root:
            path = Path(root) / "studio.html"
            path.write_text(build_fixture(), encoding="utf-8")
            args = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                    "--disable-dev-shm-usage", "--disable-background-networking",
                    "--disable-component-update", "--disable-extensions",
                    "--disable-sync", "--no-first-run", "--no-default-browser-check",
                    "--no-proxy-server", "--host-resolver-rules=MAP * 0.0.0.0",
                    "--window-size=" + str(width) + "," + str(height),
                    "--virtual-time-budget=9000",
                    "--user-data-dir=" + str(Path(root) / "profile"),
                    "--dump-dom", path.as_uri()]
            done = subprocess.run(args, capture_output=True, text=True,
                                  timeout=45, check=False)
            if done.returncode != 0:
                return "fail", "Chromium process exit " + str(done.returncode)
            if PASS.search(done.stdout):
                return "pass", "synthetic map events and survey overlay"
            failed = ERROR.search(done.stdout)
            return "fail", failed.group(1) if failed else "DOM result marker absent"
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        return "fail", type(exc).__name__


def main():
    for label, width, height in (("Desktop", 1440, 900), ("Mobile", 420, 860)):
        status, detail = run_smoke(width=width, height=height)
        print(label + " / " + status.upper() + " / " + detail)
        if status != "pass":
            return 2 if status == "not_run" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
