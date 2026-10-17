"""Exercise production WGS84 overlay, bilinear DEM profile and click picking in Node."""
import re
import shutil
import subprocess

import pytest

from aeronexus.studio_page import render_studio


_JS = r"""
"use strict";
const fs=require("node:fs"),assert=require("node:assert/strict");
const script=fs.readFileSync(0,"utf8");
const start=script.indexOf("function terrainClamp(");
const stop=script.indexOf("function terrainDrawCanvas(",start);
const probe=script.indexOf("function terrainTriangleWeights(",stop);
const probeStop=script.indexOf("function terrainBindPointer(",probe);
assert.ok(start>0&&stop>start&&probe>stop&&probeStop>probe);
const logic=script.slice(start,stop)+"\n"+script.slice(probe,probeStop);
const nodes=new Map();
const $=id=>{
  if(!nodes.has(id))nodes.set(id,{textContent:"",value:"",children:[],
    replaceChildren(){this.children=[];},
    appendChild(v){this.children.push(v);},
    getContext(){return {clearRect(){},fillRect(){},beginPath(){},
      moveTo(){},lineTo(){},stroke(){}};}});
  return nodes.get(id);
};
const els=(tag,cls,text)=>({tag,cls,textContent:text,value:""});
const api=new Function("$","els","let terrainGrid=null,terrainGeo=null,"+
  "geoObjects=[],terrainProfile=null;"+logic+
  "\nreturn {terrainGridPoint,terrainHeightAt,terrainGeoFromGrid,"+
  "terrainGeoPolyline,terrainPolylineProfile,terrainProjection,"+
  "terrainProbeAt,terrainRefreshProfileOptions,terrainGenerateProfile,"+
  "setState(g,meta,objects){terrainGrid=g;terrainGeo=meta;geoObjects=objects;}};"
)($,els);
const grid={heights_m:[[100,100,100],[100,140,100],[100,100,100]],
  x_step_m:7,y_step_m:11};
const geo={crs:"EPSG:4326",west_lon:8.5,north_lat:49.2,
  lon_step_deg:0.0001,lat_step_deg:-0.0001,vertical_reference:"unspecified"};
const saved=JSON.stringify(grid);
const center=api.terrainGridPoint(grid,geo,{latitude:49.1999,longitude:8.5001});
assert.ok(center);
assert.ok(Math.abs(center.row-1)<1e-7);
assert.ok(Math.abs(center.col-1)<1e-7);
assert.equal(center.elevation,140);
const midway=api.terrainGridPoint(grid,geo,{latitude:49.19995,longitude:8.50005});
assert.ok(Math.abs(midway.elevation-110)<1e-5);
const far=api.terrainGridPoint(grid,geo,{latitude:49.1,longitude:8.6});
assert.equal(far,null);
assert.equal(api.terrainGridPoint(grid,null,{latitude:49.2,longitude:8.5}),null);
assert.equal(api.terrainGridPoint(grid,{...geo,crs:"EPSG:32632"},
  {latitude:49.2,longitude:8.5}),null);
assert.deepEqual(api.terrainGeoFromGrid(geo,1,1),{
  latitude:49.1999,longitude:8.5001});
const line={name:"Profil",kind:"line",vertices:[
  {latitude:49.2,longitude:8.5},{latitude:49.1998,longitude:8.5002}]};
const profile=api.terrainPolylineProfile(line,grid,geo);
assert.ok(profile);
assert.equal(profile.samples.length,129);
assert.ok(profile.distance_m>25&&profile.distance_m<27);
assert.ok(profile.max_m>139.5);
assert.ok(profile.min_m>=100);
assert.equal(profile.samples[0].elevation,100);
assert.equal(profile.samples[128].elevation,100);
assert.ok(profile.samples.every(p=>Number.isFinite(p.elevation)));
const outside={...line,vertices:[
  line.vertices[0],{latitude:49.18,longitude:8.6}]};
assert.equal(api.terrainGeoPolyline(outside,grid,geo),null);
assert.equal(api.terrainPolylineProfile(outside,grid,geo),null);

const view={azimuth:35,tilt:45,zoom:1,exaggeration:2};
const p=api.terrainProjection(grid,view,1000,590);
assert.equal(p.cells.length,4);
const sample=p.project(1,1,140);
const hit=api.terrainProbeAt(grid,view,sample.x,sample.y,1000,590);
assert.ok(hit&&Number.isFinite(hit.elevation));
assert.ok(hit.elevation>=100&&hit.elevation<=140);

const rows=[{id:"l1",object:line},{id:"l2",object:outside},
  {id:"c",object:{kind:"circle",vertices:[{latitude:49.1999,longitude:8.5001}],radius_m:100}}];
api.setState(grid,geo,rows);
api.terrainRefreshProfileOptions();
assert.equal($("terrain-profile-object").children.length,2);
$("terrain-profile-object").value="l1";
api.terrainGenerateProfile();
assert.match($("terrain-profile-message").textContent,/Profil Profil/);
assert.match($("terrain-profile-message").textContent,/Höhenbezug unbekannt/);
assert.equal(JSON.stringify(grid),saved,"visualization must not mutate STL input");
console.log("Phase 19 WGS84/probe/profile: OK");
"""


def test_phase19_real_studio_js_georeferencing_and_profile():
    if not shutil.which("node"):
        pytest.skip("Node.js required to test real embedded browser geometry")
    scripts = re.findall(r"<script>(.*?)</script>",render_studio(),re.DOTALL)
    assert len(scripts)==1
    result=subprocess.run(["node","-e",_JS],input=scripts[0],
                          text=True,capture_output=True,timeout=20,check=False)
    assert result.returncode==0,result.stdout+result.stderr
    assert "Phase 19 WGS84/probe/profile: OK" in result.stdout
