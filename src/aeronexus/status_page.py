"""Self-contained, auto-refreshing read-only fleet status web page.

The dashboard API remains separately authenticated for device details.
The browser holds the dashboard token in memory only (no localStorage).
"""


HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>AeroNexusAdvanced | Status</title>
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0c1523;color:#e5edf9}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at top right,#182e49,#0c1523 55%);padding:28px}
main{max-width:1250px;margin:auto}header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}
h1{font-size:clamp(25px,4vw,36px);margin:4px 0}h2{font-size:18px;margin:0 0 14px}
.subtle,.meta{color:#a9b8cb;font-size:14px}.eyebrow{color:#73aee8;letter-spacing:.16em;text-transform:uppercase;font-size:11px;font-weight:700}
.panel{border:1px solid #30435a;border-radius:14px;background:#152337;box-shadow:0 8px 35px #070d1540;padding:20px;margin:20px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(156px,1fr));gap:12px;margin-top:20px}
.metric{padding:18px;border:1px solid #34475c;border-radius:12px;background:#172b40}.metric b{display:block;font-size:28px;margin-top:10px}
.metric span{font-size:13px;color:#abc0d5}
.controls{display:flex;align-items:center;flex-wrap:wrap;gap:12px}.controls input{background:#0d1b2a;border:1px solid #486078;border-radius:7px;padding:11px;color:white;min-width:min(100%,300px)}
button{background:#3573b5;color:white;border:0;border-radius:7px;padding:11px 18px;cursor:pointer;font-weight:650}
button:hover{background:#438acd}button:focus-visible,input:focus-visible{outline:2px solid #8ac5ff}
table{border-collapse:collapse;width:100%;min-width:1240px;font-size:13px}
table.compact{min-width:760px}h3{font-size:15px;margin:18px 0 8px;color:#c9d8e8}th{text-align:left;color:#b8cae0;font-weight:600}
td,th{padding:13px 11px;border-bottom:1px solid #30435a;vertical-align:top}
.scroller{overflow-x:auto}.good{color:#8bdfbb}.warn{color:#ffcd7b}.bad{color:#ffadac}
code,pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;color:#c9d8e8}
details{max-width:350px}details summary{cursor:pointer}
footer{margin:22px 0;color:#9fb3ca;font-size:12px}

.device-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,330px),1fr));gap:14px;margin:15px 0 22px}
.device-card{min-width:0;border:1px solid #39536f;border-radius:14px;background:#102034;padding:17px}
.device-card .device-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
.device-card h3{font-size:17px;margin:0;color:#eaf3ff;overflow-wrap:anywhere}
.device-id{display:block;overflow-wrap:anywhere;font-size:11px;margin-top:6px;color:#9eb6cf}
.device-tag{display:inline-block;border-radius:20px;border:1px solid #54718f;padding:5px 9px;font-size:12px;flex-shrink:0}
.device-tag[data-tone="good"]{color:#8bdfbb;border-color:#306b58}
.device-tag[data-tone="bad"]{color:#ffadac;border-color:#98515a}
.device-tag[data-tone="warn"]{color:#ffcd7b;border-color:#80623b}
.device-meta{color:#b5c8dd;font-size:12px;margin:10px 0 14px;overflow-wrap:anywhere}
.device-values{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.device-value{border:1px solid #31465e;border-radius:8px;padding:9px;min-width:0}
.device-value span{display:block;color:#b1c4d9;font-size:11px}
.device-value b{font-size:14px;overflow-wrap:anywhere;display:block;margin-top:4px;font-weight:600}
.device-battery{margin:12px 0}
.device-battery .battery-label{display:flex;justify-content:space-between;font-size:13px;margin-bottom:5px}
.device-battery progress{display:block;width:100%;height:10px;accent-color:#5ac69c}
.device-battery progress.low{accent-color:#ef9e68}
.device-alerts{margin-top:13px;border-top:1px solid #31465e;padding-top:10px}
.device-alerts ul{padding-left:18px;margin:8px 0 0}
.device-alerts li{font-size:12px;line-height:1.5;margin:5px 0;overflow-wrap:anywhere}
.device-alerts li.warning{color:#ffadac}
.device-alerts li.reminder{color:#ffcd7b}
.device-empty{padding:16px;border:1px dashed #49627e;border-radius:10px;color:#abc0d5}
.raw-table{max-width:none}.raw-table>summary{cursor:pointer;color:#bbd4ed;font-size:14px;margin:8px 0}

.catalog-section{margin:22px 0 0}
.catalog-heading{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 10px}
.catalog-heading h3{margin:0}
.catalog-count{font-size:12px;border:1px solid #486078;border-radius:20px;padding:3px 9px;color:#cbdced}
.catalog-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:12px}
.catalog-card{min-width:0;border:1px solid #3b506a;border-radius:12px;background:#102034;padding:14px}
.catalog-card h4{margin:0;color:#f0f6ff;font-size:16px;overflow-wrap:anywhere}
.catalog-meta{font-size:12px;color:#b5c8dd;margin:6px 0 10px;overflow-wrap:anywhere}
.catalog-tags{display:flex;flex-wrap:wrap;gap:6px}
.catalog-tag{border:1px solid #405b78;border-radius:7px;padding:5px 7px;font-size:12px;overflow-wrap:anywhere}
.catalog-status{font-size:13px;color:#adbfda;padding:10px 0}
.catalog-raw{max-width:none;margin-top:10px}
.catalog-raw summary{color:#abcbe7;font-size:13px;cursor:pointer;padding:8px 0}
.catalog-card button{margin-top:12px;width:100%}
.hms-list{display:grid;gap:8px;margin-top:10px}
.hms-entry{border:1px solid #40546c;border-radius:9px;padding:10px;overflow-wrap:anywhere}
.hms-entry[data-level="warning"]{border-left:4px solid #f3a2a0}
.hms-entry[data-level="reminder"]{border-left:4px solid #eabf76}
.hms-entry[data-level="notification"]{border-left:4px solid #82b9e6}
.hms-heading{display:flex;gap:7px;align-items:center;flex-wrap:wrap;font-size:12px}
.hms-code{color:#b4c9e2;font-size:12px}
.hms-description{font-size:13px;margin-top:7px;overflow-wrap:anywhere}
.hms-secondary{color:#9faec4;font-size:12px;margin-top:7px}
.catalog-grid>.device-empty{grid-column:1/-1}
#poll-health{margin-top:12px}
@media(max-width:650px){body{padding:12px}.panel{padding:14px;margin:14px 0}.grid{gap:8px}.metric{padding:12px}.metric b{font-size:22px}.controls input{width:100%}}
</style>
</head>
<body>
<main>
<header>
<div><div class="eyebrow">DJI Monitoring · Nur Lesen</div><h1>AeroNexusAdvanced</h1>
<div class="subtle">Flottenstatus · Flugbefehle deaktiviert</div></div>
<div class="meta">Automatische Anzeigeaktualisierung: __INTERVAL_SECONDS__ s<br>
<span id="timestamp">Noch keine Daten</span><br>
<span id="feed">Live-Feed: –</span></div>
</header>
<div class="meta" id="poll-health" role="status">FlightHub-Synchronisierung noch nicht ermittelt.</div>
<section class="grid" aria-label="Flottenkennzahlen">
<div class="metric"><span>Geräte gesamt</span><b id="total">–</b></div>
<div class="metric"><span>Drohnen</span><b id="aircraft">–</b></div>
<div class="metric"><span>Fernsteuerungen</span><b id="controllers">–</b></div>
<div class="metric"><span>Aktuell online</span><b id="online">–</b></div>
<div class="metric"><span>Veraltete Telemetrie</span><b id="stale">–</b></div>
<div class="metric"><span>Fehlende/unklare Daten</span><b id="unknown">–</b></div>
<div class="metric"><span>HMS-Warnungen</span><b id="health">–</b></div>
</section>
<section class="panel">
<h2>Geschützte Gerätedetails</h2>
<p class="subtle">Separaten AeroNexus-Status-Token eingeben, nicht den DJI-Zugriffstoken. Der Token bleibt ausschließlich im Arbeitsspeicher dieses Browser-Tabs.</p>
<div class="controls">
<input id="token" type="password" autocomplete="off" spellcheck="false" placeholder="AeroNexus-Status-Token" aria-label="Status-Zugriffstoken">
<button id="connect" type="button">Details laden</button>
<button id="disconnect" type="button">Trennen</button>
<span id="message" class="meta" role="status">Details noch nicht verbunden</span>
</div>
</section>
<section class="panel">
<h2>Geräte und Telemetrie</h2>
<div class="subtle" id="device-info">Es werden ausschließlich freigegebene, authentifizierte Gerätedaten angezeigt.</div>
<div id="device-cards" class="device-grid" aria-label="Gerätekarten"><div class="device-empty">Zum Laden der Gerätekarten mit dem Status-Token verbinden.</div></div>
<details class="raw-table"><summary>Technische Gerätetabelle anzeigen</summary>
<div class="scroller">
<table>
<thead><tr><th>Provider / Projekt</th><th>Gerät</th><th>Typ</th><th>Frische</th><th>Empfangen (UTC)</th><th>Online</th><th>Kurzwerte</th><th>Zustand (HMS)</th><th>Messwerte</th></tr></thead>
<tbody id="devices"></tbody>
</table>
</div>
</details>
</section>
<section class="panel" id="catalog-panel" hidden>
<h2>FlightHub-Bibliothek</h2>
<div class="subtle" id="catalog-info" role="status">Die Projektbibliothek wird nur nach erfolgreicher Anmeldung geladen.</div>
<section class="catalog-section" aria-labelledby="wayline-heading">
<div class="catalog-heading"><h3 id="wayline-heading">Routen</h3><span class="catalog-count" id="wayline-count">–</span></div>
<div class="catalog-grid" id="wayline-cards"></div>
<details class="catalog-raw"><summary>Routentabelle anzeigen</summary>
<div class="scroller"><table class="compact"><thead><tr><th>Projekt</th><th>Name</th><th>Typ</th><th>Fluggerät</th><th>Linsen</th><th>Geändert</th><th>Größe</th></tr></thead><tbody id="waylines"></tbody></table></div>
</details></section>
<section class="catalog-section" aria-labelledby="model-heading">
<div class="catalog-heading"><h3 id="model-heading">Karten-Modelle</h3><span class="catalog-count" id="model-count">–</span></div>
<div class="catalog-grid" id="model-cards"></div>
<details class="catalog-raw"><summary>Modelltabelle anzeigen</summary>
<div class="scroller"><table class="compact"><thead><tr><th>Projekt</th><th>Name</th><th>Typ</th><th>Auf Karte</th><th>Geändert</th><th>Größe</th></tr></thead><tbody id="models"></tbody></table></div>
</details></section>
<section class="catalog-section" aria-labelledby="task-heading">
<div class="catalog-heading"><h3 id="task-heading">Flugaufträge</h3><span class="catalog-count" id="task-count">–</span></div>
<div class="catalog-grid" id="task-cards"></div>
<details class="catalog-raw"><summary>Auftragstabelle anzeigen</summary>
<div class="scroller"><table class="compact"><thead><tr><th>Projekt</th><th>Name</th><th>Art</th><th>Status</th><th>Gestartet</th><th>Wegpunkte</th><th>Flugspur</th></tr></thead><tbody id="tasks"></tbody></table></div>
</details></section>
</section>
<footer>Zeitstempel = Eingang bei AeroNexus, nicht DJI-Ereigniszeit. Veraltete Messwerte sind keine Live-Werte. Die Anzeige ruft selbst keine DJI-Endpunkte auf.</footer>
</main>
<script>
"use strict";
const intervalMs = __INTERVAL_MILLISECONDS__;
let accessToken = "";
let sessionEpoch=0;
let devicesRequest=0;
let catalogRequest=0;
const byId = id => document.getElementById(id);
const asText = value => value === null || value === undefined ? "–" : String(value);
function cell(row, value) { const el=document.createElement("td");el.textContent=asText(value);row.appendChild(el);return el; }
const flightModes={0:"Standby",1:"Startvorbereitung",2:"Startbereit",3:"Manueller Flug",
  4:"Automatischer Start",5:"Routenflug",6:"Panorama",7:"Intelligentes Tracking",8:"ADS-B-Ausweichen",
  9:"R\u00fcckkehr (RTH)",10:"Automatische Landung",11:"Erzwungene Landung",12:"Dreiblatt-Landung",
  13:"Update",14:"Nicht verbunden",15:"APAS",16:"Virtueller Stick",17:"Live-Flugsteuerung",
  18:"RTK-Fixierung in der Luft",19:"Dock-Standortwahl",20:"POI"};
const feedStates={disabled:"aus",stopped:"gestoppt",connecting:"verbinde",connected:"verbunden",
  subscribed:"empfange",subscription_denied:"Abo verweigert (ACL)",auth_failed:"Anmeldung abgelehnt",
  disconnected:"getrennt",unreachable:"Broker nicht erreichbar"};
function num(v,digits,unit){return v===null||v===undefined?null:Number(v).toFixed(digits)+" "+unit;}
function keyValues(t) {
  const parts=[];
  const add=(label,value)=>{if(value!==null)parts.push(label+": "+value);};
  add("Akku",num(t.battery_percent,0,"%"));
  add("H\u00f6he",num(t.elevation_m,1,"m"));
  add("Geschw.",num(t.horizontal_speed_mps,1,"m/s"));
  add("Distanz",num(t.home_distance_m,0,"m"));
  if(t.flight_mode_code!==null&&t.flight_mode_code!==undefined)
    add("Modus",flightModes[t.flight_mode_code]||("Code "+t.flight_mode_code));
  if(t.gps_satellites!==null&&t.gps_satellites!==undefined)
    add("Sat.",t.gps_satellites+" GPS / "+asText(t.rtk_satellites)+" RTK");
  return parts.length?parts.join(" \u00b7 "):"\u2013";
}
const modelNames={"0-99-0":"Matrice 4E","0-99-1":"Matrice 4T","0-100-0":"Matrice 4D","0-100-1":"Matrice 4TD",
  "0-77-0":"Mavic 3E","0-77-1":"Mavic 3T","0-77-2":"Mavic 3M","0-91-0":"Matrice 3D","0-91-1":"Matrice 3TD",
  "0-67-0":"Matrice 30","0-67-1":"Matrice 30T","0-89-0":"Matrice 350 RTK","0-60-0":"Matrice 300 RTK"};
const templateNames={waypoint:"Wegpunkte",mapping_2d:"Fl\u00e4che 2D",mapping_3d:"Schr\u00e4g 3D",
  mapping_strip:"Korridor",facade:"Fassade",solid:"K\u00f6rper",mapping_gobject:"Objekt"};
const taskStates={waiting:"Wartet",starting_failure:"Startfehler",executing:"L\u00e4uft",paused:"Pausiert",
  terminated:"Abgebrochen",success:"Erfolgreich",suspended:"Ausgesetzt",timeout:"Zeit\u00fcberschreitung",
  partially_done:"Teilweise",preparing:"Vorbereitung",unknown:"Unbekannt"};
const taskTypes={immediate:"Sofort",timed:"Geplant",recurring:"Wiederkehrend",continuous:"Dauerhaft"};
function size(b){return b===null||b===undefined?null:b>1048576?(b/1048576).toFixed(1)+" MB":(b/1024).toFixed(0)+" KB";}
function date(sec){return sec?new Date(sec*1000).toISOString().slice(0,16).replace("T"," ")+" UTC":null;}
function rowOf(body,values){const row=document.createElement("tr");values.forEach(v=>cell(row,v));body.appendChild(row);return row;}
function placeholder(body,cols,text){const row=document.createElement("tr");const td=cell(row,text);td.colSpan=cols;td.className="subtle";body.appendChild(row);}
async function downloadTrack(project,task,name){
  if(!accessToken)return;
  const token=accessToken,epoch=sessionEpoch;
  try{
    const r=await fetch("/api/v1/flighthub/projects/"+encodeURIComponent(project)+"/tasks/"+encodeURIComponent(task)+"/track",
      {cache:"no-store",headers:{"Authorization":"Bearer "+token}});
    if(!r.ok)throw new Error("HTTP "+r.status);
    const geojson=await r.text();
    if(epoch!==sessionEpoch)return; // disconnect must prevent late file downloads
    const url=URL.createObjectURL(new Blob([geojson],{type:"application/geo+json"}));
    const a=document.createElement("a");a.href=url;a.download=(name||"flugspur").replace(/[^A-Za-z0-9_-]+/g,"_")+".geojson";
    document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){if(epoch===sessionEpoch)byId("catalog-info").textContent="Flugspur nicht verf\u00fcgbar ("+e.message+").";}
}

function catalogTag(card,label,value){
  if(value===null||value===undefined||value==="")return;
  const tags=card.querySelector(".catalog-tags");
  cardEl(tags,"span","catalog-tag",label?label+": "+value:value);
}
function catalogCard(parent,title,project){
  const card=cardEl(parent,"article","catalog-card");
  cardEl(card,"h4","",title||"Ohne Namen");
  cardEl(card,"div","catalog-meta","Projekt: "+project);
  cardEl(card,"div","catalog-tags");
  return card;
}
function catalogEmpty(parent,text){
  cardEl(parent,"div","device-empty",text);
}
function renderCatalogCards(project,cards,counts){
  const pname=project.name||project.project_id||"Unbekanntes Projekt";
  for(const [kind,title] of [["waylines","Routen"],["models","Karten-Modelle"],["tasks","Flugaufträge"]]){
    if(project[kind]===null){
      catalogEmpty(cards[kind],pname+": "+title+" nicht abrufbar");
      continue;
    }
    if(!Array.isArray(project[kind]))throw new Error("Ungültige Bibliotheksdaten");
    counts[kind]+=project[kind].length;
  }
  for(const wayline of project.waylines||[]){
    const card=catalogCard(cards.waylines,wayline.name,pname);
    catalogTag(card,"Typ",(wayline.template_types||[]).map(t=>templateNames[t]||t).join(", "));
    catalogTag(card,"Fluggerät",modelNames[wayline.device_model_key]||wayline.device_model_key);
    catalogTag(card,"Linsen",(wayline.lenses||[]).join(", ").toUpperCase());
    catalogTag(card,"Geändert",date(wayline.updated_at));
    catalogTag(card,"Größe",size(wayline.size_bytes));
  }
  for(const model of project.models||[]){
    const card=catalogCard(cards.models,model.name,pname);
    catalogTag(card,"Typ",model.file_type==="model_3d"?"3D":model.file_type==="model_2d"?"2D":model.file_type);
    catalogTag(card,"Kartenanzeige",model.show_on_map?"Ja":"Nein");
    catalogTag(card,"Geändert",model.updated_at_ms?date(Math.floor(model.updated_at_ms/1000)):null);
    catalogTag(card,"Größe",size(model.size_bytes));
  }
  for(const task of project.tasks||[]){
    const card=catalogCard(cards.tasks,task.name,pname);
    catalogTag(card,"Art",taskTypes[task.task_type]||task.task_type);
    catalogTag(card,"Status",taskStates[task.status]||task.status);
    catalogTag(card,"Gestartet",task.run_at);
    if(task.total_waypoints!==null&&task.total_waypoints!==undefined){
      catalogTag(card,"Wegpunkte",(task.current_waypoint_index??0)+"/"+task.total_waypoints);
    }
    if(task.exceptions)catalogTag(card,"Auftragsmeldungen",task.exceptions);
    if(task.uuid){
      const button=cardEl(card,"button","","Flugspur als GeoJSON");
      button.type="button";
      button.addEventListener("click",()=>downloadTrack(project.project_id,task.uuid,task.name));
    }
  }
}

async function updateCatalog() {
  if(!accessToken)return;
  const token=accessToken,epoch=sessionEpoch,request=++catalogRequest;
  const lists={waylines:byId("waylines"),models:byId("models"),tasks:byId("tasks")};
  const cards={waylines:byId("wayline-cards"),models:byId("model-cards"),tasks:byId("task-cards")};
  try{
    const r=await fetch("/api/v1/flighthub/catalog",{cache:"no-store",headers:{"Authorization":"Bearer "+token}});
    if(!r.ok)throw new Error("HTTP "+r.status);
    const data=await r.json();
    if(epoch!==sessionEpoch||request!==catalogRequest)return;
    if(!Array.isArray(data.projects))throw new Error("Ungültige Bibliotheksantwort");
    Object.values(lists).forEach(b=>b.replaceChildren());
    Object.values(cards).forEach(b=>b.replaceChildren());
    const counts={waylines:0,models:0,tasks:0};
    byId("catalog-panel").hidden=false;
    for(const p of data.projects){
      const pname=p.name||p.project_id;
      renderCatalogCards(p,cards,counts);
      if(p.waylines===null)placeholder(lists.waylines,7,pname+": nicht lesbar");
      for(const w of p.waylines||[])rowOf(lists.waylines,[pname,w.name,(w.template_types||[]).map(t=>templateNames[t]||t).join(", "),
        modelNames[w.device_model_key]||w.device_model_key,(w.lenses||[]).join(", ").toUpperCase(),date(w.updated_at),size(w.size_bytes)]);
      if(p.models===null)placeholder(lists.models,6,pname+": nicht lesbar");
      for(const m of p.models||[])rowOf(lists.models,[pname,m.name,m.file_type==="model_3d"?"3D":m.file_type==="model_2d"?"2D":null,
        m.show_on_map?"Ja":"Nein",m.updated_at_ms?date(Math.floor(m.updated_at_ms/1000)):null,size(m.size_bytes)]);
      if(p.tasks===null)placeholder(lists.tasks,7,pname+": nicht lesbar");
      for(const t of p.tasks||[]){
        const row=rowOf(lists.tasks,[pname,t.name,taskTypes[t.task_type]||t.task_type,taskStates[t.status]||t.status,
          t.run_at,t.total_waypoints===null?null:(t.current_waypoint_index??0)+"/"+t.total_waypoints]);
        const td=document.createElement("td");const b=document.createElement("button");b.type="button";b.textContent="GeoJSON";
        b.addEventListener("click",()=>downloadTrack(p.project_id,t.uuid,t.name));td.appendChild(b);row.appendChild(td);
      }
    }
    for(const [key,b] of Object.entries(lists)){
      if(!b.children.length)placeholder(b,key==="models"?6:7,key==="tasks"?
        "Keine Flugauftr\u00e4ge in den letzten "+((data.projects[0]||{}).task_window_days||30)+" Tagen":"Keine Eintr\u00e4ge");
      if(!cards[key].children.length)catalogEmpty(cards[key],key==="tasks"?
        "Keine Flugauftr\u00e4ge in den letzten "+((data.projects[0]||{}).task_window_days||30)+" Tagen":"Keine Eintr\u00e4ge");
    }
    byId("wayline-count").textContent=counts.waylines;
    byId("model-count").textContent=counts.models;
    byId("task-count").textContent=counts.tasks;
    byId("catalog-info").textContent=data.updated_at?"Stand: "+data.updated_at+" (Aktualisierung alle paar Minuten)":
      "Noch nicht geladen (FlightHub-Polling aus oder erster Abruf l\u00e4uft).";
  }catch(e){
    if(epoch!==sessionEpoch||request!==catalogRequest)return;
    Object.values(lists).forEach(b=>b.replaceChildren());
    Object.values(cards).forEach(b=>b.replaceChildren());
    byId("catalog-panel").hidden=true;
    byId("catalog-info").textContent="Bibliothek nicht verf\u00fcgbar ("+e.message+").";
    byId("message").textContent="Bibliothek nicht verfügbar ("+e.message+").";
  }
}

function cardEl(parent,tag,className,text) {
  const el=document.createElement(tag);
  if(className)el.className=className;
  if(text!==undefined&&text!==null)el.textContent=String(text);
  parent.appendChild(el);
  return el;
}
function cardValue(body,label,value) {
  if(value===null||value===undefined)return;
  const item=cardEl(body,"div","device-value");
  cardEl(item,"span","",label);
  cardEl(item,"b","",value);
}
function safeNumber(value,digits,unit) {
  return typeof value==="number"&&Number.isFinite(value)
    ?value.toFixed(digits)+(unit?" "+unit:""):null;
}
function rtkText(raw) {
  if(!raw)return null;
  const codes={
    "is_fixed:fixing_successful":"Fix erfolgreich",
    "is_fixed:not_started":"Nicht gestartet",
    "is_fixed:fixing":"Fix läuft",
    "is_fixed:fixing_failed":"Fix fehlgeschlagen"
  };
  return codes[raw]||raw;
}
function ageText(device) {
  const age=device.age_seconds;
  return typeof age==="number"&&Number.isFinite(age)&&age>=0
    ?"vor "+Math.floor(age)+" s empfangen"
    :"Empfangsalter unbekannt";
}
function renderDeviceCards(devices) {
  const body=byId("device-cards");body.replaceChildren();
  if(!devices.length) {
    cardEl(body,"div","device-empty","Keine Geräte vorhanden oder für diese Ansicht freigegeben.");
    return;
  }
  for(const device of devices) {
    const t=device.telemetry||{};
    const card=cardEl(body,"article","device-card");
    const header=cardEl(card,"div","device-head");
    const name=cardEl(header,"div","");
    cardEl(name,"h3","",device.name||"Unbenanntes Gerät");
    cardEl(name,"code","device-id",device.device_id);
    const tag=cardEl(header,"span","device-tag",statusLabel(device.freshness));
    tag.dataset.tone=device.freshness==="fresh"?"good":
      device.freshness==="stale"||device.freshness==="missing"?"warn":"bad";
    const kind=device.kind==="aircraft"?"Drohne":device.kind==="controller"?"Fernsteuerung":device.kind;
    const online=device.freshness!=="fresh"?"Online-Zustand nicht aktuell":
      device.online===true?"Online":device.online===false?"Offline":"Online-Zustand unbekannt";
    cardEl(card,"div","device-meta",kind+" · "+online+" · "+ageText(device));
    const battery=t.battery_percent;
    if(typeof battery==="number"&&Number.isFinite(battery)&&battery>=0&&battery<=100){
      const wrap=cardEl(card,"div","device-battery");
      const label=cardEl(wrap,"div","battery-label");
      cardEl(label,"span","","Akku (letzter Messwert)");
      cardEl(label,"b","",battery.toFixed(0)+" %");
      const bar=cardEl(wrap,"progress",battery<=20?"low":"");
      bar.max=100;bar.value=battery;
      bar.setAttribute("aria-label","Akkustand "+battery.toFixed(0)+" Prozent");
    }
    const values=cardEl(card,"div","device-values");
    const mode=t.flight_mode_code;
    cardValue(values,"Flugmodus",mode===null||mode===undefined?null:flightModes[mode]||"Code "+mode);
    cardValue(values,"Höhe über Start",safeNumber(t.elevation_m,1,"m"));
    cardValue(values,"Absolute Höhe",safeNumber(t.height_m,1,"m"));
    cardValue(values,"Horizontale Geschwindigkeit",safeNumber(t.horizontal_speed_mps,1,"m/s"));
    cardValue(values,"Vertikale Geschwindigkeit",safeNumber(t.vertical_speed_mps,1,"m/s"));
    cardValue(values,"Distanz zum Homepoint",safeNumber(t.home_distance_m,0,"m"));
    cardValue(values,"GPS-Satelliten",t.gps_satellites);
    cardValue(values,"RTK-Satelliten",t.rtk_satellites);
    cardValue(values,"RTK-Status",rtkText(t.rtk_state));
    cardValue(values,"Akkuspannung",typeof t.battery_voltage_mv==="number"&&
      Number.isFinite(t.battery_voltage_mv)?(t.battery_voltage_mv/1000).toFixed(2)+" V":null);
    cardValue(values,"Akkutemperatur",safeNumber(t.battery_temperature_c,1,"°C"));
    cardValue(values,"Flugzeit gesamt",typeof t.total_flight_time_s==="number"&&
      Number.isFinite(t.total_flight_time_s)?(t.total_flight_time_s/3600).toFixed(1)+" h":null);
    cardValue(values,"Starts gesamt",t.total_flight_sorties);
    const lat=t.latitude,lon=t.longitude;
    if(typeof lat==="number"&&typeof lon==="number"&&Number.isFinite(lat)&&Number.isFinite(lon)&&
       Math.abs(lat)<=90&&Math.abs(lon)<=180&&(lat!==0||lon!==0)){
      cardValue(values,"Position (GPS)",lat.toFixed(5)+", "+lon.toFixed(5));
    }
    if(!values.children.length)cardEl(card,"p","subtle","Noch keine Telemetriewerte verfügbar.");
    const alerts=device.health||[];
    if(alerts.length){
      const section=cardEl(card,"div","device-alerts");
      cardEl(section,"b","","HMS · "+alerts.length+" zuletzt gemeldete Meldung(en)");
      const list=cardEl(section,"ul","");
      for(const alert of alerts.slice(0,5)){
        const level=alert.level==="warning"?"Warnung":alert.level==="reminder"?"Hinweis":"Info";
        cardEl(list,"li",alert.level==="warning"?"warning":alert.level==="reminder"?"reminder":"",
          level+": "+(alert.message||alert.code||"Ohne Beschreibung"));
      }
      if(alerts.length>5)cardEl(section,"div","subtle","Weitere "+(alerts.length-5)+" Meldung(en) in der technischen Tabelle.");
    }
  }
}

function statusLabel(v) {
  return ({fresh:"Aktuell",stale:"Veraltet",missing:"Keine Daten",
           unknown_age:"Zeit unbekannt",clock_skew:"Uhrzeitfehler"})[v] || "Unbekannt";
}
async function updateSummary() {
  try {
    const r=await fetch("/api/v1/status/summary",{cache:"no-store"});
    if(!r.ok)throw new Error("HTTP "+r.status);
    const data=await r.json();
    byId("total").textContent=data.registered_devices;
    byId("aircraft").textContent=data.aircraft;
    byId("controllers").textContent=data.controllers;
    byId("online").textContent=data.online_fresh;
    byId("stale").textContent=data.stale;
    byId("unknown").textContent=data.missing+data.unknown_age+data.clock_skew;
    byId("health").textContent=data.health_warnings;
    byId("timestamp").textContent="Letzter Aufruf: "+data.server_time+" · Polling: "+data.polling;
    const fh=data.flighthub||{};
    byId("timestamp").textContent+=" · FlightHub: "+({ok:"OK",error:"Fehler",unknown:"unbekannt"}[fh.system_status]||"unbekannt");
    const pollState={disabled:"deaktiviert",running:"Abruf läuft",idle:"bereit",error:"letzter Abruf fehlgeschlagen",stopped:"gestoppt"};
    const lastOk=data.last_refresh_success_at;
    const since=lastOk?Math.max(0,Math.floor((Date.parse(data.server_time)-Date.parse(lastOk))/1000)):null;
    byId("poll-health").textContent="DJI-Polling: "+(pollState[data.polling]||data.polling)+
      " · Letzter erfolgreicher Abruf: "+(lastOk?lastOk+" ("+since+" s zurück)":"noch keiner")+
      " · Grenzwert für veraltete Telemetrie: "+data.stale_after_seconds+" s";

    const feed=data.live_feed||{state:"disabled"};
    byId("feed").textContent="Live-Feed (DJI Cloud API): "+(feedStates[feed.state]||"unbekannt")+
      (feed.state==="disabled"?"":" · "+feed.accepted+" ok / "+feed.rejected+" verworfen");
  } catch (_) {byId("timestamp").textContent="Status-API nicht erreichbar";byId("poll-health").textContent="DJI-Polling-Status nicht erreichbar";}
}
async function updateDevices() {
  if(!accessToken)return;
  const token=accessToken,epoch=sessionEpoch,request=++devicesRequest;
  try {
    const r=await fetch("/api/v1/status/devices?limit=200",{
      cache:"no-store",headers:{"Authorization":"Bearer "+token}
    });
    if(!r.ok)throw new Error("HTTP "+r.status);
    const data=await r.json();
    if(epoch!==sessionEpoch||request!==devicesRequest)return;
    renderDeviceCards(data.devices);
    const body=byId("devices");body.replaceChildren();
    for(const device of data.devices) {
      const row=document.createElement("tr");
      cell(row,device.provider+" / "+device.project_id);
      cell(row,device.name+" ("+device.device_id+")");
      cell(row,device.kind);
      const freshness=cell(row,statusLabel(device.freshness));
      freshness.className=device.freshness==="fresh"?"good":"warn";
      cell(row,device.received_at);
      cell(row,device.online===null?"Unbekannt":device.online?"Online":"Offline");
      cell(row,keyValues(device.telemetry||{}));
      const alerts=device.health||[];
      const hms=cell(row,alerts.length?alerts.slice(0,3).map(a=>
        ({warning:"Warnung",reminder:"Hinweis",notification:"Info"}[a.level]||a.level)+": "+
        (a.message||a.code||"\u2013")).join(" \u00b7 ")+(alerts.length>3?" (+"+(alerts.length-3)+")":""):"\u2013");
      hms.className=alerts.some(a=>a.level==="warning")?"bad":(alerts.length?"warn":"");
      const td=document.createElement("td");
      const details=document.createElement("details");
      const summary=document.createElement("summary");summary.textContent="Werte anzeigen";
      const pre=document.createElement("pre");pre.textContent=JSON.stringify(device.telemetry,null,2);
      details.append(summary,pre);td.appendChild(details);row.appendChild(td);
      body.appendChild(row);
    }
    byId("device-info").textContent=data.total+" Geräte gefunden; "+data.devices.length+
      " angezeigt. Veraltete Daten ausdrücklich gekennzeichnet.";
    byId("message").textContent="Verbunden";
  } catch(e) {
    if(epoch!==sessionEpoch||request!==devicesRequest)return;
    byId("devices").replaceChildren();
    byId("device-cards").replaceChildren();
    byId("device-info").textContent="Keine Gerätedaten verfügbar.";
    byId("message").textContent="Details nicht verfügbar ("+e.message+").";
  }
}
byId("connect").addEventListener("click",()=>{
  const token=byId("token").value;
  if(!token){byId("message").textContent="Bitte Status-Token eingeben.";return;}
  sessionEpoch++;accessToken=token;byId("token").value="";updateDevices();updateCatalog();
});
byId("disconnect").addEventListener("click",()=>{
  sessionEpoch++;accessToken="";byId("token").value="";byId("devices").replaceChildren();
  byId("device-cards").replaceChildren();
  ["waylines","models","tasks","wayline-cards","model-cards","task-cards"].forEach(id=>byId(id).replaceChildren());
  byId("catalog-panel").hidden=true;
  ["wayline-count","model-count","task-count"].forEach(id=>byId(id).textContent="–");
  byId("device-info").textContent="Details getrennt.";byId("catalog-info").textContent="Bibliothek getrennt.";byId("message").textContent="Getrennt";
});
updateSummary();
setInterval(()=>{updateSummary();updateDevices();},intervalMs);
setInterval(updateCatalog,60000);
</script>
</body>
</html>"""


def render_page(refresh_every_seconds: int) -> str:
    if type(refresh_every_seconds) is not int or not 5 <= refresh_every_seconds <= 3600:
        raise ValueError("Invalid refresh interval")
    return (HTML.replace("__INTERVAL_SECONDS__", str(refresh_every_seconds))
                .replace("__INTERVAL_MILLISECONDS__", str(refresh_every_seconds * 1000)))
