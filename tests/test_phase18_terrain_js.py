"""Execute Phase-18's real browser terrain renderer in Node without a network.

The tests exercise the production JS functions, not a Python reimplementation.
"""
import re
import shutil
import subprocess

import pytest

from aeronexus.studio_page import render_studio


_TERRAIN_TEST = r"""
"use strict";
const fs=require("node:fs"),assert=require("node:assert/strict");
const script=fs.readFileSync(0,"utf8");
const start=script.indexOf("// Phase 18: local 2D-canvas rasterizer");
const end=script.indexOf("async function previewTerrain(){",start);
assert.ok(start>0&&end>start,"production terrain renderer not found");
const code=script.slice(start,end);

class Canvas {
  constructor(id){
    this.id=id;this.width=id==="terrain-canvas-large"?1000:320;
    this.height=id==="terrain-canvas-large"?590:210;
    this.calls={fills:0,strokes:0};
    this.events=new Map();
    const calls=this.calls;
    this.context={
      clearRect(){},fillRect(){},beginPath(){},moveTo(x,y){
        assert.ok(Number.isFinite(x)&&Number.isFinite(y));},
      lineTo(x,y){assert.ok(Number.isFinite(x)&&Number.isFinite(y));},
      closePath(){},fill(){calls.fills++;},stroke(){calls.strokes++;}
    };
  }
  getContext(kind){assert.equal(kind,"2d");return this.context;}
  addEventListener(type,listener){this.events.set(type,listener);}
  setPointerCapture(){}
  dispatch(type,extra={}){
    let prevented=false;
    const event={pointerId:1,button:0,clientX:100,clientY:100,deltaY:0,
      preventDefault(){prevented=true;},...extra};
    const listener=this.events.get(type);
    assert.ok(listener,"Missing "+type+" listener");
    listener(event);
    return prevented;
  }
}
const elements=new Map();
const $=id=>{
  if(!elements.has(id))elements.set(id,id.startsWith("terrain-canvas")?
    new Canvas(id):{value:"",checked:false,textContent:""});
  return elements.get(id);
};
const api=new Function("$","window","let terrainGrid=null;\n"+code+
  "\nreturn {terrainColor,terrainProjection,terrainDrawCanvas,drawTerrainPreview,"+
  "terrainBindPointer,terrainResetView,terrainControlChanged,terrainSyncControls,"+
  "setGrid(grid){terrainGrid=grid},get view(){return terrainView;}};"
)($,{requestAnimationFrame(fn){fn();}});

assert.equal(api.terrainColor(0),api.terrainColor(-10));
assert.equal(api.terrainColor(1),api.terrainColor(10));
assert.match(api.terrainColor(0.5),/^rgb\(\d+,\d+,\d+\)$/);

const grid={
  heights_m:[[120,125,130],[121,139,131],[122,130,140]],
  x_step_m:5,y_step_m:12,base_m:2
};
const saved=JSON.stringify(grid);
const projected=api.terrainProjection(grid,api.view,1000,590);
assert.equal(projected.rows,3);
assert.equal(projected.cols,3);
assert.equal(projected.cells.length,4);
assert.equal(projected.zmin,120);
assert.equal(projected.zmax,140);
assert.ok(projected.cells.every(cell=>cell.points.length===4));
assert.ok(projected.cells.every(cell=>cell.points.every(
  p=>Number.isFinite(p.x)&&Number.isFinite(p.y)&&Number.isFinite(p.depth))));
assert.equal(JSON.stringify(grid),saved,"source elevations must never be changed");

api.setGrid(grid);
api.drawTerrainPreview(grid);
const small=$("terrain-canvas"),large=$("terrain-canvas-large");
assert.equal(small.calls.fills,4);
assert.equal(large.calls.fills,4);
assert.equal(large.calls.strokes,4);
api.terrainSyncControls();
assert.equal($("terrain-azimuth").value,"45");
assert.equal($("terrain-exaggeration").value,"2");

$("terrain-azimuth").value="-100";
$("terrain-tilt").value="70";
$("terrain-zoom").value="2";
$("terrain-exaggeration").value="4.5";
$("terrain-color").checked=false;
$("terrain-wire").checked=false;
const previousStrokes=large.calls.strokes;
api.terrainControlChanged();
assert.equal(api.view.azimuth,-100);
assert.equal(api.view.tilt,70);
assert.equal(api.view.zoom,2);
assert.equal(api.view.exaggeration,4.5);
assert.equal(api.view.color,false);
assert.equal(api.view.wire,false);
assert.equal(large.calls.strokes,previousStrokes,"mesh disabled must suppress strokes");
assert.equal(JSON.stringify(grid),saved);

// Both mouse and touch via Pointer Events operate only when a grid is loaded.
api.terrainBindPointer(small);
api.terrainBindPointer(large);
assert.equal(large.dispatch("pointerdown"),true);
assert.equal(large.dispatch("pointermove",{clientX:140,clientY:150}),true);
assert.equal(api.view.azimuth,-80);
assert.equal(api.view.tilt,80);
large.dispatch("pointerup",{clientX:140,clientY:150});
assert.equal(large.dispatch("wheel",{deltaY:1}),true);
assert.ok(api.view.zoom<2);

api.terrainResetView();
assert.equal(api.view.azimuth,45);
assert.equal(api.view.tilt,45);
assert.equal(api.view.zoom,1);
assert.equal(api.view.exaggeration,2);
assert.equal(api.view.color,true);
assert.equal(api.view.wire,true);
assert.equal($("terrain-zoom-value").textContent,"1,0×");

const flat={heights_m:[[100,100],[100,100]],x_step_m:1,y_step_m:3};
const zero=api.terrainProjection(flat,api.view,320,210);
assert.equal(zero.cells.length,1);
assert.ok(zero.cells[0].points.every(p=>Number.isFinite(p.y)));
assert.equal(JSON.stringify(grid),saved);
console.log("Phase-18 terrain renderer: OK");
"""


def test_phase18_real_js_renderer_geometry_and_pointer_controls():
    if not shutil.which("node"):
        pytest.skip("Node.js is needed for the production terrain JS regression")
    scripts = re.findall(r"<script>(.*?)</script>", render_studio(), re.DOTALL)
    assert len(scripts) == 1
    result = subprocess.run(
        ["node", "-e", _TERRAIN_TEST], input=scripts[0],
        text=True, capture_output=True, timeout=20, check=False,
    )
    assert result.returncode == 0, (
        "Production 3D geometry/control regression failed:\n" +
        result.stdout + result.stderr
    )
    assert "Phase-18 terrain renderer: OK" in result.stdout
