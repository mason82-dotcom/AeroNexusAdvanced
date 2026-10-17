"""Mobile map focus, expandable map controls and compact cloud-route legend."""
import shutil
import subprocess

import pytest

from aeronexus.studio_page import render_studio


def test_mobile_layout_preserves_cloud_readonly_layers_and_map_controls():
    page = render_studio()
    for name in ("map-toolbar", "map-focus-toggle", "map-tools-toggle", "map-info-toggle",
                 "cloud-overview-expand", "cloud-overview-panel", "cloud-overview-list"):
        assert f'id="{name}"' in page
    assert 'id="map-toolbar" data-compact="true"' in page
    assert 'id="map-tools-toggle" type="button" class="map-primary" aria-expanded="false"' in page
    assert 'id="cloud-overview-expand" type="button" aria-expanded="false"' in page
    assert '.map-bar[data-compact="true"] .map-extra{display:none}' in page
    assert 'body.map-focus-active .content{position:fixed;inset:0;z-index:1500;' in page
    assert 'body.map-focus-active #map{height:100%;min-height:0}' in page
    assert '#cloud-overview-panel[data-minimized="true"] #cloud-overview-list' in page
    assert 'function setMapFocus(enabled)' in page
    assert 'function setMapInfoExpanded(expanded)' in page
    assert 'function setMapToolsExpanded(expanded)' in page
    assert 'function setCloudOverviewMinimized(minimized)' in page
    assert 'setMapInfoExpanded(!window.matchMedia("(max-width:700px)").matches)' in page
    assert 'map.invalidateSize({pan:false})' in page
    # The cloud layer and all WPML previews are always non-interactive.
    assert "interactive:false" in page
    segment = page[page.index("function setCloudOverviewMinimized("):
                   page.index("function closeCloudOverview(")]
    assert "innerHTML" not in segment
    assert "saveMission" not in segment
    assert "mission.waypoints" not in segment


def test_mobile_controls_can_expand_and_exit_focus_without_browser_fullscreen():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    page = render_studio()
    source = page[page.index("function setCloudOverviewMinimized("):
                  page.index("function closeCloudOverview(")]
    program = r"""
const fs=require('node:fs'),assert=require('node:assert/strict');
const code='const mapStatusSummary=message=>String(message);\\n'+fs.readFileSync(0,'utf8');
const elems=new Map();
const $=id=>{
  if(!elems.has(id))elems.set(id,{
    dataset:{},textContent:'',attrs:{},
    classList:{contains:token=>id==='map-pane'&&token==='active'},
    setAttribute(key,val){this.attrs[key]=val}
  });
  return elems.get(id);
};
const active=new Set();
const body={classList:{
  toggle(name,enabled){if(enabled)active.add(name);else active.delete(name);return enabled},
  contains(name){return active.has(name)}
}};
const document={body};
let frames=[],resized=0,visited=[];
const requestAnimationFrame=callback=>frames.push(callback);
const map={invalidateSize(opts){assert.equal(opts.pan,false);resized++}};
const switchTab=id=>visited.push(id);
const methods=new Function('$','document','map','requestAnimationFrame','switchTab',code+
 '\nreturn {setCloudOverviewMinimized,setMapToolsExpanded,setMapInfoExpanded,setMapFocus};')(
 $,document,map,requestAnimationFrame,switchTab);
const flush=()=>{while(frames.length)frames.shift()()};
methods.setMapToolsExpanded(false);
assert.equal($('map-toolbar').dataset.compact,'true');
assert.equal($('map-tools-toggle').attrs['aria-expanded'],'false');
methods.setMapToolsExpanded(true);
assert.equal($('map-toolbar').dataset.compact,'false');
assert.equal($('map-tools-toggle').attrs['aria-expanded'],'true');
methods.setMapInfoExpanded(false);
assert.equal($('map-info').dataset.minimized,'true');
methods.setMapInfoExpanded(true);
assert.equal($('map-info').dataset.minimized,'false');
methods.setCloudOverviewMinimized(true);
assert.equal($('cloud-overview-panel').dataset.minimized,'true');
assert.equal($('cloud-overview-expand').attrs['aria-expanded'],'false');
methods.setCloudOverviewMinimized(false);
assert.equal($('cloud-overview-panel').dataset.minimized,'false');
assert.equal($('cloud-overview-expand').attrs['aria-expanded'],'true');
methods.setMapFocus(true);flush();
assert.equal(active.has('map-focus-active'),true);
assert.equal($('map-focus-toggle').attrs['aria-pressed'],'true');
assert.equal(resized,1);
assert.deepEqual(visited,[]);
methods.setMapFocus(false);flush();
assert.equal(active.has('map-focus-active'),false);
assert.equal($('map-focus-toggle').attrs['aria-pressed'],'false');
assert.equal(resized,2);
console.log('Mobile map focus controls passed');
"""
    result = subprocess.run([node, "-e", program], input=source,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
