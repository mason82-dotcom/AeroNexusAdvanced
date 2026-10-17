"""Execute the handoff helper with browser primitives and network stubbed."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_existing_browser_session_handoff_without_passwords():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable")
    script = Path(__file__).resolve().parents[1] / "deploy/cloud-server/aeronexus-wayline-session.js"
    program = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(process.argv[1],'utf8');
async function flush(){await new Promise(setImmediate);}
function setup(host='192.168.178.63',storage={}){
 const calls=[],events={},intervals=[],timers=[];
 let release=null;
 const document={visibilityState:'visible',addEventListener:(key,fn)=>events[key]=fn};
 const context={location:{protocol:'http:',port:'8085',hostname:host},document,
  localStorage:{getItem:key=>storage[key]||null},AbortController,
  setInterval:fn=>intervals.push(fn),setTimeout:fn=>timers.push(fn),clearTimeout:()=>{},
  window:{addEventListener:(key,fn)=>events[key]=fn},
  fetch:async(url,options)=>{calls.push({url,options});await new Promise(r=>release=r);return {status:204};}};
 vm.runInNewContext(source,context);
 return {calls,events,intervals,document,storage,release:()=>release?.()};
}
(async()=>{
 const noSession=setup();await flush();assert.equal(noSession.calls.length,0);
 const external=setup('external.invalid',{'x-auth-token':'private','workspace_id':'workspace'});
 assert.equal(external.calls.length,0);assert.equal(external.intervals.length,0);
 const s=setup('192.168.178.63',{'x-auth-token':'existing-private-token','workspace_id':'workspace'});
 await flush();assert.equal(s.calls.length,1);
 const req=s.calls[0];assert.equal(req.url,'https://192.168.178.63:8000/api/v1/local-cloud/session');
 assert.equal(req.options.credentials,'omit');assert.equal(req.options.redirect,'error');
 assert.equal(req.options.method,'POST');assert.equal(req.options.headers['Content-Type'],'application/json');
 assert.deepEqual(JSON.parse(req.options.body),{access_token:'existing-private-token',workspace_id:'workspace'});
 s.events.storage();assert.equal(s.calls.length,1); // no concurrent submissions
 s.release();await flush();s.document.visibilityState='hidden';s.intervals[0]();assert.equal(s.calls.length,1);
 s.document.visibilityState='visible';s.storage['x-auth-token']='rotated-private-token';s.events.storage();
 assert.equal(s.calls.length,2);assert.equal(JSON.parse(s.calls[1].options.body).access_token,'rotated-private-token');
 s.release();await flush();delete s.storage['x-auth-token'];s.intervals[0]();assert.equal(s.calls.length,2);
 console.log('Session handoff JS passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
    result = subprocess.run([node, "-e", program, str(script)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
