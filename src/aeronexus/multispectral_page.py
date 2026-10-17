"""Multispectral workspace (own web UI tab ``/multispectral``) for DJI Mavic 3M.

Static HTML/JS without credentials. Index and band grids are float32 arrays
computed by the local API (DJI M3M processing guide); the browser never
contacts MinIO and never sees object keys.
"""

HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="dark">
<title>AeroNexusAdvanced · Multispektral</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<style>
:root{font:14px/1.45 system-ui,"Segoe UI",sans-serif;color-scheme:dark;--bg:#0b1323;--pane:#122139;--line:#334e69;--ink:#eaf4ff;--sub:#a9bfd8;--mint:#75e3bd;--amber:#e4bd78;--red:#ff9ba8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink)}
a{color:#9dd5ff}
button,select,input{font:inherit;color:#eef7ff;background:#213d5e;border:1px solid #426487;border-radius:8px;padding:7px 10px}
button{cursor:pointer}button:hover{background:#2a517a}button:disabled{opacity:.5;cursor:not-allowed}
button.active{border-color:var(--mint);background:#245a55}
input{min-width:0}
:focus-visible{outline:2px solid var(--mint);outline-offset:2px}
header{display:flex;align-items:center;gap:15px;flex-wrap:wrap;padding:12px 20px;background:#142440;border-bottom:1px solid var(--line)}
.logo{font-weight:800;font-size:18px;white-space:nowrap}.logo small{display:block;font-size:10px;letter-spacing:.18em;color:#7abef0}
.tabs{display:flex;align-items:center;flex-wrap:wrap;gap:13px}
.tabs a{font-size:13px;text-decoration:none}.tabs .active{font-weight:700;color:var(--mint)}
.header-state{margin-left:auto;font-size:12px;color:var(--sub)}
.layout{display:grid;grid-template-columns:minmax(250px,300px) minmax(320px,1fr) minmax(290px,350px);gap:12px;padding:12px;height:calc(100vh - 66px);min-height:640px}
.panel{min-width:0;min-height:0;border:1px solid var(--line);border-radius:13px;background:var(--pane);padding:14px;display:flex;flex-direction:column;overflow:hidden}
.panel h2{font-size:16px;margin:0 0 8px}.panel h3{font-size:13px;margin:14px 0 6px;color:#cfe3f7}
.eyebrow{font-size:11px;letter-spacing:.12em;color:#87b6e1;text-transform:uppercase;font-weight:700}
.sub{font-size:12px;color:var(--sub)}
.scroll{overflow-y:auto;min-height:0;flex:1;overscroll-behavior:contain}
.row{display:flex;gap:7px;align-items:center;flex-wrap:wrap}
.grow{flex:1}
.item{display:block;width:100%;text-align:left;margin:6px 0;background:#142842;border:1px solid #33506d;border-radius:9px;padding:9px}
.item:hover,.item.active{border-color:#76bfff;background:#214362}
.item b{display:block;font-size:13px}.item small{display:block;color:#b5cae1;font-size:11px;margin-top:3px}
.band{display:inline-block;font-size:10px;padding:1px 6px;border-radius:999px;margin-right:3px;border:1px solid #4e6a84}
.band.on{color:#0b1323;background:var(--mint);border-color:var(--mint)}
.badge{display:inline-block;font-size:11px;padding:2px 8px;border:1px solid #486d8b;border-radius:999px}
.badge.good{color:var(--mint);border-color:#327f6b}.badge.warn{color:var(--amber);border-color:#806844}.badge.bad{color:var(--red);border-color:#984b5d}
.toolbar{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin-bottom:9px}
.toolbar label{font-size:12px;color:var(--sub);display:flex;gap:5px;align-items:center}
.toolbar input[type=number]{width:72px}
.viewer{position:relative;flex:1;min-height:260px;display:flex;align-items:center;justify-content:center;background:#08101c;border-radius:9px;overflow:hidden}
.stack{position:relative}
.stack canvas{position:absolute;inset:0;width:100%;height:100%}
#overlay{cursor:crosshair;touch-action:none}
.empty{color:var(--sub);text-align:center;padding:30px}
.views{display:flex;gap:6px;margin:0 0 9px}
#ms-map{position:absolute;inset:0;display:none;background:#23374f}
.map-state{position:absolute;z-index:500;left:10px;bottom:10px;max-width:min(560px,88%);background:#112137e8;border-radius:8px;padding:7px 9px;font-size:11px;color:#c8dbed}
.map-legend{position:absolute;z-index:500;right:10px;bottom:22px;background:#112137e8;border-radius:8px;padding:7px 9px;font-size:11px;color:#c8dbed;display:none}
.map-legend canvas{display:block;width:140px;height:10px;margin:4px 0;border-radius:3px}
.readout{position:absolute;left:10px;bottom:10px;background:#0f1d31e6;border:1px solid #35536f;border-radius:8px;padding:5px 9px;font:12px ui-monospace,Consolas,monospace;pointer-events:none}
.colorbar{display:flex;align-items:center;gap:8px;margin-top:9px;font-size:12px}
.colorbar canvas{flex:1;height:14px;border-radius:4px;border:1px solid #3a5876}
.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
.stat{background:#0e2137;border:1px solid #2c465e;border-radius:8px;padding:7px;min-width:0}
.stat span{display:block;font-size:10px;color:var(--sub)}.stat b{font-size:16px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 10px;font-size:12px}
.kv span{color:var(--sub)}.kv b{font-weight:600;overflow-wrap:anywhere}
.classbar{display:flex;height:16px;border-radius:5px;overflow:hidden;margin:6px 0;border:1px solid #3a5876}
table{width:100%;border-collapse:collapse;font-size:12px}
td,th{padding:5px 4px;border-bottom:1px solid #2f4a64;text-align:left}
th{color:var(--sub);font-weight:600}
.note{font-size:11px;color:var(--sub);line-height:1.5;margin:8px 0}
.warnbox{font-size:12px;color:#ffd0a4;border-left:3px solid #d6a862;background:#2a2a2a55;padding:6px 8px;margin:6px 0}
.error{color:var(--red)}
@media(max-width:1200px){.layout{grid-template-columns:270px minmax(0,1fr)}.side-right{grid-column:1/-1}}
@media(max-width:760px){.layout{display:flex;flex-direction:column;height:auto}.panel{overflow:visible}.scroll{max-height:340px}.viewer{min-height:320px}.header-state{margin-left:0}}
</style>
</head>
<body>
<header>
<div class="logo"><small>AERONEXUS ADVANCED</small>Multispektral (M3M)</div>
<nav class="tabs" aria-label="Projektbereiche">
<a href="/operations">Operations Center</a>
<a href="/studio">Mission Studio</a>
<a href="/status">Live-Status</a>
<a href="/media">DJI Medien</a>
<a href="/thermal">Thermografie</a>
<span class="active" aria-current="page">Multispektral</span>
</nav>
<span class="header-state" id="state" role="status" aria-live="polite">Lade Aufnahmen…</span>
</header>
<div class="layout">
<section class="panel" aria-labelledby="list-title">
<div class="eyebrow">MinIO · nur lesen</div>
<h2 id="list-title">M3M-Aufnahmen</h2>
<div class="sub">Bänder werden über die CaptureUUID zusammengeführt (auch FlightHub-Uploads und SD-Importe).</div>
<div class="scroll" id="list" style="margin-top:8px"></div>
</section>

<section class="panel" aria-labelledby="viewer-title">
<div class="row" style="justify-content:space-between"><h2 id="viewer-title">Keine Aufnahme gewählt</h2><span id="viewer-badge"></span></div>
<div class="views" role="tablist" aria-label="Ansicht">
<button type="button" role="tab" id="view-image" class="active" aria-selected="true">Bild</button>
<button type="button" role="tab" id="view-map" aria-selected="false">Karte</button>
<span class="grow"></span>
<button type="button" id="map-compute" hidden title="NDVI aller Aufnahmen ohne Übersicht berechnen">NDVI-Übersicht berechnen</button>
<label class="sub" id="map-overlay-label" hidden><input type="checkbox" id="map-overlay" checked> NDVI-Bilder auf Footprints</label>
</div>
<div class="toolbar" role="toolbar" aria-label="Darstellung" id="image-tools">
<label>Ebene <select id="layer">
<option value="ndvi">NDVI</option><option value="gndvi">GNDVI</option><option value="ndre">NDRE</option><option value="lci">LCI</option>
<option value="cir">Falschfarben CIR (NIR/R/G)</option>
<option value="band_g">Band Grün</option><option value="band_r">Band Rot</option><option value="band_re">Band RedEdge</option><option value="band_nir">Band NIR</option></select></label>
<label>Farben <select id="cmap"><option value="rdylgn">Rot–Gelb–Grün</option><option value="viridis">Viridis</option><option value="gray">Graustufen</option></select></label>
<label>Bereich <select id="range-mode"><option value="auto">P2–P98</option><option value="fixed">−1 … 1</option><option value="veg">0 … 1</option><option value="manual">Manuell</option></select></label>
<label id="manual-range" hidden><input id="range-low" type="number" step="0.01" aria-label="Untergrenze"> – <input id="range-high" type="number" step="0.01" aria-label="Obergrenze"></label>
<label>Auflösung <select id="scale"><option value="2">1296×972</option><option value="4">648×486</option><option value="1">2592×1944 (langsam)</option></select></label>
<span class="grow"></span>
<button id="tool-point" type="button" class="active" aria-pressed="true">Punkt</button>
<button id="tool-box" type="button" aria-pressed="false">Bereich</button>
</div>
<div class="viewer" id="viewer">
<div class="empty" id="empty">Aufnahme links wählen.<br>Berechnung nach DJI Mavic 3M Image Processing Guide auf dem Server.</div>
<div class="stack" id="stack" hidden><canvas id="image"></canvas><canvas id="overlay" aria-label="Indexkarte, klicken zum Messen"></canvas></div>
<div class="readout" id="readout" hidden></div>
<div id="ms-map" aria-label="Karte der Multispektral-Aufnahmen"></div>
<div class="map-state" id="map-state" hidden>Lade Karte…</div>
<div class="map-legend" id="map-legend">NDVI (Median)<canvas id="map-legend-bar" width="140" height="1"></canvas><span>0</span><span style="float:right">1</span></div>
</div>
<div class="colorbar" id="colorbar-row"><span id="cb-low">–</span><canvas id="colorbar" width="256" height="1"></canvas><span id="cb-high">–</span></div>
<div class="row" style="margin-top:9px">
<button id="export-png" type="button" disabled>PNG speichern</button>
<button id="export-csv" type="button" disabled>Messungen CSV</button>
<button id="export-grid" type="button" disabled>Raster CSV</button>
<button id="export-json" type="button" disabled>Bericht JSON</button>
<span class="grow"></span>
<a id="open-rgb" href="#" target="_blank" rel="noopener" hidden>RGB-Foto ↗</a>
<a id="open-preview" href="#" target="_blank" rel="noopener" hidden>MS-Vorschau ↗</a>
</div>
</section>

<aside class="panel side-right scroll" aria-label="Statistik und Metadaten">
<div class="eyebrow">Analyse</div>
<h2 id="layer-title">Statistik</h2>
<div class="sub" id="formula"></div>
<div class="stats" style="margin-top:8px">
<div class="stat"><span>Minimum</span><b id="s-min">–</b></div>
<div class="stat"><span>Median</span><b id="s-median">–</b></div>
<div class="stat"><span>Maximum</span><b id="s-max">–</b></div>
<div class="stat"><span>P5</span><b id="s-p05">–</b></div>
<div class="stat"><span>Mittel</span><b id="s-mean">–</b></div>
<div class="stat"><span>P95</span><b id="s-p95">–</b></div>
</div>
<div id="classes"></div>
<div class="note error" id="error" hidden></div>
<div id="warnings"></div>
<h3>Messungen</h3>
<table><thead><tr><th>#</th><th>Art</th><th>Wert</th><th></th></tr></thead><tbody id="spots"></tbody></table>
<h3>Bänder</h3>
<table><thead><tr><th>Band</th><th>Wellenlänge</th><th>Irradiance</th><th>Belichtung</th></tr></thead><tbody id="bands"></tbody></table>
<h3>Aufnahme</h3>
<div class="kv" id="meta"><span>–</span><b>–</b></div>
<div class="note" id="method">Verarbeitung: Schwarzwert, Gain und Belichtungszeit (Gl. 9), Vignettierung (Gl. 7/8), Objektiv-Entzerrung, Bandausrichtung per Calibrated HMatrix, Sonnenlichtsensor (Gl. 4–6). Reflexionswerte sind relativ (Faktor ρ_NIR ohne Referenztafel unbekannt); NDVI, GNDVI, NDRE und LCI sind davon unabhängig. Bei Nahaufnahmen bleibt Parallaxe zwischen den Bändern. Seriennummern werden nicht angezeigt.</div>
</aside>
</div>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
"use strict";
const $=id=>document.getElementById(id);
let captures=[],current=null,data=null,W=0,H=0,cir=null,spots=[],tool="point",drag=null,busy=0;
const CMAPS={
  rdylgn:[[0,165,0,38],[.25,244,109,67],[.5,255,255,191],[.75,102,189,99],[1,0,104,55]],
  viridis:[[0,68,1,84],[.25,59,82,139],[.5,33,145,140],[.75,94,201,98],[1,253,231,37]],
  gray:[[0,0,0,0],[1,255,255,255]]
};
const CLASS_COLORS=["#3b6fb6","#c8a77a","#f4e285","#9ccc65","#1b7a3d"];
function lut(name){
  const stops=CMAPS[name]||CMAPS.rdylgn,out=new Uint8ClampedArray(256*3);
  for(let i=0;i<256;i++){const t=i/255;let k=0;while(k<stops.length-2&&t>stops[k+1][0])k++;
    const a=stops[k],b=stops[k+1],f=(t-a[0])/((b[0]-a[0])||1);for(let c=0;c<3;c++)out[i*3+c]=a[c+1]+(b[c+1]-a[c+1])*f;}
  return out;
}
function fmt(v,d=3){return typeof v==="number"&&Number.isFinite(v)?v.toFixed(d).replace(".",","):"–";}
function el(tag,text,cls){const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;}
async function api(path,binary){
  const res=await fetch(path,{cache:"no-store",credentials:"same-origin"});
  if(!res.ok){let d="HTTP "+res.status;try{const j=await res.json();if(typeof j.detail==="string")d=j.detail;}catch(e){}throw new Error(d);}
  return binary?res:res.json();
}
function isIndex(layer){return !layer.startsWith("band_")&&layer!=="cir";}

async function loadCaptures(){
  try{
    const r=await api("/api/v1/multispectral/captures");captures=r.captures||[];
    const list=$("list");list.replaceChildren();
    for(const c of captures){
      const b=el("button",null,"item");b.type="button";b.dataset.id=c.capture_uuid;
      const t=c.captured_at?new Date(c.captured_at).toLocaleString("de-DE"):"Zeit unbekannt";
      b.append(el("b",t));
      const s=el("small");for(const band of ["Green","Red","RedEdge","NIR"])s.append(el("span",{Green:"G",Red:"R",RedEdge:"RE",NIR:"NIR"}[band],"band"+(c.bands[band]?" on":"")));
      b.append(s);
      const irr=Object.values(c.bands).map(x=>x.irradiance).filter(x=>typeof x==="number");
      b.append(el("small",[c.position?(c.position.gps_status||"GNSS"):"kein GNSS",irr.length?"Sonne "+Math.round(Math.min(...irr))+"–"+Math.round(Math.max(...irr)):"",c.rgb?"mit RGB":""].filter(Boolean).join(" · ")));
      if(c.warnings.length)b.append(el("small","⚠ "+c.warnings.length+" Hinweis(e)"));
      b.addEventListener("click",()=>select(c));list.append(b);
    }
    $("state").textContent=captures.length?`${captures.length} Aufnahmen · Katalog ${r.scanned_at?new Date(r.scanned_at).toLocaleString("de-DE"):"–"}`:"Keine M3M-Aufnahmen – auf dem Pi: .venv/bin/python -m aeronexus.multispectral";
  }catch(e){$("state").textContent="Katalog nicht verfügbar: "+e.message;}
}

function select(c){
  current=c;spots=[];renderSpots();
  document.querySelectorAll(".item.active").forEach(e=>e.classList.remove("active"));
  const btn=document.querySelector(`.item[data-id="${c.capture_uuid}"]`);if(btn)btn.classList.add("active");
  $("viewer-title").textContent=c.captured_at?new Date(c.captured_at).toLocaleString("de-DE"):c.capture_uuid;
  $("open-rgb").hidden=!c.rgb;if(c.rgb)$("open-rgb").href=`/api/v1/studio/dji-media/${c.rgb.id}/file`;
  $("open-preview").hidden=!c.preview;if(c.preview)$("open-preview").href=`/api/v1/studio/dji-media/${c.preview.id}/file`;
  for(const o of $("layer").options)o.disabled=o.value==="cir"?!["band_nir","band_r","band_g"].every(l=>c.layers.includes(l)):!c.layers.includes(o.value);
  if($("layer").selectedOptions[0].disabled){const ok=[...$("layer").options].find(o=>!o.disabled);if(ok)$("layer").value=ok.value;}
  renderMeta(c);load();if(typeof highlight==="function")highlight();
}

async function grid(layer,scale){
  const res=await api(`/api/v1/multispectral/captures/${current.capture_uuid}/layers/${layer}/grid?scale=${scale}`,true);
  const w=+res.headers.get("X-Grid-Width"),h=+res.headers.get("X-Grid-Height"),buf=await res.arrayBuffer();
  if(!(w>0&&h>0&&buf.byteLength===w*h*4))throw new Error("Unerwartetes Raster");
  return {w,h,g:new Float32Array(buf)};
}

async function load(){
  if(!current)return;
  const token=++busy,layer=$("layer").value,scale=$("scale").value;
  $("viewer-badge").innerHTML='<span class="badge">Berechne…</span>';$("error").hidden=true;
  try{
    if(layer==="cir"){
      const parts=[];for(const l of ["band_nir","band_r","band_g"])parts.push(await grid(l,scale));
      if(token!==busy)return;
      cir=parts;data=null;W=parts[0].w;H=parts[0].h;
      $("layer-title").textContent="Falschfarben CIR";$("formula").textContent="Rot = NIR, Grün = Rot, Blau = Grün (je P99 skaliert): vitale Vegetation erscheint rot.";
      renderStats(null);
    }else{
      const [a,g]=await Promise.all([api(`/api/v1/multispectral/captures/${current.capture_uuid}/layers/${layer}?scale=${scale}`),grid(layer,scale)]);
      if(token!==busy)return;
      data={...a,grid:g.g};cir=null;W=g.w;H=g.h;
      $("layer-title").textContent=a.label;$("formula").textContent=a.formula||a.relative;
      renderStats(a.stats);
    }
    $("viewer-badge").innerHTML='<span class="badge good">DJI-M3M-Kalibrierung</span>';
    show();
  }catch(e){if(token!==busy)return;$("error").textContent="Berechnung fehlgeschlagen: "+e.message;$("error").hidden=false;$("viewer-badge").innerHTML='<span class="badge bad">Fehler</span>';}
  finally{exportState();}
}

function renderStats(s){
  for(const k of ["min","median","max","p05","mean","p95"])$("s-"+k).textContent=s?fmt(s[k]):"–";
  const box=$("classes");box.replaceChildren();
  if(s&&s.classes){
    box.append(el("h3","NDVI-Klassen (Richtwerte)"));
    const bar=el("div",null,"classbar");
    s.classes.forEach((c,i)=>{const seg=el("div");seg.style.width=(c.share*100)+"%";seg.style.background=CLASS_COLORS[i];seg.title=`${c.label}: ${(c.share*100).toFixed(1)} %`;bar.append(seg);});
    box.append(bar);
    const t=el("table"),tb=el("tbody");t.append(tb);
    s.classes.forEach((c,i)=>{const tr=el("tr");const sw=el("td","■");sw.style.color=CLASS_COLORS[i];tr.append(sw,el("td",`${fmt(c.from,1)} … ${fmt(c.to,1)}`),el("td",c.label),el("td",(c.share*100).toFixed(1).replace(".",",")+" %"));tb.append(tr);});
    box.append(t);
  }
  const warn=$("warnings");warn.replaceChildren();
  for(const w of (current&&current.warnings)||[])warn.append(el("div",w,"warnbox"));
}

function renderMeta(c){
  const tb=$("bands");tb.replaceChildren();
  for(const b of ["Green","Red","RedEdge","NIR"]){
    const x=c.bands[b],tr=el("tr");
    tr.append(el("td",b),el("td",x?x.band_freq||"–":"fehlt"),el("td",x&&typeof x.irradiance==="number"?fmt(x.irradiance,1):"–"),el("td",x&&x.exposure_time_us?Math.round(x.exposure_time_us)+" µs":"–"));tb.append(tr);
  }
  const rows=[["Modell",c.model],["Aufnahme",c.captured_at],["CaptureUUID",c.capture_uuid.slice(0,8)+"…"]];
  if(c.position)rows.push(["Position",`${fmt(c.position.latitude,6)}, ${fmt(c.position.longitude,6)}`],["Höhe rel.",fmt(c.position.relative_altitude_m,1)+" m"],["GNSS",c.position.gps_status]);
  else rows.push(["Position","kein GNSS-Fix"]);
  if(c.gimbal)rows.push(["Gimbal Pitch",fmt(c.gimbal.pitch_deg,1)+"°"]);
  const box=$("meta");box.replaceChildren();for(const [k,v] of rows)box.append(el("span",k),el("b",v==null||v===""?"–":String(v)));
}

function range(){
  const mode=$("range-mode").value,s=data&&data.stats;
  if(mode==="fixed")return [-1,1];if(mode==="veg")return [0,1];
  if(mode==="manual"){const lo=parseFloat($("range-low").value),hi=parseFloat($("range-high").value);if(Number.isFinite(lo)&&Number.isFinite(hi)&&hi>lo)return [lo,hi];}
  return s?[s.p02,s.p98]:[0,1];
}
function show(){
  if(view==="map")return;
  $("empty").hidden=true;const c=$("image"),o=$("overlay");c.width=o.width=W;c.height=H;$("stack").hidden=false;fit();draw();
}
function fit(){const v=$("viewer"),s=$("stack");if(!W)return;const k=Math.min(v.clientWidth/W,v.clientHeight/H);s.style.width=Math.floor(W*k)+"px";s.style.height=Math.floor(H*k)+"px";}
function p99(g){const step=Math.max(1,Math.floor(g.length/20000)),sample=[];for(let i=0;i<g.length;i+=step)if(Number.isFinite(g[i]))sample.push(g[i]);sample.sort((a,b)=>a-b);return sample[Math.floor(sample.length*.99)]||1;}
function draw(){
  const ctx=$("image").getContext("2d"),img=ctx.createImageData(W,H),px=img.data;
  if(cir){
    const sc=cir.map(p=>255/p99(p.g));
    for(let i=0;i<W*H;i++){const j=i*4;for(let c=0;c<3;c++){const v=cir[c].g[i];px[j+c]=Number.isFinite(v)?v*sc[c]:0;}px[j+3]=255;}
    $("colorbar-row").hidden=true;
  }else if(data){
    const pal=lut($("cmap").value),[lo,hi]=range(),span=(hi-lo)||1,g=data.grid;
    for(let i=0;i<g.length;i++){const j=i*4,v=g[i];if(!Number.isFinite(v)){px[j]=px[j+1]=px[j+2]=20;px[j+3]=255;continue;}
      let k=Math.round((v-lo)/span*255);k=k<0?0:k>255?255:k;px[j]=pal[k*3];px[j+1]=pal[k*3+1];px[j+2]=pal[k*3+2];px[j+3]=255;}
    const cb=$("colorbar").getContext("2d"),bar=cb.createImageData(256,1);
    for(let k=0;k<256;k++){bar.data[k*4]=pal[k*3];bar.data[k*4+1]=pal[k*3+1];bar.data[k*4+2]=pal[k*3+2];bar.data[k*4+3]=255;}
    cb.putImageData(bar,0,0);$("cb-low").textContent=fmt(lo,2);$("cb-high").textContent=fmt(hi,2);$("colorbar-row").hidden=false;
  }
  ctx.putImageData(img,0,0);drawOverlay();
}
function value(i){if(cir)return null;return data?data.grid[i]:null;}
function drawOverlay(){
  const ctx=$("overlay").getContext("2d");ctx.clearRect(0,0,W,H);const lw=Math.max(1.5,W/400);
  spots.forEach((s,i)=>{ctx.lineWidth=lw+2;ctx.strokeStyle="#000";
    if(s.kind==="point"){const r=Math.max(5,W/90);ctx.beginPath();ctx.moveTo(s.x-r,s.y);ctx.lineTo(s.x+r,s.y);ctx.moveTo(s.x,s.y-r);ctx.lineTo(s.x,s.y+r);ctx.stroke();ctx.strokeStyle="#fff";ctx.lineWidth=lw;ctx.stroke();}
    else{ctx.strokeRect(s.x,s.y,s.w,s.h);ctx.strokeStyle="#fff";ctx.lineWidth=lw;ctx.setLineDash([6,4]);ctx.strokeRect(s.x,s.y,s.w,s.h);ctx.setLineDash([]);}
    ctx.font=`bold ${Math.max(12,W/45)}px system-ui`;ctx.lineWidth=3;ctx.strokeStyle="#000";ctx.strokeText(String(i+1),s.x+6,s.y-6);ctx.fillStyle="#fff";ctx.fillText(String(i+1),s.x+6,s.y-6);});
  if(drag&&drag.w!==undefined){ctx.strokeStyle="#75e3bd";ctx.lineWidth=lw;ctx.strokeRect(drag.x,drag.y,drag.w,drag.h);}
}
function cell(e){const r=$("overlay").getBoundingClientRect();return [Math.min(W-1,Math.max(0,Math.floor((e.clientX-r.left)/r.width*W))),Math.min(H-1,Math.max(0,Math.floor((e.clientY-r.top)/r.height*H)))];}
function areaStats(x,y,w,h){let mn=Infinity,mx=-Infinity,sum=0,n=0;for(let j=y;j<y+h;j++)for(let i=x;i<x+w;i++){const v=data.grid[j*W+i];if(!Number.isFinite(v))continue;sum+=v;n++;if(v<mn)mn=v;if(v>mx)mx=v;}return n?{min:mn,max:mx,mean:sum/n,n}:{n:0};}
function renderSpots(){
  const tb=$("spots");tb.replaceChildren();
  spots.forEach((s,i)=>{const tr=el("tr");const v=s.kind==="point"?fmt(s.v):s.n?`Ø ${fmt(s.mean)} · ${fmt(s.min)}…${fmt(s.max)}`:"keine gültigen Pixel";
    tr.append(el("td",String(i+1)),el("td",(s.layer||"").toUpperCase()+(s.kind==="point"?` (${s.x}, ${s.y})`:` ${s.w}×${s.h}`)),el("td",v));
    const td=el("td"),b=el("button","✕");b.type="button";b.style.padding="2px 7px";b.addEventListener("click",()=>{spots.splice(i,1);renderSpots();drawOverlay();});td.append(b);tr.append(td);tb.append(tr);});
  exportState();
}
const ov=$("overlay");
ov.addEventListener("pointerdown",e=>{if(!data)return;const [x,y]=cell(e);ov.setPointerCapture(e.pointerId);drag={x0:x,y0:y,x,y};});
ov.addEventListener("pointermove",e=>{if(!W)return;const [x,y]=cell(e);const v=value(y*W+x);const ro=$("readout");ro.hidden=false;
  ro.textContent=cir?`x ${x} · y ${y} · NIR ${fmt(cir[0].g[y*W+x],4)} · R ${fmt(cir[1].g[y*W+x],4)} · G ${fmt(cir[2].g[y*W+x],4)}`:`x ${x} · y ${y} · ${data?data.label:""} ${fmt(v)}`;
  if(drag&&tool==="box"){drag.x=Math.min(drag.x0,x);drag.y=Math.min(drag.y0,y);drag.w=Math.abs(x-drag.x0)+1;drag.h=Math.abs(y-drag.y0)+1;drawOverlay();}});
ov.addEventListener("pointerleave",()=>{$("readout").hidden=true;});
ov.addEventListener("pointerup",e=>{if(!data||!drag)return;const [x,y]=cell(e);
  if(tool==="box"&&drag.w>1&&drag.h>1)spots.push({kind:"box",layer:data.layer,x:drag.x,y:drag.y,w:drag.w,h:drag.h,...areaStats(drag.x,drag.y,drag.w,drag.h)});
  else if(tool==="point")spots.push({kind:"point",layer:data.layer,x,y,v:data.grid[y*W+x]});
  drag=null;if(spots.length>50)spots.shift();renderSpots();drawOverlay();});
function setTool(t){tool=t;for(const [id,v] of [["tool-point","point"],["tool-box","box"]]){$(id).classList.toggle("active",t===v);$(id).setAttribute("aria-pressed",String(t===v));}}
$("tool-point").addEventListener("click",()=>setTool("point"));$("tool-box").addEventListener("click",()=>setTool("box"));

function save(blob,name){const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),2000);}
function base(){return "m3m_"+(current?current.capture_uuid.slice(0,8):"capture")+"_"+$("layer").value;}
function exportState(){$("export-png").disabled=!(data||cir);$("export-grid").disabled=!data;$("export-csv").disabled=!spots.length;$("export-json").disabled=!data;}
$("export-png").addEventListener("click",()=>{const c=document.createElement("canvas");c.width=W;c.height=H;const x=c.getContext("2d");x.drawImage($("image"),0,0);x.drawImage($("overlay"),0,0);c.toBlob(b=>b&&save(b,base()+".png"),"image/png");});
$("export-csv").addEventListener("click",()=>{const l=["nr;ebene;art;x;y;breite;hoehe;wert;min;max;mittel"];
  spots.forEach((s,i)=>l.push([i+1,s.layer,s.kind==="point"?"punkt":"bereich",s.x,s.y,s.w||1,s.h||1,s.v==null?"":s.v.toFixed(4),s.min==null?"":s.min.toFixed(4),s.max==null?"":s.max.toFixed(4),s.mean==null?"":s.mean.toFixed(4)].join(";")));
  save(new Blob([l.join("\n")+"\n"],{type:"text/csv"}),base()+"_messungen.csv");});
$("export-grid").addEventListener("click",()=>{const rows=[];for(let y=0;y<H;y++){const r=new Array(W);for(let x=0;x<W;x++){const v=data.grid[y*W+x];r[x]=Number.isFinite(v)?v.toFixed(4):"";}rows.push(r.join(";"));}
  save(new Blob([rows.join("\n")+"\n"],{type:"text/csv"}),base()+"_raster.csv");});
$("export-json").addEventListener("click",()=>{const d={...data};delete d.grid;save(new Blob([JSON.stringify({generated_at:new Date().toISOString(),analysis:d,measurements:spots},null,2)],{type:"application/json"}),base()+"_bericht.json");});

$("layer").addEventListener("change",()=>{
  const layer=$("layer").value;
  if(isIndex(layer)){$("cmap").value="rdylgn";if($("range-mode").value==="auto")$("range-mode").value=layer==="ndvi"?"veg":"auto";}
  else if(layer!=="cir"){$("cmap").value="gray";$("range-mode").value="auto";}
  load();});
$("scale").addEventListener("change",()=>{spots=[];renderSpots();load();});
for(const id of ["cmap","range-low","range-high"])$(id).addEventListener("input",()=>{if(data)draw();});
$("range-mode").addEventListener("change",()=>{const m=$("range-mode").value==="manual";$("manual-range").hidden=!m;
  if(m&&data&&$("range-low").value===""){$("range-low").value=data.stats.p02.toFixed(2);$("range-high").value=data.stats.p98.toFixed(2);}if(data)draw();});

/* ----------------------------------------------------------------- map --- */
let view="image",map=null,mapLayer=null,overlayLayer=null,mapItems=[],selectedMark=null;
function ndviColor(v){if(typeof v!=="number")return "#8aa0b8";const pal=lut("rdylgn");let k=Math.round(Math.max(0,Math.min(1,v))*255);return `rgb(${pal[k*3]},${pal[k*3+1]},${pal[k*3+2]})`;}
function setView(v){
  view=v;
  for(const [id,name] of [["view-image","image"],["view-map","map"]]){$(id).classList.toggle("active",v===name);$(id).setAttribute("aria-selected",String(v===name));}
  const isMap=v==="map";
  $("image-tools").hidden=isMap;$("colorbar-row").hidden=isMap||!!cir;$("ms-map").style.display=isMap?"block":"none";
  $("map-state").hidden=!isMap;$("map-legend").style.display=isMap?"block":"none";
  $("map-compute").hidden=!isMap;$("map-overlay-label").hidden=!isMap;
  if(isMap){$("stack").hidden=true;$("empty").hidden=true;$("readout").hidden=true;initMap();}
  else if(data||cir)show();else $("empty").hidden=false;
}
function initMap(){
  if(typeof L==="undefined"){$("map-state").textContent="Kartenbibliothek (Leaflet) konnte nicht geladen werden.";return;}
  if(!map){
    map=L.map("ms-map",{preferCanvas:true}).setView([51.1,10.4],6);
    const sat=L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",{maxZoom:22,maxNativeZoom:19,attribution:"Esri World Imagery"});
    const osm=L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:22,maxNativeZoom:19,attribution:"© OpenStreetMap"});
    sat.addTo(map);L.control.layers({"Satellit":sat,"Straßenkarte":osm}).addTo(map);
    mapLayer=L.layerGroup().addTo(map);overlayLayer=L.layerGroup().addTo(map);
    const bar=$("map-legend-bar").getContext("2d"),img=bar.createImageData(140,1),pal=lut("rdylgn");
    for(let i=0;i<140;i++){const k=Math.round(i/139*255);img.data.set([pal[k*3],pal[k*3+1],pal[k*3+2],255],i*4);}bar.putImageData(img,0,0);
  }
  setTimeout(()=>map.invalidateSize(),50);loadMap(true);
}
async function loadMap(fit){
  try{
    const r=await api("/api/v1/multispectral/map");mapItems=r.items||[];
    mapLayer.clearLayers();overlayLayer.clearLayers();
    for(const it of mapItems){
      const color=ndviColor(it.ndvi&&it.ndvi.median);
      const tip=`${it.captured_at?new Date(it.captured_at).toLocaleString("de-DE"):""}<br>NDVI-Median ${it.ndvi?fmt(it.ndvi.median,2):"noch nicht berechnet"} · Höhe ${fmt(it.relative_altitude_m,1)} m · Pitch ${fmt(it.gimbal_pitch_deg,0)}°`+(it.ground_sample_cm?` · ${fmt(it.ground_sample_cm,1)} cm/px`:"");
      if(it.footprint)mapLayer.addLayer(L.polygon(it.footprint,{color,weight:2,fillOpacity:.12,interactive:false}));
      if(it.view_cone)mapLayer.addLayer(L.polygon(it.view_cone,{color,weight:1,fillColor:color,fillOpacity:.25,interactive:false}));
      const mk=L.circleMarker([it.latitude,it.longitude],{radius:7,color:"#0b1323",weight:2,fillColor:color,fillOpacity:1});
      mk.bindTooltip(tip);mk.on("click",()=>{const c=captures.find(x=>x.capture_uuid===it.capture_uuid);if(c)select(c);});mapLayer.addLayer(mk);
    }
    const missing=mapItems.filter(i=>i.has_ndvi&&!i.ndvi).length;
    $("map-compute").disabled=!missing;
    $("map-state").textContent=mapItems.length?`${mapItems.length} Aufnahmen mit Position · ${r.without_position} ohne GNSS · ${missing?missing+" ohne NDVI-Übersicht":"NDVI vollständig"} · Footprints nur bei Nadir-Aufnahmen (sonst Sichtkegel), ebenes Gelände angenommen`:"Keine Aufnahmen mit Position.";
    if(fit&&mapItems.length)map.fitBounds(L.latLngBounds(mapItems.map(i=>[i.latitude,i.longitude])),{padding:[40,40],maxZoom:19});
    if($("map-overlay").checked)drawOverlays();
    highlight();
  }catch(e){$("map-state").textContent="Karte nicht verfügbar: "+e.message;}
}
function highlight(){
  if(!map)return;if(selectedMark){map.removeLayer(selectedMark);selectedMark=null;}
  const it=current&&mapItems.find(i=>i.capture_uuid===current.capture_uuid);
  if(it)selectedMark=L.circleMarker([it.latitude,it.longitude],{radius:12,color:"#75e3bd",weight:3,fill:false,interactive:false}).addTo(map);
}
async function drawOverlays(){
  overlayLayer.clearLayers();
  for(const it of mapItems.filter(i=>i.footprint&&i.has_ndvi).slice(0,30)){
    try{
      const res=await api(`/api/v1/multispectral/captures/${it.capture_uuid}/layers/ndvi/grid?scale=4`,true);
      const w=+res.headers.get("X-Grid-Width"),h=+res.headers.get("X-Grid-Height"),g=new Float32Array(await res.arrayBuffer());
      const src=document.createElement("canvas");src.width=w;src.height=h;const sc=src.getContext("2d"),im=sc.createImageData(w,h),pal=lut("rdylgn");
      for(let i=0;i<g.length;i++){const v=g[i];if(!Number.isFinite(v))continue;const k=Math.round(Math.max(0,Math.min(1,v))*255);im.data.set([pal[k*3],pal[k*3+1],pal[k*3+2],235],i*4);}
      sc.putImageData(im,0,0);
      const lats=it.footprint.map(p=>p[0]),lons=it.footprint.map(p=>p[1]);
      const n=Math.max(...lats),s=Math.min(...lats),e=Math.max(...lons),wv=Math.min(...lons);
      const cw=768,ch=Math.max(1,Math.round(cw*(n-s)/((e-wv)*Math.cos(n*Math.PI/180))));
      const px=p=>[(p[1]-wv)/(e-wv)*cw,(n-p[0])/(n-s)*ch];
      const [tl,tr,,bl]=it.footprint.map(px);
      const out=document.createElement("canvas");out.width=cw;out.height=ch;const oc=out.getContext("2d");
      oc.setTransform((tr[0]-tl[0])/w,(tr[1]-tl[1])/w,(bl[0]-tl[0])/h,(bl[1]-tl[1])/h,tl[0],tl[1]);oc.drawImage(src,0,0);
      overlayLayer.addLayer(L.imageOverlay(out.toDataURL("image/png"),[[s,wv],[n,e]],{opacity:.85,interactive:false}));
    }catch(e){/* single overlay failures do not block the map */}
  }
}
$("view-image").addEventListener("click",()=>setView("image"));
$("view-map").addEventListener("click",()=>setView("map"));
$("map-overlay").addEventListener("change",()=>{if($("map-overlay").checked)drawOverlays();else overlayLayer.clearLayers();});
$("map-compute").addEventListener("click",async()=>{
  const todo=mapItems.filter(i=>i.has_ndvi&&!i.ndvi);$("map-compute").disabled=true;
  for(const [n,it] of todo.entries()){$("map-state").textContent=`Berechne NDVI-Übersicht ${n+1}/${todo.length}…`;
    try{await api(`/api/v1/multispectral/captures/${it.capture_uuid}/layers/ndvi?scale=4`);}catch(e){}}
  loadMap(false);
});
window.addEventListener("resize",fit);
$("range-mode").value="veg";
loadCaptures();
</script>
</body>
</html>
"""


def render_multispectral_page() -> str:
    return HTML
