"""Regression for hidden/mobile Leaflet map sizes during DJI KMZ preview focus."""
import shutil
import subprocess

import pytest

from aeronexus.studio_page import render_studio


def test_preview_recenter_is_readonly_and_available_in_map_toolbar():
    page = render_studio()
    assert 'id="wayline-preview-fit" hidden' in page
    assert 'id="wayline-preview-clear" hidden' in page
    assert 'addEventListener("click",centerCloudWaylinePreview)' in page
    assert 'map.invalidateSize({pan:false})' in page
    block = page[page.index("function fitWaylineMapBounds("):
                 page.index("function clearCloudWaylinePreview()")]
    assert 'requestAnimationFrame(()=>requestAnimationFrame(' in block
    assert 'map.getContainer()' in block
    assert 'map.fitBounds(bounds.pad(.18),{maxZoom:17,animate:false})' in block
    assert "saveMission" not in block
    assert "mission.waypoints" not in block
    assert "innerHTML" not in block


def test_hidden_mobile_map_is_measured_before_fit_and_old_requests_cannot_fit():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable")
    page = render_studio()
    script = page[page.index("function fitWaylineMapBounds("):
                  page.index("function clearCloudWaylinePreview()")]
    node_script = r"""
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(0,'utf8');
let ticks=[],width=0,active=false,current=true,events=[];
const map={
 invalidateSize(opts){assert.equal(opts.pan,false);events.push('invalidate');},
 getContainer(){events.push('container');return {clientWidth:width,clientHeight:640}},
 hasLayer(){return true},
 fitBounds(bounds,options){
   assert.equal(options.maxZoom,17);
   assert.equal(options.animate,false);
   assert.equal(width,390);
   assert.equal(active,true);
   assert.equal(bounds.name,'KMZ bounds');
   events.push('fit');
 }
};
const bounds={name:'KMZ bounds',isValid(){return true},pad(){return this}};
const $=()=>({classList:{contains(){return active;}}});
const raf=callback=>{ticks.push(callback)};
const lib=new Function('requestAnimationFrame','map','$','waylinePreviewBounds',
                      'waylinePreviewLayer',source+
 '\nreturn {fitWaylineMapBounds,centerCloudWaylinePreview};')(
 raf,map,$,bounds,{});
const flush=()=>{
 while(ticks.length)ticks.shift()();
};
lib.fitWaylineMapBounds(bounds,()=>current);
flush();
assert.deepEqual(events,[]);
active=true;width=390;
lib.centerCloudWaylinePreview();
flush();
assert.deepEqual(events,['invalidate','container','fit']);
events=[];
lib.fitWaylineMapBounds(bounds,()=>current);
current=false;flush();
assert.deepEqual(events,[]);
events=[];
current=true;width=0;
lib.fitWaylineMapBounds(bounds,()=>current);
flush();
assert.deepEqual(events,['invalidate','container']);
console.log('Mobile preview fit passed');
"""
    output = subprocess.run([node, "-e", node_script], input=script,
                            capture_output=True, text=True, timeout=15)
    assert output.returncode == 0, output.stderr
