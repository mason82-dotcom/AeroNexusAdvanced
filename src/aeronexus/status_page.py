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
<div class="scroller">
<table>
<thead><tr><th>Provider / Projekt</th><th>Gerät</th><th>Typ</th><th>Frische</th><th>Empfangen (UTC)</th><th>Online</th><th>Kurzwerte</th><th>Zustand (HMS)</th><th>Messwerte</th></tr></thead>
<tbody id="devices"></tbody>
</table>
</div>
</section>
<section class="panel">
<h2>FlightHub-Bibliothek</h2>
<div class="subtle" id="catalog-info">Nach dem Verbinden: Routen, Karten-Modelle und Flugaufträge der FlightHub-Projekte (nur lesen).</div>
<h3>Routen</h3>
<div class="scroller"><table class="compact"><thead><tr><th>Projekt</th><th>Name</th><th>Typ</th><th>Fluggerät</th><th>Linsen</th><th>Geändert</th><th>Größe</th></tr></thead><tbody id="waylines"></tbody></table></div>
<h3>Karten-Modelle</h3>
<div class="scroller"><table class="compact"><thead><tr><th>Projekt</th><th>Name</th><th>Typ</th><th>Auf Karte</th><th>Geändert</th><th>Größe</th></tr></thead><tbody id="models"></tbody></table></div>
<h3>Flugaufträge</h3>
<div class="scroller"><table class="compact"><thead><tr><th>Projekt</th><th>Name</th><th>Art</th><th>Status</th><th>Gestartet</th><th>Wegpunkte</th><th>Flugspur</th></tr></thead><tbody id="tasks"></tbody></table></div>
</section>
<footer>Zeitstempel = Eingang bei AeroNexus, nicht DJI-Ereigniszeit. Veraltete Messwerte sind keine Live-Werte. Die Anzeige ruft selbst keine DJI-Endpunkte auf.</footer>
</main>
<script>
"use strict";
const intervalMs = __INTERVAL_MILLISECONDS__;
let accessToken = "";
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
  try{
    const r=await fetch("/api/v1/flighthub/projects/"+encodeURIComponent(project)+"/tasks/"+encodeURIComponent(task)+"/track",
      {cache:"no-store",headers:{"Authorization":"Bearer "+accessToken}});
    if(!r.ok)throw new Error("HTTP "+r.status);
    const url=URL.createObjectURL(new Blob([await r.text()],{type:"application/geo+json"}));
    const a=document.createElement("a");a.href=url;a.download=(name||"flugspur").replace(/[^A-Za-z0-9_-]+/g,"_")+".geojson";
    document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){byId("catalog-info").textContent="Flugspur nicht verf\u00fcgbar ("+e.message+").";}
}
async function updateCatalog() {
  if(!accessToken)return;
  const lists={waylines:byId("waylines"),models:byId("models"),tasks:byId("tasks")};
  try{
    const r=await fetch("/api/v1/flighthub/catalog",{cache:"no-store",headers:{"Authorization":"Bearer "+accessToken}});
    if(!r.ok)throw new Error("HTTP "+r.status);
    const data=await r.json();
    Object.values(lists).forEach(b=>b.replaceChildren());
    for(const p of data.projects){
      const pname=p.name||p.project_id;
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
    for(const [key,b] of Object.entries(lists))if(!b.children.length)placeholder(b,7,key==="tasks"?
      "Keine Flugauftr\u00e4ge in den letzten "+((data.projects[0]||{}).task_window_days||30)+" Tagen":"Keine Eintr\u00e4ge");
    byId("catalog-info").textContent=data.updated_at?"Stand: "+data.updated_at+" (Aktualisierung alle paar Minuten)":
      "Noch nicht geladen (FlightHub-Polling aus oder erster Abruf l\u00e4uft).";
  }catch(e){byId("catalog-info").textContent="Bibliothek nicht verf\u00fcgbar ("+e.message+").";}
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
    const feed=data.live_feed||{state:"disabled"};
    byId("feed").textContent="Live-Feed (DJI Cloud API): "+(feedStates[feed.state]||"unbekannt")+
      (feed.state==="disabled"?"":" · "+feed.accepted+" ok / "+feed.rejected+" verworfen");
  } catch (_) {byId("timestamp").textContent="Status-API nicht erreichbar";}
}
async function updateDevices() {
  if(!accessToken)return;
  try {
    const r=await fetch("/api/v1/status/devices?limit=200",{
      cache:"no-store",headers:{"Authorization":"Bearer "+accessToken}
    });
    if(!r.ok)throw new Error("HTTP "+r.status);
    const data=await r.json();
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
    byId("devices").replaceChildren();
    byId("device-info").textContent="Keine Gerätedaten verfügbar.";
    byId("message").textContent="Details nicht verfügbar ("+e.message+").";
  }
}
byId("connect").addEventListener("click",()=>{
  const token=byId("token").value;
  if(!token){byId("message").textContent="Bitte Status-Token eingeben.";return;}
  accessToken=token;byId("token").value="";updateDevices();updateCatalog();
});
byId("disconnect").addEventListener("click",()=>{
  accessToken="";byId("token").value="";byId("devices").replaceChildren();
  ["waylines","models","tasks"].forEach(id=>byId(id).replaceChildren());
  byId("device-info").textContent="Details getrennt.";byId("message").textContent="Getrennt";
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
