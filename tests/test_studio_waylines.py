"""The read-only library must not turn metadata hints into editable missions."""
import shutil
import subprocess

import pytest

from aeronexus.studio_page import render_studio


def test_cloud_library_is_accessible_read_only_and_separate_from_editor():
    page = render_studio()
    for item in ("waylines-pane", "wayline-panel", "wayline-search", "wayline-source", "wayline-grid",
                 "wayline-state", "refresh-waylines", "clear-wayline-search", "wayline-prev", "wayline-next"):
        assert f'id="{item}"' in page
    assert 'data-tab="waylines-pane"' in page
    assert 'for="wayline-search"' in page and 'for="wayline-source"' in page
    assert "Der offene Studio-Entwurf bleibt unverändert" in page
    assert "Keine Bearbeitung und keine Flugfreigabe" in page
    assert "Vorschau auf Karte (nur lesen)" in page
    logic = page[page.index("// Read-only library:"):page.index("function switchTab(id)")]
    assert "innerHTML" not in logic
    assert "saveMission" not in logic and "importMission" not in logic
    assert "/export.kmz" not in logic


def test_cloud_library_javascript_state_and_response_ordering():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable")
    page = render_studio()
    logic = page[page.index("// Read-only library:"):page.index("function switchTab(id)")]
    program = r"""
const fs=require('node:fs'),assert=require('node:assert/strict');
const code=fs.readFileSync(0,'utf8');
const nodes=new Map();
const $=id=>{if(!nodes.has(id))nodes.set(id,{value:id==='wayline-source'?'all':'',textContent:'',children:[],disabled:false,
 replaceChildren(){this.children=[]},appendChild(v){this.children.push(v)},setAttribute(k,v){this[k]=v}});return nodes.get(id)};
const els=(tag,cls,text)=>({tag,className:cls,textContent:text,children:[],appendChild(v){this.children.push(v)}});
let handler=async()=>({json:async()=>fixture});
const api=async(...args)=>handler(...args);
const lib=new Function('$','els','api','errorMessage','clean',code+
 '\nreturn {loadWaylines,renderWaylines,waylineModel,waylineType,waylineTime,waylineSourceState,waylineCheck,'+
 'setData(d){waylineData=d},data(){return waylineData},setPage(p){waylinePage=p}};')($,els,api,e=>e.message,v=>v??'–');
const routes=Array.from({length:14},(_,i)=>({provider:'pilot2-local-cloud',project_id:'scope',wayline_id:String(i),
 name:'Route '+i,device_model_key:'0-77-0',template_types:['mapping_2d'],updated_at_ms:1790885465345}));
const candidate=(id,match)=>({...routes[id],model_match:match});
const fixture={waylines:routes,missions:[{candidates:[candidate(1,false),candidate(2,true),candidate(3,true)]},
 {candidates:[candidate(3,true)]}],local_pilot:{state:'connected',pagination_complete:true},coverage:{flighthub_cache_available:false},projects:[]};
(async()=>{
 assert.equal(lib.waylineModel('0-77-3'),'Mavic 3TA');
 assert.match(lib.waylineType({template_type_codes:[5]}),/Code 5/);
 assert.equal(lib.waylineTime({updated_at_ms:1790885465000}),lib.waylineTime({updated_at:1790885465}));
 assert.equal(lib.waylineTime({updated_at_ms:NaN}),'nicht übermittelt');
 lib.setData(fixture);lib.renderWaylines();assert.equal($('wayline-grid').children.length,12);
 assert.equal($('wayline-next').disabled,false);lib.setPage(2);lib.renderWaylines();assert.equal($('wayline-grid').children.length,2);
 assert.match($('wayline-range').textContent,/13–14 von 14/);
 assert.match(lib.waylineCheck(routes[1]),/Modellkonflikt/);assert.match(lib.waylineCheck(routes[2]),/Unbestätigte/);
 assert.match(lib.waylineCheck(routes[3]),/Mehrere/);assert.match(lib.waylineCheck(routes[0]),/Keine/);
 fixture.missions.push({candidate_count:20,candidates:[]});assert.match(lib.waylineCheck(routes[0]),/begrenzt/);fixture.missions.pop();
 $('wayline-search').value='Route 13';lib.renderWaylines();assert.equal($('wayline-grid').children.length,1);
 assert.match($('wayline-page').textContent,/Seite 1 von 1/);
 $('wayline-source').value='flighthub-public-v2';lib.renderWaylines();assert.match($('wayline-grid').children[0].textContent,/Keine Route passt/);
 $('wayline-source').value='all';$('wayline-search').value='';
 // File-derived strings must remain text, with no executable DOM inserted.
 lib.setData({...fixture,waylines:[{...routes[0],name:'<img src=x onerror=alert(1)>'}]});lib.renderWaylines();
 assert.equal($('wayline-grid').children[0].children[0].tag,'h2');
 assert.equal($('wayline-grid').children[0].children[0].textContent,'<img src=x onerror=alert(1)>');
 assert.match(lib.waylineSourceState(fixture),/alle gemeldeten Seiten/);
 assert.match(lib.waylineSourceState({...fixture,local_pilot:{state:'awaiting_browser_session'}}),/wartet/);
 // Failed refresh must clear previously visible results and permit retry.
 handler=async()=>{throw new Error('HTTP 403')};await lib.loadWaylines();assert.equal(lib.data(),null);
 assert.match($('wayline-state').textContent,/HTTP 403/);assert.equal($('refresh-waylines').disabled,false);
 assert.equal($('wayline-grid').children.length,0);
 // An older request/body completing after a newer one cannot replace it.
 const pending=[];handler=async(path,opts)=>{assert.equal(path,'/api/v1/studio/missions/reconciliation');
  assert.ok(opts.signal);return await new Promise(resolve=>pending.push(resolve))};
 const old=lib.loadWaylines(),newer=lib.loadWaylines();
 pending[1]({json:async()=>({...fixture,waylines:[routes[2]]})});await newer;
 pending[0]({json:async()=>({...fixture,waylines:[routes[1]]})});await old;
 assert.equal(lib.data().waylines[0].wayline_id,'2');
 // Refresh preserves a valid page, then clamps after source shrinkage.
 lib.setData(fixture);lib.setPage(2);handler=async()=>({json:async()=>fixture});await lib.loadWaylines();
 assert.match($('wayline-page').textContent,/Seite 2 von 2/);
 handler=async()=>({json:async()=>({...fixture,waylines:[]})});await lib.loadWaylines();
 assert.match($('wayline-grid').children[0].textContent,/Quellenstatus/);
 console.log('Wayline library JS passed');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run([node, "-e", program], input=logic, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
