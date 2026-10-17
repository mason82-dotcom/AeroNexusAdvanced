"""Exercise the real viewer script through load failure and response races."""
import re
import shutil
import subprocess

import pytest

from aeronexus.multispectral_page import render_multispectral_page


RUNTIME = r"""
const assert=require('node:assert/strict'),fs=require('node:fs');
const script=fs.readFileSync(0,'utf8');
class Element{
  constructor(){this.children=[];this.style={};this.hidden=false;this.value='';this.textContent='';
    this.clientWidth=600;this.clientHeight=400;this.classList={toggle(){}};}
  append(...e){this.children.push(...e);} replaceChildren(...e){this.children=e;}
  addEventListener(){} setAttribute(k,v){this[k]=v;}
  getContext(){return {createImageData:(w,h)=>({data:new Uint8ClampedArray(w*h*4)}),
    putImageData(){},clearRect(){},setLineDash(){}};}
}
const nodes=new Map(),document={getElementById(id){if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},
  createElement(){return new Element();},querySelectorAll(){return [];},querySelector(){return null;}};
const $=document.getElementById;
$('layer').value='ndvi';$('scale').value='2';
const window={addEventListener(){}},fetch=()=>new Promise(()=>{});
const app=new Function('document','window','fetch',script+`\nreturn {
 load,quadPoint,drawOverlays,
 set(c,l='ndvi'){current=c;document.getElementById('layer').value=l;},
 mock(a,g){api=a;grid=g;},
 snapshot(){return {data,cir,W,H,spots,busy};},
 overlays(items,layer){mapItems=items;overlayLayer=layer;},
 cancelOverlays(){overlayGeneration++;},
};`)(document,window,fetch);
const capture=id=>({capture_uuid:id,warnings:[]});
const stats={min:.1,max:.9,p02:.1,p05:.1,median:.5,mean:.5,p95:.9,p98:.9};
const analysis=c=>({capture:c,layer:'ndvi',label:'NDVI',stats});
const raster=()=>({w:2,h:2,g:new Float32Array([.1,.2,.3,.4])});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
(async()=>{
 const old=capture('old'),next=capture('next');
 app.set(old);app.mock(async()=>analysis(old),async()=>raster());await app.load();
 assert.equal($('export-grid').disabled,false);assert.equal(app.snapshot().data.capture.capture_uuid,'old');
 const fail=deferred();app.set(next);app.mock(()=>fail.promise,async()=>raster());
 const failed=app.load();
 assert.equal(app.snapshot().data,null);assert.equal($('export-grid').disabled,true);
 assert.equal($('stack').hidden,true);assert.equal($('viewer')['aria-busy'],'true');
 fail.resolve(Promise.reject(new Error('invalid calibration')));await failed;
 assert.equal(app.snapshot().data,null);assert.equal($('export-png').disabled,true);
 assert.equal($('viewer')['aria-busy'],'false');assert.equal($('error').hidden,false);
 // An older successful response cannot overwrite the newer selected capture.
 const slow=deferred();app.set(old);app.mock(()=>slow.promise,async()=>raster());const first=app.load();
 app.set(next);app.mock(async()=>analysis(next),async()=>raster());await app.load();
 slow.resolve(analysis(old));await first;
 assert.equal(app.snapshot().data.capture.capture_uuid,'next');
 // Superseded completion must not clear the busy state of a pending request.
 const slowOld=deferred(),slowNew=deferred();
 app.set(old);app.mock(()=>slowOld.promise,async()=>raster());const stale=app.load();
 app.set(next);app.mock(()=>slowNew.promise,async()=>raster());const pending=app.load();
 slowOld.resolve(analysis(old));await stale;assert.equal($('viewer')['aria-busy'],'true');
 assert.equal($('export-grid').disabled,true);
 slowNew.resolve(analysis(next));await pending;assert.equal($('export-grid').disabled,false);
 // A CIR request is pinned to the capture chosen when loading started.
 const cirStart=deferred(),seen=[];app.set(old,'cir');
 app.mock(async()=>analysis(old),async(l,s,c)=>{seen.push(c.capture_uuid);if(seen.length===1)await cirStart.promise;return raster();});
 const cirLoad=app.load();app.set(next);cirStart.resolve();await cirLoad;
 assert.deepEqual(seen,['old','old','old']);
 // Perspective mapping must hit all four corners, including bottom-right.
 const q=[[0,0],[100,0],[80,100],[20,100]];
 for(const [u,v,i] of [[0,0,0],[1,0,1],[1,1,2],[0,1,3]]){
  const p=app.quadPoint(q,u,v);assert.ok(Math.abs(p[0]-q[i][0])<1e-8&&Math.abs(p[1]-q[i][1])<1e-8);
 }
 // Disabling overlays while a request is in flight must prevent reappearance.
 const wait=deferred(),layer={clearLayers(){},addLayer(){throw Error('stale overlay added');}};
 $('map-overlay').checked=true;app.overlays([{capture_uuid:'old',footprint:q,has_ndvi:true}],layer);
 app.mock(()=>wait.promise,async()=>raster());const overlay=app.drawOverlays();
 app.cancelOverlays();$('map-overlay').checked=false;
 wait.resolve({headers:{get:()=>2},arrayBuffer:async()=>new Float32Array(4).buffer});await overlay;
})().catch(e=>{console.error(e);process.exitCode=1;});
"""


def test_viewer_failure_races_and_projective_overlay():
    if shutil.which("node") is None:
        pytest.skip("Node.js is required for embedded viewer runtime checks")
    script, = re.findall(r"<script>(.*?)</script>", render_multispectral_page(), re.S)
    result = subprocess.run(["node", "-e", RUNTIME], input=script, text=True,
                            capture_output=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
