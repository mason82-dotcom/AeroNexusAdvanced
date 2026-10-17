"""Auto-refreshing read-only fleet dashboard for trusted HTTPS LAN clients.

The frontend has no token form, cookie or credential storage. The backend
enforces an explicitly enabled, direct-to-Pi LAN policy.
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
.device-battery progress.caution{accent-color:#e8c06b}
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
<div class="subtle">Flottenstatus · Flugbefehle deaktiviert · <a href="/studio" style="color:#9cd2ff">Mission Studio für Chrome ↗</a> · <a href="/operations" style="color:#9cd2ff">Operations Center ↗</a> · <a href="/thermal" style="color:#9cd2ff">Thermal ↗</a> · <a href="/multispectral" style="color:#9cd2ff">Multispektral ↗</a> · <a href="/results" style="color:#9cd2ff">Ergebnisraster ↗</a></div></div>
<div class="meta">Automatische Anzeigeaktualisierung: __INTERVAL_SECONDS__ s<br>
<span id="timestamp">Noch keine Daten</span><br>
<span id="feed">Live-Feed: –</span></div>
</header>
<div class="meta" id="poll-health" role="status">Lokale Cloud-Verbindung wird geprüft.</div>
<section class="grid" aria-label="Flottenkennzahlen">
<div class="metric"><span>Geräte gesamt</span><b id="total">–</b></div>
<div class="metric"><span>Drohnen</span><b id="aircraft">–</b></div>
<div class="metric"><span>Fernsteuerungen</span><b id="controllers">–</b></div>
<div class="metric"><span>Aktuell online</span><b id="online">–</b></div>
<div class="metric"><span>Veraltete Telemetrie</span><b id="stale">–</b></div>
<div class="metric"><span>Fehlende/unklare Daten</span><b id="unknown">–</b></div>
<div class="metric"><span>HMS-Warnungen</span><b id="health">–</b></div>
</section>
<section class="panel" id="cloud-panel">
<h2>Lokaler DJI-Cloud-Server</h2>
<p class="subtle" id="cloud-overall" role="status">Prüfe Dienste…</p>
<div class="grid" id="cloud-services" aria-label="Dienste des lokalen Cloud-Servers"></div>
<p class="subtle" id="cloud-fleet">Verbundene Geräte werden geladen…</p>
</section>
<section class="panel">
<h2>Lokaler Flottenzugriff</h2>
<p class="subtle">Geräte, MQTT-Telemetrie und die Routenbibliothek des lokalen Pilot-2-Cloud-Servers werden im freigegebenen HTTPS-Heimnetz gelesen.</p>
<span id="message" class="meta" role="status">Lade lokale Cloud-Daten…</span>
</section>
<section class="panel">
<h2>Geräte und Telemetrie</h2>
<div class="subtle" id="device-info">Die Daten werden über die lokale AeroNexus-Schnittstelle geladen.</div>
<div id="device-cards" class="device-grid" aria-label="Gerätekarten"><div class="device-empty">Gerätekarten werden geladen…</div></div>
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
<h2>Lokale Pilot-2-Missionsbibliothek</h2>
<p class="subtle">Routen aus dem lokalen DJI-Cloud-Server. Diese Ansicht liest nur Metadaten und sendet keine Missionen oder Flugbefehle.</p>
<div class="subtle" id="catalog-info" role="status">Lese lokale Cloud-Waylines…</div>
<section class="catalog-section" aria-labelledby="wayline-heading">
<div class="catalog-heading"><h3 id="wayline-heading">Cloud-Waylines</h3><span class="catalog-count" id="wayline-count">–</span></div>
<div class="catalog-grid" id="wayline-cards"></div>
<details class="catalog-raw"><summary>Technische Routentabelle anzeigen</summary>
<div class="scroller"><table class="compact"><thead><tr><th>Name</th><th>Fluggerät</th><th>Typ</th><th>Geändert (UTC)</th></tr></thead><tbody id="waylines"></tbody></table></div>
</details></section>
</section>
<footer>Zeitstempel = Eingang bei AeroNexus, nicht DJI-Ereigniszeit. Veraltete Messwerte sind keine Live-Werte. Die Anzeige ruft selbst keine DJI-Endpunkte auf.</footer>
</main>
<script>
"use strict";
const intervalMs = __INTERVAL_MILLISECONDS__;
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
  "0-77-0":"Mavic 3E","0-77-1":"Mavic 3T","0-77-2":"Mavic 3M","0-77-3":"Mavic 3TA","0-91-0":"Matrice 3D","0-91-1":"Matrice 3TD",
  "0-67-0":"Matrice 30","0-67-1":"Matrice 30T","0-89-0":"Matrice 350 RTK","0-60-0":"Matrice 300 RTK"};
const templateNames={waypoint:"Wegpunkte",mapping_2d:"Fl\u00e4che 2D",mapping_3d:"Schr\u00e4g 3D",
  mapping_strip:"Korridor",facade:"Fassade",solid:"K\u00f6rper",mapping_gobject:"Objekt"};
function date(sec){return sec?new Date(sec*1000).toISOString().slice(0,16).replace("T"," ")+" UTC":null;}
const localRouteStates={
  connected:"verbunden",not_configured:"nicht eingerichtet",awaiting_browser_session:"Warte auf vorhandene Cloud-Sitzung",
  authentication_required:"Cloud-Anmeldung abgelaufen",configuration_error:"Konfigurationsfehler",
  unavailable:"Cloud-Server nicht erreichbar",upstream_error:"Cloud-Server antwortet fehlerhaft",
  invalid_response:"Ungültige Cloud-Antwort",business_error:"Cloud-Dienst meldet Fehler",
  inventory_changed:"Routenbestand während des Abrufs verändert"
};
function catalogTag(card,label,value){
  if(value===null||value===undefined||value==="")return;
  const tags=card.querySelector(".catalog-tags");
  cardEl(tags,"span","catalog-tag",label+": "+value);
}
function renderLocalWaylines(data) {
  const body=byId("waylines"),cards=byId("wayline-cards");
  body.replaceChildren();cards.replaceChildren();
  const connected=data.state==="connected";
  const routes=connected?data.waylines:[];
  for(const route of routes){
    if(!route||typeof route.name!=="string")throw new Error("Ungültiger Routeneintrag");
    const model=modelNames[route.device_model_key]||route.device_model_key||"Modell unbekannt";
    const kinds=(route.template_types||[]).map(t=>templateNames[t]||t).join(", ")||
      ((route.template_type_codes||[]).length?"Unbekannter DJI-Template-Typ":"Nicht angegeben");
    const changed=typeof route.updated_at_ms==="number"?
      date(Math.floor(route.updated_at_ms/1000)):null;
    const card=cardEl(cards,"article","catalog-card");
    cardEl(card,"h4","",route.name);
    cardEl(card,"div","catalog-meta",model);
    cardEl(card,"div","catalog-tags");
    catalogTag(card,"Typ",kinds);
    catalogTag(card,"Geändert",changed);
    const row=document.createElement("tr");
    for(const value of [route.name,model,kinds,changed]){
      const cell=document.createElement("td");cell.textContent=value||"–";row.appendChild(cell);
    }
    body.appendChild(row);
  }
  byId("wayline-count").textContent=connected?routes.length:"–";
  if(!routes.length)cardEl(cards,"div","device-empty",connected?
    "Keine Cloud-Waylines in diesem Workspace.":"Keine aktuellen Routen: "+(localRouteStates[data.state]||"Quelle unbekannt")+".");
  let status="Lokaler Pilot-2-Cloud-Server: "+(localRouteStates[data.state]||"Status unbekannt");
  if(connected){
    status+=" · "+routes.length+" Rout(en)";
    if(typeof data.reported_total==="number")status+=" von "+data.reported_total+" gemeldet";
    if(data.pagination_complete===false)status+=" · Bestand unvollständig (Abruflimit)";
    if(data.updated_at)status+=" · Stand: "+data.updated_at;
  }
  byId("catalog-info").textContent=status;
}
async function updateCatalog() {
  const epoch=sessionEpoch,request=++catalogRequest;
  try{
    const r=await fetch("/api/v1/local-cloud/waylines",{cache:"no-store"});
    if(!r.ok)throw new Error("HTTP "+r.status);
    const data=await r.json();
    if(epoch!==sessionEpoch||request!==catalogRequest)return;
    if(typeof data.state!=="string"||!Array.isArray(data.waylines))throw new Error("Ungültige Cloud-Antwort");
    renderLocalWaylines(data);
    byId("catalog-panel").hidden=false;
  }catch(e){
    if(epoch!==sessionEpoch||request!==catalogRequest)return;
    byId("waylines").replaceChildren();
    byId("wayline-cards").replaceChildren();
    byId("wayline-count").textContent="–";
    byId("catalog-panel").hidden=false;
    byId("catalog-info").textContent="Lokale Routenbibliothek nicht abrufbar ("+e.message+").";
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
      const bar=cardEl(wrap,"progress",battery<=20?"low":battery<=30?"caution":"");
      bar.max=100;bar.value=battery;
      bar.setAttribute("aria-label","Akkustand "+battery.toFixed(0)+" Prozent");
      if(battery<=30)cardEl(wrap,"div","hms-secondary",
        "AeroNexus-Farbhinweis: niedriger Akkustand. Keine DJI-Flugfreigabe oder Warnschwelle.");
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
      cardEl(section,"div","hms-secondary",
        device.freshness==="fresh"?"Stand der letzten HMS-Abfrage; DJI-Ereigniszeit unbekannt.":
        "HMS-Stand möglicherweise veraltet; letzte DJI-Abfrage unbekannt.");
      const list=cardEl(section,"div","hms-list");
      for(const alert of alerts.slice(0,5)){
        const entry=cardEl(list,"div","hms-entry");
        const level=alert.level==="warning"?"Warnung":alert.level==="reminder"?"Hinweis":
          alert.level==="notification"?"Information":"Nicht klassifiziert";
        entry.dataset.level=alert.level||"unknown";
        const title=cardEl(entry,"div","hms-heading");
        cardEl(title,"b","",level);
        if(alert.imminent===true)cardEl(title,"span","bad","· Dringend laut DJI");
        if(alert.in_the_sky===true)cardEl(title,"span","warn","· Im Flug gemeldet");
        if(alert.code)cardEl(entry,"code","hms-code","Code: "+alert.code);
        cardEl(entry,"div","hms-description",
          alert.message&&alert.message!==alert.code?alert.message:
          "DJI hat für diesen HMS-Code keinen Beschreibungstext übermittelt.");
      }
      if(alerts.length>5)cardEl(section,"div","hms-secondary",
        "Weitere "+(alerts.length-5)+" Meldung(en) in der technischen Tabelle.");
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
    const feed=data.live_feed||{state:"disabled"};
    byId("timestamp").textContent="Letzter Aufruf: "+data.server_time+" · DJI Cloud API lokal";
    byId("poll-health").textContent="MQTT: "+(feedStates[feed.state]||feed.state||"unbekannt")+
      " · Letzte gültige Nachricht: "+(feed.last_message_at||"noch keine")+
      " · "+(feed.accepted??0)+" akzeptiert / "+(feed.rejected??0)+" verworfen"+
      " / "+(feed.outdated??0)+" veraltete Duplikate"+
      " · Telemetrie-Frischegrenze: "+data.stale_after_seconds+" s";
    byId("feed").textContent="Live-Feed (DJI Cloud API): "+(feedStates[feed.state]||"unbekannt")+
      (feed.state==="disabled"?"":" · "+feed.accepted+" ok / "+feed.rejected+" verworfen");
  } catch (_) {byId("timestamp").textContent="Status-API nicht erreichbar";byId("poll-health").textContent="Cloud-API-Status nicht erreichbar";}
}
async function updateCloud() {
  try {
    const r=await fetch("/api/v1/cloud/stack",{cache:"no-store"});
    if(!r.ok)throw new Error("HTTP "+r.status);
    const data=await r.json();
    const box=byId("cloud-services");box.replaceChildren();
    const names={up:"erreichbar",down:"nicht erreichbar",error:"Fehler"};
    for(const [key,svc] of Object.entries(data.services||{})){
      const card=document.createElement("div");card.className="metric";
      const label=document.createElement("span");label.textContent=svc.label;
      const value=document.createElement("b");value.style.fontSize="17px";
      value.textContent=(svc.state==="up"?"● ":"○ ")+(names[svc.state]||svc.state)+
        (key==="mediamtx"&&svc.state==="up"?" · "+svc.streams+" Stream(s)":"");
      value.style.color=svc.state==="up"?"#83e5ba":key==="mediamtx"?"#f1ca82":"#ffb0bb";
      card.append(label,value);box.appendChild(card);
    }
    const fleet=data.fleet||{devices:[]};
    const online=fleet.devices.filter(d=>d.online);
    byId("cloud-overall").textContent=(data.overall==="ok"?"Alle Kerndienste erreichbar":"Mindestens ein Kerndienst gestört")+
      " · MQTT-Feed: "+(feedStates[fleet.feed_state]||fleet.feed_state);
    byId("cloud-fleet").textContent=online.length?"Verbunden: "+online.map(d=>
      (d.kind==="controller"?"Fernsteuerung ":"Fluggerät ")+d.name).join(" · "):
      "Keine Fernsteuerung verbunden"+(fleet.devices.length?" (bekannt: "+fleet.devices.length+", zuletzt "+
      (fleet.last_message_at||"–")+")":"");
  } catch (error) {byId("cloud-overall").textContent="Cloud-Server-Status nicht abrufbar: "+error.message;}
}
async function updateDevices() {
  const epoch=sessionEpoch,request=++devicesRequest;
  try {
    const r=await fetch("/api/v1/status/devices?limit=200",{cache:"no-store"});
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
// All dashboard sections load automatically for trusted HTTPS LAN browsers.
byId("message").textContent="Gerätedaten werden automatisch geladen…";
updateDevices();
updateCatalog();
updateSummary();
setInterval(()=>{updateSummary();updateDevices();},intervalMs);
updateCloud();setInterval(updateCloud,15000);
setInterval(updateCatalog,60000);
</script>
</body>
</html>"""


def render_page(refresh_every_seconds: int) -> str:
    if type(refresh_every_seconds) is not int or not 5 <= refresh_every_seconds <= 3600:
        raise ValueError("Invalid refresh interval")
    return (HTML.replace("__INTERVAL_SECONDS__", str(refresh_every_seconds))
                .replace("__INTERVAL_MILLISECONDS__", str(refresh_every_seconds * 1000)))
