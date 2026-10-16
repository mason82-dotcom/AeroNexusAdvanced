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
.progress{width:100%;height:12px;accent-color:#6bd7a8;margin:6px 0}
.progress.low{accent-color:#e5a776}
.select-wide{width:100%;min-width:0}
.cockpit-alert{border-top:1px solid #35516f;padding:8px 0;font-size:12px;overflow-wrap:anywhere}
.cockpit-alert b{color:#ffe0aa}
.list-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:6px 0}
.library-scroll{max-height:310px;min-height:125px}
.tracks-scroll{min-height:125px;flex:1}
.tracks-scroll button,.library-scroll button{font-size:12px;padding:5px 8px}
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
<div class="row" style="margin:10px 0"><span id="cockpit-freshness" class="badge">Unbekannt</span><span id="cockpit-received" class="sub">Empfangszeit ausstehend</span></div>
<div id="cockpit-content" class="scroll grow"><div class="note">Die Cockpitwerte werden lokal geladen…</div></div>
</section>
<section class="panel grow">
<div class="eyebrow">Flugspur- und Bibliotheksansicht</div><h2>FlightHub-Bibliothek</h2>
<div id="catalog-info" class="sub">Katalog wird geladen…</div>
<div class="scroll library-scroll" id="catalog-items"></div>
<h3>Flugaufträge und Tracks</h3>
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
let devices=[],projects=[],missionList=[],currentProject="",currentDevice="",currentOverlay=null;
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
function selectedDevices(){return currentDevices().filter(d=>d.kind==="aircraft")}
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
    dot.bindTooltip((d.name||"Fluggerät")+" · aktuell");
    dot.on("click",()=>{currentDevice=d.device_id;renderCockpit();});
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
  if(!candidates.some(d=>d.device_id===currentDevice))currentDevice=candidates[0]?.device_id||"";
  $("project-filter").value=projectId;
  repaintDeviceLayer();
  renderSummary();
  renderDevices();
  renderCockpit();
  renderCatalog();
  renderTracks();
  clearOverlays();
}
function renderSummary(){
  const relevant=currentDevices();
  const aircraft=selectedDevices();
  message("count-online",aircraft.filter(d=>d.freshness==="fresh"&&d.online===true).length);
  message("count-drones",aircraft.length);
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
    const card=add(body,"div","list-card clickable"+(d.device_id===currentDevice?" active":""));
    add(card,"b","",d.name||"Unbenanntes Gerät");
    add(card,"small","",d.kind==="aircraft"?"Drohne":"Fernsteuerung");
    const state=d.freshness==="fresh"?(d.online===true?"Online":"Offline"):"Nicht aktuell";
    add(card,"span","badge "+(state==="Online"?"good":"warn"),state);
    card.addEventListener("click",()=>{currentDevice=d.device_id;renderCockpit();renderDevices();});
  }
}
function metric(parent,title,value){
  const box=add(parent,"div","");
  add(box,"span","",title);
  add(box,"b","",value);
}
function renderCockpit(){
  const options=$("cockpit-select");options.replaceChildren();
  const available=selectedDevices();
  if(!available.some(d=>d.device_id===currentDevice))currentDevice=available[0]?.device_id||"";
  for(const d of available){const option=add(options,"option","",d.name||d.device_id);option.value=d.device_id;}
  options.value=currentDevice;
  const body=$("cockpit-content");body.replaceChildren();
  const d=available.find(x=>x.device_id===currentDevice);
  if(!d){
    message("cockpit-name","Kein Fluggerät ausgewählt");
    message("cockpit-freshness","Keine Daten");
    message("cockpit-received","Kein Datenempfang");
    add(body,"div","note","Kein Fluggerät vom gewählten FlightHub-Projekt empfangen.");
    return;
  }
  message("cockpit-name",d.name||"Unbenanntes Fluggerät");
  const state=d.freshness==="fresh"?"Aktuell":d.freshness==="stale"?"Veraltet":"Nicht verfügbar";
  message("cockpit-freshness",state);
  $("cockpit-freshness").className="badge "+(state==="Aktuell"?"good":"warn");
  message("cockpit-received",finite(d.age_seconds)?"Vor "+Math.floor(d.age_seconds)+" s empfangen":"Empfangsalter unbekannt");
  const t=d.telemetry||{};
  if(finite(t.battery_percent)&&t.battery_percent>=0&&t.battery_percent<=100){
    add(body,"div","sub","Akku (letzter Messwert)");
    const level=add(body,"progress","progress"+(t.battery_percent<=30?" low":""));
    level.max=100;level.value=t.battery_percent;
    add(body,"div","badge "+(t.battery_percent<=30?"warn":"good"),formatNumber(t.battery_percent,0,"%"));
  }
  const grid=add(body,"div","cockpit");
  const modes={0:"Manuell",1:"GPS",2:"Position",3:"Sport"};
  metric(grid,"Flugmodus",t.flight_mode_code==null?"–":(modes[t.flight_mode_code]||"DJI-Code "+t.flight_mode_code));
  metric(grid,"Höhe über Start",formatNumber(t.elevation_m,1,"m"));
  metric(grid,"Absolute Höhe",formatNumber(t.height_m,1,"m"));
  metric(grid,"Geschwindigkeit horizontal",formatNumber(t.horizontal_speed_mps,1,"m/s"));
  metric(grid,"Geschwindigkeit vertikal",formatNumber(t.vertical_speed_mps,1,"m/s"));
  metric(grid,"GPS-Satelliten",text(t.gps_satellites));
  metric(grid,"RTK-Satelliten",text(t.rtk_satellites));
  metric(grid,"RTK-Status",text(t.rtk_state));
  metric(grid,"Akkuspannung",finite(t.battery_voltage_mv)?formatNumber(t.battery_voltage_mv/1000,2,"V"):"–");
  metric(grid,"Akkutemperatur",formatNumber(t.battery_temperature_c,1,"°C"));
  const warnings=Array.isArray(d.health)?d.health:[];
  if(warnings.length){
    add(body,"h3","","HMS (zuletzt übermittelt)");
    for(const a of warnings.slice(0,6)){
      const warning=add(body,"div","cockpit-alert");
      add(warning,"b","",a.level==="warning"?"Warnung":a.level==="reminder"?"Hinweis":"Meldung");
      add(warning,"div","",a.message&&a.message!==a.code?a.message:"Code: "+text(a.code));
    }
    add(body,"div","sub","HMS-Meldungen besitzen hier keine gesonderte garantierte Ereigniszeit.");
  }
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
function renderTracks(){
  const body=$("flight-tracks");body.replaceChildren();
  let count=0;
  for(const p of selectedProjectCatalog()){
    if(p.tasks===null){add(body,"div","note","Flugaufträge für "+text(p.name)+" nicht abrufbar.");continue;}
    for(const task of (p.tasks||[]).slice(0,30)){
      count++;
      const card=add(body,"div","list-card");
      add(card,"b","",task.name||"Unbenannter Flugauftrag");
      add(card,"small","",text(p.name||p.project_id)+" · "+text(task.status)+" · "+text(task.run_at));
      if(task.uuid){
        const btn=add(card,"button","","Flugspur auf Karte");
        btn.type="button";
        btn.addEventListener("click",()=>viewTrack(p.project_id,task).catch(err=>
          message("map-message","Flugspur nicht verfügbar: "+err.message)));
      }
    }
  }
  if(!count&&!body.children.length)add(body,"div","note","Keine Flugaufträge im abgefragten Zeitraum (in der Regel 30 Tage).");
}
async function getJSON(path){
  const response=await fetch(path,{cache:"no-store"});
  if(!response.ok)throw new Error("HTTP "+response.status);
  return response.json();
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
    const [fleet,library,local,summary]=await Promise.all([
      getJSON("/api/v1/status/devices?limit=200"),
      getJSON("/api/v1/flighthub/catalog"),
      getJSON("/api/v1/studio/missions"),
      getJSON("/api/v1/status/summary")
    ]);
    if(generation!==refreshCount||stopped)return;
    devices=Array.isArray(fleet.devices)?fleet.devices:[];
    projects=Array.isArray(library.projects)?library.projects:[];
    missionList=Array.isArray(local.missions)?local.missions:[];
    const before=currentProject;
    renderProjects();
    if(before&&!projects.some(p=>p.project_id===before)&&!devices.some(d=>d.project_id===before))
      currentProject="";
    renderSummary();renderDevices();renderCockpit();renderCatalog();renderTracks();
    renderSavedMissions();
    repaintDeviceLayer();
    message("project-sync",receiveUpdatedAt(summary));
    message("catalog-info","Stand: "+text(library.updated_at)+" · Nur gelesener lokaler Cache");
    message("connection","LAN-Verbindung aktiv · letzte Anzeige "+new Date().toLocaleTimeString("de-DE"));
  }catch(err){
    message("connection","Datenabruf fehlgeschlagen: "+err.message);
    message("project-sync","Schnittstelle konnte nicht abgefragt werden. Browser und Pi prüfen.");
  }finally{refreshing=false;}
}
function wire(){
  $("refresh-now").addEventListener("click",refreshAll);
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
