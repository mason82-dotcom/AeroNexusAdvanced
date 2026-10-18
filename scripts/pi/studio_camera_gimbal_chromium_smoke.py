#!/usr/bin/env python3
"""Real Chromium DOM test of actual AeroNexus Mission Studio camera/gimbal JS.

Uses unchanged HTML controls and exact controller functions from render_studio.
Runs in temporary local file:// origin with external network/DNS disabled.
Synthetic waypoint draft only. No service listener, secrets, DJI Cloud GET/write,
MQTT, KMZ upload, mission start, or production deployment.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from aeronexus.studio_page import render_studio

PASS = re.compile(r'<html\b[^>]*\bdata-camera-browser-smoke="PASS"', re.I)
MODEL_START = '<select id="mission-model">'
ACTION_START = '<section aria-labelledby="point-actions-title">'
ACTION_END = "</section>"
CONSTANT_START = "const WPML_ACTION_TYPES="
CONSTANT_END = "let mission=EMPTY()"
FUNCTION_START = "function actionControls()"
FUNCTION_END = "function redraw()"
APPLY_START = '  $("apply-point").addEventListener("click",()=>{'
APPLY_END = '  $("remove-point").addEventListener("click",'

# Actual browser DOM, not a fake JS DOM. All application handlers are extracted
# unchanged from render_studio() and called through click/change events.
HARNESS = r"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>Camera/Gimbal Studio DOM test</title></head>
<body>
<div id="test-editor">
  <label>Fluggerät __MODEL_SELECT__</label>
  <label>Breite<input id="point-lat" type="number" step="0.0000001"></label>
  <label>Länge<input id="point-lon" type="number" step="0.0000001"></label>
  <label>Foto<input id="point-photo" type="checkbox"></label>
  <button id="apply-point" type="button">Übernehmen</button>
  __ACTUAL_CONTROLS__
</div>
<script>
const $=id=>document.getElementById(id);
function els(tag,cls='',value){
  const el=document.createElement(tag);el.className=cls;
  if(value!==undefined)el.textContent=String(value);return el;
}
function cardText(parent,tag,cls,value){
  const el=els(tag,cls,value);parent.appendChild(el);return el;
}
const mission={
  drone_model:'mavic3e', close_route:false,
  waypoints:[
    {latitude:49.1533,longitude:8.58417,take_photo:true,actions:[]},
    {latitude:49.1535,longitude:8.5844,take_photo:false,actions:[]},
  ]
};
let selected=0,renderCount=0,historyCount=0;
let warnings=[];
function notice(text,error=false){warnings.push({text:String(text),error})}
function resolvedWaypoints(){return mission.waypoints}
function historyRecord(){++historyCount}
function redraw(){++renderCount;drawWaypointActions(mission.waypoints[selected]);actionControls()}
__STUDIO_CONSTANTS__
__STUDIO_HANDLERS__
__STUDIO_BINDINGS__
function check(ok,message){if(!ok)throw new Error(message)}
const choice=(name)=>{
  $('point-action-type').value=name;
  $('point-action-type').dispatchEvent(new Event('change',{bubbles:true}));
};
const model=(name)=>{
  $('mission-model').value=name;
  $('mission-model').dispatchEvent(new Event('change',{bubbles:true}));
};
const clickAdd=()=>$('point-action-add').click();
function run(){
  check($('point-action-list').children.length===0,'preloaded actions');
  check(historyCount===0,'unexpected initial write');
  model('mavic3ta');
  check($('point-action-add').disabled,'M3TA button not blocked');
  check($('point-action-support').textContent.includes('nicht ausdrücklich'),
        'missing explicit unsupported reason');
  for(const allowed of ['matrice4e','matrice4t','mavic3e','mavic3t','mavic3m']){
    model(allowed);check(!$('point-action-add').disabled,'allowed model blocked: '+allowed);
  }
  model('mavic3e');
  choice('focus');
  check(!$('point-focus-params').hidden,'focus controls invisible');
  check($('point-zoom-params').hidden,'zoom incorrectly shown');
  check($('point-pitch-params').hidden,'pitch incorrectly shown');
  $('point-focus-x').value='0.25';$('point-focus-y').value='0.75';
  clickAdd();
  check(mission.waypoints[0].actions[0].type==='focus','focus not added');
  check(mission.waypoints[0].actions[0].focus_x===0.25,'focus X lost');
  check($('point-action-list').textContent.includes('Punktfokus'),'focus not rendered');

  choice('zoom');
  check(!$('point-zoom-params').hidden,'zoom controls invisible');
  $('point-zoom-mm').value='35';clickAdd();
  check(mission.waypoints[0].actions[1].focal_length_mm===35,'zoom not added');
  choice('gimbalRotate');
  check(!$('point-pitch-params').hidden,'gimbal control invisible');
  $('point-pitch-deg').value='-45';clickAdd();
  check(mission.waypoints[0].actions[2].pitch_deg===-45,'gimbal not added');
  choice('gimbalEvenlyRotate');
  $('point-pitch-deg').value='-70';clickAdd();
  check(mission.waypoints[0].actions[3].type==='gimbalEvenlyRotate','segment gimbal missing');
  choice('startRecord');clickAdd();
  choice('stopRecord');clickAdd();
  check(mission.waypoints[0].actions.length===6,'missing video action');
  check($('point-action-list').querySelectorAll('button').length===6,'removal buttons missing');

  // Invalid numbers must not mutate the draft.
  choice('focus');$('point-focus-x').value='1.3';clickAdd();
  check(mission.waypoints[0].actions.length===6,'invalid focus accepted');
  choice('zoom');$('point-zoom-mm').value='0';clickAdd();
  check(mission.waypoints[0].actions.length===6,'invalid zoom accepted');
  choice('gimbalRotate');$('point-pitch-deg').value='15';clickAdd();
  check(mission.waypoints[0].actions.length===6,'invalid gimbal pitch accepted');
  check(warnings.filter(x=>x.error).length>=3,'missing validation feedback');

  // Existing edit handler must preserve action metadata with the {...p} copy.
  $('point-lat').value='49.154';
  $('point-lon').value='8.586';
  $('point-photo').checked=false;
  $('apply-point').click();
  check(mission.waypoints[0].latitude===49.154,'coordinate not updated');
  check(!mission.waypoints[0].take_photo,'photo flag not updated');
  check(mission.waypoints[0].actions.length===6,'coordinate edit discarded actions');

  // Remove by actual UI button, not by direct state mutation.
  $('point-action-list').querySelector('button').click();
  check(mission.waypoints[0].actions.length===5,'remove button did not remove');
  check(historyCount>=7,'undo history not recorded');

  // Model restrictions also guard direct function calls.
  model('mavic3ta');
  const before=mission.waypoints[0].actions.length;
  addWaypointAction();
  check(mission.waypoints[0].actions.length===before,'M3TA model gate bypassed');

  // A segment action is invalid when no next waypoint exists.
  model('mavic3e');selected=1;redraw();choice('gimbalEvenlyRotate');
  $('point-pitch-deg').value='-30';const old=mission.waypoints[1].actions.length;
  clickAdd();
  check(mission.waypoints[1].actions.length===old,'final waypoint segment accepted');

  // Render untrusted diagnostic text as textContent, never HTML.
  selected=0;
  const keep=mission.waypoints[0].actions;
  mission.waypoints[0].actions=[{type:'<img src=x onerror=alert(1)>'}];
  drawWaypointActions(mission.waypoints[0]);
  check(!$('point-action-list').querySelector('img'),'untrusted type executed as HTML');
  mission.waypoints[0].actions=keep;

  check(!('fetch' in window && window.__studioBrowserNetworkUsed),
        'unexpected network marker');
  return true;
}
try {
  if(run())document.documentElement.setAttribute('data-camera-browser-smoke','PASS');
} catch(error) {
  document.documentElement.setAttribute('data-camera-browser-smoke','FAIL');
  document.documentElement.setAttribute('data-camera-smoke-error',String(error.message).slice(0,120));
}
</script>
</body></html>"""


def browser_binary():
    configured = os.environ.get("AERONEXUS_CHROMIUM_BIN", "").strip()
    if configured:
        return shutil.which(configured)
    for binary in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(binary)
        if found:
            return found
    return None


def _section(text, start, end):
    begin = text.index(start)
    finish = text.index(end, begin + len(start))
    return text[begin:finish]


def build_fixture():
    source = render_studio()
    controls = _section(source, ACTION_START, ACTION_END) + ACTION_END
    models = _section(source, MODEL_START, "</select>") + "</select>"
    constants = _section(source, CONSTANT_START, CONSTANT_END)
    handlers = _section(source, FUNCTION_START, FUNCTION_END)
    apply = _section(source, APPLY_START, APPLY_END)
    # Bindings must be the actual event registrations from the Studio source.
    bindings = []
    for marker in (
        '$("point-action-type").addEventListener("change",actionControls);',
        '$("mission-model").addEventListener("change",actionControls);',
        '$("point-action-add").addEventListener("click",addWaypointAction);',
    ):
        if source.count(marker) != 1:
            raise RuntimeError("Camera/gimbal event binding changed")
        bindings.append(marker)
    if (not all(token in handlers for token in
                ("addWaypointAction", "drawWaypointActions", "historyRecord()"))
            or "actions" not in apply
            or "mission.waypoints[selected]={...p," not in apply):
        raise RuntimeError("Studio action semantics changed; fixture must be reviewed")
    for block in (models, controls, constants, handlers, apply):
        if "</script" in block.lower():
            raise RuntimeError("Unexpected script boundary in Studio UI")
    return (HARNESS.replace("__MODEL_SELECT__", models)
            .replace("__ACTUAL_CONTROLS__", controls)
            .replace("__STUDIO_CONSTANTS__", constants)
            .replace("__STUDIO_HANDLERS__", handlers + "\n" + apply)
            .replace("__STUDIO_BINDINGS__", "\n".join(bindings)))


def run_smoke(browser=None):
    executable = browser or browser_binary()
    if not executable:
        return 2
    try:
        html = build_fixture()
        with tempfile.TemporaryDirectory(prefix="aeronexus-camera-chromium-") as tmp:
            root = Path(tmp)
            path = root / "index.html"
            path.write_text(html, encoding="utf-8")
            command = [
                executable, "--headless=new", "--disable-gpu",
                "--disable-background-networking", "--disable-component-update",
                "--disable-extensions", "--disable-sync", "--no-first-run",
                "--no-default-browser-check", "--no-proxy-server",
                "--host-resolver-rules=MAP * 0.0.0.0",
                "--virtual-time-budget=3000",
                "--user-data-dir=" + str(root / "profile"),
                "--dump-dom", path.as_uri(),
            ]
            result = subprocess.run(
                command, capture_output=True, text=True,
                timeout=45, check=False,
            )
            return 0 if result.returncode == 0 and PASS.search(result.stdout) else 1
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
        return 1


def main():
    outcome = run_smoke()
    if outcome == 0:
        print("Studio Kamera/Gimbal Chromium DOM smoke: PASS (offline, echte UI-Handler)")
    elif outcome == 2:
        print("Studio Kamera/Gimbal Chromium DOM smoke: NOT RUN (Chromium fehlt)",
              file=sys.stderr)
    else:
        print("Studio Kamera/Gimbal Chromium DOM smoke: FAIL (Details unterdrueckt)",
              file=sys.stderr)
    return outcome


if __name__ == "__main__":
    raise SystemExit(main())
