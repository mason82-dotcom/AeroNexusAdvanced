"""Package controls run from the actual embedded multispectral JavaScript."""
import re
import shutil
import subprocess

import pytest

from aeronexus.multispectral_page import render_multispectral_page


RUNTIME = r"""
const fs=require('node:fs'),assert=require('node:assert/strict');
class Element{
 constructor(){this.children=[];this.style={};this.dataset={};this.listeners={};this.value='';this.hidden=false;
  this.classList={toggle(){},remove(){},add(){}};}
 append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}
 addEventListener(k,f){this.listeners[k]=f;}setAttribute(k,v){this[k]=v;}
}
const nodes=new Map(),document={getElementById(id){if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},
 createElement(){return new Element();},querySelectorAll(){return [];},querySelector(){return null;}};
const $=id=>document.getElementById(id),window={addEventListener(){}};
let transport=()=>new Promise(()=>{});const fetch=(...args)=>transport(...args);
const app=new Function('document','window','fetch',fs.readFileSync(0,'utf8')+`\nreturn {
 selectIds(ids){orthoSelection.clear();for(const id of ids)orthoSelection.add(id);orthoState();},
 state(){return {pending:orthoPending,selection:[...orthoSelection]};},loadPackages};`)(document,window,fetch);
const captures=['1','2','3'].map(c=>c.repeat(32)),id='a'.repeat(32);
const response=value=>({ok:true,status:200,json:async()=>value});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
(async()=>{
 $('ortho-mode').value='rgb';
 app.selectIds(captures.slice(0,2));assert.equal($('ortho-export').disabled,true);
 app.selectIds(captures);assert.equal($('ortho-export').disabled,false);
 const pending=deferred();let posts=0;
 transport=async(path,options)=>{
  assert.equal(options.credentials,'same-origin');
  if(options.method==='POST'){
   posts++;assert.deepEqual(JSON.parse(options.body),{capture_uuids:captures,mode:'rgb'});
   return pending.promise;
  }
  return response({packages:[{id,mode:'rgb',captures:3,size_bytes:2048},
    {id:'javascript:bad',mode:'rgb',captures:3,size_bytes:1}]});
 };
 const exportHandler=$('ortho-export').listeners.click,work=exportHandler();
 assert.equal(app.state().pending,true);assert.equal($('ortho-export').disabled,true);
 assert.equal($('ortho-mode').disabled,true);await exportHandler();assert.equal(posts,1);
 pending.resolve(response({id}));await work;
 assert.equal(app.state().pending,false);assert.equal($('ortho-mode').disabled,false);
 assert.equal($('ortho-packages').children.length,1);
 const link=$('ortho-packages').children[0].children[0];
 assert.equal(link.href,'/api/v1/multispectral/metashape/packages/'+id+'/file');
 assert.match(link.download,/\.zip$/);assert.ok(!('blob' in link));
 assert.match($('ortho-state').textContent,/Paket bereit/);
 // Network failure keeps the selection and restores usable controls.
 transport=async()=>{throw Error('offline');};await exportHandler();
 assert.equal(app.state().pending,false);assert.deepEqual(app.state().selection,captures);
 assert.equal($('ortho-export').disabled,false);assert.match($('ortho-state').textContent,/nicht bestätigt/);
 // A late package listing cannot resurrect rows removed by a newer listing.
 const slow=deferred();transport=()=>slow.promise;const first=app.loadPackages();
 transport=async()=>response({packages:[]});await app.loadPackages();
 slow.resolve(response({packages:[{id,mode:'rgb',captures:3,size_bytes:2}]}));await first;
 assert.equal($('ortho-packages').children.length,0);
})().catch(e=>{console.error(e);process.exitCode=1;});
"""


def test_package_selection_download_and_failure_recovery():
    if shutil.which("node") is None:
        pytest.skip("Node.js is required for embedded package-control checks")
    script, = re.findall(r"<script>(.*?)</script>", render_multispectral_page(), re.S)
    result = subprocess.run(["node", "-e", RUNTIME], input=script, text=True,
                            capture_output=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
