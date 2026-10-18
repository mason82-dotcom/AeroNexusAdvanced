#!/usr/bin/env python3
"""Run real Chromium against the FULL rendered Mission Studio UI, offline.

Every original Studio element and inline handler remains intact. External
Leaflet is deliberately removed to verify graceful offline fallback; the
browser receives synthetic GET-only responses from a strict local fetch stub.
No production data, DJI write request, server socket or service restart.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from aeronexus.studio_page import render_studio


PASS = re.compile(r'<html\b[^>]*\bdata-studio-full-smoke="PASS"', re.I)
ERROR = re.compile(r'data-studio-full-error="([^"]{0,180})"', re.I)
CDN = re.compile(
    r'<script src="https://cdn\.jsdelivr\.net/npm/leaflet@1\.9\.4/dist/leaflet\.js"[^>]*></script>'
)
SCRIPT_START = '<script>\n"use strict";'
PAGE_END = "</body>"

PRELUDE = r"""<script>
"use strict";
window.__uiErrors=[];
window.__uiCalls=[];
window.addEventListener('error',event=>window.__uiErrors.push(String(event.message)));
window.addEventListener('unhandledrejection',event=>
  window.__uiErrors.push(String(event.reason?.message||event.reason)));
window.confirm=()=>false;
window.fetch=async function(path,opts={}){
  const url=String(path),method=String(opts.method||'GET').toUpperCase();
  window.__uiCalls.push(method+' '+url);
  if(method!=='GET' || !url.startsWith('/api/v1/'))
    throw Error('Non-readonly UI request prevented: '+method);
  let data;
  if(url==='/api/v1/studio/missions'){
    data={missions:[]};
  }else if(url==='/api/v1/studio/media'){
    data={media:[{id:'sample-video',name:'Synthetischer Testclip.mp4',
      mime:'video/mp4',size_bytes:1024,created_at:'2026-10-18T12:00:00Z'}]};
  }else if(url.startsWith('/api/v1/studio/dji-media?')){
    data={media:[{id:'sample-dji',name:'Synthetische DJI-Datei.mp4',
      mime:'video/mp4',size_bytes:4096,modified_at:'2026-10-18T12:00:00Z',
      previewable:false}],total:1,last_scanned_at:'2026-10-18T12:00:00Z'};
  }else if(url==='/api/v1/status/devices?limit=200'){
    data={total:1,devices:[{name:'Testdrohne',device_id:'SYNTHETIC-ONLY',
      kind:'aircraft',freshness:'current',online:true,
      telemetry:{battery_percent:70,gps_satellites:20}}]};
  }else if(url==='/api/v1/studio/geo-objects'){
    data={objects:[]};
  }else if(url==='/api/v1/studio/missions/reconciliation'){
    data={waylines:[{name:'Synthetische Cloud-Route',provider:'pilot2-local-cloud',
      wayline_id:'synthetic-only-route',device_model_key:'mavic3e',
      updated_at_ms:1792324800000}],missions:[],projects:[],
      local_pilot:{state:'connected',pagination_complete:true,updated_at:'2026-10-18T12:00:00Z'},
      coverage:{flighthub_cache_available:false}};
  }else if(url==='/api/v1/local-cloud/topology'){
    data={state:'connected',devices:[{role:'aircraft',
      serial_number:'SYNTHETIC-ONLY',callsign:'Testdrohne',
      device_model_key:'matrice4t',online:true}],links:[],
      updated_at:'2026-10-18T12:00:00Z'};
  }else if(url==='/api/v1/studio/pilot2/action-summary'){
    data={state:'connected',checked:1,total:1,recognized_actions:1,unknown_actions:0,
      identified_actions:0,unresolved_actions:0,
      read_only:true,wpml_semantics_verified:false,full_content_verified:false,
      flight_compatibility_verified:false,
      documented_types:[{name:'gimbalRotate',label:'Gimbal',
        occurrences:1,export_supported:true}],
      identified_types:[],anonymous_types:[],waylines:[{index:1}]};
  }else{
    throw Error('Unexpected mocked API request: '+url);
  }
  return new Response(JSON.stringify(data),
    {status:200,headers:{'Content-Type':'application/json'}});
};
</script>"""

CHECKS = r"""<script>
"use strict";
const uiCheck=(yes,why)=>{if(!yes)throw Error(why)};
const uiSleep=()=>new Promise(resolve=>setTimeout(resolve,0));
const uiClick=id=>{document.getElementById(id).click()};
const uiTab=id=>{
  const target=document.querySelector('nav button[data-tab="'+id+'"]');
  uiCheck(target,'missing navigation button: '+id);
  target.click();
  uiCheck(target.classList.contains('active'),'nav not selected: '+id);
  const pane=id==='geo-pane'?'map-pane':id;
  uiCheck(document.getElementById(pane).classList.contains('active'),
    'corresponding content not active: '+id);
  const side={ 'map-pane':'mission-panel','geo-pane':'geo-panel',
    'terrain-pane':'geo-panel','media-pane':'media-panel',
    'waylines-pane':'wayline-panel','fleet-pane':'fleet-panel'}[id];
  uiCheck(!document.getElementById(side).hidden,'matching controls hidden: '+id);
};
async function uiRun(){
  await uiSleep();await uiSleep();await uiSleep();
  uiCheck(window.__uiErrors.length===0,'startup script errors: '+window.__uiErrors.join(';'));
  uiCheck(document.querySelectorAll('nav button[data-tab]').length===6,
    'missing one of six primary tabs');
  uiCheck(document.getElementById('auth-message').textContent.includes('aktiv'),
    'synthetic workspace did not load');
  uiCheck(document.getElementById('gallery').textContent.includes('Synthetischer Testclip'),
    'media list not rendered');
  uiCheck(document.getElementById('fleet-grid').textContent.includes('Testdrohne'),
    'fleet list not rendered');
  uiCheck(document.getElementById('dji-media-gallery').textContent.includes('Synthetische DJI-Datei'),
    'DJI media not rendered');
  uiCheck(document.getElementById('map').textContent.includes('Leaflet'),
    'map unavailable fallback not visible');
  const secondary=['/status','/operations','/thermal','/multispectral','/results'];
  for(const href of secondary)
    uiCheck(document.querySelector('header nav a[href="'+href+'"]'),
      'missing linked module '+href);

  // Real click events must switch ALL tabs, with correct side panels.
  for(const id of ['map-pane','geo-pane','terrain-pane','media-pane',
    'waylines-pane','fleet-pane','map-pane'])uiTab(id);
  await uiSleep();await uiSleep();
  uiCheck(document.getElementById('wayline-grid').textContent.includes('Synthetische Cloud-Route'),
    'cloud route list not rendered');
  uiTab('waylines-pane');
  uiClick('pilot2-action-load');await uiSleep();await uiSleep();
  uiCheck(document.getElementById('pilot2-action-status').textContent.includes('1 Waylines geprüft'),
    'read-only action diagnostics did not render');
  uiTab('media-pane');
  uiCheck(document.getElementById('pilot2-action-results').children.length===0,
    'leaving waylines did not clear diagnostic view');

  // Search fields and refresh controls call only the synthetic GET API.
  document.getElementById('media-search').value='does-not-match';
  document.getElementById('media-search').dispatchEvent(new Event('input'));
  await uiSleep();
  uiCheck(document.getElementById('gallery').textContent.includes('Keine passenden'),
    'media search did not filter');
  document.getElementById('media-search').value='';
  document.getElementById('media-search').dispatchEvent(new Event('input'));
  await uiSleep();
  uiClick('refresh-media');uiClick('refresh-dji-media');await uiSleep();await uiSleep();
  uiClick('refresh-fleet');await uiSleep();
  uiTab('fleet-pane');uiClick('pilot2-topology-refresh');
  await uiSleep();await uiSleep();
  uiCheck(document.getElementById('pilot2-topology-grid').textContent.includes('Testdrohne'),
    'topology not rendered');

  // Map toolbar, expanded info and focus behavior with Leaflet blocked.
  uiTab('map-pane');
  uiClick('map-tools-toggle');
  uiCheck(document.getElementById('map-tools-toggle').getAttribute('aria-expanded')==='true',
    'map tools cannot expand');
  uiClick('map-info-toggle');
  uiCheck(document.getElementById('map-info-toggle').getAttribute('aria-expanded')==='false',
    'map info cannot collapse');
  uiClick('map-focus-toggle');
  uiCheck(document.body.classList.contains('map-focus-active'),'map focus cannot open');
  uiClick('map-focus-toggle');
  uiCheck(!document.body.classList.contains('map-focus-active'),'map focus cannot close');

  // Mission editing uses synthetic in-memory waypoints ONLY, no POST/PUT.
  mission.waypoints=[
    {latitude:49.1533,longitude:8.58417,take_photo:true,actions:[]},
    {latitude:49.1536,longitude:8.5845,take_photo:false,actions:[]}
  ];
  selected=0;redraw();historyReset();
  uiCheck(document.getElementById('point-count').textContent==='2',
    'point-list number incorrect');
  uiCheck(document.getElementById('route-legs').textContent==='1',
    'route analysis inaccurate');
  uiClick('insert-midpoint');
  uiCheck(mission.waypoints.length===3,'midpoint insertion failed');
  uiClick('undo-edit');
  uiCheck(mission.waypoints.length===2,'undo failed');
  uiClick('redo-edit');
  uiCheck(mission.waypoints.length===3,'redo failed');
  document.getElementById('point-action-type').value='gimbalRotate';
  document.getElementById('point-action-type').dispatchEvent(new Event('change'));
  document.getElementById('point-pitch-deg').value='-40';
  uiClick('point-action-add');
  uiCheck(mission.waypoints[selected].actions.length===1,'camera/gimbal editor failed');
  document.getElementById('point-lat').value='49.1538';
  document.getElementById('point-lon').value='8.5848';
  uiClick('apply-point');
  uiCheck(mission.waypoints[selected].actions[0].pitch_deg===-40,
    'coordinate editing lost camera/gimbal action');
  uiClick('remove-point');
  uiCheck(mission.waypoints.length===2,'point deletion failed');

  // Reorder controls, changes tracked in browser history.
  selected=0;redraw();
  const reorder=document.querySelector('#point-list .point-row button');
  uiCheck(!!reorder,'reorder control missing');
  const oldLatitude=mission.waypoints[0].latitude;
  // First up button disabled; the adjacent down button must be enabled.
  const down=document.querySelectorAll('#point-list .point-row')[0].querySelectorAll('button')[1];
  uiCheck(!down.disabled,'move-down unnecessarily disabled');
  down.click();
  uiCheck(mission.waypoints[1].latitude===oldLatitude,'reorder did not move point');

  // Read-only map is absent: verify Geo, CSV, 3D UI still works gracefully.
  uiTab('geo-pane');uiClick('geo-draw');
  uiCheck(document.getElementById('geo-draw').textContent.includes('beenden'),
    'Geo drawing mode not toggled');
  uiClick('geo-draw');
  uiCheck(document.getElementById('geo-draw').textContent.includes('Punkte'),
    'Geo drawing mode could not exit');
  uiClick('geo-reset');
  uiTab('terrain-pane');
  const tilt=document.getElementById('terrain-tilt');
  tilt.value='55';tilt.dispatchEvent(new Event('input'));
  uiCheck(document.getElementById('terrain-tilt-value').textContent.includes('55'),
    '3D viewer tilt control does not update');
  uiClick('terrain-reset-view');
  uiCheck(document.getElementById('terrain-tilt-value').textContent.includes('45'),
    '3D reset did not restore defaults');

  uiTab('map-pane');uiClick('open-csv');
  uiCheck(document.getElementById('csv-dialog').open,'CSV dialog did not open');
  uiClick('csv-close');
  uiCheck(!document.getElementById('csv-dialog').open,'CSV dialog did not close');
  uiClick('new-mission');
  // Confirmation is deliberately declined, so unsaved work MUST survive.
  uiCheck(mission.waypoints.length===2,
    'unsaved edits discarded despite decline confirmation');

  uiCheck(window.__uiErrors.length===0,
    'uncaught UI runtime error: '+window.__uiErrors.join(';'));
  uiCheck(window.__uiCalls.length>=6,'not enough real read-only GET code exercised');
  uiCheck(window.__uiCalls.every(x=>x.startsWith('GET /api/v1/')),
    'UI attempted unexpected method');
  return window.__uiCalls.length;
}
uiRun().then(count=>{
  document.documentElement.setAttribute('data-studio-full-smoke','PASS');
  document.documentElement.setAttribute('data-studio-full-gets',String(count));
}).catch(error=>{
  document.documentElement.setAttribute('data-studio-full-smoke','FAIL');
  document.documentElement.setAttribute('data-studio-full-error',
    String(error?.message||error).slice(0,180));
});
</script>"""


def build_fixture():
    source = render_studio()
    source, count = CDN.subn("", source)
    if count != 1 or source.count(SCRIPT_START) != 1:
        raise RuntimeError("Studio script boundary changed; review smoke harness")
    if source.count(PAGE_END) != 1:
        raise RuntimeError("Studio page body boundary changed")
    return source.replace(SCRIPT_START, PRELUDE + "\n" + SCRIPT_START, 1).replace(
        PAGE_END, CHECKS + "\n" + PAGE_END, 1
    )


def browser_binary():
    configured = os.environ.get("AERONEXUS_CHROMIUM_BIN", "").strip()
    if configured:
        return shutil.which(configured)
    for binary in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(binary)
        if found:
            return found
    return None


def run_smoke(*, width=1440, height=900):
    browser = browser_binary()
    if not browser:
        return "not_run", "browser unavailable"
    try:
        with tempfile.TemporaryDirectory(prefix="aeronexus-studio-full-ui-") as temp:
            path = Path(temp) / "index.html"
            path.write_text(build_fixture(), encoding="utf-8")
            args = [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
                    "--disable-dev-shm-usage", "--disable-background-networking",
                    "--disable-component-update", "--disable-extensions",
                    "--disable-sync", "--no-first-run", "--no-default-browser-check",
                    "--no-proxy-server", "--host-resolver-rules=MAP * 0.0.0.0",
                    "--window-size=" + str(width) + "," + str(height),
                    "--virtual-time-budget=7000",
                    "--user-data-dir=" + str(Path(temp) / "profile"),
                    "--dump-dom", path.as_uri()]
            completed = subprocess.run(
                args, capture_output=True, text=True, timeout=45, check=False
            )
            if completed.returncode != 0:
                return "fail", "chromium process exit " + str(completed.returncode)
            if PASS.search(completed.stdout):
                return "pass", "synthetic GET-only DOM interactions passed"
            failure = ERROR.search(completed.stdout)
            return "fail", failure.group(1) if failure else "DOM result marker absent"
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return "fail", type(exc).__name__


def main():
    outcomes = [(label, *run_smoke(width=w, height=h)) for label, w, h in (
        ("Desktop", 1440, 900), ("Mobile", 420, 860)
    )]
    for label, status, info in outcomes:
        print("Full Studio Chromium UI / " + label + ": " +
              status.upper() + " (" + info + ")")
    if all(item[1] == "pass" for item in outcomes):
        return 0
    if all(item[1] == "not_run" for item in outcomes):
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
