"""DJI FlightHub 2-inspired local Operations Center.

This is an independent AeroNexus read-only UI, NOT the proprietary FH2
passthrough microfrontend. No DJI credentials, product serials, mission
commands or raw upstream API responses are embedded in the public HTML.
"""


HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="dark">
<title>AeroNexus Operations Center · FlightHub 2</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<style>
:root{font:14px/1.45 system-ui,"Segoe UI",sans-serif;color-scheme:dark;--bg:#0b1323;--pane:#122139;--card:#152b47;--line:#334e69;--ink:#eaf4ff;--sub:#a9bfd8;--mint:#75e3bd;--blue:#72bdff;--amber:#e4bd78;--red:#ff9ba8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink)}
button,select,input{font:inherit}
button,select{background:#213d5e;border:1px solid #426487;color:#eef7ff;border-radius:9px;padding:8px 11px;cursor:pointer}
button:hover{background:#2a517a}button:disabled{opacity:.5;cursor:not-allowed}
button:focus-visible,select:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid var(--mint);outline-offset:2px}
a{color:#9dd5ff}
header{display:flex;align-items:center;gap:15px;flex-wrap:wrap;padding:12px 20px;background:#142440;border-bottom:1px solid var(--line)}
.logo{font-weight:800;font-size:18px;letter-spacing:-.02em;white-space:nowrap}.logo small{display:block;font-size:10px;letter-spacing:.18em;color:#7abef0}
.tabs{display:flex;align-items:center;flex-wrap:wrap;gap:13px}
.tabs a{font-size:13px;text-decoration:none}.tabs .active{font-weight:700;color:var(--mint)}
.eyebrow{font-size:11px;letter-spacing:.12em;color:#87b6e1;text-transform:uppercase;font-weight:700}
.header-state{margin-left:auto;color:var(--mint);font-size:12px}
.layout{display:grid;grid-template-columns:minmax(245px,300px) minmax(300px,1fr) minmax(285px,340px);gap:12px;padding:12px;height:calc(100vh - 68px);min-height:620px}
.column{display:flex;flex-direction:column;gap:12px;min-width:0;min-height:0}
.panel{min-width:0;min-height:0;border:1px solid var(--line);border-radius:13px;background:var(--pane);padding:14px;display:flex;flex-direction:column;overflow:hidden}
.panel h2{font-size:17px;line-height:1.3;margin:0 0 8px}
.panel h3{font-size:14px;margin:13px 0 7px}
.sub{font-size:12px;color:var(--sub);line-height:1.5}
.scroll{overflow-y:auto;overflow-x:hidden;min-height:0;overscroll-behavior:contain}
#cockpit-content{position:relative;isolation:isolate;contain:paint;overflow-wrap:anywhere;scrollbar-gutter:stable}
#cockpit-summary{position:relative;z-index:1;background:var(--pane)}
#cockpit-content .cockpit-technical{min-width:0;max-width:100%}
#cockpit-content .cockpit-technical .cockpit>div b{font-size:14px;line-height:1.4;overflow-wrap:anywhere;word-break:break-word}
#cockpit-content .cockpit-technical .cockpit>div.cockpit-raw{grid-column:1/-1}
#cockpit-content .cockpit-technical .cockpit>div.cockpit-raw b{font:12px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word}
.grow{flex:1}
.row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.between{justify-content:space-between}
.kpi-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:12px 0}
.kpi{background:#0e2137;border:1px solid #2c465e;border-radius:9px;padding:9px;min-width:0}
.kpi strong{display:block;font-size:21px;margin-top:4px}
.kpi span{font-size:11px;color:var(--sub)}
.note{font-size:12px;color:var(--sub);padding:9px 0}
.list-card{border:1px solid #33506d;border-radius:9px;padding:10px;margin:7px 0;background:#142842}
.list-card.clickable{cursor:pointer}
.list-card.clickable:hover,.list-card.active{border-color:#76bfff;background:#214362}
.list-card b{display:block;overflow-wrap:anywhere}
.list-card small{display:block;font-size:11px;color:#b5cae1;margin-top:4px;overflow-wrap:anywhere}
.badge{display:inline-block;font-size:11px;padding:3px 8px;border:1px solid #486d8b;border-radius:999px}
.badge.good{color:var(--mint);border-color:#327f6b}.badge.warn{color:var(--amber);border-color:#806844}.badge.bad{color:var(--red);border-color:#984b5d}
#project-filter{width:100%;min-width:0;margin:10px 0 3px}
#map-wrap{position:relative;min-height:320px;flex:1;overflow:hidden;border-radius:8px}
#operations-map{height:100%;width:100%;background:#23374f}
.map-controls{position:absolute;z-index:500;top:10px;left:10px;display:flex;flex-wrap:wrap;gap:7px}
.map-controls select{max-width:170px}
.map-note{position:absolute;z-index:500;bottom:13px;left:10px;max-width:min(510px,85%);background:#112137e8;color:#c8dbed;border-radius:8px;padding:8px;font-size:11px;pointer-events:none}
.cockpit{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.cockpit>div{background:#102339;border-radius:8px;padding:10px;min-width:0}
.cockpit>div span{display:block;font-size:11px;color:#a6bdd7}
.cockpit>div b{font-size:17px;display:block;overflow-wrap:anywhere;margin-top:4px}
.cockpit-status-row{margin:9px 0;gap:6px;flex-shrink:0}
.cockpit-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;flex-shrink:0;margin:1px 0 10px}
.cockpit-summary .hero-value{background:#102c46;border:1px solid #335773;border-radius:10px;padding:7px 9px;min-width:0}
.cockpit-summary .hero-value.battery{grid-column:1/-1}
.osd-live-card{border-color:#386989;background:#102c43}
.osd-live-card .sub{margin-top:6px}
.controller-status{margin:0 0 10px;display:grid;gap:6px;flex-shrink:0}
.controller-card{border:1px solid #365370;background:#112840;border-radius:9px;padding:9px}
.controller-card b{font-size:12px;display:block}
.controller-card span{font-size:12px;color:#b9cfe5;display:block;margin-top:3px}
.gnss-note{border-left:3px solid #568caf;padding:8px 10px;background:#132d44;border-radius:4px;margin:9px 0}
.gnss-note.warn{border-left-color:#d6a862}
.right>.panel:first-child{flex:1.2}
.right>.panel:last-child{flex:.8}
.hero-value .hero-label{font-size:11px;color:#b4cce5;display:block}
.hero-value strong{display:block;font-size:18px;overflow-wrap:anywhere;margin-top:3px}
.hero-value.battery strong{font-size:23px}
.cockpit-info{font-size:11px;color:#bad2e8;line-height:1.5;margin:0 0 9px}
.cockpit-section-title{font-size:13px;font-weight:700;margin:12px 0 7px}
.cockpit-technical{border-top:1px solid #385574;margin-top:11px;padding-top:9px}
.cockpit-technical summary{cursor:pointer;color:#a9d9fa;font-size:13px;font-weight:700;padding:5px 0}
.cockpit-technical summary:focus-visible{outline:2px solid #8bd7fc}
.cockpit-technical[open] .cockpit{margin-top:8px}
.cockpit-secondary-note{color:#b4c6db;font-size:11px;line-height:1.5;padding:8px 0}
.progress{width:100%;height:12px;accent-color:#6bd7a8;margin:6px 0}
.progress.low{accent-color:#e5a776}
.select-wide{width:100%;min-width:0}
.cockpit-alert{border-top:1px solid #35516f;padding:8px 0;font-size:12px;overflow-wrap:anywhere}
.cockpit-alert b{color:#ffe0aa}
.list-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:6px 0}
.library-scroll{max-height:310px;min-height:125px}
.tracks-scroll{min-height:125px;flex:1}
.tracks-scroll button,.library-scroll button{font-size:12px;padding:5px 8px}
.task-filter{display:flex;gap:7px;margin:10px 0;flex-wrap:wrap}
.task-filter button{font-size:12px;flex:1;padding:6px 8px}
.task-filter button.active{border-color:#77bfeb;background:#2b577b;font-weight:700}
.task-day{font-size:12px;color:#9ccbea;border-bottom:1px solid #365270;padding:9px 0 5px;margin-top:8px}
.task-state{font-size:11px;font-weight:600;display:inline-flex;align-items:center;gap:7px;margin:6px 0}
.task-state.pending{color:#a9ccfa}.task-state.active{color:#78e9bd}
.task-state.complete{color:#94dfaa}.task-state.failed{color:#ffacb6}
.task-progress{margin:6px 0;font-size:11px;color:#b5c9e1}
.legend{border-top:1px solid #35516d;margin-top:10px;padding-top:8px}
div[hidden],section[hidden],aside[hidden]{display:none!important}
.point-icon{width:22px;height:22px;border:2px solid white;border-radius:50%;display:grid;place-items:center;color:#fff;background:#287ac4;font-size:11px;font-weight:700;box-shadow:0 2px 7px #0019}
.selected-route{color:#ffcc81}
.critical{color:#ffa7ae}
@media(max-width:1200px){.layout{grid-template-columns:260px minmax(300px,1fr)}.right{grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr}.right>.panel{min-height:290px}}
@media(max-width:750px){.layout{display:flex;flex-direction:column;height:auto;min-height:0}.column{display:contents}.panel{min-height:240px}.map-panel{min-height:520px}#map-wrap{min-height:390px}.right{display:contents}.header-state{margin-left:0}}
</style>
</head>
<body>
<header>
<div class="logo"><small>AERONEXUS ADVANCED</small>Operations Center</div>
<nav class="tabs" aria-label="Projektbereiche">
<span class="active">FlightHub 2 Übersicht</span>
<a href="/studio">Mission Studio ↗</a>
<a href="/status">Live-Status ↗</a>
<a href="/media">DJI Medien ↗</a>
<a href="/thermal">Thermografie ↗</a>
<a href="/multispectral">Multispektral ↗</a>
</nav>
<span class="header-state" id="connection" role="status" aria-live="polite">Lade lokalen FlightHub-Status…</span>
</header>
<div class="layout">
<div class="column">
<section class="panel" id="project-panel">
<div class="eyebrow">DJI-Projektübersicht</div><h2>FlightHub-Projekte</h2>
<p class="sub">Projektkarte und Geräteliste aus der lokalen AeroNexus-API; keine direkte Verbindung des Browsers zur DJI Cloud.</p>
<select id="project-filter" aria-label="FlightHub-Projekt wählen"><option value="">Alle Projekte</option></select>
<div class="kpi-grid">
<div class="kpi"><span>Online & aktuell</span><strong id="count-online">–</strong></div>
<div class="kpi"><span>Fluggeräte</span><strong id="count-drones">–</strong></div>
<div class="kpi"><span>Routen</span><strong id="count-routes">–</strong></div>
<div class="kpi"><span>3D-Modelle</span><strong id="count-models">–</strong></div>
</div>
<div class="sub" id="project-sync">Synchronisierung läuft…</div>
<div class="list-card" id="cloud-api-panel">
<div class="eyebrow">DJI Cloud API 2</div>
<div class="row between"><b>Zusätzlicher SDK-Datenkanal</b><span id="cloud-api-state" class="badge">Nicht konfiguriert</span></div>
<div id="cloud-api-detail" class="sub">Schreibgeschützte Anbindung über eine separate Cloud-API-2-Serverinstanz. Keine direkte DJI-Cloud-Verbindung im Browser.</div>
</div>
<div class="list-card osd-live-card" id="cloud-osd-panel">
<div class="eyebrow">DJI Cloud API · MQTT</div>
<div class="row between"><b>OSD-Liveempfang (nur lesen)</b><span id="osd-feed-state" class="badge" role="status">Prüfe…</span></div>
<div id="osd-feed-detail" class="sub">Lokaler Telemetrieempfänger wird geprüft.</div>
</div>
<h3>Geräte im Projekt</h3><div class="scroll grow" id="project-devices"><div class="note">Lade Geräte…</div></div>
</section>
</div>
<div class="column">
<section class="panel map-panel grow">
<div class="row between">
<div><div class="eyebrow">Projektkarte</div><h2>Fluggeräte und Flugspuren</h2></div>
<button id="refresh-now" type="button">Aktualisieren</button>
</div>
<div id="map-wrap">
<div id="operations-map" aria-label="Interaktive Projektkarte" role="application"></div>
<div class="map-controls">
<select id="tile-choice" aria-label="Kartenstil"><option value="satellite">Satellit (Esri)</option><option value="street">Straße (OSM)</option></select>
<button id="map-forst">76694 Forst</button>
<button id="map-fit-data">Daten einpassen</button>
<button id="map-clear">Overlays entfernen</button>
</div>
<div class="map-note">Satellitenkarte © Esri / Straßenkarte © OpenStreetMap-Mitwirkende. Der Kartenanbieter sieht den sichtbaren Kartenausschnitt, keine DJI-Zugangsdaten.</div>
</div>
<div class="row legend">
<span class="badge good">● Aktuelle Flugposition</span>
<span class="badge warn">● Lokale Mission</span>
<span class="badge">● Historische Flugspur</span>
</div>
<div id="map-message" class="sub" role="status">Karte startet über 76694 Forst (Baden).</div>
</section>
<section class="panel" style="max-height:34%">
<div class="eyebrow">Routenverwaltung</div><h2>Gespeicherte Missionen (nur lokal)</h2>
<p class="sub">Vorschau der im Mission Studio erstellten WPML-Missionen; keine Übertragung an DJI.</p>
<div class="scroll grow" id="saved-missions"><div class="note">Lade gespeicherte Missionen…</div></div>
</section>
</div>
<div class="column right">
<section class="panel grow">
<div class="eyebrow">DJI-Cockpit (nur lesen)</div>
<h2 id="cockpit-name">Keine Drohne ausgewählt</h2>
<label class="sub" for="cockpit-select">Gerät auswählen</label>
<select id="cockpit-select" class="select-wide" aria-label="Cockpit-Fluggerät wählen"><option value="">Keine Fluggeräte</option></select>
<div class="row cockpit-status-row">
<span id="cockpit-connection" class="badge">Verbindung unbekannt</span>
<span id="cockpit-freshness" class="badge">Daten unbekannt</span>
<span id="cockpit-received" class="sub">Empfangszeit ausstehend</span>
</div>
<div id="cockpit-summary" class="cockpit-summary" aria-label="Wichtigste Fluggerätedaten"></div>
<div id="controller-status" class="controller-status" aria-label="Status der Fernsteuerungen"></div>
<div id="cockpit-content" class="scroll grow"><div class="note">Die Cockpitwerte werden lokal geladen…</div></div>
</section>
<section class="panel grow">
<div class="eyebrow">Flugspur- und Bibliotheksansicht</div><h2>FlightHub-Bibliothek</h2>
<div id="catalog-info" class="sub">Katalog wird geladen…</div>
<div class="scroll library-scroll" id="catalog-items"></div>
<h3>Flugaufträge und Tracks</h3>
<div class="task-filter" role="group" aria-label="Flugaufträge filtern">
<button id="tasks-in-progress" type="button" class="active">Aktiv / Offen</button>
<button id="tasks-finished" type="button">Abgeschlossen</button>
<button id="tasks-all" type="button">Alle</button>
</div>
<div class="scroll tracks-scroll" id="flight-tracks"><div class="note">Lade Aufgaben…</div></div>
<div class="sub">Flugspuren nur bei tatsächlich vorhandenen FlightHub-Aufträgen; GeoJSON stammt aus dem vorhandenen schreibgeschützten lokalen Endpunkt.</div>
</section>
</div>
</div>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
"use strict";
const $=id=>document.getElementById(id);
const elem=(tag,className,text)=>{
  const el=document.createElement(tag);
  if(className)el.className=className;
  if(text!==undefined&&text!==null)el.textContent=String(text);
  return el;
};
const add=(parent,tag,css,text)=>{const result=elem(tag,css,text);parent.appendChild(result);return result;};
const home={lat:49.1533,lon:8.58417,zoom:15};
let map=null,tileLayer=null,mapLayers={},deviceLayer=null,routeLayer=null;
let devices=[],projects=[],missionList=[],currentProject="",currentDevice="",currentOverlay=null,taskFilter="progress";
let lastCockpitSignature=null;
let refreshing=false,refreshCount=0,stopped=false;
function message(id,text){$(id).textContent=text;}
function text(value,fallback="–"){return value===null||value===undefined||value===""?fallback:String(value)}
function finite(v){return typeof v==="number"&&Number.isFinite(v)}
function formatNumber(v,digits=1,unit=""){return finite(v)?v.toFixed(digits)+(unit?" "+unit:""):"–"}
function gps(t){
  if(!t||!finite(t.latitude)||!finite(t.longitude)||Math.abs(t.latitude)>90||
    Math.abs(t.longitude)>180||(t.latitude===0&&t.longitude===0))return null;
  return [t.latitude,t.longitude];
}
function currentDevices(){
  return devices.filter(d=>!currentProject||d.project_id===currentProject);
}
// Multiple providers can report one aircraft with the same serial number.
// The full identity prevents the FlightHub-only row from masking live MQTT.
function deviceKey(d){return JSON.stringify([d.provider,d.project_id,d.device_id]);}
function providerLabel(provider){
  return provider==="dji-cloud-api"?"DJI Cloud API MQTT":
    provider==="flighthub-public-v2"?"FlightHub EU":
    provider==="flighthub-onprem-v2"?"FlightHub On-Prem":
    provider==="dji-cloud-api-2"?"DJI Cloud API 2":"Andere Quelle";
}
function selectedDevices(){
  return currentDevices().filter(d=>d.kind==="aircraft").sort((a,b)=>
    Number(b.provider==="dji-cloud-api")-Number(a.provider==="dji-cloud-api"));
}
function selectedProjectCatalog(){
  return projects.filter(p=>!currentProject||p.project_id===currentProject);
}
function visibleCatalogCount(field){
  return selectedProjectCatalog().reduce((sum,p)=>sum+(Array.isArray(p[field])?p[field].length:0),0);
}
function initializeMap(){
  if(!window.L){message("map-message","Leaflet konnte nicht geladen werden. Kartenansicht nicht verfügbar.");return;}
  map=L.map("operations-map",{zoomControl:true,worldCopyJump:true}).setView([home.lat,home.lon],home.zoom);
  mapLayers.satellite=L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",{
    maxZoom:19,attribution:"Tiles &copy; Esri and data providers"
  });
  mapLayers.street=L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{
    maxZoom:19,referrerPolicy:"strict-origin-when-cross-origin",
    attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>'
  });
  tileLayer=mapLayers.satellite.addTo(map);
  deviceLayer=L.layerGroup().addTo(map);
  routeLayer=L.layerGroup().addTo(map);
  mapLayers.street.on("tileerror",()=>{
    if(tileLayer!==mapLayers.street)return;
    chooseTile("satellite");
    message("map-message","Straßenkarten-Kacheln nicht verfügbar. Satellitenkarte aktiviert.");
  });
  mapLayers.satellite.on("tileerror",()=>{
    if(tileLayer===mapLayers.satellite)
      message("map-message","Satellitenkacheln konnten nicht geladen werden. Browsernetzwerk prüfen.");
  });
}
function chooseTile(value){
  if(!map||!mapLayers[value])return;
  if(tileLayer)map.removeLayer(tileLayer);
  tileLayer=mapLayers[value].addTo(map);
  $("tile-choice").value=value;
}
function repaintDeviceLayer(){
  if(!deviceLayer||!map)return;
  deviceLayer.clearLayers();
  const available=[];
  for(const d of selectedDevices()){
    if(d.freshness!=="fresh"||d.online!==true)continue;
    const loc=gps(d.telemetry);
    if(!loc)continue;
    available.push(loc);
    const dot=L.circleMarker(loc,{radius:8,color:"#75e3bd",fillColor:"#33a88c",fillOpacity:.9,weight:3});
    dot.bindTooltip(elem("span","",(d.name||"Fluggerät")+" · aktuell"));
    dot.on("click",()=>{currentDevice=deviceKey(d);renderCockpit();});
    dot.addTo(deviceLayer);
  }
  return available;
}
function fitOverlay(){
  if(!map)return;
  const coords=[];
  deviceLayer?.eachLayer(layer=>{if(typeof layer.getLatLng==="function")coords.push(layer.getLatLng());});
  routeLayer?.eachLayer(layer=>{
    if(typeof layer.getLatLngs==="function"){
      for(const loc of layer.getLatLngs())if(loc&&Number.isFinite(loc.lat))coords.push(loc);
    }
  });
  if(!coords.length){map.setView([home.lat,home.lon],home.zoom);return;}
  if(coords.length===1){map.setView(coords[0],16);return;}
  map.fitBounds(L.latLngBounds(coords),{padding:[40,40],maxZoom:17});
}
function clearOverlays(){
  routeLayer?.clearLayers();currentOverlay=null;
  message("map-message","Zusätzliche Flugspuren entfernt. Karte weiterhin über 76694 Forst zentrierbar.");
}
function selectProject(projectId){
  currentProject=projectId;
  const candidates=selectedDevices();
  if(!candidates.some(d=>deviceKey(d)===currentDevice))currentDevice=candidates.length?deviceKey(candidates[0]):"";
  $("project-filter").value=projectId;
  repaintDeviceLayer();
  renderSummary();
  renderDevices();
  renderControllerStatus();
  renderCockpit();
  renderCatalog();
  renderTracks();
  clearOverlays();
}
function renderSummary(){
  const relevant=currentDevices();
  const aircraft=selectedDevices();
  // Count physical aircraft once even when FlightHub and MQTT both report it.
  message("count-online",new Set(aircraft.filter(d=>d.freshness==="fresh"&&d.online===true)
    .map(d=>d.device_id)).size);
  message("count-drones",new Set(aircraft.map(d=>d.device_id)).size);
  message("count-routes",visibleCatalogCount("waylines"));
  message("count-models",visibleCatalogCount("models"));
}
function renderProjects(){
  const dropdown=$("project-filter");dropdown.replaceChildren();
  const any=add(dropdown,"option","","Alle Projekte");any.value="";
  const grouped=new Map();
  for(const p of projects)grouped.set(p.project_id,p.name||p.project_id);
  for(const d of devices)if(!grouped.has(d.project_id))grouped.set(d.project_id,d.project_id);
  for(const [id,name] of Array.from(grouped.entries()).sort((a,b)=>a[1].localeCompare(b[1]))){
    const option=add(dropdown,"option","",name);option.value=id;
  }
  if(currentProject&&!grouped.has(currentProject))currentProject="";
  dropdown.value=currentProject;
}
function renderDevices(){
  const body=$("project-devices");body.replaceChildren();
  const relevant=currentDevices();
  if(!relevant.length){add(body,"div","note","Für dieses Projekt werden noch keine Fluggeräte übermittelt.");return;}
  for(const d of relevant){
    if(d.kind!=="aircraft"&&d.kind!=="controller")continue;
    const selectable=d.kind==="aircraft";
    const card=add(body,"div","list-card"+(selectable?" clickable":"")+
      (selectable&&deviceKey(d)===currentDevice?" active":""));
    add(card,"b","",d.name||"Unbenanntes Gerät");
    add(card,"small","",d.kind==="aircraft"?"Drohne":"Fernsteuerung");
    add(card,"small","",providerLabel(d.provider));
    const state=d.freshness==="fresh"?(d.online===true?"Online":"Offline"):"Nicht aktuell";
    add(card,"span","badge "+(state==="Online"?"good":"warn"),state);
    if(selectable)card.addEventListener("click",()=>{
      currentDevice=deviceKey(d);renderCockpit();renderDevices();
    });
  }
}
function renderControllerStatus(){
  const body=$("controller-status");body.replaceChildren();
  const controllers=currentDevices().filter(d=>d.kind==="controller");
  if(!controllers.length)return;
  for(const d of controllers.slice(0,4)){
    const t=d.telemetry||{};
    const card=add(body,"div","controller-card");
    add(card,"b","",(d.name||"Fernsteuerung")+" · "+providerLabel(d.provider));
    const battery=finite(t.battery_percent)&&t.battery_percent>=0&&t.battery_percent<=100?
      formatNumber(t.battery_percent,0,"%"):"Nicht übermittelt";
    const age=finite(d.age_seconds)&&d.age_seconds>=0?
      " · vor "+Math.floor(d.age_seconds)+" s empfangen":"";
    const connection=connectionStatus(d)[0];
    add(card,"span","",connection+" · Akku "+battery+age);
  }
  if(controllers.length>4)
    add(body,"div","sub",(controllers.length-4)+" weitere Fernsteuerungen");
}
function renderOsdPanel(summary){
  const feed=summary?.live_feed||{};
  const state=feed.state||"unknown";
  const accepted=Number.isSafeInteger(feed.accepted)&&feed.accepted>=0?feed.accepted:null;
  const rejected=Number.isSafeInteger(feed.rejected)&&feed.rejected>=0?feed.rejected:null;
  const parsed=typeof feed.last_message_at==="string"?Date.parse(feed.last_message_at):NaN;
  const age=Number.isFinite(parsed)?Math.floor((Date.now()-parsed)/1000):null;
  const recent=state==="subscribed"&&accepted>0&&age!==null&&age>=0&&age<=60;
  const labels={
    disabled:"Deaktiviert",connecting:"Verbindet",connected:"Verbunden",
    subscribed:"Abonniert · wartet",auth_failed:"Anmeldung fehlgeschlagen",
    subscription_denied:"Abonnement verweigert",unreachable:"Broker nicht erreichbar",
    disconnected:"Getrennt",stopped:"Gestoppt"
  };
  const label=recent?"OSD-Empfang aktiv":labels[state]||"Status unbekannt";
  message("osd-feed-state",label);
  $("osd-feed-state").className="badge "+(recent?"good":
    state==="subscribed"||state==="connecting"?"warn":"bad");
  let detail="Schreibgeschützter MQTT-Kanal · ";
  detail+=accepted===null?"Noch keine Empfangszähler":
    accepted+" gültige OSD-Nachrichten seit Dienststart";
  if(rejected!==null)detail+=" · "+rejected+" abgewiesen";
  if(age!==null&&age>=0)detail+=" · letzter Empfang vor "+age+" s";
  if(state==="subscribed"&&!recent)
    detail+=" · derzeit kein neuer Telemetrieempfang bestätigt";
  message("osd-feed-detail",detail);
}
function metric(parent,title,value){
  const box=add(parent,"div","");
  add(box,"span","",title);
  add(box,"b","",value);
  return box;
}
function rtkLabel(raw){
  const officialObserved={
    "is_fixed:not_started":"RTK nicht gestartet",
    "is_fixed:0":"Kein bestätigter RTK-Fix",
    "is_fixed:fixing":"RTK-Fix läuft",
    "is_fixed:fixing_successful":"RTK-Fix erfolgreich",
    "is_fixed:fixing_failed":"RTK-Fix fehlgeschlagen",
    "is_fixed:0":"Kein bestätigter RTK-Fix (DJI-Code 0)"
  };
  // This map is deliberately limited to strings already handled in /status.
  // Unknown raw values stay accessible only in the technical section.
  return typeof raw==="string"?(officialObserved[raw]||"RTK-Status unbekannt"):"Nicht übermittelt";
}
function modeLabel(t){
  const modes={0:"Standby",1:"Startvorbereitung",2:"Startbereit",3:"Manueller Flug",
    4:"Automatischer Start",5:"Routenflug",9:"Rückkehr (RTH)",10:"Automatische Landung"};
  return typeof t.flight_mode_label==="string"&&t.flight_mode_label.trim()?
    t.flight_mode_label.trim():
    t.flight_mode_code==null?"–":(modes[t.flight_mode_code]||"DJI-Code "+t.flight_mode_code);
}
function connectionStatus(device){
  if(device.online===true)
    return device.freshness==="fresh"?["Online","good"]:["Zuletzt online","warn"];
  if(device.online===false)
    return device.freshness==="fresh"?["Offline","bad"]:["Zuletzt offline","warn"];
  return ["Verbindung unbekannt","warn"];
}
function freshnessStatus(device){
  const labels={
    fresh:"Daten aktuell",stale:"Daten veraltet",missing:"Keine Telemetrie",
    unknown_age:"Alter unbekannt",clock_skew:"Zeitabweichung"
  };
  return [labels[device.freshness]||"Status unbekannt",
    device.freshness==="fresh"?"good":"warn"];
}
function hero(parent,label,value,extra=""){
  const box=add(parent,"div","hero-value"+(extra?" "+extra:""));
  add(box,"span","hero-label",label);
  add(box,"strong","",value);
  return box;
}
function renderCockpit(){
  const options=$("cockpit-select");options.replaceChildren();
  const available=selectedDevices();
  if(!available.some(d=>deviceKey(d)===currentDevice))
    currentDevice=available.length?deviceKey(available[0]):"";
  for(const d of available){
    const option=add(options,"option","",
      (d.name||"Fluggerät")+" · "+providerLabel(d.provider));
    option.value=deviceKey(d);
  }
  options.value=currentDevice;
  const summary=$("cockpit-summary");
  const body=$("cockpit-content");
  const d=available.find(x=>deviceKey(x)===currentDevice);
  if(!d){
    lastCockpitSignature=null;
    summary.replaceChildren();body.replaceChildren();
    message("cockpit-name","Kein Fluggerät ausgewählt");
    message("cockpit-connection","Verbindung unbekannt");
    message("cockpit-freshness","Keine Daten");
    message("cockpit-received","Kein Datenempfang");
    add(body,"div","note","Kein Fluggerät vom gewählten FlightHub-Projekt empfangen.");
    return;
  }
  message("cockpit-name",d.name||"Unbenanntes Fluggerät");
  const [connection,connectionTone]=connectionStatus(d);
  const [freshness,freshnessTone]=freshnessStatus(d);
  message("cockpit-connection",connection);
  $("cockpit-connection").className="badge "+connectionTone;
  message("cockpit-freshness",freshness);
  $("cockpit-freshness").className="badge "+freshnessTone;
  message("cockpit-received",finite(d.age_seconds)&&d.age_seconds>=0?
    "Vor "+Math.floor(d.age_seconds)+" s empfangen":"Empfangsalter unbekannt");
  const t=d.telemetry||{};
  // Updating "received age" must not tear down a scrolling/open details
  // panel every 15 seconds if all underlying device readings are unchanged.
  const cockpitSignature=JSON.stringify([
    d.device_id,d.project_id,d.provider,d.name,d.online,d.freshness,t,d.health
  ]);
  if(cockpitSignature===lastCockpitSignature)return;
  const detailsWasOpen=body.querySelector("#cockpit-technical")?.open===true;
  const oldScroll=body.scrollTop;
  summary.replaceChildren();body.replaceChildren();
  lastCockpitSignature=cockpitSignature;
  const isCurrent=d.freshness==="fresh"&&d.online===true;
  const labelSuffix=isCurrent?" (letzter Messwert)":" (gespeichert)";
  const battery=finite(t.battery_percent)&&t.battery_percent>=0&&t.battery_percent<=100?
    t.battery_percent:null;
  const batteryCard=hero(summary,"Akku"+labelSuffix,
    battery===null?"–":formatNumber(battery,0,"%"),"battery");
  if(battery!==null){
    const level=add(batteryCard,"progress","progress"+(battery<=30?" low":""));
    level.max=100;level.value=battery;
    level.setAttribute("aria-label","Akkustand "+Math.round(battery)+" Prozent (AeroNexus-Anzeige)");
  }
  hero(summary,"Flugmodus",modeLabel(t));
  hero(summary,"DJI elevation (Bezug ungeprüft)",formatNumber(t.elevation_m,1,"m"));
  hero(summary,"Geschwindigkeit horizontal",formatNumber(t.horizontal_speed_mps,1,"m/s"));
  hero(summary,"RTK-Status",rtkLabel(t.rtk_state));
  const position=gps(t);
  const gnss=add(body,"div","gnss-note"+(!position?" warn":""));
  add(gnss,"b","","GNSS / RTK · "+(position?"Koordinaten vorhanden":"Keine gültige GPS-Position"));
  add(gnss,"div","sub","GPS-Satelliten: "+text(t.gps_satellites)+
    " · RTK-Satelliten: "+text(t.rtk_satellites)+
    " · "+rtkLabel(t.rtk_state));
  if(!position)
    add(gnss,"div","sub","Indoor oder ohne Positionsfix möglich; keine Position auf der Karte.");
  add(body,"div","cockpit-info","Quelle: "+providerLabel(d.provider)+
    " · Höhendefinition und Höhenbezug der DJI-Rohwerte sind nicht verifiziert.");
  if(!isCurrent){
    add(body,"div","cockpit-info critical",
      "Keine bestätigte Live-Verbindung. Die folgenden Werte sind nur zuletzt übermittelte Messwerte.");
  }else{
    add(body,"div","cockpit-info",
      "Gerät online, Statusdaten aktuell. Messwerte sind die zuletzt von DJI gemeldeten Werte.");
  }
  const warnings=Array.isArray(d.health)?d.health:[];
  if(warnings.length){
    add(body,"div","cockpit-section-title","HMS · "+warnings.length+" zuletzt gemeldete Hinweise");
    for(const alert of warnings.slice(0,6)){
      const warning=add(body,"div","cockpit-alert");
      add(warning,"b","",alert.level==="warning"?"Warnung":
        alert.level==="reminder"?"Hinweis":"Meldung");
      add(warning,"div","",alert.message&&alert.message!==alert.code?
        alert.message:"Code: "+text(alert.code));
    }
    add(body,"div","cockpit-secondary-note",
      "HMS-Meldungen besitzen hier keine gesonderte garantierte Ereigniszeit.");
  }
  const technical=add(body,"details","cockpit-technical");
  technical.id="cockpit-technical";
  technical.open=detailsWasOpen;
  add(technical,"summary","","Technische Details und Flugstatistik");
  const grid=add(technical,"div","cockpit");
  metric(grid,"DJI height (Bezug ungeprüft)",formatNumber(t.height_m,1,"m"));
  metric(grid,"DJI elevation (Rohwert)",formatNumber(t.elevation_m,1,"m"));
  metric(grid,"Flugmodus (DJI-Code)",text(t.flight_mode_code));
  metric(grid,"GPS-Position",position?
    formatNumber(position[0],6,"°")+" / "+formatNumber(position[1],6,"°"):"Nicht übermittelt");
  metric(grid,"Geschwindigkeit vertikal",formatNumber(t.vertical_speed_mps,1,"m/s"));
  if(finite(t.speed_mps))
    metric(grid,"Geschwindigkeit (SDK)",formatNumber(t.speed_mps,1,"m/s"));
  metric(grid,"Distanz zum Homepoint",formatNumber(t.home_distance_m,0,"m"));
  metric(grid,"GPS-Satelliten (DJI)",text(t.gps_satellites));
  metric(grid,"RTK-Satelliten (DJI)",text(t.rtk_satellites));
  const rawRtk=metric(grid,"RTK-Status (Rohwert)",text(t.rtk_state));
  rawRtk.className+=" cockpit-raw";
  metric(grid,"Akkuspannung",finite(t.battery_voltage_mv)?
    formatNumber(t.battery_voltage_mv/1000,2,"V"):"–");
  metric(grid,"Akkutemperatur",formatNumber(t.battery_temperature_c,1,"°C"));
  metric(grid,"Flugzeit gesamt (API)",finite(t.total_flight_time_s)?
    formatNumber(t.total_flight_time_s/3600,1,"h"):"–");
  metric(grid,"Flugstarts gesamt (API)",text(t.total_flight_sorties));
  add(technical,"div","cockpit-secondary-note",
    "Flugzeit und Flugstarts sind die von DJI zuletzt gelieferten API-Werte. " +
    "0 bedeutet nicht zwingend, dass das Fluggerät nie geflogen ist. " +
    "Satellitenanzahlen sind gemeldete Werte und keine Bestätigung eines GPS-/RTK-Fixes.");
  body.scrollTop=oldScroll;
}
function renderCatalog(){
  const body=$("catalog-items");body.replaceChildren();
  const relevant=selectedProjectCatalog();
  if(!relevant.length){add(body,"div","note","Noch kein FlightHub-Katalog verfügbar.");return;}
  for(const project of relevant){
    const heading=add(body,"div","list-head");add(heading,"b","",project.name||project.project_id);
    for(const [type,label] of [["waylines","Flugrouten"],["models","3D-/2D-Modelle"]]){
      const entries=project[type];
      if(entries===null){add(body,"div","sub",label+": nicht abrufbar");continue;}
      for(const entry of (entries||[]).slice(0,30)){
        const item=add(body,"div","list-card");
        add(item,"b","",entry.name||"Ohne Titel");
        add(item,"small","",label+" · "+(type==="waylines"?(entry.template_types||[]).join(", "):text(entry.file_type)));
      }
    }
  }
}
// Status groups follow the display logic in DJI's public V2 demo, but
// these values are normalized from our actual FlightHub PUBLIC task API.
// Never present an unknown state as a successful or live-running task.
const taskStates={
  waiting:["Ausstehend","pending","progress"],
  preparing:["Vorbereitung","pending","progress"],
  executing:["In Ausführung","active","progress"],
  paused:["Pausiert","pending","progress"],
  suspended:["Ausgesetzt","pending","progress"],
  success:["Erfolgreich","complete","finished"],
  partially_done:["Teilweise abgeschlossen","failed","finished"],
  terminated:["Abgebrochen","failed","finished"],
  starting_failure:["Start fehlgeschlagen","failed","finished"],
  timeout:["Zeitüberschreitung","failed","finished"]
};
function taskState(status){
  return Object.hasOwn(taskStates,status)?taskStates[status]:
    ["Unbekannter Status","pending","unknown"];
}
function taskDate(t){
  const raw=t.run_at||t.begin_at||t.completed_at;
  if(!raw||typeof raw!=="string")return "Zeit unbekannt";
  const date=new Date(raw);
  if(!Number.isFinite(date.getTime()))return "Zeit unbekannt";
  return date.toLocaleDateString("de-DE",{day:"2-digit",month:"2-digit",year:"numeric"});
}
function renderTracks(){
  const body=$("flight-tracks");body.replaceChildren();
  const tabs={
    progress:$("tasks-in-progress"),finished:$("tasks-finished"),all:$("tasks-all")
  };
  for(const [kind,button] of Object.entries(tabs)){
    button.classList.toggle("active",taskFilter===kind);
    button.setAttribute("aria-pressed",String(taskFilter===kind));
  }
  const selected=[];
  let unavailable=false;
  for(const project of selectedProjectCatalog()){
    if(project.tasks===null||project.tasks===undefined){unavailable=true;continue;}
    for(const task of project.tasks||[]){
      const state=taskState(task.status);
      if(taskFilter!=="all"&&state[2]!==taskFilter)continue;
      selected.push({project,task,state});
    }
  }
  selected.sort((a,b)=>
    String(b.task.run_at||b.task.begin_at||"").localeCompare(
      String(a.task.run_at||a.task.begin_at||"")));
  let currentDay="";
  for(const {project,task,state} of selected.slice(0,150)){
    const day=taskDate(task);
    if(day!==currentDay){add(body,"div","task-day",day);currentDay=day;}
    const card=add(body,"div","list-card");
    add(card,"b","",task.name||"Unbenannter Flugauftrag");
    add(card,"span","task-state "+state[1],state[0]);
    add(card,"small","",text(project.name||project.project_id)+" · "+text(task.task_type)+
      " · "+text(task.run_at||task.begin_at,"Zeit unbekannt"));
    if(typeof task.current_waypoint_index==="number"&&
      typeof task.total_waypoints==="number"&&task.total_waypoints>0)
      add(card,"div","task-progress","Wegpunktfortschritt laut DJI: "+
        task.current_waypoint_index+" / "+task.total_waypoints);
    if(task.exceptions>0)
      add(card,"div","critical","DJI meldet "+task.exceptions+" Ausnahme(n).");
    if(task.media_upload_status)
      add(card,"div","sub","Medienübertragung laut DJI: "+task.media_upload_status);
    if(task.uuid){
      const mediaButton=add(card,"button","","Medienliste anzeigen");
      mediaButton.type="button";
      const mediaBody=add(card,"div","sub","");
      mediaButton.addEventListener("click",async()=>{
        mediaButton.disabled=true;
        mediaBody.replaceChildren();
        add(mediaBody,"div","sub","DJI-Dateimetadaten werden geladen…");
        try{
          await viewTaskMedia(project.project_id,task.uuid,mediaBody);
        }catch(err){
          mediaBody.replaceChildren();
          add(mediaBody,"div","critical","Medienliste nicht verfügbar: "+err.message);
        }finally{
          mediaButton.disabled=false;
        }
      });
      const btn=add(card,"button","","Historische Flugspur auf Karte");
      btn.type="button";
      btn.addEventListener("click",()=>viewTrack(project.project_id,task).catch(err=>
        message("map-message","Flugspur nicht verfügbar: "+err.message)));
    }
  }
  if(!selected.length){
    add(body,"div","note",unavailable?
      "Keine passenden Aufgaben im verfügbaren Katalog. Mindestens ein Projekt ist derzeit nicht abrufbar.":
      "Keine passenden Flugaufträge im abgefragten Zeitraum (in der Regel 30 Tage).");
  }
  if(selected.length>150)add(body,"div","sub","Anzeige auf 150 Flugaufträge begrenzt.");
}
async function getJSON(path){
  const response=await fetch(path,{cache:"no-store"});
  if(!response.ok)throw new Error("HTTP "+response.status);
  return response.json();
}
async function viewTaskMedia(projectId,taskUuid,container){
  const path="/api/v1/flighthub/projects/"+encodeURIComponent(projectId)+
    "/tasks/"+encodeURIComponent(taskUuid)+"/media";
  const result=await getJSON(path);
  container.replaceChildren();
  if(!Array.isArray(result.media)||!result.media.length){
    add(container,"div","sub","DJI meldet keine Medien zu diesem Auftrag.");
    return;
  }
  add(container,"div","sub","Medienmetadaten · "+result.media.length+
    " Dateien. Keine Download- oder Vorschau-URLs freigegeben.");
  for(const file of result.media.slice(0,200)){
    const box=add(container,"div","list-card");
    add(box,"b","",file.name||"Unbenannte DJI-Datei");
    const size=typeof file.size_bytes==="number"?
      (file.size_bytes/1024/1024).toFixed(1)+" MiB":"Größe unbekannt";
    add(box,"small","",text(file.file_type,"Dateityp unbekannt")+" · "+
      size+" · "+text(file.created_at,"Zeit unbekannt"));
  }
}
async function viewTrack(projectId,task){
  // Backend restricts this read-only request to cached tasks in the local
  // FlightHub catalog, preventing arbitrary provider ID enumeration.
  const url="/api/v1/flighthub/projects/"+encodeURIComponent(projectId)+
    "/tasks/"+encodeURIComponent(task.uuid)+"/track";
  const feature=await getJSON(url);
  const coords=feature?.geometry?.coordinates;
  if(feature?.geometry?.type!=="LineString"||!Array.isArray(coords))
    throw new Error("Keine gültige GeoJSON-Linie");
  const locations=coords.slice(0,20000).filter(p=>Array.isArray(p)&&p.length>=2&&
    finite(p[0])&&finite(p[1])&&Math.abs(p[0])<=180&&Math.abs(p[1])<=90&&
    (p[0]!==0||p[1]!==0)).map(p=>[p[1],p[0]]);
  if(locations.length<2){message("map-message","Keine Flugspurkoordinaten im ausgewählten Auftrag.");return;}
  if(!map||!routeLayer)return;
  routeLayer.clearLayers();currentOverlay="track";
  const line=L.polyline(locations,{color:"#d6a4ff",weight:4,opacity:1}).addTo(routeLayer);
  map.fitBounds(line.getBounds(),{padding:[45,45],maxZoom:17});
  message("map-message","Historische Flugspur: "+text(task.name)+" · "+locations.length+" GPS-Punkte (keine geplante Mission).");
}
async function viewMission(id){
  const record=await getJSON("/api/v1/studio/missions/"+encodeURIComponent(id));
  const mission=record.mission||{};
  const coords=(mission.waypoints||[]).map(w=>[w.latitude,w.longitude])
    .filter(p=>finite(p[0])&&finite(p[1])&&Math.abs(p[0])<=90&&Math.abs(p[1])<=180&&
      (p[0]!==0||p[1]!==0)).slice(0,500);
  if(coords.length<2){message("map-message","Für die Mission sind noch nicht genügend Wegpunkte vorhanden.");return;}
  if(mission.close_route&&coords.length>=3&&
    (coords[0][0]!==coords[coords.length-1][0]||coords[0][1]!==coords[coords.length-1][1])){
    coords.push(coords[0]);
  }
  if(!map||!routeLayer)return;
  routeLayer.clearLayers();currentOverlay="mission";
  const polyline=L.polyline(coords,{color:"#ffc86c",weight:4,opacity:1}).addTo(routeLayer);
  map.fitBounds(polyline.getBounds(),{padding:[45,45],maxZoom:17});
  message("map-message","Lokaler Missionsentwurf: "+text(mission.name)+
    " · "+coords.length+" dargestellte Wegpunkte · noch keine DJI-Flugmission hochgeladen.");
}
function renderSavedMissions(){
  const body=$("saved-missions");body.replaceChildren();
  if(!missionList.length){add(body,"div","note","Noch keine lokalen Missionen. Im Mission Studio kannst du eine erstellen.");return;}
  for(const mission of missionList.slice(0,50)){
    const card=add(body,"div","list-card");
    add(card,"b","",mission.name||"Entwurf");
    add(card,"small","",text(mission.drone_model)+" · "+text(mission.waypoints)+" editierbare Wegpunkte");
    const btn=add(card,"button","","Route auf Karte");
    btn.type="button";
    btn.addEventListener("click",()=>viewMission(mission.id).catch(err=>
      message("map-message","Mission konnte nicht angezeigt werden: "+err.message)));
  }
}
function receiveUpdatedAt(summary){
  const at=summary?.last_refresh_success_at;
  if(!at)return "Letzter erfolgreicher FlightHub-Abruf noch unbekannt";
  const timestamp=Date.parse(at);
  if(!Number.isFinite(timestamp))return "Synchronisierungszeit unbekannt";
  return "Letzter erfolgreicher FlightHub-Abruf: "+
    new Date(timestamp).toLocaleTimeString("de-DE")+" (Serverzeit empfangen)";
}
async function refreshAll(){
  if(refreshing||stopped)return;
  refreshing=true;
  const generation=++refreshCount;
  try{
    // Keep cockpit usable even if FlightHub catalog or local workspace fails.
    // Reading is local only; the browser never queries DJI directly.
    const [fleetResult,libraryResult,localResult,summaryResult,api2Result]=await Promise.allSettled([
      getJSON("/api/v1/status/devices?limit=200"),
      getJSON("/api/v1/flighthub/catalog"),
      getJSON("/api/v1/studio/missions"),
      getJSON("/api/v1/status/summary"),
      getJSON("/api/v1/cloudapi2/devices")
    ]);
    if(generation!==refreshCount||stopped)return;
    const errors=[];
    if(fleetResult.status==="fulfilled"){
      const fleet=fleetResult.value;
      devices=Array.isArray(fleet.devices)?fleet.devices:[];
      if(fleet.total>devices.length)errors.push(
        "Geräteliste auf 200 Einträge begrenzt");
    }else{errors.push("Gerätedaten nicht verfügbar");}
    if(libraryResult.status==="fulfilled"){
      const library=libraryResult.value;
      projects=Array.isArray(library.projects)?library.projects:[];
      message("catalog-info","Stand: "+text(library.updated_at)+" · lokaler schreibgeschützter Cache");
    }else{
      errors.push("FlightHub-Bibliothek nicht verfügbar");
      message("catalog-info","FlightHub-Katalog derzeit nicht erreichbar.");
    }
    if(localResult.status==="fulfilled"){
      const local=localResult.value;
      missionList=Array.isArray(local.missions)?local.missions:[];
    }else{errors.push("Lokale Missionsablage nicht verfügbar");}
    if(api2Result.status==="fulfilled"){
      const api2=api2Result.value;
      const states={disabled:"Deaktiviert",waiting:"Wartet",ok:"Verbunden",unavailable:"Nicht erreichbar"};
      message("cloud-api-state",states[api2.state]||"Unbekannt");
      $("cloud-api-state").className="badge "+
        (api2.state==="ok"?"good":api2.state==="disabled"?"":"warn");
      message("cloud-api-detail",api2.state==="disabled"?
        "Der separate Cloud-API-2-SDK-Server ist nicht konfiguriert. FlightHub 2 läuft unabhängig weiter.":
        api2.state==="ok"?
        "Quelle: DJI Cloud API 2 SDK-BFF · "+Number(api2.total||0)+" Fluggeräte · keine Dock-Daten.":
        "SDK-Backend aktuell nicht erreichbar oder Authentifizierung fehlgeschlagen. Keine Flugdaten vorgetäuscht.");
      if(api2.state==="ok"&&Array.isArray(api2.devices)){
        // Separate providers share an aircraft serial; do not hide a second
        // source as a phantom new aircraft. FlightHub remains authoritative
        // if the same SN is already present, otherwise show the SDK source.
        const existingIds=new Set(devices.filter(d=>d.kind==="aircraft").map(d=>d.device_id));
        for(const drone of api2.devices.slice(0,50)){
          if(drone.kind==="aircraft"&&!existingIds.has(drone.device_id)){
            devices.push(drone);existingIds.add(drone.device_id);
          }
        }
      }
    }else{
      message("cloud-api-state","Nicht erreichbar");
      $("cloud-api-state").className="badge warn";
      message("cloud-api-detail","Cloud-API-2-Schnittstelle nicht verfügbar; FlightHub läuft unabhängig weiter.");
    }
    const before=currentProject;
    renderProjects();
    if(before&&!projects.some(p=>p.project_id===before)&&!devices.some(d=>d.project_id===before))
      currentProject="";
    renderSummary();renderDevices();renderControllerStatus();renderCockpit();renderCatalog();renderTracks();
    renderSavedMissions();repaintDeviceLayer();
    renderOsdPanel(summaryResult.status==="fulfilled"?summaryResult.value:null);
    message("project-sync",summaryResult.status==="fulfilled"?
      summaryResult.value?.polling==="disabled"?
        "FlightHub-Polling deaktiviert · DJI MQTT funktioniert unabhängig":
        receiveUpdatedAt(summaryResult.value):"Synchronisierungsstatus nicht verfügbar");
    if(summaryResult.status!=="fulfilled")errors.push("Statusübersicht nicht verfügbar");
    message("connection",errors.length?
      "Teilweise verfügbar · "+errors.join(" · "):
      "LAN-Verbindung aktiv · "+new Date().toLocaleTimeString("de-DE"));
  }catch(err){
    message("connection","Darstellungsfehler: "+err.message);
  }finally{refreshing=false;}
}
function wire(){
  $("refresh-now").addEventListener("click",refreshAll);
  const taskTabs=[["tasks-in-progress","progress"],["tasks-finished","finished"],["tasks-all","all"]];
  for(const [id,value] of taskTabs){
    $(id).addEventListener("click",()=>{taskFilter=value;renderTracks();});
  }
  $("project-filter").addEventListener("change",event=>selectProject(event.target.value));
  $("cockpit-select").addEventListener("change",event=>{
    currentDevice=event.target.value;renderCockpit();renderDevices();
  });
  $("tile-choice").addEventListener("change",event=>chooseTile(event.target.value));
  $("map-forst").addEventListener("click",()=>map?.setView([home.lat,home.lon],home.zoom));
  $("map-fit-data").addEventListener("click",fitOverlay);
  $("map-clear").addEventListener("click",clearOverlays);
  initializeMap();
  refreshAll();
  window.setInterval(refreshAll,15000);
  window.addEventListener("pagehide",()=>{stopped=true;});
}
wire();
</script>
</body>
</html>"""


def render_operations() -> str:
    """Render only the empty static shell; no DJI identifiers or tokens."""
    return HTML
