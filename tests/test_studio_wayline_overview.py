"""Opt-in shared Wayline map overview; colors, bounded GET and no mutations."""
import shutil
import subprocess

import pytest

from aeronexus.studio_page import render_studio


def test_cloud_overview_has_explicit_button_and_private_readonly_layers():
    page = render_studio()
    for element in ("wayline-overview-open", "cloud-overview-panel", "cloud-overview-status",
                    "cloud-overview-list", "cloud-overview-close", "cloud-overview-fit"):
        assert f'id="{element}"' in page
    assert 'id="wayline-overview-open" disabled' in page
    assert 'id="cloud-overview-panel" role="region"' in page
    block = page[page.index("function closeCloudOverview("):page.index("function waylineSourceState(")]
    assert 'route.provider!=="pilot2-local-cloud"' in block
    assert "pilot.pagination_complete!==true" in block
    assert ").slice(0,8)" in block
    assert 'encodeURIComponent(entry.id)+"/preview"' in block
    assert 'method:"POST"' not in block and 'method:"DELETE"' not in block
    assert "saveMission" not in block and "mission.waypoints" not in block
    assert "innerHTML" not in block
    assert "interactive:false" in block
    assert "cloudOverviewController.abort()" in block
    assert "cloudOverviewLayer.removeLayer(entry.layer)" in block
    assert "cloudOverviewLayer.addLayer(entry.layer)" in block
    assert "if(generation!==cloudOverviewGeneration" in block
    assert 'style:()=>({color:entry.color' in block
    assert "fitCloudRoutes(entry)" in block
    assert 'cloudOverviewLayer=L.layerGroup()' in page
    assert '(cloudOverviewLayer&&map.hasLayer(cloudOverviewLayer))' in page
    assert 'closeCloudOverview(true);' in page


def test_cloud_overview_javascript_fetches_only_8_local_routes_and_toggles_layers():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    page = render_studio()
    logic = page[page.index("// Read-only library:"):page.index("function switchTab(id)")]
    script = r"""
const fs=require('node:fs'),assert=require('node:assert/strict');
const logic=fs.readFileSync(0,'utf8');
const elems=new Map();
function element(){return {textContent:'',children:[],style:{},hidden:true,disabled:false,checked:false,value:'',
  setAttribute(){},replaceChildren(){this.children=[]},appendChild(el){this.children.push(el);return el}}}
const $=id=>{if(!elems.has(id))elems.set(id,element());return elems.get(id)};
const els=(tag,cls,text)=>Object.assign(element(),{tag,className:cls,textContent:String(text??'')});
class Group {
 constructor(){this.layers=[]}
 addLayer(layer){if(!this.layers.includes(layer))this.layers.push(layer);return this}
 removeLayer(layer){this.layers=this.layers.filter(x=>x!==layer);return this}
 clearLayers(){this.layers=[];return this}
 addTo(parent){parent.addLayer(this);return this}
 getBounds(){return {isValid:()=>this.layers.length>0,pad(){return this},extend(){return this}}}
}
const map={layers:[],lastBounds:null,addLayer(l){if(!this.layers.includes(l))this.layers.push(l)},
 removeLayer(l){this.layers=this.layers.filter(x=>x!==l)},
 hasLayer(l){return this.layers.includes(l)},fitBounds(b){this.lastBounds=b}};
const L={layerGroup:()=>new Group(),featureGroup:()=>new Group(),
 geoJSON:(feature,options)=>{assert.equal(options.interactive,false);
   assert.match(options.style().color,/^#/);
   return {addTo(parent){parent.addLayer(this);return this}} },
 latLngBounds:()=>({isValid:()=>true,extend(){return this},pad(){return this}})};
let hits=[],warn=[];
const api=async (url,options)=>{
 hits.push(url);assert.ok(options.signal);
 const ident=decodeURIComponent(url.split('/')[5]);
 const status=ident==="r3"?"storage_unavailable":"connected";
 return {json:async()=>status==="connected"?
   {state:status,features:[{geometry:{type:'LineString',coordinates:[[8,49],[9,50]]}}],
    point_count:6,source:"waylines.wpml"}:{state:status}};
};
const main=new Function('$','els','api','map','L','switchTab','getMap','mapWarning',
 'errorMessage','clean','cloudOverviewLayer','waylinePreviewLayer',
 'cloudOverviewGeneration','cloudOverviewController','cloudOverviewRoutes',
 'CLOUD_OVERVIEW_COLORS','waylinePreviewRequest',logic+
 '\nreturn {openCloudOverview,closeCloudOverview,renderCloudOverview,fitCloudRoutes,'+
 'setData(d){waylineData=d},getRoutes(){return cloudOverviewRoutes},getLayer(){return cloudOverviewLayer}};');
const overview=main($,els,api,map,L,()=>{},()=>{},s=>warn.push(s),e=>e.message,v=>String(v??'–'),
 new Group(),new Group(),0,null,[],
 ["#ffb74d","#60b5ff","#82d39a","#df9eff","#ff7993","#66d8d5","#f3dc6d","#b8abff"],0);
const routes=Array.from({length:10},(_,n)=>({provider:n===9?'flighthub-public-v2':'pilot2-local-cloud',
 wayline_id:'r'+n,name:'Route '+n}));
overview.setData({waylines:routes,local_pilot:{state:'connected',pagination_complete:true},missions:[]});
(async()=>{
 await overview.openCloudOverview();
 assert.equal(hits.length,8);
 assert.deepEqual(hits.map(h=>h.split('/')[5]),['r0','r1','r2','r3','r4','r5','r6','r7']);
 assert.equal(overview.getRoutes().length,8);
 assert.equal(overview.getRoutes().filter(x=>x.state==='connected').length,7);
 assert.equal(overview.getRoutes().filter(x=>x.state!=='connected').length,1);
 assert.equal(overview.getRoutes()[0].pointCount,6);
 assert.equal(new Set(overview.getRoutes().map(x=>x.color)).size,8);
 assert.match($('cloud-overview-status').textContent,/7\/8 Routen gelesen/);
 assert.equal($('cloud-overview-panel').hidden,false);
 assert.equal(overview.getLayer().layers.length,7);
 const row=$('cloud-overview-list').children[0], input=row.children[0].children[0];
 assert.equal(input.checked,true);input.checked=false;input.onchange();
 assert.equal(overview.getLayer().layers.length,6);
 row.children[1].onclick();
 assert.equal(overview.getLayer().layers.length,7);
 assert.ok(map.lastBounds);
 overview.closeCloudOverview();
 assert.equal($('cloud-overview-panel').hidden,true);
 assert.equal(overview.getLayer().layers.length,0);
 assert.equal(map.hasLayer(overview.getLayer()),false);
 hits=[];
 overview.setData({waylines:routes,local_pilot:{state:'connected',pagination_complete:false}});
 await overview.openCloudOverview();assert.equal(hits.length,0);
 console.log('Cloud overview JS passed');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run([node, "-e", script], input=logic,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
