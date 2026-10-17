"""Tests execute the production Phase-20 DEM slope math and rendering in Node."""
import re
import shutil
import subprocess

import pytest

from aeronexus.studio_page import render_studio


_NODE = r"""
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const script=fs.readFileSync(0,"utf8");
const start=script.indexOf("// Phase 18: local 2D-canvas rasterizer");
const end=script.indexOf("async function previewTerrain(){",start);
assert.ok(start>=0&&end>start);
const elements=new Map();
const canvas={id:"terrain-canvas",width:320,height:210,
  fills:[],getContext(){
    const self=this;
    return {fillStyle:"",clearRect(){},fillRect(){},beginPath(){},
      moveTo(){},lineTo(){},closePath(){},stroke(){},
      fill(){self.fills.push(this.fillStyle);}};
  }};
const $=id=>{
  if(id==="terrain-canvas")return canvas;
  if(!elements.has(id))elements.set(id,{checked:false,value:"",textContent:""});
  return elements.get(id);
};
const api=new Function("$","window",
  "let terrainGrid=null,terrainGeo=null,geoObjects=[];\n"+
  script.slice(start,end)+"\nreturn {terrainSlopeAt,terrainSlopeStatistics,"+
  "terrainSlopeColor,terrainUpdateSlopeInfo,terrainDrawCanvas,"+
  "terrainResetView,terrainControlChanged,terrainSyncControls,"+
  "get view(){return terrainView;},setGrid(g){terrainGrid=g;}};"
)($,{requestAnimationFrame(){/* explicit renderer call below */}});
const flat={heights_m:[[100,100],[100,100]],x_step_m:2,y_step_m:10};
assert.equal(api.terrainSlopeAt(flat,0.5,0.5),0);
assert.equal(api.terrainSlopeAt(flat,-0.1,0.5),null);
assert.equal(api.terrainSlopeAt(flat,0.5,2),null);
const x={heights_m:[[10,20],[10,20]],x_step_m:10,y_step_m:5};
const y={heights_m:[[0,0],[10,10]],x_step_m:10,y_step_m:10};
assert.ok(Math.abs(api.terrainSlopeAt(x,0.5,0.5)-45)<1e-10);
assert.ok(Math.abs(api.terrainSlopeAt(y,0.5,0.5)-45)<1e-10);
const diagonal={heights_m:[[0,10],[10,20]],x_step_m:10,y_step_m:10};
assert.ok(Math.abs(api.terrainSlopeAt(diagonal,0.5,0.5)-54.735610317)<1e-6);
assert.equal(api.terrainSlopeStatistics(flat).max_deg,0);
const stats=api.terrainSlopeStatistics(x);
assert.equal(stats.total_cells,1);
assert.equal(stats.steep_cells,1);
assert.ok(Math.abs(stats.mean_deg-45)<1e-10);
assert.equal(api.terrainSlopeStatistics(null),null);
assert.notEqual(api.terrainSlopeColor(4),api.terrainSlopeColor(10));
assert.notEqual(api.terrainSlopeColor(10),api.terrainSlopeColor(20));
assert.notEqual(api.terrainSlopeColor(20),api.terrainSlopeColor(45));
const original=JSON.stringify(x);
api.terrainUpdateSlopeInfo(x);
assert.match($("terrain-slope-info").textContent,/45\.0°/);
assert.match($("terrain-slope-info").textContent,/keine Flugfreigabe/);
api.setGrid(x);
api.terrainSyncControls();
assert.equal($("terrain-slope").checked,false);
$("terrain-slope").checked=true;
api.terrainControlChanged();
assert.equal(api.view.slope,true);
api.terrainDrawCanvas(canvas,x,api.view);
assert.equal(canvas.fills.at(-1),api.terrainSlopeColor(45));
assert.equal(JSON.stringify(x),original,
  "slope preview must not alter source elevations used for STL");
api.terrainResetView();
assert.equal(api.view.slope,false);
assert.equal($("terrain-slope").checked,false);
api.terrainUpdateSlopeInfo(null);
assert.match($("terrain-slope-info").textContent,/Noch keine/);
console.log("Phase 20 local DEM slopes: OK");
"""


def test_phase20_studio_has_slope_legend_and_safe_access_contract():
    page = render_studio()
    assert 'id="terrain-slope"' in page
    assert 'id="terrain-slope-info"' in page
    assert "function terrainSlopeAt(grid,row,col)" in page
    assert "function terrainSlopeStatistics(grid)" in page
    assert "function terrainUpdateSlopeInfo(grid)" in page
    assert "Höhenüberhöhung" in page
    assert "keine Flugfreigabe" in page
    assert "/api/v1/flight/command" not in page
    assert "innerHTML" not in page


def test_phase20_uses_actual_browser_slope_calculations():
    if not shutil.which("node"):
        pytest.skip("Node.js needed to test actual embedded browser code")
    scripts = re.findall(r"<script>(.*?)</script>", render_studio(), re.DOTALL)
    assert len(scripts) == 1
    result = subprocess.run(["node", "-e", _NODE], input=scripts[0],
                            text=True, capture_output=True, timeout=20,
                            check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 20 local DEM slopes: OK" in result.stdout
