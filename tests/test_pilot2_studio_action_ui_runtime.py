"""Exercise the exact Studio action readout JavaScript in a minimal Node DOM.

This tests rendering, opt-in fetch, no HTML interpretation, and cancellation.
It does not claim a real Chrome, HTTPS, or production deployment acceptance.
"""
import shutil
import subprocess

import pytest

from aeronexus.studio_page import render_studio


_NODE = r"""
const fs=require('node:fs');
const assert=require('node:assert/strict');
const js=fs.readFileSync(0,'utf8');
const nodes=new Map(), calls=[];
const element=(tag='div')=>({
  tag,children:[],disabled:false,textContent:'',className:'',
  replaceChildren(...xs){this.children=xs},
  appendChild(el){this.children.push(el);return el}
});
const $=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)};
const els=(tag,cls,text)=>{
  const el=element(tag);
  el.className=cls||'';
  if(text!==undefined)el.textContent=String(text);
  return el;
};
const cardText=(parent,tag,cls,text)=>{
  const el=els(tag,cls,text);
  parent.appendChild(el);return el;
};
const clean=v=>v===null||v===undefined?'–':String(v);
const errorMessage=e=>'SAFE-ERROR: '+String(e.message||'Unknown');
let respond=async()=>{throw Error('no response configured')};
const api=(path,opts)=>{
  assert.equal(path,'/api/v1/studio/pilot2/action-summary');
  assert.ok(opts.signal);
  calls.push({path,signal:opts.signal});
  return respond(opts.signal);
};
const factory=new Function('$','els','cardText','api','clean','errorMessage',js+
  '\nreturn {loadPilot2ActionSummary,clearPilot2ActionSummary};');
const view=factory($,els,cardText,api,clean,errorMessage);
const base=()=>({
 state:'connected',checked:8,total:8,recognized_actions:70,
 unknown_actions:579,read_only:true,
 flight_compatibility_verified:false,wpml_semantics_verified:false,
 full_content_verified:false,
 anonymous_types:[{alias:'A02',occurrences:369,file_count:7,
   triggers:{betweenAdjacentPoints:369}}],
 waylines:Array.from({length:8},(_,i)=>({index:i+1}))
});
(async()=>{
 assert.equal(calls.length,0,'no fetch on initial render');
 respond=async()=>({json:async()=>base()});
 await view.loadPilot2ActionSummary();
 assert.equal(calls.length,1);
 assert.equal($('pilot2-action-load').disabled,false);
 assert.match($('pilot2-action-status').textContent,/8 Waylines geprüft/);
 assert.match($('pilot2-action-status').textContent,/579/);
 const list=$('pilot2-action-results');
 assert.equal(list.children.length,2);
 assert.equal(list.children[0].children[0].textContent,'A02');
 assert.match(list.children[0].children[2].textContent,/betweenAdjacentPoints: 369/);
 // DOM input is textContent, never an interpreted HTML fragment.
 const hostile='<img src=x onerror=PRIVATE_SCRIPT>';
 respond=async()=>({json:async()=>({
   ...base(),anonymous_types:[{alias:hostile,occurrences:1,file_count:1,
   triggers:{reachPoint:1}}]})});
 await view.loadPilot2ActionSummary();
 assert.equal(list.children[0].children[0].textContent,hostile);
 assert.equal(list.children[0].children[0].children.length,0);

 // Never render an invalid compatibility claim.
 respond=async()=>({json:async()=>({
   ...base(),flight_compatibility_verified:true})});
 await view.loadPilot2ActionSummary();
 assert.equal(list.children.length,0);
 assert.match($('pilot2-action-status').textContent,/SAFE-ERROR/);
 assert.equal($('pilot2-action-load').disabled,false);
 // A compromised or outdated API must never show a partial library as complete.
 for(const mutation of [
   {full_content_verified:true},{full_content_verified:null},
   {checked:7},{total:9},{waylines:[]},
   {recognized_actions:-1},{unknown_actions:'579'}
 ]){
   respond=async()=>({json:async()=>({...base(),...mutation})});
   await view.loadPilot2ActionSummary();
   assert.equal(list.children.length,0);
   assert.match($('pilot2-action-status').textContent,/SAFE-ERROR/);
   assert.equal($('pilot2-action-load').disabled,false);
 }

 // Simulate leaving the tab after response headers but before JSON is ready.
 let resolveResponse;
 respond=()=>new Promise(resolve=>{resolveResponse=resolve});
 const pending=view.loadPilot2ActionSummary();
 assert.equal($('pilot2-action-load').disabled,true);
 view.clearPilot2ActionSummary();
 assert.equal($('pilot2-action-load').disabled,false);
 assert.equal($('pilot2-action-results').children.length,0);
 assert.equal(calls[calls.length-1].signal.aborted,true);
 resolveResponse({json:async()=>base()});
 await pending;
 assert.equal($('pilot2-action-results').children.length,0);
 assert.match($('pilot2-action-status').textContent,/Nur nach Klick/);

 // Old request must not overwrite a new generation.
 let releaseOld;
 respond=()=>new Promise(resolve=>{releaseOld=resolve});
 const first=view.loadPilot2ActionSummary();
 view.clearPilot2ActionSummary();
 respond=async()=>({json:async()=>base()});
 await view.loadPilot2ActionSummary();
 assert.equal(list.children[0].children[0].textContent,'A02');
 releaseOld({json:async()=>({...base(),unknown_actions:12345})});
 await first;
 assert.match($('pilot2-action-status').textContent,/579/);
 assert.doesNotMatch($('pilot2-action-status').textContent,/12345/);
 assert.equal($('pilot2-action-load').disabled,false);
 console.log('Pilot 2 action Studio DOM runtime passed');
})().catch(e=>{console.error(e);process.exitCode=1});
"""


def test_pilot2_action_actual_studio_js_dom_runtime():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js unavailable")
    page = render_studio()
    begin = page.index("let pilot2ActionController=null")
    end = page.index("function waylineSourceState(", begin)
    js = page[begin:end]
    assert "loadPilot2ActionSummary" in js
    assert "innerHTML" not in js
    result = subprocess.run(
        [node, "-e", _NODE], input=js, text=True,
        capture_output=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_ui_diagnostic_is_explicit_opt_in_and_tab_switch_clears():
    page = render_studio()
    assert 'id="pilot2-action-load"' in page
    assert 'if(id!=="waylines-pane")clearPilot2ActionSummary();' in page
    assert '$("pilot2-action-load").addEventListener("click"' in page
    assert 'await api("/api/v1/studio/pilot2/action-summary"' in page
    assert 'method:"POST"' not in page[
        page.index("let pilot2ActionController=null"):
        page.index("function waylineSourceState(")
    ]



def test_studio_actions_do_not_enable_flight_or_write_controls():
    page = render_studio()
    section = page[page.index("async function loadPilot2ActionSummary()"):
                   page.index("function waylineSourceState(")]
    assert "identified_types" in section
    assert "export_supported" not in section or "Flugkompatibilität" in section
    assert 'method:"POST"' not in section
    assert "innerHTML" not in section
