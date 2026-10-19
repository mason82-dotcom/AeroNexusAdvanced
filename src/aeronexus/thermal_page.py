"""Thermal workspace (own web UI tab ``/thermal``).

Static HTML/JS without credentials. Temperatures are fetched as a float32
grid from the local API, which obtains them from the DJI Thermal SDK; the
browser never contacts MinIO or DJI and never sees object keys. Views:
thermal image, thermal/visual overlay, map of image positions and
footprints; PV inspection panel (IEC TS 62446-3 orientation).
"""

from .ui_navigation import with_navigation


HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="dark">
<title>AeroNexusAdvanced · Thermal</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<style>
:root{font:14px/1.45 system-ui,"Segoe UI",sans-serif;color-scheme:dark;--bg:#0b1323;--pane:#122139;--card:#152b47;--line:#334e69;--ink:#eaf4ff;--sub:#a9bfd8;--mint:#75e3bd;--amber:#e4bd78;--red:#ff9ba8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink)}
a{color:#9dd5ff}
button,select,input{font:inherit;color:#eef7ff;background:#213d5e;border:1px solid #426487;border-radius:8px;padding:7px 10px}
button{cursor:pointer}button:hover{background:#2a517a}button:disabled{opacity:.5;cursor:not-allowed}
button.active{border-color:var(--mint);background:#245a55}
input{min-width:0}input[type=range]{padding:0;accent-color:var(--mint)}
:focus-visible{outline:2px solid var(--mint);outline-offset:2px}
header{display:flex;align-items:center;gap:15px;flex-wrap:wrap;padding:12px 20px;background:#142440;border-bottom:1px solid var(--line)}
.logo{font-weight:800;font-size:18px;white-space:nowrap}.logo small{display:block;font-size:10px;letter-spacing:.18em;color:#7abef0}
.tabs{display:flex;align-items:center;flex-wrap:wrap;gap:13px}
.tabs a{font-size:13px;text-decoration:none}.tabs .active{font-weight:700;color:var(--mint)}
.header-state{margin-left:auto;font-size:12px}
.layout{display:grid;grid-template-columns:minmax(250px,300px) minmax(320px,1fr) minmax(300px,370px);gap:12px;padding:12px;height:calc(100vh - 66px);min-height:680px}
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
.views{display:flex;gap:6px;margin:0 0 9px}
.toolbar{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin-bottom:9px}
.toolbar label{font-size:12px;color:var(--sub);display:flex;gap:5px;align-items:center}
.toolbar input[type=number]{width:78px}
.viewer{position:relative;flex:1;min-height:260px;display:flex;align-items:center;justify-content:center;background:#08101c;border-radius:9px;overflow:hidden}
.stack{position:relative;max-width:100%;max-height:100%}
.stack canvas{position:absolute;inset:0;width:100%;height:100%;image-rendering:pixelated}
#visual{image-rendering:auto}
#overlay{cursor:crosshair;touch-action:none}
#preview{max-width:100%;max-height:100%;display:none}
#thermal-map{position:absolute;inset:0;display:none;background:#23374f}
.empty{color:var(--sub);text-align:center;padding:30px}
.readout{position:absolute;left:10px;bottom:10px;background:#0f1d31e6;border:1px solid #35536f;border-radius:8px;padding:5px 9px;font:12px ui-monospace,Consolas,monospace;pointer-events:none;z-index:2}
.side-tabs{display:flex;gap:6px;margin:4px 0 8px}
.flight{border:1px solid #33506d;border-radius:9px;padding:9px;margin:6px 0;background:#142842}
.flight.active{border-color:#76bfff;background:#1b3a59}
.flight b{display:block;font-size:13px}.flight small{display:block;color:#b5cae1;font-size:11px;margin-top:2px}
.flight progress{width:100%;height:9px;accent-color:#ff8a5c;margin-top:6px}
.rank td:first-child{color:var(--sub)}
.map-tools{position:absolute;z-index:500;top:10px;right:52px;display:flex;gap:6px;flex-wrap:wrap;background:#112137e8;border-radius:8px;padding:6px 8px;font-size:12px;color:#c8dbed;align-items:center}
.map-tools select{padding:4px 6px;font-size:12px}
.map-legend{position:absolute;z-index:500;right:10px;bottom:22px;background:#112137e8;border-radius:8px;padding:6px 9px;font-size:11px;color:#c8dbed}
.map-legend canvas{display:block;width:150px;height:10px;margin:4px 0;border-radius:3px}
.map-state{position:absolute;z-index:500;left:10px;bottom:10px;max-width:min(520px,85%);background:#112137e8;border-radius:8px;padding:7px 9px;font-size:11px;color:#c8dbed}
.colorbar{display:flex;align-items:center;gap:8px;margin-top:9px;font-size:12px}
.colorbar canvas{flex:1;min-width:0;width:0;height:14px;border-radius:4px;border:1px solid #3a5876}
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
td,th{padding:5px 4px;border-bottom:1px solid #2f4a64;text-align:left;vertical-align:top}
th{color:var(--sub);font-weight:600}
tr.pick{cursor:pointer}tr.pick:hover{background:#1b3553}
.c1{color:#f3dc6b}.c2{color:#ffab5c}.c3{color:#ff6b6b;font-weight:700}
.st-ok{color:var(--mint)}.st-warn{color:var(--amber)}.st-fail{color:var(--red)}.st-unknown{color:var(--sub)}
.note{font-size:11px;color:var(--sub);line-height:1.5;margin:8px 0}
.warnbox{font-size:12px;color:#ffd0a4;border-left:3px solid #d6a862;background:#2a2a2a55;padding:6px 8px;margin:6px 0}
.error{color:var(--red)}
details.section{border-top:1px solid #2f4a64;margin-top:12px;padding-top:6px}
details.section summary{cursor:pointer;font-weight:700;font-size:13px;padding:4px 0}
@media(max-width:1200px){.layout{grid-template-columns:270px minmax(0,1fr)}.side-right{grid-column:1/-1}}
@media(max-width:760px){.layout{display:flex;flex-direction:column;height:auto}.panel{overflow:visible}.scroll{max-height:340px}.viewer{min-height:340px}.header-state{margin-left:0}}
</style>
</head>
<body>
<header>
<div class="logo"><small>AERONEXUS ADVANCED</small>Thermal</div>
__APP_NAVIGATION__
<span class="header-state" id="sdk-state" role="status" aria-live="polite">Prüfe DJI Thermal SDK…</span>
</header>
<div class="layout">
<section class="panel" aria-labelledby="list-title">
<div class="eyebrow">MinIO · nur lesen</div>
<h2 id="list-title">Wärmebilder (R-JPEG)</h2>
<div class="side-tabs" role="tablist" aria-label="Liste">
<button type="button" role="tab" id="tab-images" class="active" aria-selected="true">Bilder</button>
<button type="button" role="tab" id="tab-flights" aria-selected="false">Flüge</button>
</div>
<div id="pane-flights" hidden style="display:none;flex-direction:column;min-height:0;flex:1">
<div class="sub" id="flight-state" role="status" aria-live="polite">Lade Flüge…</div>
<div class="scroll" id="flights"></div>
</div>
<div id="pane-images" style="display:flex;flex-direction:column;min-height:0;flex:1">
<div class="row"><input id="search" class="grow" type="search" maxlength="120" placeholder="Dateiname / Datum (z. B. 20261002)" aria-label="Wärmebilder suchen">
<button id="search-go" type="button">Suchen</button></div>
<div class="sub" id="list-state" role="status" aria-live="polite" style="margin:7px 0">Lade…</div>
<div class="scroll" id="list"></div>
<div class="row" style="justify-content:space-between;margin-top:8px">
<button id="prev" type="button">Zurück</button><span class="sub" id="page">–</span><button id="next" type="button">Weiter</button></div>
</div>
</section>

<section class="panel" aria-labelledby="viewer-title">
<div class="row" style="justify-content:space-between"><h2 id="viewer-title" style="overflow-wrap:anywhere">Kein Bild gewählt</h2><span id="viewer-badge"></span></div>
<div class="views" role="tablist" aria-label="Ansicht">
<button type="button" role="tab" id="view-image" class="active" aria-selected="true">Wärmebild</button>
<button type="button" role="tab" id="view-overlay" aria-selected="false">Overlay mit Sichtbild</button>
<button type="button" role="tab" id="view-map" aria-selected="false">Karte</button>
</div>
<div class="toolbar" role="toolbar" aria-label="Darstellung und Messwerkzeuge" id="image-tools">
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
<button id="tool-pv" type="button" aria-pressed="false" title="Rechteck um die PV-Module ziehen">PV-Bereich</button>
</div>
<div class="toolbar" id="overlay-tools" hidden>
<label>Deckkraft Wärmebild <input id="ov-alpha" type="range" min="0" max="100" value="55"></label>
<label>Skalierung <input id="ov-scale" type="range" min="70" max="130" value="100"> <span id="ov-scale-v">100 %</span></label>
<label>Versatz X <input id="ov-dx" type="range" min="-150" max="150" value="0"></label>
<label>Versatz Y <input id="ov-dy" type="range" min="-150" max="150" value="0"></label>
<button id="ov-reset" type="button">Zurücksetzen</button>
</div>
<div class="viewer" id="viewer">
<div class="empty" id="empty">Wärmebild links oder auf der Karte auswählen.<br>Temperaturen berechnet das DJI Thermal SDK auf dem Server.</div>
<div class="stack" id="stack" hidden><canvas id="visual"></canvas><canvas id="thermal"></canvas><canvas id="overlay" aria-label="Wärmebild, klicken zum Messen"></canvas></div>
<img id="preview" alt="Wärmebild-Vorschau (ohne Temperaturdaten)">
<div id="thermal-map" aria-label="Karte der Wärmebilder"></div>
<div class="map-state" id="map-state" hidden>Lade Geo-Index…</div>
<div class="map-tools" id="map-tools" hidden>
<label>Flug <select id="map-flight"><option value="">alle</option></select></label>
<label>Färbung <select id="map-color"><option value="max">Max-Temperatur</option><option value="delta">ΔT (Max − Median)</option><option value="none">einheitlich</option></select></label>
<label><input type="checkbox" id="map-thermal" checked> Wärmebild auf Karte</label>
</div>
<div class="map-legend" id="map-legend" hidden><span id="legend-title">Max-Temperatur</span><canvas id="legend-bar" width="150" height="1"></canvas><span id="legend-low">–</span><span id="legend-high" style="float:right">–</span></div>
<div class="readout" id="readout" hidden></div>
</div>
<div class="colorbar" id="colorbar-row"><span id="cb-low">–</span><canvas id="colorbar" width="256" height="1"></canvas><span id="cb-high">–</span></div>
<div class="note" id="overlay-note" hidden></div>
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

<aside class="panel side-right scroll" aria-label="Messwerte, PV-Inspektion und Metadaten">
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

<details class="section" id="pv-section" open>
<summary>PV-Inspektion (IEC TS 62446-3)</summary>
<div class="note">Mit „PV-Bereich“ ein Rechteck um die Module ziehen. Referenz ist der Median des Bereichs, Anomalien sind zusammenhängende Flächen oberhalb Referenz + Erkennungsschwelle. Klassen-Schwellen sind einstellbare Richtwerte; die verbindliche Einstufung trifft ein qualifizierter Thermograf.</div>
<div class="params">
<label>Einstrahlung W/m²<input id="pv-irradiance" type="number" min="0" max="1500" step="10" placeholder="Pflicht ≥ 600"></label>
<label>Wind km/h<input id="pv-wind" type="number" min="0" max="200" step="1" placeholder="≤ 28"></label>
<label>Bewölkung (Achtel)<input id="pv-cloud" type="number" min="0" max="8" step="1" placeholder="≤ 2"></label>
<label>Modulneigung °<input id="pv-tilt" type="number" min="0" max="90" step="1" placeholder="0 = horizontal"></label>
<label>Modulausrichtung °<input id="pv-azimuth" type="number" min="0" max="360" step="1" placeholder="180 = Süd"></label>
<label>Zellkante m<input id="pv-cell" type="number" min="0.05" max="0.5" step="0.001" value="0.166"></label>
<label>Erkennung ΔT K<input id="pv-detect" type="number" min="0.5" max="50" step="0.5" value="3"></label>
<label>Min. Pixel<input id="pv-minpx" type="number" min="1" max="10000" step="1" value="4"></label>
<label>Klasse 2 ab ΔT K<input id="pv-c2" type="number" min="1" max="100" step="0.5" value="10"></label>
<label>Klasse 3 ab ΔT K<input id="pv-c3" type="number" min="1" max="150" step="0.5" value="20"></label>
</div>
<div class="row" style="margin-top:8px"><button id="pv-run" type="button" disabled>PV-Analyse</button><button id="pv-clear" type="button">Bereich löschen</button><button id="pv-export" type="button" disabled>PV-Bericht</button><button id="pv-csv" type="button" disabled>Anomalien CSV</button></div>
<div class="sub" id="pv-region">Kein PV-Bereich gewählt (gesamtes Bild).</div>
<div id="pv-result"></div>
</details>

<details class="section" open>
<summary>Messparameter</summary>
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
<div class="note">Leere Felder verwenden die in der Aufnahme gespeicherten Parameter. Materialwerte sind grobe Richtwerte.</div>
</details>

<details class="section" open>
<summary>Aufnahme</summary>
<div class="kv" id="meta"><span>–</span><b>–</b></div>
<div class="note">Seriennummern, NTRIP-Zugangsdaten und unbekannte Herstellerfelder werden nicht angezeigt. Keine Schreibzugriffe auf MinIO oder DJI.</div>
</details>
</aside>
</div>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
"use strict";
const $=id=>document.getElementById(id);
const PAGE=40;
let offset=0,total=0,current=null,analysis=null,grid=null,W=0,H=0,spots=[],tool="point",drag=null;
let view="image",pvRegion=null,pvReport=null,pvFocus=-1,visualImg=null,visualFor=null;
let map=null,mapLoaded=false,markerLayer=null,footLayer=null,selectedFoot=null,mapItems=[],thermalOverlay=null;
let flightsData=null,openFlight=null,jobTimer=null,gridFor=null;

const PALETTES={
  iron:[[0,0,0,0],[.15,32,0,90],[.35,140,0,140],[.55,220,40,40],[.75,250,140,0],[.9,255,220,40],[1,255,255,240]],
  rainbow:[[0,20,0,120],[.2,0,60,255],[.4,0,200,220],[.6,40,220,40],[.8,255,220,0],[1,230,0,0]],
  whitehot:[[0,0,0,0],[1,255,255,255]],
  blackhot:[[0,255,255,255],[1,0,0,0]],
  arctic:[[0,10,10,60],[.35,20,80,200],[.65,80,200,240],[.85,230,240,255],[1,255,190,60]],
  lava:[[0,20,10,40],[.3,90,20,90],[.6,200,40,40],[.85,255,150,30],[1,255,250,200]]
};
const CLASS_COLORS={1:"#f3dc6b",2:"#ffab5c",3:"#ff4d4d"};
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
function el(tag,text,cls){const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;}

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
      const b=el("button",null,"item"+(current&&current.id===item.id?" active":""));b.type="button";b.dataset.id=item.id;
      b.append(el("b",item.name),el("small",[when(item.name),bytes(item.size_bytes),item.visual_id?"mit Sichtbild":""].filter(Boolean).join(" · ")));
      b.addEventListener("click",()=>select(item));list.append(b);
    }
    setState($("list-state"),total?`${total.toLocaleString("de-DE")} Wärmebilder${r.last_scanned_at?" · Index "+new Date(r.last_scanned_at).toLocaleString("de-DE"):""}`:"Keine Wärmebilder im Index (MinIO-Scan ausführen).");
    $("page").textContent=total?`${offset+1}–${Math.min(offset+PAGE,total)} / ${total}`:"–";
    $("prev").disabled=offset===0;$("next").disabled=offset+PAGE>=total;
  }catch(e){setState($("list-state"),"Liste nicht verfügbar: "+e.message,"error");}
}

function measureQuery(){
  const out=new URLSearchParams();
  for(const k of ["emissivity","distance","humidity","reflection","ambient"]){
    const v=$("p-"+k).value.trim();if(v!=="")out.set(k,v);
  }
  return out;
}

async function select(item){
  current=item;
  document.querySelectorAll(".item.active").forEach(e=>e.classList.remove("active"));
  const btn=document.querySelector(`.item[data-id="${item.id}"]`);if(btn)btn.classList.add("active");
  $("viewer-title").textContent=item.name;
  $("open-thermal").href=`/api/v1/studio/dji-media/${item.id}/file`;$("open-thermal").hidden=false;
  spots=[];pvRegion=null;pvReport=null;pvFocus=-1;renderSpots();renderPv();
  // Stay on the map: the measured image is drawn into its footprint there.
  await analyse();
}

async function analyse(){
  if(!current)return;
  const id=current.id,q=measureQuery().toString();
  $("viewer-badge").innerHTML='<span class="badge">SDK rechnet…</span>';
  $("measure-error").hidden=true;$("recalc").disabled=true;
  try{
    const a=await api(`/api/v1/thermal/images/${id}/analysis${q?"?"+q:""}`);
    if(!current||current.id!==id)return;
    analysis=a;current.visual_id=a.visual_id;renderMeta(a);
    $("open-visual").hidden=!a.visual_id;if(a.visual_id)$("open-visual").href=`/api/v1/studio/dji-media/${a.visual_id}/file`;
    if(map)highlightFootprint(a);
    if(a.measurement){
      const res=await api(`/api/v1/thermal/images/${id}/temperatures${q?"?"+q:""}`,true);
      const w=+res.headers.get("X-Thermal-Width"),h=+res.headers.get("X-Thermal-Height");
      const buf=await res.arrayBuffer();
      if(!(w>0&&h>0&&buf.byteLength===w*h*4))throw new Error("Unerwartetes Temperaturraster");
      if(!current||current.id!==id)return;
      grid=new Float32Array(buf);W=w;H=h;gridFor=id;
      renderStats(a.measurement);
      if(view!=="map")showGrid();
      else{for(const c of [$("thermal"),$("overlay"),$("visual")]){c.width=W;c.height=H;}draw();}  // map overlay source
      $("viewer-badge").innerHTML='<span class="badge good">Radiometrisch · DJI TSDK</span>';
    }else{
      grid=null;gridFor=null;renderStats(null);if(view!=="map")showPreview(`/api/v1/studio/dji-media/${id}/file`);
      $("measure-error").textContent=a.measurement_error||"Keine Temperaturdaten";$("measure-error").hidden=false;
      $("viewer-badge").innerHTML='<span class="badge warn">Nur Vorschau</span>';
    }
  }catch(e){
    $("measure-error").textContent="Analyse fehlgeschlagen: "+e.message;$("measure-error").hidden=false;
    $("viewer-badge").innerHTML='<span class="badge bad">Fehler</span>';
  }finally{$("recalc").disabled=!current;$("pv-run").disabled=!grid;exportState();}
}

function renderStats(m){
  for(const k of ["max","min","mean","p05","median","p95"])$("s-"+k).textContent=m?deg(m[k+"_c"]):"–";
  if(m&&$("iso-value").value==="")$("iso-value").value=(m.p95_c).toFixed(1);
}

function renderMeta(a){
  const geo=a.geometry||{};
  const rows=[["Modell",a.model],["Kamera",a.image_source],["Aufnahme",a.captured_at],["Auflösung",a.width&&`${a.width}×${a.height}${a.raw_width&&a.raw_width!==a.width?` (Raster ${a.raw_width}×${a.raw_height})`:""}`],
    ["Radiometrisch",a.radiometric?"ja":"nein"],["Dateigröße",bytes(a.size_bytes)]];
  const p=a.position;
  if(p){rows.push(["Position",`${fmt(p.latitude,6)}, ${fmt(p.longitude,6)}`],["Höhe rel./abs.",`${fmt(p.relative_altitude_m)} m / ${fmt(p.absolute_altitude_m)} m`],["GNSS",p.gps_status]);}
  else rows.push(["Position","kein GNSS-Fix"]);
  const g=a.gimbal||{};rows.push(["Gimbal Pitch/Yaw",`${fmt(g.pitch_deg)}° / ${fmt(g.yaw_deg)}°`]);
  if(geo.ground_sample_cm)rows.push(["Bodenauflösung",`${fmt(geo.ground_sample_cm,1)} cm/px (Schätzung)`]);
  if(geo.thermal_hfov_deg)rows.push(["Sichtfeld IR",`${fmt(geo.thermal_hfov_deg)}° × ${fmt(geo.thermal_vfov_deg)}°`]);
  if(a.laser_range)rows.push(["Laser-Distanz",fmt(a.laser_range.distance_m,2)+" m"]);
  const m=a.measurement;
  if(m){const o=Object.entries(m.parameter_overrides||{});rows.push(["Parameter",o.length?o.map(([k,v])=>k+"="+v).join(", "):"aus Bild"]);}
  if(a.sdk&&a.sdk.available)rows.push(["SDK",`dji_irp ${a.sdk.tool||""} (${a.sdk.runner})`]);
  const box=$("meta");box.replaceChildren();
  for(const [k,v] of rows)box.append(el("span",k),el("b",v==null||v===""?"–":String(v)));
}

/* ---------------------------------------------------------------- views --- */
function setView(v){
  view=v;
  for(const [id,name] of [["view-image","image"],["view-overlay","overlay"],["view-map","map"]]){
    $(id).classList.toggle("active",v===name);$(id).setAttribute("aria-selected",String(v===name));
  }
  $("image-tools").hidden=v==="map";$("overlay-tools").hidden=v!=="overlay";$("colorbar-row").hidden=v==="map";
  $("thermal-map").style.display=v==="map"?"block":"none";$("map-state").hidden=v!=="map";
  $("map-tools").hidden=v!=="map";$("map-legend").hidden=v!=="map"||$("map-color").value==="none";
  $("overlay-note").hidden=v!=="overlay";
  if(v==="map"){
    $("stack").hidden=true;$("preview").style.display="none";$("empty").hidden=true;$("readout").hidden=true;
    initMap();return;
  }
  if(grid)showGrid();else if(current)showPreview(`/api/v1/studio/dji-media/${current.id}/file`);else{$("empty").hidden=false;}
}

function showPreview(url){
  if(view==="map")return;
  $("stack").hidden=true;$("empty").hidden=true;$("readout").hidden=true;
  const img=$("preview");img.src=url;img.style.display="block";
}

function showGrid(){
  $("preview").style.display="none";$("preview").removeAttribute("src");$("empty").hidden=true;
  for(const c of [$("thermal"),$("overlay"),$("visual")]){c.width=W;c.height=H;}
  $("stack").hidden=false;fitStack();draw();
  if(view==="overlay")drawVisual();else{$("visual").getContext("2d").clearRect(0,0,W,H);$("thermal").style.opacity=1;}
}
function fitStack(){
  const v=$("viewer"),s=$("stack");if(!W)return;
  const scale=Math.min(v.clientWidth/W,v.clientHeight/H);
  s.style.width=Math.floor(W*scale)+"px";s.style.height=Math.floor(H*scale)+"px";
  if(map&&view==="map")map.invalidateSize();
}

function range(){
  const m=analysis&&analysis.measurement;if(!m)return [0,1];
  const mode=$("range-mode").value;
  if(mode==="p")return [m.p05_c,m.p95_c];
  if(mode==="manual"){const lo=parseFloat($("range-low").value),hi=parseFloat($("range-high").value);
    if(Number.isFinite(lo)&&Number.isFinite(hi)&&hi>lo)return [lo,hi];}
  return [m.min_c,m.max_c];
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
  if(view==="map")updateMapThermal();
}

/* -------------------------------------------------------------- overlay --- */
function fovPair(dfov,w,h){const t=Math.tan(dfov*Math.PI/360)/Math.hypot(w,h);return [Math.atan(t*w)*2,Math.atan(t*h)*2];}
async function drawVisual(){
  const note=$("overlay-note");
  $("thermal").style.opacity=$("ov-alpha").value/100;
  if(!analysis||!analysis.visual_id){note.textContent="Zu diesem Wärmebild ist kein Sichtbild im Index.";$("thermal").style.opacity=1;return;}
  const vid=analysis.visual_id;
  if(visualFor!==vid){
    note.textContent="Lade Sichtbild (Originaldatei, mehrere MB)…";
    const img=new Image();img.decoding="async";
    img.src=`/api/v1/studio/dji-media/${vid}/file`;
    try{await img.decode();}catch(e){note.textContent="Sichtbild konnte nicht geladen werden.";return;}
    if(!analysis||analysis.visual_id!==vid||view!=="overlay")return;
    visualImg=img;visualFor=vid;
  }
  const optics=analysis.geometry&&analysis.geometry.optics,vw=visualImg.naturalWidth,vh=visualImg.naturalHeight;
  let rw=1,rh=1;
  if(optics){
    const [tH,tV]=fovPair(optics.thermal_dfov_deg,W,H),[vH,vV]=fovPair(optics.visual_dfov_deg,vw,vh);
    rw=Math.tan(tH/2)/Math.tan(vH/2);rh=Math.tan(tV/2)/Math.tan(vV/2);
  }
  const scale=$("ov-scale").value/100;$("ov-scale-v").textContent=$("ov-scale").value+" %";
  const sw=vw*rw/scale,sh=vh*rh/scale;
  const sx=(vw-sw)/2+(+$("ov-dx").value)/1000*vw,sy=(vh-sh)/2+(+$("ov-dy").value)/1000*vh;
  const ctx=$("visual").getContext("2d");ctx.clearRect(0,0,W,H);ctx.drawImage(visualImg,sx,sy,sw,sh,0,0,W,H);
  note.textContent=optics?`Ausschnitt aus Sichtfeld-Verhältnis ${optics.camera} (IR ${optics.thermal_dfov_deg}° / Weitwinkel ${optics.visual_dfov_deg}° diagonal). Parallaxe zwischen den Kameras mit Versatz ausgleichen.`:"Keine Optikdaten für dieses Modell – Skalierung und Versatz manuell anpassen.";
}

/* ------------------------------------------------------------ overlay draw --- */
function marker(ctx,x,y,color,label){
  const r=Math.max(4,W/90);
  ctx.strokeStyle="#000";ctx.lineWidth=Math.max(2,W/320)+2;ctx.beginPath();ctx.moveTo(x-r,y);ctx.lineTo(x+r,y);ctx.moveTo(x,y-r);ctx.lineTo(x,y+r);ctx.stroke();
  ctx.strokeStyle=color;ctx.lineWidth=Math.max(1.5,W/320);ctx.beginPath();ctx.moveTo(x-r,y);ctx.lineTo(x+r,y);ctx.moveTo(x,y-r);ctx.lineTo(x,y+r);ctx.stroke();
  if(label){ctx.font=`bold ${Math.max(11,W/45)}px system-ui`;ctx.lineWidth=3;ctx.strokeStyle="#000";ctx.strokeText(label,x+r+2,y-r);ctx.fillStyle=color;ctx.fillText(label,x+r+2,y-r);}
}
function box(ctx,b,color,dash,label){
  ctx.lineWidth=Math.max(1.5,W/320);ctx.strokeStyle="#000";ctx.setLineDash([]);ctx.strokeRect(b.x,b.y,b.w,b.h);
  ctx.setLineDash(dash||[]);ctx.strokeStyle=color;ctx.strokeRect(b.x,b.y,b.w,b.h);ctx.setLineDash([]);
  if(label){ctx.font=`bold ${Math.max(11,W/45)}px system-ui`;ctx.lineWidth=3;ctx.strokeStyle="#000";ctx.strokeText(label,b.x+3,b.y+Math.max(12,W/40));ctx.fillStyle=color;ctx.fillText(label,b.x+3,b.y+Math.max(12,W/40));}
}
function drawOverlay(){
  const ctx=$("overlay").getContext("2d");ctx.clearRect(0,0,W,H);
  const m=analysis&&analysis.measurement;
  if(m&&$("extremes").checked){
    marker(ctx,m.hotspot.x+.5,m.hotspot.y+.5,"#ff5a4f","▲ "+fmt(m.max_c));
    marker(ctx,m.coldspot.x+.5,m.coldspot.y+.5,"#5ab8ff","▼ "+fmt(m.min_c));
  }
  if(pvRegion)box(ctx,pvRegion,"#ffd84a",[10,5],"PV");
  if(pvReport)pvReport.anomalies.forEach((a,i)=>{
    const pad=i===pvFocus?3:1;
    box(ctx,{x:a.x-pad,y:a.y-pad,w:a.w+2*pad,h:a.h+2*pad},CLASS_COLORS[a.class],i===pvFocus?[]:[4,3],"A"+(i+1));
  });
  spots.forEach((s,i)=>{
    if(s.kind==="point")marker(ctx,s.x+.5,s.y+.5,"#ffffff",`${i+1}`);
    else box(ctx,s,"#ffffff",[6,4],`${i+1}`);
  });
  if(drag&&drag.w!==undefined){ctx.strokeStyle=tool==="pv"?"#ffd84a":"#75e3bd";ctx.lineWidth=Math.max(1.5,W/320);ctx.strokeRect(drag.x,drag.y,drag.w,drag.h);}
}

function cell(e){
  const r=$("overlay").getBoundingClientRect();
  const x=Math.floor((e.clientX-r.left)/r.width*W),y=Math.floor((e.clientY-r.top)/r.height*H);
  return [Math.min(W-1,Math.max(0,x)),Math.min(H-1,Math.max(0,y))];
}
function area(x,y,w,h){
  let mn=Infinity,mx=-Infinity,sum=0,n=0;
  for(let j=y;j<y+h;j++)for(let i=x;i<x+w;i++){const t=grid[j*W+i];sum+=t;n++;if(t<mn)mn=t;if(t>mx)mx=t;}
  return {min:mn,max:mx,mean:sum/n};
}
function renderSpots(){
  const body=$("spots");body.replaceChildren();
  spots.forEach((s,i)=>{
    const tr=el("tr");
    const val=s.kind==="point"?deg(s.t):`max ${deg(s.max)} · min ${deg(s.min)} · Ø ${deg(s.mean)}`;
    for(const v of [String(i+1),s.kind==="point"?`Punkt (${s.x}, ${s.y})`:`Bereich ${s.w}×${s.h}`,val])tr.append(el("td",v));
    const td=el("td"),b=el("button","✕");b.type="button";b.title="Messung entfernen";b.style.padding="2px 7px";
    b.addEventListener("click",()=>{spots.splice(i,1);renderSpots();drawOverlay();});td.append(b);tr.append(td);body.append(tr);
  });
  exportState();
}
const ov=$("overlay");
ov.addEventListener("pointerdown",e=>{if(!grid)return;const [x,y]=cell(e);ov.setPointerCapture(e.pointerId);drag={x0:x,y0:y,x,y};});
ov.addEventListener("pointermove",e=>{
  if(!grid)return;const [x,y]=cell(e);
  const ro=$("readout");ro.hidden=false;ro.textContent=`x ${x} · y ${y} · ${deg(grid[y*W+x])}`;
  if(drag&&tool!=="point"){drag.x=Math.min(drag.x0,x);drag.y=Math.min(drag.y0,y);drag.w=Math.abs(x-drag.x0)+1;drag.h=Math.abs(y-drag.y0)+1;drawOverlay();}
});
ov.addEventListener("pointerleave",()=>{$("readout").hidden=true;});
ov.addEventListener("pointerup",e=>{
  if(!grid||!drag)return;const [x,y]=cell(e);
  if(tool==="box"&&drag.w>1&&drag.h>1)spots.push({kind:"box",x:drag.x,y:drag.y,w:drag.w,h:drag.h,...area(drag.x,drag.y,drag.w,drag.h)});
  else if(tool==="pv"&&drag.w>2&&drag.h>2){pvRegion={x:drag.x,y:drag.y,w:drag.w,h:drag.h};pvReport=null;renderPv();}
  else if(tool==="point")spots.push({kind:"point",x,y,t:grid[y*W+x]});
  drag=null;if(spots.length>50)spots.shift();renderSpots();drawOverlay();
});
function setTool(t){tool=t;for(const [id,v] of [["tool-point","point"],["tool-box","box"],["tool-pv","pv"]]){$(id).classList.toggle("active",t===v);$(id).setAttribute("aria-pressed",String(t===v));}}
$("tool-point").addEventListener("click",()=>setTool("point"));
$("tool-box").addEventListener("click",()=>setTool("box"));
$("tool-pv").addEventListener("click",()=>setTool("pv"));

/* ------------------------------------------------------------------ PV --- */
function pvQuery(){
  const q=measureQuery();
  const fields={irradiance:"pv-irradiance",wind:"pv-wind",cloud:"pv-cloud",tilt:"pv-tilt",azimuth:"pv-azimuth",
    cell_size_m:"pv-cell",detect_k:"pv-detect",min_pixels:"pv-minpx",class2_k:"pv-c2",class3_k:"pv-c3"};
  for(const [k,id] of Object.entries(fields)){const v=$(id).value.trim();if(v!=="")q.set(k,v);}
  if(pvRegion)for(const k of ["x","y","w","h"])q.set(k,pvRegion[k]);
  return q.toString();
}
async function runPv(){
  if(!current||!grid)return;
  const id=current.id;$("pv-run").disabled=true;$("pv-result").replaceChildren(el("div","PV-Analyse läuft…","sub"));
  try{
    const r=await api(`/api/v1/thermal/images/${id}/pv?${pvQuery()}`);
    if(!current||current.id!==id)return;
    pvReport=r;pvFocus=-1;renderPv();drawOverlay();
  }catch(e){$("pv-result").replaceChildren(el("div","PV-Analyse fehlgeschlagen: "+e.message,"error"));}
  finally{$("pv-run").disabled=!grid;}
}
function renderPv(){
  $("pv-region").textContent=pvRegion?`PV-Bereich x ${pvRegion.x}, y ${pvRegion.y}, ${pvRegion.w}×${pvRegion.h} px`:"Kein PV-Bereich gewählt (gesamtes Bild).";
  $("pv-export").disabled=!pvReport;$("pv-csv").disabled=!pvReport||!pvReport.anomalies.length;
  const out=$("pv-result");out.replaceChildren();if(!pvReport)return;
  const r=pvReport,c=r.class_counts||{};
  const head=el("div",null,"stats");head.style.marginTop="8px";
  for(const [label,val,cls] of [["Referenz (Median)",deg(r.reference_c),""],["Anomalien",String(r.anomaly_count),""],["Schlechteste Klasse",r.worst_class?"Klasse "+r.worst_class:"keine",r.worst_class?"c"+r.worst_class:""]]){
    const s=el("div",null,"stat");s.append(el("span",label),el("b",val,cls));head.append(s);
  }
  out.append(head,el("div",`Klasse 1: ${c[1]||0} · Klasse 2: ${c[2]||0} · Klasse 3: ${c[3]||0} · Streuung P5–P95 ${fmt(r.spread_p5_p95_k)} K`+(r.cell_size_px?` · ${fmt(r.cell_size_px)} px/Zelle`:""),"sub"));
  for(const w of r.warnings||[])out.append(el("div",w,"warnbox"));
  out.append(el("h3","Messbedingungen"));
  const ct=el("table"),cb=el("tbody");ct.append(cb);
  const icon={ok:"✔",warn:"⚠",fail:"✖",unknown:"?"};
  for(const k of r.checks||[]){
    const tr=el("tr");tr.title=k.note||"";
    tr.append(el("td",icon[k.status]||"?","st-"+k.status),el("td",k.label),el("td",k.value==null?"–":String(k.value).replace(".",",")),el("td",k.limit,"sub"));
    cb.append(tr);
  }
  out.append(ct);
  if(r.anomalies.length){
    out.append(el("h3","Anomalien"));
    const t=el("table"),th=el("thead"),tb=el("tbody"),hr=el("tr");
    for(const h of ["#","Klasse","ΔT","Tmax","Fläche","Muster"])hr.append(el("th",h));th.append(hr);t.append(th,tb);
    r.anomalies.forEach((a,i)=>{
      const tr=el("tr",null,"pick");
      tr.append(el("td","A"+(i+1)),el("td",String(a.class),"c"+a.class),el("td",fmt(a.delta_k)+" K"),el("td",deg(a.max_c)),
        el("td",a.area_m2!=null?fmt(a.area_m2,2)+" m²":a.pixels+" px"),el("td",a.pattern_hint));
      tr.addEventListener("click",()=>{pvFocus=i;drawOverlay();});tb.append(tr);
    });
    out.append(t);
    if(r.anomaly_count>r.anomalies.length)out.append(el("div",`Nur die ${r.anomalies.length} wichtigsten von ${r.anomaly_count} angezeigt.`,"sub"));
  }
  out.append(el("div",r.basis,"note"));
}
$("pv-run").addEventListener("click",runPv);
$("pv-clear").addEventListener("click",()=>{pvRegion=null;pvReport=null;renderPv();drawOverlay();});

/* ---------------------------------------------------------------- map --- */
function initMap(){
  if(typeof L==="undefined"){$("map-state").textContent="Kartenbibliothek (Leaflet) konnte nicht geladen werden.";return;}
  if(!map){
    map=L.map("thermal-map",{zoomControl:true,preferCanvas:true}).setView([51.1,10.4],6);
    const sat=L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",{maxZoom:21,maxNativeZoom:19,attribution:"Esri World Imagery"});
    const osm=L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:21,maxNativeZoom:19,referrerPolicy:"strict-origin-when-cross-origin",attribution:"© OpenStreetMap"});
    osm.addTo(map);L.control.layers({"Straßenkarte":osm,"Satellit":sat}).addTo(map);
    markerLayer=L.layerGroup().addTo(map);footLayer=L.layerGroup();
    map.on("zoomend",()=>{if(map.getZoom()>=17)footLayer.addTo(map);else map.removeLayer(footLayer);});
  }
  setTimeout(()=>map.invalidateSize(),50);
  if(!mapLoaded)loadMap();
}
async function loadMap(fit=true){
  try{
    const r=await api("/api/v1/thermal/map");mapLoaded=true;mapItems=r.items||[];
    const stamp=r.scanned_at?new Date(r.scanned_at).toLocaleString("de-DE"):"nie";
    $("map-state").textContent=mapItems.length?`${mapItems.length.toLocaleString("de-DE")} Wärmebilder mit Position · ${r.without_position} ohne GNSS-Fix · Footprints ab Zoom 17 (ebenes Gelände) · Geo-Index ${stamp}`:
      "Geo-Index leer. Auf dem Pi ausführen: .venv/bin/python -m aeronexus.thermal_geo";
    renderMapItems(fit);
  }catch(e){$("map-state").textContent="Geo-Index nicht verfügbar: "+e.message;}
}
function mapValue(it){
  const mode=$("map-color").value;
  if(!it.stats||mode==="none")return null;
  return mode==="delta"?it.stats.delta_k:it.stats.max_c;
}
function renderMapItems(fit){
  if(!map)return;
  markerLayer.clearLayers();footLayer.clearLayers();
  const flight=$("map-flight").value,items=mapItems.filter(i=>!flight||i.flight_id===flight);
  const vals=items.map(mapValue).filter(v=>typeof v==="number").sort((a,b)=>a-b);
  const lo=vals.length?vals[Math.floor(vals.length*.02)]:0,hi=vals.length?vals[Math.floor((vals.length-1)*.98)]:1;
  const pal=lut("iron"),color=v=>{if(typeof v!=="number")return "#7d8fa3";const k=Math.round(Math.max(0,Math.min(1,(v-lo)/((hi-lo)||1)))*255);return `rgb(${pal[k*3]},${pal[k*3+1]},${pal[k*3+2]})`;};
  for(const it of items){
    const v=mapValue(it),c=$("map-color").value==="none"?"#ff7a45":color(v);
    const st=it.stats?` · Max ${deg(it.stats.max_c)} · ΔT ${fmt(it.stats.delta_k)} K`:" · noch nicht gemessen";
    const label=`${it.name}<br>${it.model||""} · ${fmt(it.relative_altitude_m)} m · Pitch ${fmt(it.gimbal_pitch_deg)}°`+(it.ground_sample_cm?` · ${fmt(it.ground_sample_cm,1)} cm/px`:"")+st;
    const mk=L.circleMarker([it.latitude,it.longitude],{radius:it.stats?5:3,color:"#0b1323",weight:1,fillColor:c,fillOpacity:.95});
    mk.bindTooltip(label);mk.on("click",()=>select({id:it.id,name:it.name}));markerLayer.addLayer(mk);
    if(it.footprint)footLayer.addLayer(L.polygon(it.footprint,{color:c,weight:1,fillOpacity:.05,interactive:false}));
  }
  const showLegend=$("map-color").value!=="none"&&vals.length>0;
  $("map-legend").hidden=view!=="map"||!showLegend;
  if(showLegend){
    $("legend-title").textContent=$("map-color").value==="delta"?"ΔT Max − Median (P2–P98)":"Max-Temperatur (P2–P98)";
    const unit=$("map-color").value==="delta"?" K":" °C";$("legend-low").textContent=fmt(lo)+unit;$("legend-high").textContent=fmt(hi)+unit;
    const bar=$("legend-bar").getContext("2d"),img=bar.createImageData(150,1);
    for(let i=0;i<150;i++){const k=Math.round(i/149*255);img.data.set([pal[k*3],pal[k*3+1],pal[k*3+2],255],i*4);}bar.putImageData(img,0,0);
  }
  if(fit&&items.length)map.fitBounds(L.latLngBounds(items.map(i=>[i.latitude,i.longitude])),{padding:[20,20],maxZoom:18});
  if(analysis)highlightFootprint(analysis);
}
function highlightFootprint(a){
  if(!map)return;
  if(selectedFoot){map.removeLayer(selectedFoot);selectedFoot=null;}
  const fp=a.geometry&&a.geometry.footprint,p=a.position;
  if(fp)selectedFoot=L.polygon(fp,{color:"#75e3bd",weight:3,fillOpacity:.15}).addTo(map);
  else if(p)selectedFoot=L.circleMarker([p.latitude,p.longitude],{radius:9,color:"#75e3bd",weight:3}).addTo(map);
  if(selectedFoot&&view==="map")map.panTo(fp?selectedFoot.getBounds().getCenter():[p.latitude,p.longitude]);
  updateMapThermal();
}
function updateMapThermal(){
  if(!map)return;
  if(thermalOverlay){map.removeLayer(thermalOverlay);thermalOverlay=null;}
  const fp=analysis&&analysis.geometry&&analysis.geometry.footprint;
  // Only the raster that belongs to the shown analysis (no stale image on a new footprint).
  if(!fp||!grid||gridFor!==analysis.id||!$("map-thermal").checked)return;
  // Affine image -> footprint mapping (corners: top-left, top-right, bottom-right, bottom-left).
  const lats=fp.map(q=>q[0]),lons=fp.map(q=>q[1]);
  const n=Math.max(...lats),so=Math.min(...lats),e=Math.max(...lons),w=Math.min(...lons);
  const cw=900,ch=Math.max(1,Math.round(cw*(n-so)/((e-w)*Math.cos(n*Math.PI/180))));
  const px=q=>[(q[1]-w)/(e-w)*cw,(n-q[0])/(n-so)*ch];
  const [tl,tr,,bl]=fp.map(px);
  const out=document.createElement("canvas");out.width=cw;out.height=ch;const oc=out.getContext("2d");
  oc.setTransform((tr[0]-tl[0])/W,(tr[1]-tl[1])/W,(bl[0]-tl[0])/H,(bl[1]-tl[1])/H,tl[0],tl[1]);
  oc.drawImage($("thermal"),0,0);
  thermalOverlay=L.imageOverlay(out.toDataURL("image/png"),[[so,w],[n,e]],{opacity:.85,interactive:false}).addTo(map);
}

/* -------------------------------------------------------------- flights --- */
function setSideTab(t){
  for(const [id,name] of [["tab-images","images"],["tab-flights","flights"]]){$(id).classList.toggle("active",t===name);$(id).setAttribute("aria-selected",String(t===name));}
  $("pane-images").hidden=t!=="images";$("pane-flights").hidden=t!=="flights";
  $("pane-images").style.display=t==="images"?"flex":"none";$("pane-flights").style.display=t==="flights"?"flex":"none";
  $("list-title").textContent=t==="images"?"Wärmebilder (R-JPEG)":"Flugauswertung";
  if(t==="flights")loadFlights();
}
function when2(v){const d=v?new Date(v):null;return d&&!isNaN(d)?d.toLocaleString("de-DE",{dateStyle:"short",timeStyle:"short"}):"–";}
async function loadFlights(){
  try{
    flightsData=await api("/api/v1/thermal/flights");renderFlights();
    const sel=$("map-flight"),keep=sel.value;sel.replaceChildren(new Option("alle",""));
    for(const f of flightsData.flights)if(f.with_position)sel.append(new Option(`${when2(f.start)} (${f.images})`,f.id));
    sel.value=keep;
    scheduleJobPoll(flightsData.job);
  }catch(e){$("flight-state").textContent="Flüge nicht verfügbar: "+e.message;}
}
function renderFlights(){
  const box=$("flights");box.replaceChildren();const job=flightsData.job||{};
  $("flight-state").textContent=flightsData.flights.length?`${flightsData.flights.length} Flüge (neuer Flug nach > ${flightsData.gap_minutes} min Pause)`:"Keine Flüge – Geo-Index aufbauen: python -m aeronexus.thermal_geo";
  for(const f of flightsData.flights){
    const card=el("div",null,"flight"+(openFlight&&openFlight.id===f.id?" active":""));
    card.append(el("b",`${when2(f.start)} – ${new Date(f.end).toLocaleTimeString("de-DE",{hour:"2-digit",minute:"2-digit"})}`));
    card.append(el("small",`${f.model||"–"} · ${f.images} Bilder · ${f.with_position} mit Position · ${f.analyzed} gemessen`+(f.max_c!=null?` · Max ${deg(f.max_c)}`:"")));
    const running=job.state==="running"&&job.flight_id===f.id;
    if(running){const pr=el("progress");pr.max=job.total||1;pr.value=job.processed;card.append(pr,el("small",`${job.processed}/${job.total} · ${fmt(job.seconds,0)} s`+(job.failed?` · ${job.failed} Fehler`:"")));}
    if(job.flight_id===f.id&&(job.state==="done"||job.state==="cancelled")){
      const title=job.state==="cancelled"?"Auswertung abgebrochen":job.failed?"Auswertung mit Fehlern beendet":"Auswertung beendet";
      const summary=el("small",`${title}: ${job.measured||0} gespeichert · ${job.skipped||0} übersprungen · ${job.failed||0} Fehler`);
      summary.setAttribute("role","status");card.append(summary);
    }
    const row=el("div",null,"row");row.style.marginTop="6px";
    const go=el("button",running?"Abbrechen":(f.analyzed<f.images?"Auswerten":"Erneut prüfen"));go.type="button";
    go.disabled=!running&&job.state==="running";
    go.addEventListener("click",()=>running?cancelJob():startJob(f.id));
    const show=el("button","Rangliste");show.type="button";show.disabled=!f.analyzed;show.addEventListener("click",()=>openRanking(f.id));
    const onMap=el("button","Karte");onMap.type="button";onMap.disabled=!f.with_position;
    onMap.addEventListener("click",()=>{$("map-flight").value=f.id;setView("map");if(mapLoaded)renderMapItems(true);});
    row.append(go,show,onMap);card.append(row);
    if(openFlight&&openFlight.id===f.id)card.append(rankingTable(openFlight));
    box.append(card);
  }
}
function rankingTable(d){
  const wrap=el("div");wrap.append(el("div",`Hotspot-Rangliste: ${d.analyzed} gemessen`+(d.pending?`, ${d.pending} offen`:""),"sub"));
  const t=el("table",null,"rank"),tb=el("tbody");t.append(tb);
  d.ranking.slice(0,50).forEach((r,i)=>{const tr=el("tr",null,"pick");
    tr.append(el("td",String(i+1)),el("td",deg(r.max_c)),el("td","ΔT "+fmt(r.delta_k)+" K"),el("td",new Date(r.captured_at).toLocaleTimeString("de-DE")));
    tr.title=r.name;tr.addEventListener("click",()=>select({id:r.id,name:r.name}));tb.append(tr);});
  wrap.append(t);return wrap;
}
async function openRanking(id){
  try{openFlight=await api(`/api/v1/thermal/flights/${id}`);renderFlights();}catch(e){$("flight-state").textContent="Rangliste nicht verfügbar: "+e.message;}
}
async function post(path){
  const res=await fetch(path,{method:"POST",cache:"no-store",credentials:"same-origin"});
  let body=null;try{body=await res.json();}catch(e){}
  if(!res.ok)throw new Error(body&&body.detail||"HTTP "+res.status);
  return body;
}
async function startJob(id){
  try{const job=await post(`/api/v1/thermal/flights/${id}/analyze`);flightsData.job=job;renderFlights();scheduleJobPoll(job);}
  catch(e){$("flight-state").textContent="Start fehlgeschlagen: "+e.message;}
}
async function cancelJob(){try{flightsData.job=await post("/api/v1/thermal/jobs/current/cancel");renderFlights();}catch(e){}}
function scheduleJobPoll(job){
  clearTimeout(jobTimer);
  if(!job||job.state!=="running")return;
  jobTimer=setTimeout(async()=>{
    try{
      const j=await api("/api/v1/thermal/jobs/current");flightsData.job=j;
      if(j.state!=="running"){await loadFlights();if(openFlight&&openFlight.id===j.flight_id)openRanking(j.flight_id);if(mapLoaded)loadMap(false);}
      else{renderFlights();scheduleJobPoll(j);}
    }catch(e){scheduleJobPoll(job);}
  },2000);
}
$("tab-images").addEventListener("click",()=>setSideTab("images"));
$("tab-flights").addEventListener("click",()=>setSideTab("flights"));
$("map-color").addEventListener("change",()=>renderMapItems(false));
$("map-flight").addEventListener("change",()=>renderMapItems(true));
$("map-thermal").addEventListener("change",updateMapThermal);

/* -------------------------------------------------------------- exports --- */
function save(blob,name){const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),2000);}
function base(){return (current&&current.name||"thermal").replace(/\.[^.]+$/,"");}
function exportState(){const ok=!!grid;$("export-png").disabled=!ok;$("export-grid").disabled=!ok;$("export-csv").disabled=!ok||!spots.length;$("export-json").disabled=!analysis;}
function csvNum(v){return typeof v==="number"?v.toFixed(2):"";}
$("export-png").addEventListener("click",()=>{
  const c=document.createElement("canvas");c.width=W;c.height=H;const ctx=c.getContext("2d");
  if(view==="overlay"){ctx.drawImage($("visual"),0,0);ctx.globalAlpha=+$("thermal").style.opacity||1;}
  ctx.drawImage($("thermal"),0,0);ctx.globalAlpha=1;ctx.drawImage($("overlay"),0,0);c.toBlob(b=>b&&save(b,base()+"_analyse.png"),"image/png");
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
  const report={generated_at:new Date().toISOString(),image:analysis,measurements:spots,pv_inspection:pvReport};
  save(new Blob([JSON.stringify(report,null,2)],{type:"application/json"}),base()+"_bericht.json");
});
$("pv-export").addEventListener("click",()=>{
  const report={generated_at:new Date().toISOString(),image:{id:analysis.id,name:analysis.name,model:analysis.model,captured_at:analysis.captured_at,position:analysis.position,gimbal:analysis.gimbal},pv_inspection:pvReport};
  save(new Blob([JSON.stringify(report,null,2)],{type:"application/json"}),base()+"_pv_bericht.json");
});
$("pv-csv").addEventListener("click",()=>{
  const lines=["nr;klasse;delta_k;tmax_c;tmittel_c;x;y;breite;hoehe;pixel;flaeche_m2;muster;referenz_c"];
  pvReport.anomalies.forEach((a,i)=>lines.push(["A"+(i+1),a.class,csvNum(a.delta_k),csvNum(a.max_c),csvNum(a.mean_c),a.x,a.y,a.w,a.h,a.pixels,a.area_m2==null?"":a.area_m2,a.pattern_hint,csvNum(pvReport.reference_c)].join(";")));
  save(new Blob([lines.join("\n")+"\n"],{type:"text/csv"}),base()+"_pv_anomalien.csv");
});

/* --------------------------------------------------------------- wiring --- */
$("material").addEventListener("change",()=>{$("p-emissivity").value=$("material").value;});
$("recalc").addEventListener("click",()=>{spots=[];pvReport=null;renderSpots();renderPv();analyse();});
$("reset-params").addEventListener("click",()=>{for(const k of ["emissivity","distance","humidity","reflection","ambient"])$("p-"+k).value="";$("material").value="";if(current){spots=[];pvReport=null;renderSpots();renderPv();analyse();}});
for(const id of ["palette","range-low","range-high","iso-on","iso-value"])$(id).addEventListener("input",draw);
for(const id of ["ov-alpha","ov-scale","ov-dx","ov-dy"])$(id).addEventListener("input",()=>{if(view==="overlay"&&grid)drawVisual();});
$("ov-reset").addEventListener("click",()=>{$("ov-alpha").value=55;$("ov-scale").value=100;$("ov-dx").value=0;$("ov-dy").value=0;if(view==="overlay"&&grid)drawVisual();});
$("extremes").addEventListener("change",drawOverlay);
$("range-mode").addEventListener("change",()=>{
  const manual=$("range-mode").value==="manual";$("manual-range").hidden=!manual;
  if(manual&&analysis&&analysis.measurement&&$("range-low").value===""){$("range-low").value=analysis.measurement.min_c.toFixed(1);$("range-high").value=analysis.measurement.max_c.toFixed(1);}
  draw();
});
$("view-image").addEventListener("click",()=>setView("image"));
$("view-overlay").addEventListener("click",()=>setView("overlay"));
$("view-map").addEventListener("click",()=>setView("map"));
$("search-go").addEventListener("click",()=>{offset=0;loadList();});
$("search").addEventListener("keydown",e=>{if(e.key==="Enter"){offset=0;loadList();}});
$("prev").addEventListener("click",()=>{offset=Math.max(0,offset-PAGE);loadList();});
$("next").addEventListener("click",()=>{offset+=PAGE;loadList();});
window.addEventListener("resize",fitStack);
loadStatus();loadList();loadFlights();
</script>
</body>
</html>
"""


HTML = with_navigation(HTML, "thermal")


def render_thermal_page() -> str:
    return HTML
