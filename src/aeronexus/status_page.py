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
table{border-collapse:collapse;width:100%;min-width:930px;font-size:13px}th{text-align:left;color:#b8cae0;font-weight:600}
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
<span id="timestamp">Noch keine Daten</span></div>
</header>
<section class="grid" aria-label="Flottenkennzahlen">
<div class="metric"><span>Geräte gesamt</span><b id="total">–</b></div>
<div class="metric"><span>Drohnen</span><b id="aircraft">–</b></div>
<div class="metric"><span>Fernsteuerungen</span><b id="controllers">–</b></div>
<div class="metric"><span>Aktuell online</span><b id="online">–</b></div>
<div class="metric"><span>Veraltete Telemetrie</span><b id="stale">–</b></div>
<div class="metric"><span>Fehlende/unklare Daten</span><b id="unknown">–</b></div>
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
<thead><tr><th>Provider / Projekt</th><th>Gerät</th><th>Typ</th><th>Frische</th><th>Empfangen (UTC)</th><th>Online</th><th>Messwerte</th></tr></thead>
<tbody id="devices"></tbody>
</table>
</div>
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
    byId("timestamp").textContent="Letzter Aufruf: "+data.server_time+" · Polling: "+data.polling;
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
  accessToken=token;byId("token").value="";updateDevices();
});
byId("disconnect").addEventListener("click",()=>{
  accessToken="";byId("token").value="";byId("devices").replaceChildren();
  byId("device-info").textContent="Details getrennt.";byId("message").textContent="Getrennt";
});
updateSummary();
setInterval(()=>{updateSummary();updateDevices();},intervalMs);
</script>
</body>
</html>"""


def render_page(refresh_every_seconds: int) -> str:
    if type(refresh_every_seconds) is not int or not 5 <= refresh_every_seconds <= 3600:
        raise ValueError("Invalid refresh interval")
    return (HTML.replace("__INTERVAL_SECONDS__", str(refresh_every_seconds))
                .replace("__INTERVAL_MILLISECONDS__", str(refresh_every_seconds * 1000)))
