#!/usr/bin/env python3
"""Real Chromium DOM acceptance across six original AeroNexus standalone views.

Each full HTML page runs unchanged with a defensive synthetic GET-only response
that reports offline unavailability. The smoke exercises navigation, filters,
view switches and graceful failures, not positive media/SDK interaction.
Never contacts a service, private file, DJI/MinIO or any writable API.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from aeronexus.operations_page import render_operations
from aeronexus.thermal_page import render_thermal_page
from aeronexus.multispectral_page import render_multispectral_page
from aeronexus.results_page import render_results_page
from aeronexus.dji_media_page import render_dji_media_page
from aeronexus.status_page import render_page

PAGES = {
    "operations": render_operations,
    "thermal": render_thermal_page,
    "multispectral": render_multispectral_page,
    "results": render_results_page,
    "media": render_dji_media_page,
    "status": lambda: render_page(30),
}

EXTERNAL_LEAFLET = re.compile(
    r'<script src="https://cdn\.jsdelivr\.net/npm/leaflet@1\.9\.4/dist/leaflet\.js"[^>]*></script>'
)
PASS = re.compile(r'<html\b[^>]*\bdata-standalone-ui="PASS"', re.I)
ISSUE = re.compile(r'data-standalone-error="([^"]{0,180})"', re.I)
ORIGINAL_SCRIPT = "<script>"

PRELUDE = r"""<script>
"use strict";
window.__uiErrors=[];
window.__uiReads=0;
window.__uiWriteAttempts=[];
window.__uiBoundClickIds=new Set();
const registerClick=Element.prototype.addEventListener;
Element.prototype.addEventListener=function(event,callback,options){
  if(event==='click'&&this.id&&this.tagName==='BUTTON')
    window.__uiBoundClickIds.add(this.id);
  return registerClick.call(this,event,callback,options);
};
window.addEventListener('error',e=>window.__uiErrors.push(String(e.message)));
window.addEventListener('unhandledrejection',e=>
  window.__uiErrors.push(String(e.reason?.message||e.reason)));
window.fetch=async(path,opts={})=>{
  const text=String(path),method=String(opts.method||'GET').toUpperCase();
  if(method!=='GET'){
    window.__uiWriteAttempts.push(method);
    throw Error('No write permitted in offline UI acceptance');
  }
  if(!text.startsWith('/api/v1/'))
    throw Error('Non-API resource blocked: '+text.slice(0,120));
  window.__uiReads++;
  // Deliberately simulate a harmless private backend outage. Real scripts
  // must recover by rendering their accessible failure state.
  return new Response(JSON.stringify({detail:'Synthetisch: keine Live-Daten'}),
    {status:503,headers:{'Content-Type':'application/json'}});
};
window.confirm=()=>false;
</script>"""

PROBE = r"""<script>
"use strict";
const mod=__MODULE__;
const check=(ok,why)=>{if(!ok)throw Error(why)};
const $test=id=>document.getElementById(id);
const click=id=>{const b=$test(id);check(!!b,'button missing: '+id);b.click()};
const tick=()=>new Promise(done=>setTimeout(done,0));
async function run(){
  await tick();await tick();await tick();
  if(mod!=='status')
    check(document.querySelectorAll('nav a[href]').length>=2,
      'module navigation missing');
  const btns=[...document.querySelectorAll('button[id]')];
  const unwired=btns.filter(b=>!window.__uiBoundClickIds.has(b.id)&&
    typeof b.onclick!=='function').map(b=>b.id);
  check(unwired.length===0,'buttons without handlers: '+unwired.join(','));
  check(window.__uiReads>0,'module did not issue a read-only GET');
  if(mod==='operations'){
    click('tasks-finished');click('tasks-in-progress');click('tasks-all');
    check($test('tasks-all').classList.contains('active'),'task filter did not switch');
    click('refresh-now');
    check($test('connection').textContent.length>5,'operations status not visible');
  }else if(mod==='thermal'){
    click('tab-flights');check($test('tab-flights').getAttribute('aria-selected')==='true',
      'thermal flights tab inactive');
    click('tab-images');check($test('tab-images').getAttribute('aria-selected')==='true',
      'thermal images tab inactive');
    $test('range-mode').value='manual';
    $test('range-mode').dispatchEvent(new Event('change'));
    check(!$test('manual-range').hidden,'thermal manual range hidden');
    click('tool-box');check($test('tool-box').getAttribute('aria-pressed')==='true',
      'thermal region tool not selected');
    click('search-go');
  }else if(mod==='multispectral'){
    click('view-map');click('view-image');
    click('tool-box');
    check($test('layer')!==null,'multispectral layer control missing');
  }else if(mod==='results'){
    click('refresh');
    $test('query').value='sample';
    click('clear');
    check($test('query').value==='','result search cannot be cleared');
    check($test('controls').disabled,'result controls enabled without raster');
  }else if(mod==='media'){
    $test('search').value='sample';
    click('filter');click('refresh');
    check($test('photo-state').textContent.length>8,
      'photo offline feedback absent');
  }else if(mod==='status'){
    check($test('timestamp').textContent.includes('nicht erreichbar'),
      'status offline fallback not visible');
    check($test('cloud-overall').textContent.length>8,
      'cloud status offline fallback absent');
  }
  await tick();await tick();
  check(window.__uiWriteAttempts.length===0,'write API attempted');
  check(window.__uiErrors.length===0,
    'uncaught browser errors: '+window.__uiErrors.join('; '));
  return [btns.length,window.__uiReads];
}
run().then(([n,reads])=>{
  document.documentElement.setAttribute('data-standalone-ui','PASS');
  document.documentElement.setAttribute('data-standalone-buttons',String(n));
  document.documentElement.setAttribute('data-standalone-reads',String(reads));
}).catch(err=>{
  document.documentElement.setAttribute('data-standalone-ui','FAIL');
  document.documentElement.setAttribute('data-standalone-error',
    String(err?.message||err).slice(0,180));
});
</script>"""


def fixture(name):
    if name not in PAGES:
        raise ValueError("Unknown standalone module")
    html = PAGES[name]()
    html = EXTERNAL_LEAFLET.sub("", html)
    if html.count(ORIGINAL_SCRIPT) != 1 or html.count("</body>") != 1:
        raise RuntimeError("Unexpected module inline script structure: " + name)
    return html.replace(ORIGINAL_SCRIPT, PRELUDE + "\n" + ORIGINAL_SCRIPT, 1).replace(
        "</body>", PROBE.replace("__MODULE__", repr(name)) + "\n</body>", 1
    )


def browser_binary():
    chosen = os.environ.get("AERONEXUS_CHROMIUM_BIN", "").strip()
    if chosen:
        return shutil.which(chosen)
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    return None


def run_module(name, width=1440, height=900):
    chromium = browser_binary()
    if not chromium:
        return "not_run", "browser unavailable"
    try:
        with tempfile.TemporaryDirectory(prefix="aeronexus-standalone-ui-") as root:
            path = Path(root) / "module.html"
            path.write_text(fixture(name), encoding="utf-8")
            cmd = [
                chromium, "--headless=new", "--disable-gpu", "--no-sandbox",
                "--disable-dev-shm-usage", "--disable-background-networking",
                "--disable-component-update", "--disable-extensions",
                "--disable-sync", "--no-first-run", "--no-default-browser-check",
                "--no-proxy-server", "--host-resolver-rules=MAP * 0.0.0.0",
                "--window-size=" + str(width) + "," + str(height),
                "--virtual-time-budget=1800",
                "--user-data-dir=" + str(Path(root) / "profile"),
                "--dump-dom", path.as_uri(),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=35, check=False)
            if result.returncode != 0:
                return "fail", "chromium exit " + str(result.returncode)
            if PASS.search(result.stdout):
                return "pass", "original UI handlers, offline failure state"
            issue = ISSUE.search(result.stdout)
            return "fail", issue.group(1) if issue else "DOM result marker missing"
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        return "fail", type(exc).__name__


def main():
    failed = False
    for page in PAGES:
        for label, width, height in (("Desktop", 1440, 900), ("Mobile", 420, 860)):
            status, detail = run_module(page, width=width, height=height)
            print(page + " / " + label + ": " + status.upper() + " (" + detail + ")")
            if status != "pass":
                failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
