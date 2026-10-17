"""Thermography workspace (own web UI tab ``/thermal``).

Static HTML/JS without credentials. Temperatures are fetched as a float32
grid from the local API, which obtains them from the DJI Thermal SDK; the
browser never contacts MinIO or DJI and never sees object keys.
"""

HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="dark">
<title>AeroNexusAdvanced · Thermografie</title>
<style>
:root{font:14px/1.45 system-ui,"Segoe UI",sans-serif;color-scheme:dark;--bg:#0b1323;--pane:#122139;--card:#152b47;--line:#334e69;--ink:#eaf4ff;--sub:#a9bfd8;--mint:#75e3bd;--amber:#e4bd78;--red:#ff9ba8;--hot:#ff5a4f;--cold:#5ab8ff}
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
.header-state{margin-left:auto;font-size:12px}
.layout{display:grid;grid-template-columns:minmax(250px,310px) minmax(320px,1fr) minmax(290px,350px);gap:12px;padding:12px;height:calc(100vh - 66px);min-height:640px}
.panel{min-width:0;min-height:0;border:1px solid var(--line);border-radius:13px;background:var(--pane);padding:14px;display:flex;flex-direction:column;overflow:hidden}
.panel h2{font-size:16px;margin:0 0 8px}.panel h3{font-size:13px;margin:14px 0 6px;color:#cfe3f7}
.eyebrow{font-size:11px;letter-spacing:.12em;color:#87b6e1;text-transform:uppercase;font-weight:700}
.sub{font-size:12px;color:var(--sub)}
.scroll{overflow-y:auto;min-height:0;flex:1;overscroll-behavior:contain}
.row{display:flex;gap:7px;align-items:center;flex-wrap:wrap}
.grow{flex:1}
.item{display:block;width:100%;text-align:left;margin:6px 0;background:#142842;border:1px solid #33506d;border-radius:9px;padding:9px}
.item:hover,.item.active{border-color:#76bfff;background:#214362}
.item b{display:block;font-size:13px;overflow-wrap:anywhere}.item small{color:#b5cae1;font-size:11px}
.badge{display:inline-block;font-size:11px;padding:2px 8px;border:1px solid #486d8b;border-radius:999px}
.badge.good{color:var(--mint);border-color:#327f6b}.badge.warn{color:var(--amber);border-color:#806844}.badge.bad{color:var(--red);border-color:#984b5d}
.toolbar{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin-bottom:9px}
.toolbar label{font-size:12px;color:var(--sub);display:flex;gap:5px;align-items:center}
.toolbar input[type=number]{width:78px}
.viewer{position:relative;flex:1;min-height:260px;display:flex;align-items:center;justify-content:center;background:#08101c;border-radius:9px;overflow:hidden}
.stack{position:relative;max-width:100%;max-height:100%;aspect-ratio:5/4}
.stack canvas{position:absolute;inset:0;width:100%;height:100%;image-rendering:pixelated}
#overlay{cursor:crosshair;touch-action:none}
#preview{max-width:100%;max-height:100%;display:none}
.empty{color:var(--sub);text-align:center;padding:30px}
.readout{position:absolute;left:10px;bottom:10px;background:#0f1d31e6;border:1px solid #35536f;border-radius:8px;padding:5px 9px;font:12px ui-monospace,Consolas,monospace;pointer-events:none}
.colorbar{display:flex;align-items:center;gap:8px;margin-top:9px;font-size:12px}
.colorbar canvas{flex:1;height:14px;border-radius:4px;border:1px solid #3a5876}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 10px;font-size:12px}
.kv span{color:var(--sub)}.kv b{font-weight:600;overflow-wrap:anywhere}
.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
.stat{background:#0e2137;border:1px solid #2c465e;border-radius:8px;padding:7px;min-width:0}
.stat span{display:block;font-size:10px;color:var(--sub)}.stat b{font-size:16px}
.stat.hot b{color:#ff8a7f}.stat.cold b{color:#8fd0ff}
.params{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.params label{font-size:11px;color:var(--sub);display:grid;gap:3px}
.params input,.params select{width:100%}
table{width:100%;border-collapse:collapse;font-size:12px}
td,th{padding:5px 4px;border-bottom:1px solid #2f4a64;text-align:left}
th{color:var(--sub);font-weight:600}
.note{font-size:11px;color:var(--sub);line-height:1.5;margin:8px 0}
.error{color:var(--red)}
@media(max-width:1200px){.layout{grid-template-columns:270px minmax(0,1fr)}.side-right{grid-column:1/-1}}
@media(max-width:760px){.layout{display:flex;flex-direction:column;height:auto}.panel{overflow:visible}.scroll{max-height:340px}.viewer{min-height:300px}.header-state{margin-left:0}}
</style>
</head>
<body>
<header>
<div class="logo"><small>AERONEXUS ADVANCED</small>Thermografie</div>
<nav class="tabs" aria-label="Projektbereiche">
<a href="/operations">Operations Center</a>
<a href="/studio">Mission Studio</a>
<a href="/status">Live-Status</a>
<a href="/media">DJI Medien</a>
<span class="active" aria-current="page">Thermografie</span>
</nav>
<span class="header-state" id="sdk-state" role="status" aria-live="polite">Prüfe DJI Thermal SDK…</span>
</header>
<div class="layout">
<section class="panel" aria-labelledby="list-title">
<div class="eyebrow">MinIO · nur lesen</div>
<h2 id="list-title">Wärmebilder (R-JPEG)</h2>
<div class="row"><input id="search" class="grow" type="search" maxlength="120" placeholder="Dateiname / Datum (z. B. 20261002)" aria-label="Wärmebilder suchen">
<button id="search-go" type="button">Suchen</button></div>
<div class="sub" id="list-state" role="status" aria-live="polite" style="margin:7px 0">Lade…</div>
<div class="scroll" id="list"></div>
<div class="row" style="justify-content:space-between;margin-top:8px">
<button id="prev" type="button">Zurück</button><span class="sub" id="page">–</span><button id="next" type="button">Weiter</button></div>
</section>

<section class="panel" aria-labelledby="viewer-title">
<div class="row" style="justify-content:space-between"><h2 id="viewer-title" style="overflow-wrap:anywhere">Kein Bild gewählt</h2><span id="viewer-badge"></span></div>
<div class="toolbar" role="toolbar" aria-label="Darstellung und Messwerkzeuge">
<label>Palette <select id="palette">
<option value="iron">Iron</option><option value="rainbow">Rainbow</option><option value="whitehot">White hot</option>
<option value="blackhot">Black hot</option><option value="arctic">Arctic</option><option value="lava">Lava</option></select></label>
<label>Bereich <select id="range-mode"><option value="minmax">Min–Max</option><option value="p">P5–P95</option><option value="manual">Manuell</option></select></label>
<label id="manual-range" hidden><input id="range-low" type="number" step="0.1" aria-label="Untere Grenze °C"> – <input id="range-high" type="number" step="0.1" aria-label="Obere Grenze °C"> °C</label>
<label><input id="iso-on" type="checkbox"> Isotherme ≥ <input id="iso-value" type="number" step="0.1" aria-label="Isotherme °C"> °C</label>
<label><input id="extremes" type="checkbox" checked> Hot/Cold</label>
<span class="grow"></span>
<button id="tool-point" type="button" class="active" aria-pressed="true">Punkt</button>
<button id="tool-box" type="button" aria-pressed="false">Bereich</button>
</div>
<div class="viewer" id="viewer">
<div class="empty" id="empty">Wärmebild links auswählen.<br>Temperaturen berechnet das DJI Thermal SDK auf dem Server.</div>
<div class="stack" id="stack" hidden><canvas id="thermal"></canvas><canvas id="overlay" aria-label="Wärmebild, klicken zum Messen"></canvas></div>
<img id="preview" alt="Wärmebild-Vorschau (ohne Temperaturdaten)">
<div class="readout" id="readout" hidden></div>
</div>
<div class="colorbar"><span id="cb-low">–</span><canvas id="colorbar" width="256" height="1"></canvas><span id="cb-high">–</span></div>
<div class="row" style="margin-top:9px">
<button id="export-png" type="button" disabled>PNG speichern</button>
<button id="export-csv" type="button" disabled>Messungen CSV</button>
<button id="export-grid" type="button" disabled>Raster CSV</button>
<button id="export-json" type="button" disabled>Bericht JSON</button>
<span class="grow"></span>
<a id="open-thermal" href="#" target="_blank" rel="noopener" hidden>Wärmebild-JPEG ↗</a>
<a id="open-visual" href="#" target="_blank" rel="noopener" hidden>Sichtbild ↗</a>
</div>
</section>

<aside class="panel side-right scroll" aria-label="Messwerte und Metadaten">
<div class="eyebrow">Analyse</div>
<h2>Temperaturen</h2>
<div class="stats" id="stats">
<div class="stat hot"><span>Maximum</span><b id="s-max">–</b></div>
<div class="stat cold"><span>Minimum</span><b id="s-min">–</b></div>
<div class="stat"><span>Mittel</span><b id="s-mean">–</b></div>
<div class="stat"><span>P5</span><b id="s-p05">–</b></div>
<div class="stat"><span>Median</span><b id="s-median">–</b></div>
<div class="stat"><span>P95</span><b id="s-p95">–</b></div>
</div>
<div class="note error" id="measure-error" hidden></div>
<h3>Messungen</h3>
<table><thead><tr><th>#</th><th>Art</th><th>Wert</th><th></th></tr></thead><tbody id="spots"></tbody></table>
<div class="note">Punkt: klicken. Bereich: ziehen (Min/Max/Mittel). Werte aus dem SDK-Raster.</div>
<h3>Messparameter</h3>
<div class="params">
<label>Material (Richtwert)<select id="material">
<option value="">aus Bild</option><option value="0.95">Allgemein 0,95</option><option value="0.94">Beton 0,94</option>
<option value="0.93">Asphalt / Ziegel 0,93</option><option value="0.90">Holz / Lack 0,90</option>
<option value="0.96">Wasser / Vegetation 0,96</option><option value="0.85">PV-Modulglas ca. 0,85</option>
<option value="0.98">Haut 0,98</option></select></label>
<label>Emissionsgrad (0,1–1)<input id="p-emissivity" type="number" min="0.1" max="1" step="0.01" placeholder="aus Bild"></label>
<label>Distanz m (1–25)<input id="p-distance" type="number" min="1" max="25" step="0.1" placeholder="aus Bild"></label>
<label>Luftfeuchte % (20–100)<input id="p-humidity" type="number" min="20" max="100" step="1" placeholder="aus Bild"></label>
<label>Reflektiert °C (−40–100)<input id="p-reflection" type="number" min="-40" max="100" step="0.1" placeholder="aus Bild"></label>
<label>Umgebung °C (−40–80)<input id="p-ambient" type="number" min="-40" max="80" step="0.1" placeholder="aus Bild"></label>
</div>
<div class="row" style="margin-top:8px"><button id="recalc" type="button" disabled>Neu berechnen</button><button id="reset-params" type="button">Bildwerte</button></div>
<div class="note">Leere Felder verwenden die in der Aufnahme gespeicherten Parameter. Materialwerte sind grobe Richtwerte; für belastbare Messungen Emissionsgrad und reflektierte Temperatur vor Ort bestimmen.</div>
<h3>Aufnahme</h3>
<div class="kv" id="meta"><span>–</span><b>–</b></div>
<div class="note">Seriennummern, NTRIP-Zugangsdaten und unbekannte Herstellerfelder werden nicht angezeigt. Keine Schreibzugriffe auf MinIO oder DJI.</div>
</aside>
</div>
<script>
"use strict";
const $=id=>document.getElementById(id);
const PAGE=40;
let offset=0,total=0,current=null,analysis=null,grid=null,W=0,H=0,spots=[],tool="point",drag=null;

const PALETTES={
  iron:[[0,0,0,0],[.15,32,0,90],[.35,140,0,140],[.55,220,40,40],[.75,250,140,0],[.9,255,220,40],[1,255,255,240]],
  rainbow:[[0,20,0,120],[.2,0,60,255],[.4,0,200,220],[.6,40,220,40],[.8,255,220,0],[1,230,0,0]],
  whitehot:[[0,0,0,0],[1,255,255,255]],
  blackhot:[[0,255,255,255],[1,0,0,0]],
  arctic:[[0,10,10,60],[.35,20,80,200],[.65,80,200,240],[.85,230,240,255],[1,255,190,60]],
  lava:[[0,20,10,40],[.3,90,20,90],[.6,200,40,40],[.85,255,150,30],[1,255,250,200]]
};
function lut(name){
  const stops=PALETTES[name]||PALETTES.iron,out=new Uint8ClampedArray(256*3);
  for(let i=0;i<256;i++){
    const t=i/255;let k=0;
    while(k<stops.length-2&&t>stops[k+1][0])k++;
    const a=stops[k],b=stops[k+1],f=(t-a[0])/((b[0]-a[0])||1);
    for(let c=0;c<3;c++)out[i*3+c]=a[c+1]+(b[c+1]-a[c+1])*f;
  }
  return out;
}
function fmt(v,d=1){return typeof v==="number"&&Number.isFinite(v)?v.toFixed(d).replace(".",","):"–";}
function deg(v){return typeof v==="number"?fmt(v)+" °C":"–";}
function bytes(n){return typeof n==="number"?(n/1048576).toFixed(1).replace(".",",")+" MiB":"–";}
function when(name){const m=/(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})/.exec(name||"");
  return m?`${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}:${m[6]}`:"";}
function setState(el,text,cls){el.textContent=text;el.className=(el.id==="sdk-state"?"header-state ":"sub ")+(cls||"");}

async function api(path,binary){
  const res=await fetch(path,{cache:"no-store",credentials:"same-origin"});
  if(!res.ok){
    let detail="HTTP "+res.status;
    try{const j=await res.json();if(j&&typeof j.detail==="string")detail=j.detail;}catch(e){}
    throw new Error(detail);
  }
  return binary?res:res.json();
}

async function loadStatus(){
  try{
    const s=await api("/api/v1/thermal/status");
    const sdk=s.sdk||{};
    const count=typeof s.thermal_images==="number"?s.thermal_images.toLocaleString("de-DE")+" Wärmebilder":"Index nicht verfügbar";
    if(sdk.available)setState($("sdk-state"),`DJI Thermal SDK ${sdk.tool||""} · ${sdk.runner==="box64"?"Box64":"nativ"} · ${count}`,"");
    else setState($("sdk-state"),`DJI Thermal SDK nicht verfügbar – nur Vorschau · ${count}`,"error");
    $("sdk-state").style.color=sdk.available?"var(--mint)":"var(--amber)";
  }catch(e){setState($("sdk-state"),"Status nicht abrufbar: "+e.message,"error");}
}

async function loadList(){
  const q=$("search").value.trim();
  setState($("list-state"),"Lade…");
  try{
    const r=await api(`/api/v1/thermal/images?limit=${PAGE}&offset=${offset}&q=${encodeURIComponent(q)}`);
    total=r.total||0;
    const list=$("list");list.replaceChildren();
    for(const item of r.media||[]){
      const b=document.createElement("button");b.type="button";b.className="item"+(current&&current.id===item.id?" active":"");
      const t=document.createElement("b");t.textContent=item.name;
      const s=document.createElement("small");s.textContent=[when(item.name),bytes(item.size_bytes),item.visual_id?"mit Sichtbild":""].filter(Boolean).join(" · ");
      b.append(t,s);b.addEventListener("click",()=>select(item,b));list.append(b);
    }
    setState($("list-state"),total?`${total.toLocaleString("de-DE")} Wärmebilder${r.last_scanned_at?" · Index "+new Date(r.last_scanned_at).toLocaleString("de-DE"):""}`:"Keine Wärmebilder im Index (MinIO-Scan ausführen).");
    $("page").textContent=total?`${offset+1}–${Math.min(offset+PAGE,total)} / ${total}`:"–";
    $("prev").disabled=offset===0;$("next").disabled=offset+PAGE>=total;
  }catch(e){setState($("list-state"),"Liste nicht verfügbar: "+e.message,"error");}
}

function params(){
  const out=new URLSearchParams();
  for(const k of ["emissivity","distance","humidity","reflection","ambient"]){
    const v=$("p-"+k).value.trim();if(v!=="")out.set(k,v);
  }
  return out.toString();
}

async function select(item,button){
  current=item;
  document.querySelectorAll(".item.active").forEach(e=>e.classList.remove("active"));
  if(button)button.classList.add("active");
  $("viewer-title").textContent=item.name;
  const thermalUrl=`/api/v1/studio/dji-media/${item.id}/file`;
  $("open-thermal").href=thermalUrl;$("open-thermal").hidden=false;
  $("open-visual").hidden=!item.visual_id;
  if(item.visual_id)$("open-visual").href=`/api/v1/studio/dji-media/${item.visual_id}/file`;
  spots=[];renderSpots();
  await analyse();
}

async function analyse(){
  if(!current)return;
  const id=current.id,q=params();
  $("viewer-badge").innerHTML='<span class="badge">SDK rechnet…</span>';
  $("measure-error").hidden=true;$("recalc").disabled=true;
  try{
    const a=await api(`/api/v1/thermal/images/${id}/analysis${q?"?"+q:""}`);
    if(!current||current.id!==id)return;
    analysis=a;renderMeta(a);
    if(a.measurement){
      const res=await api(`/api/v1/thermal/images/${id}/temperatures${q?"?"+q:""}`,true);
      const w=+res.headers.get("X-Thermal-Width"),h=+res.headers.get("X-Thermal-Height");
      const buf=await res.arrayBuffer();
      if(!(w>0&&h>0&&buf.byteLength===w*h*4))throw new Error("Unerwartetes Temperaturraster");
      if(!current||current.id!==id)return;
      grid=new Float32Array(buf);W=w;H=h;
      renderStats(a.measurement);showGrid();
      $("viewer-badge").innerHTML='<span class="badge good">Radiometrisch · DJI TSDK</span>';
    }else{
      grid=null;renderStats(null);showPreview(`/api/v1/studio/dji-media/${id}/file`);
      $("measure-error").textContent=a.measurement_error||"Keine Temperaturdaten";$("measure-error").hidden=false;
      $("viewer-badge").innerHTML='<span class="badge warn">Nur Vorschau</span>';
    }
  }catch(e){
    $("measure-error").textContent="Analyse fehlgeschlagen: "+e.message;$("measure-error").hidden=false;
    $("viewer-badge").innerHTML='<span class="badge bad">Fehler</span>';
  }finally{$("recalc").disabled=!current;exportState();}
}

function renderStats(m){
  for(const k of ["max","min","mean","p05","median","p95"])$("s-"+k).textContent=m?deg(m[k+"_c"]):"–";
  if(m&&$("iso-value").value==="")$("iso-value").value=(m.p95_c).toFixed(1);
}

function renderMeta(a){
  const rows=[["Modell",a.model],["Kamera",a.image_source],["Aufnahme",a.captured_at],["Auflösung",a.width&&`${a.width}×${a.height}${a.raw_width&&a.raw_width!==a.width?` (Raster ${a.raw_width}×${a.raw_height})`:""}`],
    ["Radiometrisch",a.radiometric?"ja":"nein"],["Dateigröße",bytes(a.size_bytes)]];
  const p=a.position;
  if(p){rows.push(["Position",`${fmt(p.latitude,6)}, ${fmt(p.longitude,6)}`],["Höhe rel./abs.",`${fmt(p.relative_altitude_m)} m / ${fmt(p.absolute_altitude_m)} m`],["GNSS",p.gps_status]);}
  else rows.push(["Position","kein GNSS-Fix"]);
  const g=a.gimbal||{};rows.push(["Gimbal Pitch/Yaw",`${fmt(g.pitch_deg)}° / ${fmt(g.yaw_deg)}°`]);
  if(a.laser_range)rows.push(["Laser-Distanz",fmt(a.laser_range.distance_m,2)+" m"]);
  const m=a.measurement;
  if(m){const o=Object.entries(m.parameter_overrides||{});rows.push(["Parameter",o.length?o.map(([k,v])=>k+"="+v).join(", "):"aus Bild"]);}
  if(a.sdk&&a.sdk.available)rows.push(["SDK",`dji_irp ${a.sdk.tool||""} (${a.sdk.runner})`]);
  const el=$("meta");el.replaceChildren();
  for(const [k,v] of rows){const s=document.createElement("span");s.textContent=k;const b=document.createElement("b");b.textContent=v==null||v===""?"–":String(v);el.append(s,b);}
  if(p){const s=document.createElement("span");s.textContent="Karte";const b=document.createElement("b");const l=document.createElement("a");
    l.href=`https://www.openstreetmap.org/?mlat=${p.latitude}&mlon=${p.longitude}#map=18/${p.latitude}/${p.longitude}`;l.target="_blank";l.rel="noopener noreferrer";l.textContent="OpenStreetMap ↗";b.append(l);el.append(s,b);}
}

function range(){
  const m=analysis&&analysis.measurement;if(!m)return [0,1];
  const mode=$("range-mode").value;
  if(mode==="p")return [m.p05_c,m.p95_c];
  if(mode==="manual"){const lo=parseFloat($("range-low").value),hi=parseFloat($("range-high").value);
    if(Number.isFinite(lo)&&Number.isFinite(hi)&&hi>lo)return [lo,hi];}
  return [m.min_c,m.max_c];
}

function showPreview(url){
  $("stack").hidden=true;$("empty").hidden=true;$("readout").hidden=true;
  const img=$("preview");img.src=url;img.style.display="block";
}

function showGrid(){
  $("preview").style.display="none";$("preview").removeAttribute("src");$("empty").hidden=true;
  const c=$("thermal"),o=$("overlay");c.width=o.width=W;c.height=H;
  $("stack").style.aspectRatio=`${W}/${H}`;$("stack").hidden=false;fitStack();draw();
}
function fitStack(){
  const v=$("viewer"),s=$("stack");if(!W)return;
  const scale=Math.min(v.clientWidth/W,v.clientHeight/H);
  s.style.width=Math.floor(W*scale)+"px";s.style.height=Math.floor(H*scale)+"px";
}

function draw(){
  if(!grid)return;
  const ctx=$("thermal").getContext("2d"),img=ctx.createImageData(W,H),px=img.data;
  const pal=lut($("palette").value),[lo,hi]=range(),span=(hi-lo)||1;
  const iso=$("iso-on").checked?parseFloat($("iso-value").value):NaN;
  for(let i=0;i<grid.length;i++){
    const t=grid[i],j=i*4;
    if(t>=iso){px[j]=40;px[j+1]=255;px[j+2]=120;px[j+3]=255;continue;}
    let k=Math.round((t-lo)/span*255);k=k<0?0:k>255?255:k;
    px[j]=pal[k*3];px[j+1]=pal[k*3+1];px[j+2]=pal[k*3+2];px[j+3]=255;
  }
  ctx.putImageData(img,0,0);
  const cb=$("colorbar").getContext("2d"),bar=cb.createImageData(256,1);
  for(let k=0;k<256;k++){bar.data[k*4]=pal[k*3];bar.data[k*4+1]=pal[k*3+1];bar.data[k*4+2]=pal[k*3+2];bar.data[k*4+3]=255;}
  cb.putImageData(bar,0,0);$("cb-low").textContent=deg(lo);$("cb-high").textContent=deg(hi);
  drawOverlay();
}

function marker(ctx,x,y,color,label){
  const r=Math.max(4,W/90);
  ctx.strokeStyle="#000";ctx.lineWidth=Math.max(2,W/320)+2;ctx.beginPath();ctx.moveTo(x-r,y);ctx.lineTo(x+r,y);ctx.moveTo(x,y-r);ctx.lineTo(x,y+r);ctx.stroke();
  ctx.strokeStyle=color;ctx.lineWidth=Math.max(1.5,W/320);ctx.beginPath();ctx.moveTo(x-r,y);ctx.lineTo(x+r,y);ctx.moveTo(x,y-r);ctx.lineTo(x,y+r);ctx.stroke();
  if(label){ctx.font=`bold ${Math.max(11,W/45)}px system-ui`;ctx.lineWidth=3;ctx.strokeStyle="#000";ctx.strokeText(label,x+r+2,y-r);ctx.fillStyle=color;ctx.fillText(label,x+r+2,y-r);}
}
function drawOverlay(){
  const ctx=$("overlay").getContext("2d");ctx.clearRect(0,0,W,H);
  const m=analysis&&analysis.measurement;
  if(m&&$("extremes").checked){
    marker(ctx,m.hotspot.x+.5,m.hotspot.y+.5,"#ff5a4f","▲ "+fmt(m.max_c));
    marker(ctx,m.coldspot.x+.5,m.coldspot.y+.5,"#5ab8ff","▼ "+fmt(m.min_c));
  }
  spots.forEach((s,i)=>{
    if(s.kind==="point")marker(ctx,s.x+.5,s.y+.5,"#ffffff",`${i+1}`);
    else{ctx.lineWidth=Math.max(1.5,W/320);ctx.strokeStyle="#000";ctx.strokeRect(s.x,s.y,s.w,s.h);ctx.setLineDash([6,4]);ctx.strokeStyle="#fff";ctx.strokeRect(s.x,s.y,s.w,s.h);ctx.setLineDash([]);
      ctx.font=`bold ${Math.max(11,W/45)}px system-ui`;ctx.fillStyle="#fff";ctx.fillText(`${i+1}`,s.x+3,s.y+Math.max(12,W/40));}
  });
  if(drag&&drag.w!==undefined){ctx.strokeStyle="#75e3bd";ctx.lineWidth=Math.max(1.5,W/320);ctx.strokeRect(drag.x,drag.y,drag.w,drag.h);}
}

function cell(e){
  const r=$("overlay").getBoundingClientRect();
  const x=Math.floor((e.clientX-r.left)/r.width*W),y=Math.floor((e.clientY-r.top)/r.height*H);
  return [Math.min(W-1,Math.max(0,x)),Math.min(H-1,Math.max(0,y))];
}
function area(x,y,w,h){
  let mn=Infinity,mx=-Infinity,sum=0,n=0,hx=x,hy=y;
  for(let j=y;j<y+h;j++)for(let i=x;i<x+w;i++){const t=grid[j*W+i];sum+=t;n++;if(t<mn)mn=t;if(t>mx){mx=t;hx=i;hy=j;}}
  return {min:mn,max:mx,mean:sum/n,hot_x:hx,hot_y:hy};
}
function renderSpots(){
  const body=$("spots");body.replaceChildren();
  spots.forEach((s,i)=>{
    const tr=document.createElement("tr");
    const val=s.kind==="point"?deg(s.t):`max ${deg(s.max)} · min ${deg(s.min)} · Ø ${deg(s.mean)}`;
    for(const v of [String(i+1),s.kind==="point"?`Punkt (${s.x}, ${s.y})`:`Bereich ${s.w}×${s.h}`,val]){const td=document.createElement("td");td.textContent=v;tr.append(td);}
    const td=document.createElement("td"),b=document.createElement("button");b.type="button";b.textContent="✕";b.title="Messung entfernen";b.style.padding="2px 7px";
    b.addEventListener("click",()=>{spots.splice(i,1);renderSpots();drawOverlay();});td.append(b);tr.append(td);body.append(tr);
  });
  exportState();
}
const ov=$("overlay");
ov.addEventListener("pointerdown",e=>{if(!grid)return;const [x,y]=cell(e);ov.setPointerCapture(e.pointerId);drag={x0:x,y0:y,x,y};});
ov.addEventListener("pointermove",e=>{
  if(!grid)return;const [x,y]=cell(e);
  const ro=$("readout");ro.hidden=false;ro.textContent=`x ${x} · y ${y} · ${deg(grid[y*W+x])}`;
  if(drag&&tool==="box"){drag.x=Math.min(drag.x0,x);drag.y=Math.min(drag.y0,y);drag.w=Math.abs(x-drag.x0)+1;drag.h=Math.abs(y-drag.y0)+1;drawOverlay();}
});
ov.addEventListener("pointerleave",()=>{$("readout").hidden=true;});
ov.addEventListener("pointerup",e=>{
  if(!grid||!drag)return;const [x,y]=cell(e);
  if(tool==="box"&&drag.w>1&&drag.h>1)spots.push({kind:"box",x:drag.x,y:drag.y,w:drag.w,h:drag.h,...area(drag.x,drag.y,drag.w,drag.h)});
  else if(tool==="point")spots.push({kind:"point",x,y,t:grid[y*W+x]});
  drag=null;if(spots.length>50)spots.shift();renderSpots();drawOverlay();
});
function setTool(t){tool=t;for(const [id,v] of [["tool-point","point"],["tool-box","box"]]){$(id).classList.toggle("active",t===v);$(id).setAttribute("aria-pressed",String(t===v));}}
$("tool-point").addEventListener("click",()=>setTool("point"));
$("tool-box").addEventListener("click",()=>setTool("box"));

function save(blob,name){const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),2000);}
function base(){return (current&&current.name||"thermal").replace(/\.[^.]+$/,"");}
function exportState(){const ok=!!grid;$("export-png").disabled=!ok;$("export-grid").disabled=!ok;$("export-csv").disabled=!ok||!spots.length;$("export-json").disabled=!analysis;}
function csvNum(v){return typeof v==="number"?v.toFixed(2):"";}
$("export-png").addEventListener("click",()=>{
  const c=document.createElement("canvas");c.width=W;c.height=H;const ctx=c.getContext("2d");
  ctx.drawImage($("thermal"),0,0);ctx.drawImage($("overlay"),0,0);c.toBlob(b=>b&&save(b,base()+"_analyse.png"),"image/png");
});
$("export-csv").addEventListener("click",()=>{
  const lines=["nr;art;x;y;breite;hoehe;temp_c;min_c;max_c;mittel_c"];
  spots.forEach((s,i)=>lines.push([i+1,s.kind==="point"?"punkt":"bereich",s.x,s.y,s.w||1,s.h||1,csvNum(s.t),csvNum(s.min),csvNum(s.max),csvNum(s.mean)].join(";")));
  save(new Blob([lines.join("\n")+"\n"],{type:"text/csv"}),base()+"_messungen.csv");
});
$("export-grid").addEventListener("click",()=>{
  const rows=[];for(let y=0;y<H;y++){const r=new Array(W);for(let x=0;x<W;x++)r[x]=grid[y*W+x].toFixed(2);rows.push(r.join(";"));}
  save(new Blob([rows.join("\n")+"\n"],{type:"text/csv"}),base()+"_temperaturen.csv");
});
$("export-json").addEventListener("click",()=>{
  const report={generated_at:new Date().toISOString(),image:analysis,measurements:spots};
  save(new Blob([JSON.stringify(report,null,2)],{type:"application/json"}),base()+"_bericht.json");
});

$("material").addEventListener("change",()=>{$("p-emissivity").value=$("material").value;});
$("recalc").addEventListener("click",()=>{spots=[];renderSpots();analyse();});
$("reset-params").addEventListener("click",()=>{for(const k of ["emissivity","distance","humidity","reflection","ambient"])$("p-"+k).value="";$("material").value="";if(current){spots=[];renderSpots();analyse();}});
for(const id of ["palette","range-low","range-high","iso-on","iso-value"])$(id).addEventListener("input",draw);
$("extremes").addEventListener("change",drawOverlay);
$("range-mode").addEventListener("change",()=>{
  const manual=$("range-mode").value==="manual";$("manual-range").hidden=!manual;
  if(manual&&analysis&&analysis.measurement&&$("range-low").value===""){$("range-low").value=analysis.measurement.min_c.toFixed(1);$("range-high").value=analysis.measurement.max_c.toFixed(1);}
  draw();
});
$("search-go").addEventListener("click",()=>{offset=0;loadList();});
$("search").addEventListener("keydown",e=>{if(e.key==="Enter"){offset=0;loadList();}});
$("prev").addEventListener("click",()=>{offset=Math.max(0,offset-PAGE);loadList();});
$("next").addEventListener("click",()=>{offset+=PAGE;loadList();});
window.addEventListener("resize",fitStack);
loadStatus();loadList();
</script>
</body>
</html>
"""


def render_thermal_page() -> str:
    return HTML
