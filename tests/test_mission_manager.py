"""Mission Manager lists both stores and opens cloud routes without rewriting drafts."""
import shutil
import subprocess

import pytest

from aeronexus.studio_page import render_studio


def test_manager_uses_existing_route_sources_at_startup():
    page = render_studio()
    for ident in ("mission-list", "load-manager-route", "refresh-manager-routes", "mission-manager-state"):
        assert f'id="{ident}"' in page
    assert '<h1>Mission Manager</h1>' in page
    assert 'for="mission-list"' in page
    assert 'openManagerRoute(e.target.value)' in page
    assert 'const routes=loadWaylines();' in page


def test_manager_groups_sources_preserves_draft_and_recovers_from_failure():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable")
    page = render_studio()
    code = page[page.index('let managerRouteKey='):page.index('async function loadMission(')]
    script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs');
const code=fs.readFileSync(0,'utf8');
const nodes=new Map(),sourceDetails={open:false};
const $=id=>{if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',children:[],disabled:false,
 replaceChildren(){this.children=[]},appendChild(v){this.children.push(v)},closest(){return sourceDetails}});return nodes.get(id)};
const els=(tag,cls,text)=>({tag,textContent:text,children:[],appendChild(v){this.children.push(v)}});
let knownMissions=[{id:'local-one',name:'Local',waypoints:2}],missionId='local-one';
let waylineData={waylines:[{provider:'pilot2-local-cloud',project_id:'workspace',wayline_id:'route-one',name:'<b>Cloud</b>'},
 {provider:'flighthub-public-v2',project_id:'project',wayline_id:'route-one',name:'FlightHub'}]};
let loaded=[],previewSucceeds=true,clears=0,localSucceeds=true;
const previewCloudWayline=async(route,button)=>{loaded.push(route);return previewSucceeds};
const loadMission=async id=>{loaded.push(id);return localSucceeds};
const clearCloudWaylinePreview=()=>{clears++};
const waylineSource=p=>p,waylineType=r=>'Wegpunktmission',waylineSourceState=()=> 'Cloud verbunden';
let localError=false;
const api=async path=>{assert.equal(path,'/api/v1/studio/missions');if(localError)throw Error('offline');
 return {json:async()=>({missions:knownMissions})}};
const loadWaylines=async()=>{};
const manager=eval('(function(){'+code+';return {updateMissionSelect,managerKey,openManagerRoute,refreshMissionManager};})()');
(async()=>{
 manager.updateMissionSelect();
 const groups=$('mission-list').children.slice(1);
 assert.equal(groups.length,3);assert.equal(groups[0].label,'Lokale Entwürfe');
 assert.equal(groups[1].children[0].textContent,'<b>Cloud</b> · Wegpunktmission');
 const cloud=waylineData.waylines[0],fh=waylineData.waylines[1];
 assert.notEqual(manager.managerKey(cloud),manager.managerKey(fh));
 const key=manager.managerKey(cloud);
 await manager.openManagerRoute(key);assert.equal(loaded[0],cloud);
 assert.equal(missionId,'local-one');assert.equal(clears,0);assert.equal($('mission-list').value,key);
 assert.equal($('delete-mission').disabled,true);assert.equal($('save-mission').disabled,true);
 assert.equal($('export-mission').disabled,true);
 // The explicit load action must retry an already selected route.
 await manager.openManagerRoute(key);assert.equal(loaded.length,2);
 previewSucceeds=false;
 await manager.openManagerRoute(key);assert.equal(missionId,'local-one');
 // Metadata-only sources are visible, but must not pretend to load geometry.
 await manager.openManagerRoute(manager.managerKey(fh));
 assert.equal(loaded.length,3);assert.match($('mission-manager-state').textContent,/kein Geometrieabruf/);
 assert.match($('mission-manager-state').className,/error/);
 assert.equal(sourceDetails.open,true);
 assert.match($('mission-manager-summary').textContent,/Quellenproblem/);
 localSucceeds=false;await manager.openManagerRoute('other-local');assert.equal(clears,0);
 localSucceeds=true;await manager.openManagerRoute('local-one');assert.equal(clears,1);
 assert.equal($('mission-list').value,'local-one');
 assert.equal($('save-mission').disabled,false);assert.equal($('delete-mission').disabled,false);
 localError=true;await manager.refreshMissionManager();
 assert.match($('mission-manager-state').textContent,/Lokaler Speicher nicht erreichbar/);
 assert.equal($('refresh-manager-routes').disabled,false);
 assert.ok($('mission-list').children.some(g=>g.label==='pilot2-local-cloud'));
 localError=false;await manager.refreshMissionManager();
 assert.match($('mission-manager-state').textContent,/1 lokale Entwürfe/);
 assert.match($('mission-manager-summary').textContent,/1 lokale Entwürfe · 2 Cloud-Routen/);
 sourceDetails.open=false;
 waylineData.local_pilot={state:'connected',pagination_complete:false};
 await manager.refreshMissionManager();
 assert.equal(sourceDetails.open,true,'partial inventory must be visible');
 assert.match($('mission-manager-summary').textContent,/Quellenproblem/);
 await assert.rejects(()=>manager.openManagerRoute('cloud:missing'),/nicht mehr im Bestand/);
 console.log('Mission Manager state tests passed');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run([node, "-e", script], input=code, text=True,
                            capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
