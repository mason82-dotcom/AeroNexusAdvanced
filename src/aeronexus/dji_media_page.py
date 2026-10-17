"""Standalone read-only DJI MinIO media index browser.

Never embeds MinIO credentials, presigned links or physical object paths.
Every list request is made against the local, access-controlled FastAPI API.
"""

HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="dark">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<title>AeroNexusAdvanced · DJI Medienindex</title>
<style>
:root{font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;color-scheme:dark;
  background:#0b1423;color:#e6f1ff}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(circle at top right,#1b3450,#0b1423 58%);min-height:100vh}
main{max-width:1260px;margin:auto;padding:22px}
header{display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:18px}
a{color:#a0d8ff}
nav{display:flex;gap:18px;flex-wrap:wrap}
.eyebrow{font-size:11px;letter-spacing:.16em;color:#80bff4;text-transform:uppercase}
h1{font-size:clamp(23px,4vw,34px);margin:3px 0}
h2{font-size:17px;margin:0 0 10px}
p{color:#bbcee4}
.card{background:#12243b;border:1px solid #3c5470;border-radius:13px;padding:17px;margin:14px 0}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.metric{background:#0e2035;border:1px solid #344d66;border-radius:9px;padding:12px}
.metric b{display:block;font-size:22px;overflow-wrap:anywhere}
.metric span{display:block;color:#aac3da;font-size:12px}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:end;margin:14px 0}
label{font-size:12px;color:#bbcee4;display:grid;gap:5px}
select,input,button{font:inherit;color:#ebf6ff;background:#1a3551;border:1px solid #52708c;
  border-radius:8px;padding:9px 11px}
input{min-width:min(100%,280px)}
button{cursor:pointer}button:disabled{opacity:.5;cursor:not-allowed}
:focus-visible{outline:2px solid #87d6ff;outline-offset:2px}
.scroller{overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:690px}
td,th{padding:12px 10px;text-align:left;border-bottom:1px solid #344b64;vertical-align:top}
th{font-size:12px;color:#bcd2eb}
td:first-child{max-width:430px;overflow-wrap:anywhere}
.sub{color:#a8c0d8;font-size:12px}
.tag{font-size:12px;padding:3px 7px;border:1px solid #4e6a84;border-radius:16px;white-space:nowrap}
.ok{color:#83e5ba}.warn{color:#f1ca82}.error{color:#ffb0bb}
.pager{display:flex;gap:12px;align-items:center;justify-content:end;padding-top:15px}
footer{color:#94adc7;font-size:12px;padding:10px 0}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
.chip{border-radius:18px;padding:6px 12px}.chip[aria-pressed="true"]{background:#2d6a96;border-color:#87d6ff}
.photo-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:14px;align-items:start}
@media (max-width:900px){.photo-grid{grid-template-columns:minmax(0,1fr)}}
#photo-map{height:460px;border-radius:10px;border:1px solid #3c5470;background:#0e2035}
#photo-table table{min-width:560px}#photo-table td,#photo-table th{padding:8px}
#photo-table td:nth-child(n+3){white-space:nowrap}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:#bbcee4;margin-top:6px}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:-1px}
</style>
</head>
<body>
<main>
<header>
<div><div class="eyebrow">AERONEXUS ADVANCED · PHASE 20</div>
<h1>DJI-MinIO-Medienindex</h1></div>
<nav aria-label="Bereiche"><a href="/operations">Operations Center</a>
<a href="/status">Live-Status</a><a href="/studio">Mission Studio</a>
<a href="/thermal">Thermal</a><a href="/multispectral">Multispektral</a><a href="/results">Ergebnisraster</a></nav>
</header>
<p>Schreibgeschützter Index der DJI-Pilot-2-Uploads. Originale verbleiben in MinIO.
Der Fotokatalog liest Drohnenmodell, Kamera, Aufnahmezeit, Position und Gimbal aus den
Bild-Metadaten (nur Kopfbereich, keine Seriennummern). „Upload“ bezeichnet den Zeitstempel des Objektspeichers.</p>
<section class="card">
<div class="metrics">
<div class="metric"><span>Indexzustand</span><b id="index-state">Lade…</b></div>
<div class="metric"><span>Medienobjekte</span><b id="index-total">–</b></div>
<div class="metric"><span>Gesamtvolumen</span><b id="index-bytes">–</b></div>
<div class="metric"><span>Letzter Scan</span><b id="index-scanned" style="font-size:15px">–</b></div>
<div class="metric"><span>Auto-Sync (Pilot 2 Uploads)</span><b id="sync-state" style="font-size:15px">–</b></div>
</div>
<div class="sub" id="kind-counts" aria-live="polite">Metadaten werden geladen…</div>
</section>
<section class="card" id="photo-catalog">
<div class="eyebrow">Fotokatalog · aus Bild-Metadaten</div>
<h2>DJI-Fotos nach Drohne, Kamera und Flug</h2>
<div class="chips" id="photo-models" role="group" aria-label="Drohnenmodell"></div>
<div class="controls">
<label>Kamera<select id="photo-camera"><option value="">Alle Kameras</option></select></label>
<label>Flug<select id="photo-flight"><option value="">Alle Flüge</option></select></label>
<label><span><input id="photo-footprints" type="checkbox" checked style="min-width:0"> Footprints</span></label>
</div>
<div id="photo-state" class="sub" role="status" aria-live="polite">Fotokatalog wird geladen…</div>
<div class="photo-grid">
<div><div id="photo-map" aria-label="Karte der Aufnahmepunkte"></div>
<div class="legend" id="photo-legend"></div></div>
<div><div class="scroller" id="photo-table"><table>
<thead><tr><th>Aufnahme</th><th>Kamera</th><th>Höhe</th><th>Pitch</th><th>Brennw. (KB)</th><th></th></tr></thead>
<tbody id="photo-rows"></tbody></table></div>
<div class="pager"><button id="photo-prev" type="button">Zurück</button><span id="photo-page">–</span>
<button id="photo-next" type="button">Weiter</button></div></div>
</div>
</section>
<section class="card">
<div class="eyebrow">MinIO · nur lesen</div>
<h2>Fotos, RAW, Videos und Begleitdateien</h2>
<div class="controls">
<label>Medientyp
<select id="kind">
<option value="">Alle</option>
<option value="image">Foto / TIFF</option>
<option value="raw">RAW / DNG</option>
<option value="video">Video</option>
<option value="audio">Audio</option>
<option value="sidecar">Begleitdatei</option>
</select></label>
<label>Dateiname
<input id="search" type="search" maxlength="200" placeholder="Dateiname suchen">
</label>
<button id="filter" type="button">Filtern</button>
<button id="refresh" type="button">Aktualisieren</button>
</div>
<div id="result-message" class="sub" role="status" aria-live="polite">Lade Medienliste…</div>
<div class="scroller"><table>
<thead><tr><th>Dateiname</th><th>Art</th><th>Größe</th><th>Upload (MinIO)</th></tr></thead>
<tbody id="media-rows"></tbody>
</table></div>
<div class="pager">
<button id="previous" type="button">Zurück</button>
<span id="page">–</span>
<button id="next" type="button">Weiter</button>
</div>
</section>
<footer>Der Index enthält nur Metadaten. Originale werden nur über „Ansehen“ geladen;
diese Ansicht veröffentlicht keine Objektschlüssel und führt keine Schreiboperationen aus.</footer>
</main>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
"use strict";
const $=id=>document.getElementById(id);
let offset=0,total=0,busy=false;
const limit=50;
function fmtBytes(n){
  if(typeof n!=="number"||!Number.isFinite(n)||n<0)return "–";
  if(n<1024)return n+" B";
  const units=["KiB","MiB","GiB","TiB"];
  let v=n,i=-1;
  do{v/=1024;i++;}while(v>=1024&&i<units.length-1);
  return v.toFixed(1)+" "+units[i];
}
function fmtTime(value){
  const ms=typeof value==="string"?Date.parse(value):NaN;
  return Number.isFinite(ms)?new Date(ms).toLocaleString("de-DE"):"Nicht übermittelt";
}
function labelKind(value){
  return {image:"Foto / TIFF",raw:"RAW / DNG",video:"Video",
    audio:"Audio",sidecar:"Begleitdatei"}[value]||"Sonstige";
}
async function getJSON(url){
  const res=await fetch(url,{cache:"no-store"});
  if(!res.ok)throw new Error("HTTP "+res.status);
  return res.json();
}
function td(row,value){
  const cell=document.createElement("td");
  cell.textContent=String(value??"–");row.appendChild(cell);
  return cell;
}
async function refresh(){
  if(busy)return;
  busy=true;$("refresh").disabled=true;$("filter").disabled=true;
  try{
    const params=new URLSearchParams({limit:String(limit),offset:String(offset)});
    if($("kind").value)params.set("kind",$("kind").value);
    if($("search").value.trim())params.set("q",$("search").value.trim());
    const [summary,data]=await Promise.all([
      getJSON("/api/v1/dji/media/summary"),
      getJSON("/api/v1/dji/media?"+params.toString())
    ]);
    $("index-state").textContent=summary.state==="ready"?"Bereit":"Noch nicht indiziert";
    $("index-state").className=summary.state==="ready"?"ok":"warn";
    $("index-total").textContent=String(summary.total??0);
    $("index-bytes").textContent=fmtBytes(summary.total_bytes);
    $("index-scanned").textContent=fmtTime(summary.scanned_at);
    getJSON("/api/v1/media/sync").then(sync=>{
      const labels={idle:"Bereit",running:"Aktualisiert…",upload_in_progress:"Upload läuft…",
        starting:"Startet…",not_running:"Nicht aktiv",unreadable:"Unbekannt"};
      const mode=sync.mode==="events"?"Ereignisse":sync.mode==="poll"?"Abfrage alle 2 min":"";
      const last=sync.last_run&&sync.last_run.finished_at?" · zuletzt "+fmtTime(sync.last_run.finished_at):"";
      $("sync-state").textContent=(labels[sync.state]||sync.state)+(mode?" · "+mode:"")+last;
      $("sync-state").className=sync.state==="not_running"?"warn":(sync.last_run&&sync.last_run.ok===false?"error":"ok");
    }).catch(()=>{$("sync-state").textContent="–";});
    $("kind-counts").textContent=Object.entries(summary.kinds||{}).map(
      ([kind,count])=>labelKind(kind)+": "+count).join(" · ")||"Keine Mediendateien indiziert";
    total=Number(data.total)||0;
    const rows=$("media-rows");rows.replaceChildren();
    for(const item of data.items||[]){
      const row=document.createElement("tr");
      td(row,item.name);
      td(row,labelKind(item.kind));
      td(row,fmtBytes(item.size_bytes));
      td(row,fmtTime(item.uploaded_at));
      rows.appendChild(row);
    }
    $("result-message").textContent=summary.state!=="ready"?
      "Noch kein MinIO-Index. Bitte Scan auf dem Pi starten.":
      total?total+" Dateien gefunden. Nur Metadaten, keine Downloads.":
      "Keine Dateien für diese Filter gefunden.";
    $("page").textContent=total?(offset+1)+"–"+Math.min(offset+limit,total)+" / "+total:"0 / 0";
    $("previous").disabled=offset===0;
    $("next").disabled=offset+limit>=total;
  }catch(error){
    $("result-message").textContent="Medienindex nicht erreichbar: "+error.message;
    $("result-message").className="error";
  }finally{
    busy=false;$("refresh").disabled=false;$("filter").disabled=false;
  }
}
$("filter").addEventListener("click",()=>{offset=0;refresh();});
$("refresh").addEventListener("click",refresh);
$("search").addEventListener("keydown",event=>{
  if(event.key==="Enter"){offset=0;refresh();}
});
$("previous").addEventListener("click",()=>{offset=Math.max(0,offset-limit);refresh();});
$("next").addEventListener("click",()=>{if(offset+limit<total){offset+=limit;refresh();}});
// ---------------------------------------------------------------- photo catalogue
const CAMERA_COLORS={WideCamera:"#4fc3f7",ZoomCamera:"#ffb74d",InfraredCamera:"#ef5350",
  MS_CAMERA:"#9ccc65",VisibleCamera:"#ce93d8"};
const photoLimit=25;
let photo={model:"",camera:"",flight:"",offset:0,total:0,summary:null,names:{}},
  photoMap=null,photoLayer=null,photoGen=0;
const camColor=c=>CAMERA_COLORS[c]||"#cfd8dc";
const camName=c=>photo.names[c]||c||"Unbekannt";
const fmtNum=(v,d,unit)=>typeof v==="number"&&Number.isFinite(v)?v.toFixed(d)+(unit||""):"–";
function photoQuery(extra){
  const p=new URLSearchParams(extra||{});
  if(photo.model)p.set("model",photo.model);
  if(photo.camera)p.set("camera",photo.camera);
  if(photo.flight)p.set("flight",photo.flight);
  return p.toString();
}
function option(select,value,text){
  const o=document.createElement("option");o.value=value;o.textContent=text;select.appendChild(o);
}
function renderModels(){
  const box=$("photo-models");box.replaceChildren();
  for(const m of photo.summary.models){
    const b=document.createElement("button");b.type="button";b.className="chip";
    b.textContent=m.model+" · "+m.name+" ("+m.total+")";
    b.setAttribute("aria-pressed",String(m.model===photo.model));
    b.addEventListener("click",()=>selectModel(m.model));box.appendChild(b);
  }
  const model=photo.summary.models.find(m=>m.model===photo.model);
  const cam=$("photo-camera");cam.replaceChildren();option(cam,"","Alle Kameras");
  for(const [c,n] of Object.entries(model?model.cameras:{}))option(cam,c,camName(c)+" ("+n+")");
  cam.value=photo.camera;
  $("photo-legend").replaceChildren(...Object.keys(model?model.cameras:{}).map(c=>{
    const s=document.createElement("span"),d=document.createElement("i");
    d.className="dot";d.style.background=camColor(c);s.append(d,camName(c));return s;}));
}
async function loadFlights(gen){
  const data=await getJSON("/api/v1/photos/flights?"+new URLSearchParams(
    Object.fromEntries([["model",photo.model],["camera",photo.camera]].filter(e=>e[1]))).toString());
  if(gen!==photoGen)return;
  const sel=$("photo-flight");sel.replaceChildren();option(sel,"","Alle Flüge ("+data.flights.length+")");
  for(const f of data.flights){
    const start=new Date(Date.parse(f.start)),end=new Date(Date.parse(f.end));
    const when=Number.isFinite(start.getTime())?start.toLocaleString("de-DE",{dateStyle:"short",timeStyle:"short"})+
      "–"+end.toLocaleTimeString("de-DE",{timeStyle:"short"}):"ohne Zeit";
    option(sel,f.id,when+" · "+f.images+(f.images===1?" Bild":" Bilder")+(f.median_altitude_m!=null?" · "+fmtNum(f.median_altitude_m,0," m"):""));
  }
  if(!data.flights.some(f=>f.id===photo.flight))photo.flight="";
  sel.value=photo.flight;
}
function initPhotoMap(){
  if(photoMap||typeof L==="undefined")return;
  photoMap=L.map("photo-map",{preferCanvas:true}).setView([51.1,10.4],6);
  const sat=L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",{maxZoom:22,maxNativeZoom:19,attribution:"Esri World Imagery"});
  const osm=L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:22,maxNativeZoom:19,attribution:"© OpenStreetMap"});
  sat.addTo(photoMap);L.control.layers({"Satellit":sat,"Straßenkarte":osm}).addTo(photoMap);
  photoLayer=L.layerGroup().addTo(photoMap);
}
function popup(it){
  const box=document.createElement("div"),title=document.createElement("b"),info=document.createElement("div");
  title.textContent=it.name;
  info.textContent=[it.captured_at?fmtTime(it.captured_at):null,camName(it.camera),
    "Höhe "+fmtNum(it.relative_altitude_m,1," m"),"Pitch "+fmtNum(it.gimbal_pitch_deg,0,"°"),
    it.ground_sample_cm?"GSD "+fmtNum(it.ground_sample_cm,2," cm/px"):null,
    it.position_outlier?"Position unplausibel (> 20 km vom Flug)":null].filter(Boolean).join(" · ");
  const link=document.createElement("a");link.href="/api/v1/studio/dji-media/"+encodeURIComponent(it.id)+"/file";
  link.target="_blank";link.rel="noopener noreferrer";link.textContent="Original ansehen";
  box.append(title,info,link);return box;
}
async function loadPhotoMap(gen){
  initPhotoMap();
  if(!photoMap)return null;
  const data=await getJSON("/api/v1/photos/map?"+photoQuery());
  if(gen!==photoGen)return null;
  photoLayer.clearLayers();
  const feet=$("photo-footprints").checked;
  for(const it of data.items){
    const color=camColor(it.camera);
    if(feet&&it.footprint&&!it.position_outlier)photoLayer.addLayer(L.polygon(it.footprint,{color,weight:1,fillOpacity:.06,interactive:false}));
    photoLayer.addLayer(L.circleMarker([it.latitude,it.longitude],it.position_outlier?
      {radius:6,color:"#ffb0bb",weight:2,dashArray:"3 3",fillColor:color,fillOpacity:.4}:
      {radius:5,color:"#0b1323",weight:1,fillColor:color,fillOpacity:.95}).bindPopup(()=>popup(it)));
  }
  setTimeout(()=>photoMap.invalidateSize(),50);
  const plausible=data.items.filter(i=>!i.position_outlier);
  const fit=plausible.length?plausible:data.items;
  if(fit.length)photoMap.fitBounds(L.latLngBounds(fit.map(i=>[i.latitude,i.longitude])),{padding:[30,30],maxZoom:19});
  return data;
}
async function loadPhotoRows(gen){
  const data=await getJSON("/api/v1/photos?"+photoQuery({limit:String(photoLimit),offset:String(photo.offset)}));
  if(gen!==photoGen)return;
  photo.total=Number(data.total)||0;
  const rows=$("photo-rows");rows.replaceChildren();
  for(const it of data.items||[]){
    const row=document.createElement("tr");
    const first=td(row,it.name);const sub=document.createElement("div");sub.className="sub";
    sub.textContent=(it.captured_at?fmtTime(it.captured_at):"Zeit unbekannt")+(it.has_position?"":" · ohne GNSS");
    first.appendChild(sub);
    td(row,camName(it.camera));td(row,fmtNum(it.relative_altitude_m,1," m"));
    td(row,fmtNum(it.gimbal_pitch_deg,0,"°"));td(row,it.focal_length_35mm?it.focal_length_35mm+" mm":"–");
    const cell=document.createElement("td"),link=document.createElement("a");
    link.href="/api/v1/studio/dji-media/"+encodeURIComponent(it.id)+"/file";link.target="_blank";
    link.rel="noopener noreferrer";link.textContent="Ansehen";cell.appendChild(link);row.appendChild(cell);
    rows.appendChild(row);
  }
  $("photo-page").textContent=photo.total?(photo.offset+1)+"–"+Math.min(photo.offset+photoLimit,photo.total)+" / "+photo.total:"0 / 0";
  $("photo-prev").disabled=photo.offset===0;$("photo-next").disabled=photo.offset+photoLimit>=photo.total;
}
async function refreshPhotos(withFlights){
  const gen=++photoGen;
  try{
    if(withFlights)await loadFlights(gen);
    if(gen!==photoGen)return;
    const [map]=await Promise.all([loadPhotoMap(gen),loadPhotoRows(gen)]);
    if(gen!==photoGen)return;
    $("photo-state").className="sub";
    $("photo-state").textContent=photo.total+" Fotos"+(map?" · "+map.items.length+" mit Position, "+
      map.items.filter(i=>i.footprint).length+" mit Footprint (Nadir ±15°, ebenes Gelände)"+
      (map.position_outliers?", "+map.position_outliers+" mit unplausibler Position (gestrichelt)":""):"")+
      (photo.summary.scanned_at?" · Katalog vom "+fmtTime(photo.summary.scanned_at):"")+
      (photoMap?"":" · Kartenbibliothek (Leaflet) nicht geladen");
  }catch(error){
    if(gen!==photoGen)return;
    $("photo-state").textContent="Fotokatalog nicht erreichbar: "+error.message;$("photo-state").className="error";
  }
}
function selectModel(model){
  photo.model=model;photo.camera="";photo.flight="";photo.offset=0;renderModels();refreshPhotos(true);
}
async function initPhotos(){
  try{
    photo.summary=await getJSON("/api/v1/photos/summary");photo.names=photo.summary.camera_names||{};
    if(!photo.summary.models.length){$("photo-state").textContent="Fotokatalog noch leer – er wird vom Medien-Sync gefüllt.";return;}
    const m3e=photo.summary.models.find(m=>m.model==="M3E");
    selectModel((m3e||photo.summary.models[0]).model);
  }catch(error){
    $("photo-state").textContent="Fotokatalog nicht erreichbar: "+error.message;$("photo-state").className="error";
  }
}
$("photo-camera").addEventListener("change",e=>{photo.camera=e.target.value;photo.flight="";photo.offset=0;refreshPhotos(true);});
$("photo-flight").addEventListener("change",e=>{photo.flight=e.target.value;photo.offset=0;refreshPhotos(false);});
$("photo-footprints").addEventListener("change",()=>refreshPhotos(false));
$("photo-prev").addEventListener("click",()=>{photo.offset=Math.max(0,photo.offset-photoLimit);loadPhotoRows(photoGen).catch(()=>{});});
$("photo-next").addEventListener("click",()=>{if(photo.offset+photoLimit<photo.total){photo.offset+=photoLimit;loadPhotoRows(photoGen).catch(()=>{});}});
initPhotos();
refresh();
window.setInterval(refresh,60000);
</script>
</body></html>"""


def render_dji_media_page() -> str:
    return HTML
