"""Execute the actual CSV editor flow, including delayed responses and undo."""
import re
import shutil
import subprocess

import pytest

from aeronexus.studio_page import render_studio


_JS = r'''
const fs=require("node:fs"),assert=require("node:assert/strict");
const source=fs.readFileSync(0,"utf8").replace("\nwire();\nloadWorkspace();", "");
const nodes=new Map();
let focused=null,requests=[],reply=async()=>({ok:true,json:async()=>valid()});
class Element {
  set value(v){this._value=String(v);}
  get value(){return this._value;}
  constructor(tag="div"){this.tagName=tag.toUpperCase();this.value="";this.checked=false;
    this.children=[];this.textContent="";this.files=[];this.disabled=false;this.hidden=false;
    this.attrs={};this.style={};this.classList={toggle(){},add(){},remove(){}};}
  appendChild(el){this.children.push(el);return el;}
  append(...els){this.children.push(...els);}
  replaceChildren(...els){this.children=els;}
  addEventListener(){}
  setAttribute(k,v){this.attrs[k]=v;}
  removeAttribute(k){delete this.attrs[k];}
  focus(){focused=this;}
  showModal(){this.open=true;}
  close(){this.open=false;}
}
const document={getElementById(id){if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id)},
  createElement:tag=>new Element(tag),querySelectorAll:()=>[],body:new Element("body")};
const window={};
const fetch=async(path,options)=>{requests.push({path,options});return reply(path,options)};
const factory=new Function("document","window","fetch",source+`
syncForm();historyReset();
return {openCsvImport,previewCsv,applyCsv,csvInvalidate,csvMoreRows,undoEdit,redoEdit,editorDirty,
  historyRecord,historySaved,editorSnapshot,editorSignature,
  get mission(){return mission},get id(){return missionId},
  get preview(){return csvPreview},get signature(){return editorSignature(editorSnapshot())},
  savedId(){missionId="saved-mission"},
  setMission(v){mission=v;syncForm();redraw();historyReset()}};
`);
const ui=factory(document,window,fetch),el=id=>document.getElementById(id);
const point=(n=0)=>({latitude:49.1533+n/100000,longitude:8.58417,take_photo:n%2===0});
function valid(count=2){const waypoints=Array.from({length:count},(_,n)=>point(n));
  return {valid:true,waypoints,rows:waypoints.map((p,n)=>({line:n+2,...p})),errors:[],error_count:0};}
function selectFile(){el("csv-file").files=[{size:90}];el("csv-delimiter").value="semicolon";
  el("csv-decimal").value="dot";}
async function flush(){await new Promise(resolve=>setImmediate(resolve));}
(async()=>{
  ui.savedId();
  el("mission-name").value="Ungespeicherter Name";
  el("mission-altitude").value="42";
  ui.historyRecord();
  const before=ui.signature;
  ui.openCsvImport();
  await ui.previewCsv();
  assert.match(el("csv-message").textContent,/auswählen/);
  assert.equal(requests.length,0);
  selectFile();
  await ui.previewCsv();
  assert.equal(ui.signature,before); // preview is never a mutation
  assert.equal(ui.id,"saved-mission");
  assert.equal(el("csv-apply").disabled,false);
  assert.equal(el("csv-rows").children.length,2);
  assert.match(el("csv-map-message").textContent,/nicht verfügbar/);
  assert.match(requests[0].path,/preview.csv\?delimiter=semicolon&decimal=dot&close_route=false/);
  ui.applyCsv();
  assert.deepEqual(ui.mission.waypoints,[point(0),point(1)]);
  assert.equal(el("mission-name").value,"Ungespeicherter Name");
  assert.equal(el("mission-altitude").value,"42");
  assert.equal(ui.id,"saved-mission");
  assert.equal(ui.editorDirty(),true);
  assert.equal(requests.length,1); // applying must not POST a mission
  ui.undoEdit();assert.equal(ui.signature,before);
  ui.redoEdit();assert.equal(ui.mission.waypoints.length,2);
  ui.csvInvalidate();assert.equal(ui.preview,null);

  reply=async()=>({ok:true,json:async()=>valid(120)});
  await ui.previewCsv();
  assert.equal(el("csv-rows").children.length,50);
  ui.csvMoreRows();ui.csvMoreRows();
  assert.equal(el("csv-rows").children.length,120);
  assert.equal(el("csv-more").hidden,true);
  const beforeStale=ui.signature;
  el("mission-speed").value="6";ui.historyRecord();
  ui.applyCsv();
  assert.equal(ui.preview,null);assert.match(el("csv-message").textContent,/erneut prüfen/);
  assert.equal(ui.mission.waypoints.length,2);

  reply=async()=>({ok:true,json:async()=>({valid:false,errors:[
    {line:3,column:"latitude",message:"Wert ungültig"}],error_count:1,waypoints:[],rows:[]})});
  await ui.previewCsv();
  assert.equal(el("csv-apply").disabled,true);
  assert.equal(el("csv-errors").children.length,1);
  assert.match(el("csv-errors").children[0].textContent,/Zeile 3.*latitude/);
  assert.equal(focused,el("csv-message"));
  assert.equal(el("csv-file").files.length,1);

  reply=async()=>{throw new TypeError("Failed to fetch")};
  await ui.previewCsv();
  assert.match(el("csv-message").textContent,/Netzwerkfehler/);
  assert.equal(el("csv-check").disabled,false);
  assert.equal(el("csv-apply").disabled,true);

  // A format change during a request invalidates even a response ignoring abort.
  let release;
  reply=()=>new Promise(resolve=>{release=resolve});
  const pending=ui.previewCsv();await flush();
  assert.equal(el("csv-check").disabled,true);
  const signal=requests.at(-1).options.signal;
  ui.csvInvalidate("Format geändert.");
  assert.equal(signal.aborted,true);
  release({ok:true,json:async()=>valid()});await pending;
  assert.equal(ui.preview,null);assert.equal(el("csv-apply").disabled,true);
  assert.equal(el("csv-message").textContent,"Format geändert.");

  // Failure while decoding the body must also be stale-safe.
  let finishJson;
  reply=async()=>({ok:true,json:()=>new Promise(resolve=>{finishJson=resolve})});
  const bodyPending=ui.previewCsv();await flush();ui.csvInvalidate("Geschlossen.");
  finishJson(valid());await bodyPending;
  assert.equal(ui.preview,null);assert.equal(el("csv-message").textContent,"Geschlossen.");

  reply=async()=>{const error=new Error("timeout");error.name="AbortError";throw error};
  await ui.previewCsv();assert.match(el("csv-message").textContent,/Zeitlimit/);
  assert.equal(el("csv-check").disabled,false);
  console.log("CSV UI: preview, replace, undo, pagination, errors, cancellation and stale responses OK");
})().catch(error=>{console.error(error);process.exitCode=1});
'''


def test_csv_editor_runtime():
    if not shutil.which("node"):
        pytest.skip("Node is required for browser-JavaScript runtime checks")
    script = re.findall(r"<script>(.*?)</script>", render_studio(), re.S)[0]
    result = subprocess.run(["node", "-e", _JS], input=script, text=True,
                            capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
