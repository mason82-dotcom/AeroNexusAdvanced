#!/usr/bin/env python3
"""Real Chromium DOM smoke for the Studio Pilot 2 action summary, offline.

Reads the exact action UI JavaScript from render_studio(), embeds it into a
minimal HTML fixture and runs a real Chromium DOM. All responses are synthetic.
No server, HTTPS listener, production deployment, cloud GET, MQTT or DJI writes.
This is NOT acceptance of the deployed HTTPS Studio endpoint.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from aeronexus.studio_page import render_studio


START = "let pilot2ActionController=null"
END = "function waylineSourceState("
RESULT_PATTERN = re.compile(r'<html\b[^>]*\bdata-pilot2-browser-smoke="PASS"', re.I)

HARNESS = r"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>Isolated Pilot 2 DOM smoke</title></head>
<body>
<button id="pilot2-action-load">Aktionsdiagnose laden</button>
<p id="pilot2-action-status">Nur nach Klick: keine automatischen KMZ-Abrufe.</p>
<div id="pilot2-action-results"></div>
<script>
const $ = id => document.getElementById(id);
function els(tag, cls='', value) {
  const el=document.createElement(tag);
  el.className=cls;
  if(value!==undefined)el.textContent=String(value);
  return el;
}
function cardText(parent,tag,cls,value) {
  const child=els(tag,cls,value);parent.appendChild(child);return child;
}
function clean(v){return v===null||v===undefined?'–':String(v)}
function errorMessage(_err){return 'SAFE-ERROR'}
let requests=0, lastSignal=null;
let responder=async()=>{throw Error('no mock configured')};
async function api(path, options) {
  if(path!=='/api/v1/studio/pilot2/action-summary')throw Error('wrong route');
  if(!options || !options.signal)throw Error('missing AbortSignal');
  ++requests;lastSignal=options.signal;
  return responder(options.signal);
}
__STUDIO_JS__
const button=$('pilot2-action-load'), list=$('pilot2-action-results');
button.addEventListener('click',()=>loadPilot2ActionSummary());
const base=()=>({
  state:'connected',checked:8,total:8,recognized_actions:70,
  unknown_actions:579,read_only:true,wpml_semantics_verified:false,
  flight_compatibility_verified:false,full_content_verified:false,
  anonymous_types:[{alias:'A02',occurrences:369,file_count:7,
    triggers:{betweenAdjacentPoints:369}}],
  waylines:Array.from({length:8},(_,i)=>({index:i+1}))
});
function check(ok, code){if(!ok)throw Error(code)}
async function tick(){await new Promise(resolve=>setTimeout(resolve,0))}
async function run() {
  check(requests===0,'unexpected automatic GET');
  check(list.children.length===0,'unexpected cards on load');
  responder=async()=>({json:async()=>base()});
  button.click();
  await tick();
  check(requests===1,'click did not issue exactly one GET');
  check(button.disabled===false,'button not released');
  check(list.querySelectorAll('article').length===1,'missing anonymous card');
  check(list.querySelector('h2')?.textContent==='A02','wrong alias');
  check($('pilot2-action-status').textContent.includes('8 Waylines geprüft'),'wrong total');
  check($('pilot2-action-status').textContent.includes('579'),'wrong unknown count');

  // Untrusted text must remain text, not parsed browser DOM.
  const hostile='<img src=x onerror=window.__pilot2Xss=1>';
  responder=async()=>({json:async()=>({
    ...base(),anonymous_types:[{alias:hostile,occurrences:1,file_count:1,
      triggers:{reachPoint:1}}]
  })});
  await loadPilot2ActionSummary();
  check(list.querySelector('h2')?.textContent===hostile,'text escaped incorrectly');
  check(list.querySelectorAll('img').length===0,'HTML injection reached DOM');
  check(window.__pilot2Xss===undefined,'HTML handler executed');

  // UI must fail closed even if an upstream contract is bypassed.
  for(const mutation of [
    {read_only:false},{wpml_semantics_verified:true},
    {flight_compatibility_verified:true},{full_content_verified:true},
    {full_content_verified:null},{checked:7},{checked:0},{total:9},
    {waylines:[]},{recognized_actions:-1},{unknown_actions:'579'}
  ]){
    responder=async()=>({json:async()=>({...base(),...mutation})});
    await loadPilot2ActionSummary();
    check(list.children.length===0,'invalid response rendered');
    check($('pilot2-action-status').textContent==='SAFE-ERROR','invalid response accepted');
    check(button.disabled===false,'button stuck after error');
  }

  // Tab departure aborts pending requests and prevents stale responses.
  let resolveOld;
  responder=()=>new Promise(resolve=>{resolveOld=resolve});
  const old=loadPilot2ActionSummary();
  check(button.disabled===true,'in-flight button enabled');
  const oldSignal=lastSignal;
  clearPilot2ActionSummary();
  check(oldSignal.aborted===true,'request not aborted');
  check(list.children.length===0,'cards remain after clear');
  responder=async()=>({json:async()=>base()});
  await loadPilot2ActionSummary();
  resolveOld({json:async()=>({...base(),unknown_actions:12345})});
  await old;
  check($('pilot2-action-status').textContent.includes('579'),'old result replaced current');
  check(!$('pilot2-action-status').textContent.includes('12345'),'old count shown');
  check(button.disabled===false,'button stuck after cancellation');
}
run().then(()=>{
  document.documentElement.setAttribute('data-pilot2-browser-smoke','PASS');
}).catch(()=>{
  document.documentElement.setAttribute('data-pilot2-browser-smoke','FAIL');
});
</script></body></html>"""


def browser_binary():
    configured = os.environ.get("AERONEXUS_CHROMIUM_BIN", "").strip()
    if configured:
        found = shutil.which(configured)
        return found if found else None
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    return None


def build_fixture():
    page = render_studio()
    start = page.index(START)
    end = page.index(END, start)
    block = page[start:end]
    if ("loadPilot2ActionSummary" not in block or
            "innerHTML" in block or "</script" in block.lower()):
        raise RuntimeError("unexpected Studio script boundary")
    return HARNESS.replace("__STUDIO_JS__", block)


def run_smoke(browser=None):
    executable = browser or browser_binary()
    if not executable:
        return 2
    try:
        fixture = build_fixture()
        with tempfile.TemporaryDirectory(prefix="aeronexus-chromium-check-") as directory:
            root = Path(directory)
            page = root / "index.html"
            page.write_text(fixture, encoding="utf-8")
            command = [
                executable, "--headless=new", "--disable-gpu",
                "--disable-background-networking", "--disable-component-update",
                "--disable-extensions", "--disable-sync", "--no-first-run",
                "--no-default-browser-check", "--no-proxy-server",
                "--host-resolver-rules=MAP * 0.0.0.0",
                "--virtual-time-budget=5000",
                "--user-data-dir=" + str(root / "profile"),
                "--dump-dom", page.as_uri(),
            ]
            process = subprocess.run(
                command, capture_output=True, text=True,
                timeout=45, check=False,
            )
            if process.returncode != 0:
                return 1
            return 0 if RESULT_PATTERN.search(process.stdout) else 1
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        return 1


def main():
    result = run_smoke()
    if result == 0:
        print("Pilot 2 Studio Chromium DOM smoke: PASS (offline, synthetic API)")
    elif result == 2:
        print("Pilot 2 Studio Chromium DOM smoke: NOT RUN (browser not found)", file=sys.stderr)
    else:
        print("Pilot 2 Studio Chromium DOM smoke: FAIL (details suppressed)", file=sys.stderr)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
