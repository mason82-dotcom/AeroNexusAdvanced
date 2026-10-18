#!/usr/bin/env python3
"""Run the real Leaflet 1.9.4 map engine in an isolated Chromium Studio smoke.

Uses unchanged production Studio inline JS and real Leaflet JS/CSS, pinned by
fetch_leaflet_test_assets.py. Only the remote basemap URLs are substituted with
a tiny inline test tile; all API responses are synthesized in browser memory.
Checks actual Leaflet map layers, SVG vector paths and desktop/mobile layout.
No Tailscale, DJI, Pi, login tokens, flight commands or production data.
"""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from aeronexus.studio_page import render_studio

SCRIPT = Path(__file__).with_name("studio_survey_chromium_smoke.py")
spec = importlib.util.spec_from_file_location("studio_survey_base", SCRIPT)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

ASSETS_ENV = "AERONEXUS_LEAFLET_TEST_ASSETS"
PASS = re.compile(r'<html\b[^>]*\bdata-real-leaflet-ui="PASS"', re.I)
ERROR = re.compile(r'data-real-leaflet-error="([^"]{0,180})"', re.I)
LEAFLET_JS = re.compile(
    r'<script src="https://cdn\.jsdelivr\.net/npm/leaflet@1\.9\.4/dist/leaflet\.js"[^>]*></script>')
LEAFLET_CSS = re.compile(
    r'<link rel="stylesheet" href="https://cdn\.jsdelivr\.net/npm/leaflet@1\.9\.4/dist/leaflet\.css"[^>]*>')
# One transparent PNG; no remote imagery requested during this browser test.
TILE = ("data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4"
        "z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==")

CHECKS = r"""<script>
"use strict";
const rCheck=(good,reason)=>{if(!good)throw Error(reason)};
const rTick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function runRealLeafletSurvey(){
  for(let i=0;i<4;i++)await rTick();
  rCheck(typeof window.L==='object'&&typeof L.version==='string'&&L.version==='1.9.4',
    'Real Leaflet 1.9.4 did not load');
  rCheck(map instanceof L.Map&&map.getContainer().id==='map','Real Leaflet map missing');
  rCheck(geoLayer instanceof L.LayerGroup&&surveyLayer instanceof L.LayerGroup,
    'Geo and survey overlays are not Leaflet groups');
  rCheck(document.querySelector('#map .leaflet-pane')!==null,
    'Leaflet DOM panes were not created');
  rCheck(getComputedStyle(document.querySelector('#map')).position==='relative',
    'Leaflet stylesheet not applied');
  const original=mapTiles.street;
  rCheck(map.hasLayer(original),'OSM street tile layer not present at startup');
  rCheck(document.getElementById('map-layer').value==='street',
    'Street map is not the default in UI');
  setMapLayer('satellite');
  rCheck(map.hasLayer(mapTiles.satellite)&&!map.hasLayer(original),
    'Satellite map switch did not replace the street layer');
  rCheck(document.getElementById('map-layer').value==='satellite',
    'Satellite selection not reflected in UI');
  setMapLayer('street');
  rCheck(map.hasLayer(original)&&!map.hasLayer(mapTiles.satellite),
    'Street map restore did not work');

  // Dispatch actual DOM click events to the real Leaflet map container.
  document.querySelector('nav button[data-tab="geo-pane"]').click();
  document.getElementById('geo-kind').value='polygon';
  document.getElementById('geo-name').value='Synthetisches Rechteck';
  document.getElementById('geo-draw').click();
  rCheck(geoDraw===true,'Geo drawing mode not active');
  for(const point of __RECTANGLE__){
    const screen=map.latLngToContainerPoint(L.latLng(point.latitude,point.longitude));
    const bounds=map.getContainer().getBoundingClientRect();
    const click=new MouseEvent('click',{
      bubbles:true,cancelable:true,
      clientX:bounds.left+screen.x,
      clientY:bounds.top+screen.y
    });
    map.getContainer().dispatchEvent(click);
  }
  rCheck(geoDraft.length===4,'Real Leaflet DOM map clicks failed');
  rCheck(document.getElementById('geo-draft-points').children.length===4,
    'Draft polygon points were not displayed');
  rCheck(geoLayer.getLayers().some(layer=>layer instanceof L.Polygon),
    'Real Leaflet polygon layer missing');
  rCheck(document.querySelector('#map .leaflet-overlay-pane svg path')!==null,
    'Real SVG polygon path absent');
  document.getElementById('geo-draw').click();
  document.getElementById('geo-save').click();
  for(let i=0;i<12;i++)await rTick();
  rCheck(geoObjects.length===1,'Synthetic polygon not persisted in UI');
  rCheck(document.getElementById('survey-object').value===
    window.__surveyObjects[0].id,'Saved polygon not selected');
  document.getElementById('survey-spacing').value='20';
  document.getElementById('survey-bearing').value='0';
  document.getElementById('survey-generate').click();
  for(let i=0;i<12;i++)await rTick();
  const strips=surveyLayer.getLayers();
  rCheck(strips.length===4,'Expected four actual Leaflet polylines');
  rCheck(strips.every(layer=>layer instanceof L.Polyline&&
     layer.options.dashArray==='5 5'&&layer.getLatLngs().length===2),
     'Flight strips not represented as styled Leaflet polylines');
  rCheck(strips.every(layer=>layer._path&&layer._path.ownerSVGElement),
    'Real Leaflet vector SVG path not mounted in DOM');
  rCheck(document.getElementById('survey-message').textContent.includes('4 getrennte Flugstreifen'),
    'Survey metrics not visible in UI');
  rCheck(window.__surveyCalls.join(',')==='POST geo,POST preview',
    'Unexpected write-like API calls');
  rCheck(mission.waypoints.length===0,
    'Real survey test modified executable waypoint mission');
  rCheck(window.__uiErrors.length===0,
    'Browser JavaScript error: '+window.__uiErrors.join('; '));
  return strips.length;
}
runRealLeafletSurvey().then(count=>{
  document.documentElement.setAttribute('data-real-leaflet-ui','PASS');
  document.documentElement.setAttribute('data-real-leaflet-strips',String(count));
}).catch(err=>{
  document.documentElement.setAttribute('data-real-leaflet-ui','FAIL');
  document.documentElement.setAttribute('data-real-leaflet-error',
    String(err?.message||err).slice(0,180));
});
</script>"""


def build_fixture() -> str:
    source = render_studio()
    source, js_count = LEAFLET_JS.subn('<script src="leaflet.js"></script>', source)
    source, css_count = LEAFLET_CSS.subn('<link rel="stylesheet" href="leaflet.css">', source)
    if js_count != 1 or css_count != 1:
        raise ValueError("Expected one pinned Leaflet JS and CSS reference")
    for remote in (
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    ):
        if remote not in source:
            raise ValueError("Expected map tile source changed")
        source = source.replace(remote, TILE)
    if source.count(base.base.SCRIPT_START) != 1:
        raise ValueError("Unexpected inline Studio JS structure")
    if source.count("</body>") != 1:
        raise ValueError("Unexpected document boundary")
    polygon = base.GeoObject(name="Synthetisches Rechteck", kind="polygon",
                             vertices=base.RECTANGLE)
    data = base.generate_survey_preview(
        base.SurveyPlanRequest(polygon=polygon, spacing_m=20, bearing_deg=0))
    import json
    api = base.API_DOUBLE.replace("__PREVIEW__", json.dumps(data))
    checks = CHECKS.replace("__RECTANGLE__", json.dumps(base.RECTANGLE))
    return source.replace(
        base.base.SCRIPT_START,
        base.base.PRELUDE + "\n" + api + "\n" + base.base.SCRIPT_START, 1
    ).replace("</body>", checks + "\n</body>", 1)


def assets_dir() -> Path | None:
    value = os.environ.get(ASSETS_ENV, "").strip()
    if not value:
        return None
    result = Path(value).expanduser()
    if not all((result / item).is_file() for item in ("leaflet.js", "leaflet.css")):
        return None
    return result


def run_smoke(*, width=1440, height=900):
    chrome = base.base.browser_binary()
    assets = assets_dir()
    if not chrome:
        return "not_run", "Chromium unavailable"
    if assets is None:
        return "not_run", "Pinned Leaflet assets unavailable"
    try:
        with tempfile.TemporaryDirectory(prefix="aeronexus-real-leaflet-") as root:
            path = Path(root)
            (path / "studio.html").write_text(build_fixture(), encoding="utf-8")
            for name in ("leaflet.js", "leaflet.css"):
                shutil.copyfile(assets / name, path / name)
            args = [
                chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                "--disable-dev-shm-usage", "--disable-background-networking",
                "--disable-component-update", "--disable-extensions",
                "--disable-sync", "--no-first-run", "--no-default-browser-check",
                "--no-proxy-server", "--host-resolver-rules=MAP * 0.0.0.0",
                "--window-size=" + str(width) + "," + str(height),
                "--virtual-time-budget=12000",
                "--user-data-dir=" + str(path / "profile"),
                "--dump-dom", (path / "studio.html").as_uri(),
            ]
            done = subprocess.run(args, capture_output=True, text=True,
                                  timeout=50, check=False)
            if done.returncode != 0:
                return "fail", "Chromium process exit " + str(done.returncode)
            if PASS.search(done.stdout):
                return "pass", "genuine Leaflet vector SVG and basemap switch"
            match = ERROR.search(done.stdout)
            return "fail", match.group(1) if match else "DOM result marker missing"
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return "fail", type(exc).__name__


if __name__ == "__main__":
    failed = False
    for label, width, height in (("Desktop", 1440, 900), ("Mobile", 420, 860)):
        state, detail = run_smoke(width=width, height=height)
        print(label + ": " + state.upper() + " / " + detail)
        failed = failed or state != "pass"
    raise SystemExit(1 if failed else 0)
