"""Execute the embedded viewer script: stale statistics, errors and tile options."""
import re
import shutil
import subprocess

import pytest
from aeronexus.results_page import render_results_page

RUNTIME = r'''
const assert=require('node:assert/strict'),fs=require('node:fs');
class Element{get value(){return this._value;}set value(v){this._value=String(v);}constructor(){this.children=[];this.style={};this.hidden=false;this.value='';this.textContent='';this.classList={toggle(){}};this.listeners={};}append(...e){this.children.push(...e);if(!this.value&&e[0]?.value)this.value=String(e[0].value);}replaceChildren(...e){this.children=e;this.value='';}addEventListener(k,f){this.listeners[k]=f;}setAttribute(k,v){this[k]=v;}focus(){}}
const nodes=new Map(),document={getElementById(id){if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},createElement(){return new Element();},createDocumentFragment(){return new Element();}};
const $=id=>document.getElementById(id);$('palette').value='viridis';$('opacity').value='1';
let tiles=[];const map={setView(){return this;},fitBounds(){},removeLayer(){}};
const L={map:()=>map,tileLayer(url,options){const tile={url,options,handlers:{},on(k,f){this.handlers[k]=f;return this;},addTo(){return this;},setOpacity(){}};tiles.push(tile);return tile;}};
const script=fs.readFileSync(0,'utf8');
const app=new Function('document','L','fetch',script+`\nreturn {choose,autoRange,loadList,render,resetSelection,mock(f){api=f;},snapshot(){return {selected,layer,items};}};`)(document,L,()=>new Promise(()=>{}));
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
const item=(id,kind='ndvi')=>({id,version:id+'v',filename:id+'.tif',kind,width:32,height:32,size_bytes:1000,crs:'EPSG:4326',bounds:[8,49,9,50],rgb_bands:[],warnings:[],bands:[{index:1,name:'Band 1',dtype:'float32',unit:'m',nodata:null,overviews:[],scale:1,offset:0}]});
const stats={p02:12,p98:25};
(async()=>{
 const old=item('old','dsm'),next=item('next');
 let wait=deferred();app.mock(()=>wait.promise);app.choose(old);
 app.choose(next);assert.equal(app.snapshot().selected.id,'next');assert.match(app.snapshot().layer.url,/next\/tiles/);
 wait.resolve(stats);await new Promise(r=>setImmediate(r));assert.equal($('low').value,'-1');assert.match(app.snapshot().layer.url,/next\/tiles/);
 // Failed auto contrast clears the previous visible layer and reports failure.
 app.mock(async()=>{throw Error('changed file');});await app.autoRange();assert.equal(app.snapshot().layer,null);assert.equal($('map-state').textContent,'changed file');
 $('low').value='0';$('high').value='1';app.render();const active=app.snapshot().layer;
 assert.equal(active.options.noWrap,true);assert.match(active.url,/v=nextv/);
 active.handlers.tileerror();assert.equal($('retry').hidden,false);
 app.choose(item('new'));const current=$('map-state').textContent;active.handlers.load();assert.equal($('map-state').textContent,current);
 $('low').value='';app.render();assert.match($('map-state').textContent,/Endliche Grenzen/);
 // An older catalog response cannot overwrite the newest query result.
 const slow=deferred();app.mock(()=>slow.promise);const first=app.loadList();
 app.mock(async()=>({items:[next],offset:0,total:1,raster_available:true}));await app.loadList();
 slow.resolve({items:[old],offset:0,total:1,raster_available:true});await first;
 assert.equal(app.snapshot().items[0].id,'next');
 // File names are rendered through textContent, never HTML interpolation.
 const bad=item('<img src=x onerror=alert(1)>');app.choose(bad);assert.equal($('title').textContent,bad.filename);
 app.mock(async()=>{throw Error('offline');});await app.loadList();assert.equal(app.snapshot().selected,null);assert.equal(app.snapshot().layer,null);assert.equal($('controls').disabled,true);
})().catch(e=>{console.error(e);process.exitCode=1;});
'''


def test_results_viewer_races_failures_and_tile_parameters():
    if shutil.which('node') is None:
        pytest.skip('Node.js required for viewer runtime checks')
    script, = re.findall(r'<script>(.*?)</script>', render_results_page(), re.S)
    result = subprocess.run(['node', '-e', RUNTIME], input=script, text=True,
                            capture_output=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
