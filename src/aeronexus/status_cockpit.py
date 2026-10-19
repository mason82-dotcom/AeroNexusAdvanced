"""Read-only, inline DJI Cloud API telemetry cockpit assets.

The protected /api/v1/status/devices response is the only telemetry source.
No third-party tiles, commands, tokens, WebSockets or persistent browser storage.
"""

COCKPIT_CSS = r"""
/* Live cockpit: self-contained, responsive, no external assets. */
body{padding:20px}main{max-width:1600px}
.cockpit-shell{margin:20px 0 26px;padding:22px;border:1px solid #38617c;border-radius:20px;
  background:linear-gradient(145deg,#102a3b 0%,#0c1d30 68%,#0f2335 100%);box-shadow:0 16px 60px #050e1970}
.cockpit-top{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap}
.cockpit-top h2{font-size:clamp(22px,3vw,32px);letter-spacing:-.04em;margin:4px 0 7px;color:#f4f9ff}
.cockpit-caption{font-size:12px;color:#9fbcd0;max-width:780px;line-height:1.6}
.cockpit-live{align-self:flex-start;font-size:12px;border:1px solid #50677e;border-radius:30px;
  background:#213247;color:#e0eaf4;padding:8px 12px;font-weight:700}
.cockpit-live[data-state="live"]{background:#14382e;border-color:#368a70;color:#9bf1cf}
.cockpit-live[data-state="offline"],.cockpit-live[data-state="error"]{background:#462933;color:#ffbcb4;border-color:#b05d67}
.cockpit-live[data-state="stale"]{background:#3c3422;color:#ffe0a5;border-color:#987646}
.cockpit-toolbar{display:flex;flex-wrap:wrap;align-items:end;gap:12px;margin:18px 0}
.cockpit-toolbar label{display:grid;gap:5px;font-size:12px;color:#bed0e1;font-weight:600;flex:1;min-width:200px}
.cockpit-toolbar select{width:100%;background:#10263a;border:1px solid #52728c;border-radius:9px;
  padding:11px 13px;min-height:44px;color:#f0f8ff;font:inherit}
.cockpit-toolbar button{min-height:44px;background:#2977a7;border:1px solid #4a9ac6}
.cockpit-toolbar select:focus-visible,.cockpit-toolbar button:focus-visible{outline:2px solid #9cdbff;outline-offset:2px}
.cockpit-banner{font-size:13px;color:#b4d0df;padding:10px 14px;margin:10px 0;border-left:3px solid #498bb3;background:#0c2234}
.cockpit-banner[data-tone="warn"]{border-color:#dba858;color:#f8daa3}
.cockpit-banner[data-tone="bad"]{border-color:#db8d8d;color:#ffd1d1}
.cockpit-hero{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin:16px 0}
.cockpit-gauge{min-width:0;padding:15px 12px;border:1px solid #315371;border-radius:13px;background:#132d43;position:relative}
.cockpit-gauge .gauge-label{display:block;text-transform:uppercase;letter-spacing:.07em;font-size:10px;color:#a5c8dd}
.cockpit-gauge strong{display:block;font-weight:750;font-variant-numeric:tabular-nums;font-size:clamp(17px,2.2vw,29px);
  margin:11px 0 5px;color:#f1faff;line-height:1.15;overflow-wrap:anywhere}
.cockpit-gauge small{font-size:11px;color:#9ab5c8}
.cockpit-layout{display:grid;grid-template-columns:minmax(0,1.12fr) minmax(0,.88fr);gap:14px}
.cockpit-panel{min-width:0;border:1px solid #34546d;background:#122538;border-radius:13px;padding:15px}
.cockpit-panel h3{font-size:15px;margin:0 0 12px;color:#eff7ff}
.cockpit-panel .module-note{font-size:11px;color:#93b2cb;margin:-3px 0 11px;line-height:1.5}
.cockpit-pills{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}
.cockpit-pill{border:1px solid #3d6b80;border-radius:8px;padding:5px 9px;font-size:11px;color:#d6ecf9}
.cockpit-items{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.cockpit-item{min-width:0;padding:10px;background:#0d2032;border:1px solid #28435b;border-radius:9px}
.cockpit-item span{display:block;font-size:10px;color:#9fbed5;line-height:1.4}
.cockpit-item b{display:block;font-size:14px;color:#e9f5ff;margin-top:5px;overflow-wrap:anywhere;font-weight:650}
.cockpit-item small{display:block;color:#839eaf;margin-top:4px;font-size:10px}
.cockpit-modules{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:14px}
.cockpit-track{width:100%;height:215px;display:block;border:1px solid #294d67;border-radius:10px;
  background:repeating-linear-gradient(0deg,transparent 0,transparent 31px,#37607835 32px),
  repeating-linear-gradient(90deg,transparent 0,transparent 31px,#37607835 32px),#0b2030}
.cockpit-track .trail{stroke:#73d4c0;stroke-width:2;fill:none;stroke-linecap:round;stroke-linejoin:round}
.cockpit-track .marker{fill:#b7f5e5;stroke:#1d5d62;stroke-width:2}
.cockpit-chart-wrap{display:grid;gap:11px}
.cockpit-chart{width:100%;height:75px;border:1px solid #28455d;border-radius:8px;background:#0a2133}
.cockpit-chart path{fill:none;stroke:#76c8eb;stroke-width:2;stroke-linecap:round}
.cockpit-chart text{fill:#abc4d7;font-size:10px}
.cockpit-chart-title{display:flex;justify-content:space-between;font-size:12px;gap:9px;color:#c4d9e9}
.cockpit-fieldlist{display:grid;gap:6px;max-height:300px;overflow:auto}
.cockpit-fieldrow{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px;align-items:start;font-size:12px;
  border-bottom:1px solid #28465c;padding:7px 2px}
.cockpit-fieldrow span{overflow-wrap:anywhere}
.cockpit-fieldrow .fresh{color:#86dfbb}.cockpit-fieldrow .stale{color:#ffd08d}
.cockpit-fieldrow .skew{color:#ffaaaa}.cockpit-fieldrow .muted{color:#95b2c8}
.cockpit-field-focus{display:grid;gap:8px;margin:12px 0 16px}
.cockpit-focus-row{border:1px solid #36526a;border-radius:9px;background:#0d2032;padding:10px;
  display:grid;gap:5px;overflow-wrap:anywhere}
.cockpit-focus-row[data-state="live"]{border-left:4px solid #5bbe97}
.cockpit-focus-row[data-state="last-known"]{border-left:4px solid #edba6f;background:#302b23}
.cockpit-focus-row[data-state="not-observed"]{border-left:4px solid #7f94a8}
.cockpit-focus-title{font-size:12px;color:#c9dff0;font-weight:650}
.cockpit-focus-state{font-size:11px;font-weight:700;color:#a6dcca}
.cockpit-focus-row[data-state="last-known"] .cockpit-focus-state{color:#ffce8c}
.cockpit-focus-row[data-state="not-observed"] .cockpit-focus-state{color:#b5c4d2}
.cockpit-focus-row b{font-size:14px;color:#f2f8ff}
.cockpit-focus-row small{font-size:11px;color:#aec6da;line-height:1.5}
.cockpit-empty{font-size:12px;color:#adc5d8;line-height:1.7}
.cockpit-legend{font-size:11px;color:#93aec5;margin-top:16px;line-height:1.6}
.legacy-status{max-width:none!important;margin:18px 0}
.legacy-status>summary{color:#cde6fa;cursor:pointer;font-weight:700;font-size:15px;padding:12px 16px;
  border:1px solid #355a73;border-radius:11px;background:#152b40}
.legacy-status>.panel{margin:14px 0}
@media(max-width:1150px){.cockpit-hero{grid-template-columns:repeat(3,minmax(0,1fr))}
  .cockpit-modules{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){body{padding:10px}.cockpit-shell{padding:13px;border-radius:14px}
  .cockpit-layout{grid-template-columns:minmax(0,1fr)}.cockpit-modules{grid-template-columns:minmax(0,1fr)}
  .cockpit-hero{grid-template-columns:repeat(2,minmax(0,1fr))}.cockpit-gauge{padding:11px}
  .cockpit-items{grid-template-columns:repeat(2,minmax(0,1fr))}.cockpit-top h2{font-size:25px}
  .cockpit-toolbar{align-items:stretch}.cockpit-toolbar button{width:100%}}
@media(max-width:350px){.cockpit-items{grid-template-columns:1fr}
  .cockpit-hero{grid-template-columns:1fr 1fr}.cockpit-gauge strong{font-size:18px}}
"""

COCKPIT_HTML = r"""
<section class="cockpit-shell" id="cockpit" aria-label="Live-Telemetrie-Cockpit">
  <div class="cockpit-top">
    <div>
      <div class="eyebrow">DJI Cloud API · Read-only · Live-Diagnose</div>
      <h2>Fluggerät &amp; Fernsteuerung</h2>
      <div class="cockpit-caption">Alle verfügbaren Messwerte der gewählten DJI-Quelle.
        Pro Feld wird die Aktualität geprüft. Keine Flugfreigabe oder Gerätebedienung.</div>
    </div>
    <span class="cockpit-live" id="cockpit-live" data-state="stale" role="status">Verbindung wird geprüft</span>
  </div>
  <div class="cockpit-toolbar">
    <label for="cockpit-device">Gerät / Datenquelle
      <select id="cockpit-device" aria-label="Telemetriegerät auswählen">
        <option value="">Noch keine Geräte</option>
      </select>
    </label>
    <button id="cockpit-refresh" type="button">Jetzt aktualisieren</button>
    <span class="meta" id="cockpit-interval">Gerätedaten: max. alle 5 s</span>
  </div>
  <div class="cockpit-banner" id="cockpit-banner" role="status" data-tone="warn">
    Warte auf geschützte Telemetriedaten. Fehlende Werte werden nicht geschätzt.
  </div>
  <section class="cockpit-hero" aria-label="Primäre Livewerte">
    <div class="cockpit-gauge"><span class="gauge-label">Akku</span><strong id="cockpit-battery">–</strong><small id="cockpit-battery-note">Nicht übermittelt</small></div>
    <div class="cockpit-gauge"><span class="gauge-label">Flug- / RC-Modus</span><strong id="cockpit-mode">–</strong><small id="cockpit-mode-note">Nicht übermittelt</small></div>
    <div class="cockpit-gauge"><span class="gauge-label">Höhe Startbezug</span><strong id="cockpit-altitude">–</strong><small id="cockpit-altitude-note">Nicht übermittelt</small></div>
    <div class="cockpit-gauge"><span class="gauge-label">Horizontaltempo</span><strong id="cockpit-speed">–</strong><small id="cockpit-speed-note">Nicht übermittelt</small></div>
    <div class="cockpit-gauge"><span class="gauge-label">RTK / GNSS</span><strong id="cockpit-rtk">–</strong><small id="cockpit-rtk-note">Nicht übermittelt</small></div>
    <div class="cockpit-gauge"><span class="gauge-label">Eingangsalter</span><strong id="cockpit-age">–</strong><small id="cockpit-age-note">Kein Live-Nachweis</small></div>
  </section>
  <div class="cockpit-layout">
    <section class="cockpit-panel" aria-labelledby="cockpit-nav-title">
      <h3 id="cockpit-nav-title">Position, Orientierung &amp; Flugzustand</h3>
      <div class="cockpit-items" id="cockpit-navigation"></div>
      <p class="module-note" id="cockpit-coordinates">Keine bestätigten aktuellen Koordinaten.</p>
    </section>
    <section class="cockpit-panel" aria-labelledby="cockpit-track-title">
      <h3 id="cockpit-track-title">GNSS-Verlauf im Browser</h3>
      <p class="module-note">Lokale relative Darstellung ohne Kartenkacheln und ohne externe Dienste.</p>
      <svg class="cockpit-track" id="cockpit-track" viewBox="0 0 480 210" role="img"
        aria-label="Relative Positionspunkte dieser Browsersitzung"></svg>
      <p class="module-note" id="cockpit-track-info">Noch keine gültigen Live-Positionspunkte.</p>
    </section>
  </div>
  <div class="cockpit-modules">
    <section class="cockpit-panel"><h3>Akku &amp; Rückkehrreserve</h3><div class="cockpit-items" id="cockpit-energy"></div></section>
    <section class="cockpit-panel"><h3>Fernsteuerung &amp; Funkstrecke</h3><div class="cockpit-items" id="cockpit-radio"></div></section>
    <section class="cockpit-panel"><h3>Kamera, Zoom &amp; IR</h3><div class="cockpit-items" id="cockpit-camera"></div></section>
    <section class="cockpit-panel"><h3>Nutzlast &amp; Gimbal</h3><div class="cockpit-items" id="cockpit-payload"></div></section>
    <section class="cockpit-panel"><h3>Grenzen, Wind &amp; Sensoren</h3><div class="cockpit-items" id="cockpit-safety"></div></section>
    <section class="cockpit-panel"><h3>HMS &amp; Systemhinweise</h3><div id="cockpit-hms" class="cockpit-fieldlist"></div></section>
    <section class="cockpit-panel"><h3>Verlauf · nur Browser-RAM</h3>
      <p class="module-note">Maximal 60 eindeutig neu empfangene Messpunkte, nicht als Flugprotokoll geeignet.</p>
      <div id="cockpit-trends" class="cockpit-chart-wrap"></div></section>
    <section class="cockpit-panel"><h3>Gerätestatus &amp; Datengrundlage</h3><div class="cockpit-items" id="cockpit-diagnostics"></div></section>
    <section class="cockpit-panel"><h3>OSD-/State-Feldqualität</h3>
      <p class="module-note">Aktuell, letzter bekannter Wert (nicht live) oder nicht beobachtet.
        Empfangszeiten stammen vom AeroNexus-Server; historische RTH-Werte sind keine Grundlage für Flugentscheidungen.</p>
      <div class="cockpit-field-focus" id="cockpit-field-focus" aria-label="Ausgewählte DJI-State-Felder"></div>
      <p class="module-note">Alle beobachteten DJI-Eigenschaften · Kanal und Feldalter:</p>
      <div class="cockpit-fieldlist" id="cockpit-fields"></div></section>
  </div>
  <p class="cockpit-legend">„Live“ bedeutet: Gerät online, Quelle und Einzelfeld höchstens 15 Sekunden alt. Die Server-Frischegrenze kann großzügiger sein.
    Ohne gültige Positionsdaten wird keine Position gezeichnet. HMS kann aus einem anderen Datenpfad stammen;
    eine OSD-Verbindung bestätigt keine flugsichere Verbindung.</p>
</section>
"""

COCKPIT_JS = r"""
/* Protected status endpoint -> local-only UI. No DJI control actions. */
let cockpitRows=[],cockpitChosen="",cockpitError=null;
let cockpitOptionsSignature=null;
const cockpitHistory=new Map();
const cockpitMaxSamples=60;
const cockpitLiveLimitSeconds=15;
function cockpitKey(d){return JSON.stringify([d.provider,d.project_id,d.device_id]);}
function cockpitNumber(v,dec=0,unit=""){
  return typeof v==="number"&&Number.isFinite(v)
    ? v.toFixed(dec)+(unit?" "+unit:""):null;
}
function cockpitPath(obj,path){
  return path.split(".").reduce((o,key)=>o!==null&&o!==undefined?o[key]:undefined,obj);
}
function cockpitClock(dev,path){
  const clocks=dev.field_status||{};
  if(Object.prototype.hasOwnProperty.call(clocks,path))return clocks[path];
  const parts=path.split(".");
  while(parts.length>1){
    parts.pop();
    const key=parts.join(".");
    if(Object.prototype.hasOwnProperty.call(clocks,key))return clocks[key];
  }
  return null;
}
function cockpitIsLive(dev){
  const age=dev&&dev.age_seconds;
  return Boolean(dev&&dev.freshness==="fresh"&&dev.online===true
    &&typeof age==="number"&&Number.isFinite(age)
    &&age>=0&&age<=cockpitLiveLimitSeconds);
}
function cockpitRead(dev,path){
  if(!cockpitIsLive(dev))return null;
  const clock=cockpitClock(dev,path);
  if(clock){
    if(clock.freshness!=="fresh")return null;
    const ages=[clock.age_seconds,clock.source_age_seconds]
      .filter(x=>typeof x==="number"&&Number.isFinite(x));
    if(!ages.length||Math.max(...ages)>cockpitLiveLimitSeconds)return null;
  }
  const raw=cockpitPath(dev.telemetry||{},path);
  return raw===undefined?null:raw;
}
function cockpitStatusText(dev){
  if(!dev)return "Kein Gerät ausgewählt";
  if(cockpitError)return "API nicht erreichbar";
  if(dev.freshness==="stale")return "Telemetrie veraltet";
  if(dev.freshness==="clock_skew")return "Quellzeit unplausibel";
  if(dev.freshness==="missing")return "Keine Telemetrie";
  if(dev.freshness==="unknown_age")return "Zeit unbekannt";
  if(dev.online===false)return "Gerät offline";
  if(dev.online!==true)return "Online-Status unbekannt";
  if(!cockpitIsLive(dev))return "OSD-Empfang älter als 15 s";
  return "Live · Empfang bestätigt";
}
function cockpitSourceLabel(category){
  return ({controller_a:"Fernsteuerung A",controller_b:"Fernsteuerung B",
    browser:"Cloud-Browser",unassigned:"Nicht zugewiesen",other:"Andere/unklar"})[category]||null;
}
function cockpitMode(dev){
  if(dev.kind==="aircraft"){
    const raw=cockpitRead(dev,"flight_mode_code");
    return raw===null?null:(flightModes[raw]||"DJI-Code "+raw);
  }
  const code=cockpitRead(dev,"cloud_details.drc_link_state_code");
  return code===null?null:({0:"DRC getrennt",1:"DRC-Aufbau",2:"DRC verbunden"})[code]||"DRC-Code "+code;
}
function cockpitRtk(dev){
  const raw=cockpitRead(dev,"rtk_state");
  if(raw===null)return null;
  return ({'is_fixed:fixing_successful':"RTK-Fix", 'is_fixed:not_started':"Nicht gestartet",
    'is_fixed:fixing':"Fix läuft",'is_fixed:fixing_failed':"Fix fehlgeschlagen"})[raw]||"RTK-Code vorhanden";
}
function cockpitAge(dev){
  return dev&&typeof dev.age_seconds==="number"&&Number.isFinite(dev.age_seconds)&&dev.age_seconds>=0
    ? Math.floor(dev.age_seconds)+" s":null;
}
function cockpitSetGauge(id,value,note){
  byId("cockpit-"+id).textContent=value===null||value===undefined?"–":String(value);
  byId("cockpit-"+id+"-note").textContent=note;
}
function cockpitRawValue(value){
  if(value===null||value===undefined)return null;
  if(typeof value==="boolean")return value?"Ein":"Aus";
  if(typeof value==="number")return Number.isFinite(value)?String(value):null;
  if(typeof value==="string")return value;
  return null;
}
function cockpitItem(parent,label,value,note){
  if(value===null||value===undefined||value==="")return;
  const el=cardEl(parent,"div","cockpit-item");
  cardEl(el,"span","",label);
  cardEl(el,"b","",value);
  if(note)cardEl(el,"small","",note);
}
function cockpitRowsFor(id,rows,dev){
  const parent=byId(id);
  parent.replaceChildren();
  let count=0;
  for(const [label,path,formatter] of rows){
    const raw=cockpitRead(dev,path);
    if(raw===null||raw===undefined)continue;
    const val=formatter?formatter(raw):cockpitRawValue(raw);
    if(val===null||val===undefined)continue;
    const clock=cockpitClock(dev,path);
    cockpitItem(parent,label,val,clock?clock.channel.toUpperCase():"");
    count++;
  }
  if(!count)cardEl(parent,"p","cockpit-empty","Keine aktuell übermittelten Werte für diesen Bereich.");
  return count;
}
function cockpitRenderNavigation(dev){
  const fmt1=v=>cockpitNumber(v,1,"m");
  cockpitRowsFor("cockpit-navigation",[
    ["Höhe (Startbezug)","elevation_m",fmt1],
    ["Höhe (DJI absolut)","height_m",fmt1],
    ["Vertikalgeschwindigkeit","vertical_speed_mps",v=>cockpitNumber(v,2,"m/s")],
    ["Horizontalgeschwindigkeit","horizontal_speed_mps",v=>cockpitNumber(v,2,"m/s")],
    ["Home-Distanz","home_distance_m",v=>cockpitNumber(v,0,"m")],
    ["GPS-Satelliten","gps_satellites"],["RTK-Satelliten","rtk_satellites"],
    ["RTK-State","rtk_state"],
    ["Positionsqualität (DJI-Code)","cloud_details.position.quality_code"],
    ["Kurs","cloud_details.heading_deg",v=>cockpitNumber(v,1,"°")],
    ["Nickwinkel","cloud_details.pitch_deg",v=>cockpitNumber(v,1,"°")],
    ["Rollwinkel","cloud_details.roll_deg",v=>cockpitNumber(v,1,"°")],
    ["Home-Breitengrad","cloud_details.home_latitude",v=>cockpitNumber(v,6,"°")],
    ["Home-Längengrad","cloud_details.home_longitude",v=>cockpitNumber(v,6,"°")],
    ["Gesamtflugstrecke","cloud_details.total_flight_distance_m",v=>cockpitNumber(v,0,"m")],
    ["Flugzeit gesamt","total_flight_time_s",v=>cockpitNumber(v/3600,1,"h")],
    ["Flugstarts","total_flight_sorties"],
    ["Flugmodus-Code","flight_mode_code"],
  ],dev);
  const lat=cockpitRead(dev,"latitude"),lon=cockpitRead(dev,"longitude");
  const valid=cockpitValidGps(lat,lon);
  byId("cockpit-coordinates").textContent=valid?
    "GPS (WGS84): "+lat.toFixed(6)+"°, "+lon.toFixed(6)+"° · Quelle: "+
      (dev.provider==="dji-cloud-api"?"DJI MQTT OSD":"Gerätestatus"):
    "Keine bestätigten aktuellen Koordinaten. GPS 0/0 wird nicht als Position ausgegeben.";
}
function cockpitRenderEnergy(dev){
  const n=v=>cockpitNumber(v,1);
  cockpitRowsFor("cockpit-energy",[
    ["Akkustand","battery_percent",v=>cockpitNumber(v,0,"%")],
    ["Spannung (erster Akku)","battery_voltage_mv",v=>cockpitNumber(v/1000,2,"V")],
    ["Temperatur (erster Akku)","battery_temperature_c",v=>cockpitNumber(v,1,"°C")],
    ["Restflugzeit","cloud_details.battery.remaining_flight_time_s",v=>cockpitNumber(v/60,1,"min")],
    ["RTH-Reserve","cloud_details.battery.return_home_battery_percent",v=>cockpitNumber(v,0,"%")],
    ["Landereserve","cloud_details.battery.landing_battery_percent",v=>cockpitNumber(v,0,"%")],
    ["Warnschwelle","cloud_details.low_battery_warning_percent",v=>cockpitNumber(v,0,"%")],
    ["Kritische Schwelle","cloud_details.critical_battery_warning_percent",v=>cockpitNumber(v,0,"%")],
  ],dev);
  const list=cockpitRead(dev,"cloud_details.battery_packs");
  if(Array.isArray(list)){
    const root=byId("cockpit-energy");
    list.slice(0,8).forEach((pack,index)=>{
      const at=pack.index===null||pack.index===undefined?index:pack.index;
      cockpitItem(root,"Akku "+at+" · Kapazität",cockpitNumber(pack.capacity_percent,0,"%"));
      cockpitItem(root,"Akku "+at+" · Spannung",cockpitNumber(pack.voltage_mv/1000,2,"V"));
      cockpitItem(root,"Akku "+at+" · Temperatur",cockpitNumber(pack.temperature_c,1,"°C"));
      cockpitItem(root,"Akku "+at+" · Zyklen",cockpitRawValue(pack.cycle_count));
      cockpitItem(root,"Akku "+at+" · Firmware",cockpitRawValue(pack.firmware_version));
    });
  }
}
function cockpitRenderRadio(dev){
  const q=v=>cockpitNumber(v,0,"/ 5");
  cockpitRowsFor("cockpit-radio",[
    ["RC-Höhe (DJI)","cloud_details.controller_height_m",v=>cockpitNumber(v,1,"m")],
    ["Steuerquelle","cloud_details.control_source_category",cockpitSourceLabel],
    ["DRC-Verbindungs-Code","cloud_details.drc_link_state_code"],
    ["Cloud-Berechtigungen · Anzahl","cloud_details.cloud_control_authorization_count"],
    ["SDR-Verbindung","cloud_details.wireless_link.sdr_link_state_code"],
    ["4G-Verbindung","cloud_details.wireless_link.cellular_link_state_code"],
    ["Link-Betriebsart","cloud_details.wireless_link.link_workmode_code"],
    ["SDR-Qualität","cloud_details.wireless_link.sdr_quality",q],
    ["4G-Qualität","cloud_details.wireless_link.cellular_quality",q],
    ["4G · Drohne","cloud_details.wireless_link.cellular_aircraft_quality",q],
    ["4G · Boden","cloud_details.wireless_link.cellular_ground_quality",q],
    ["SDR-Frequenz","cloud_details.wireless_link.sdr_frequency_ghz",v=>cockpitNumber(v,2,"GHz")],
    ["4G-Frequenz","cloud_details.wireless_link.cellular_frequency_ghz",v=>cockpitNumber(v,2,"GHz")],
    ["Mobilfunk-Dongles","cloud_details.wireless_link.dongle_count"],
    ["Livestream-Kapazität","cloud_details.live_capacity.available_videos"],
    ["Max. parallele Streams","cloud_details.live_capacity.simultaneous_videos"],
    ["DJI-Videoquellen","cloud_details.live_capacity.source_devices_count"],
    ["DJI-Kameras mit Quellen","cloud_details.live_capacity.source_cameras_count"],
    ["DJI-Videostreams auswählbar","cloud_details.live_capacity.source_streams_count"],
  ],dev);
  const labels={normal:"Normal",wide:"Weitwinkel",zoom:"Zoom",ir:"IR",
                thermal:"Thermal",infrared:"Infrarot",other:"Sonstige"};
  for(const [path,label] of [
      ["video_types","Gemeldete Objektivtypen"],
      ["switchable_video_types","Umschaltbare Objektivtypen"]]){
    const values=cockpitRead(dev,"cloud_details.live_capacity."+path);
    if(Array.isArray(values)){
      cockpitItem(byId("cockpit-radio"),label,
        values.length?values.map(value=>labels[value]||"Sonstige").join(", "):"Keine gemeldet");
    }
  }
  const lives=cockpitRead(dev,"cloud_details.live_status");
  if(Array.isArray(lives)){
    const root=byId("cockpit-radio");
    lives.slice(0,16).forEach((row,i)=>{
      cockpitItem(root,"Stream "+(i+1)+" · Status",cockpitRawValue(row.status_code));
      cockpitItem(root,"Stream "+(i+1)+" · Fehlercode",cockpitRawValue(row.error_code));
      cockpitItem(root,"Stream "+(i+1)+" · Typ",cockpitRawValue(row.video_type));
    });
  }
}
function cockpitRenderCameras(dev){
  const root=byId("cockpit-camera");root.replaceChildren();
  const cams=cockpitRead(dev,"cloud_details.cameras");
  if(!Array.isArray(cams)||!cams.length){
    cardEl(root,"p","cockpit-empty","Keine aktuellen Kamerazustände übertragen.");
    return;
  }
  cams.slice(0,16).forEach((cam,index)=>{
    const title=cam.payload_index||"Kamera "+(index+1);
    cockpitItem(root,"Kamera / Nutzlast",title);
    for(const [key,label,fmt] of [
      ["camera_mode_code","Modus"],["photo_state_code","Fotostatus"],
      ["recording_state_code","Aufnahmestatus"],["record_time_s","Aufnahmezeit",v=>cockpitNumber(v,0,"s")],
      ["remaining_photos","Verbleibende Fotos"],["remaining_record_time_s","Verbleibende Videozeit",v=>cockpitNumber(v,0,"s")],
      ["zoom_factor","Zoom",v=>cockpitNumber(v,1,"×")],
      ["ir_zoom_factor","IR-Zoom",v=>cockpitNumber(v,1,"×")],
      ["gimbal_pitch_deg","Gimbal Pitch",v=>cockpitNumber(v,1,"°")],
      ["gimbal_yaw_deg","Gimbal Yaw",v=>cockpitNumber(v,1,"°")],
      ["ir_metering_mode_code","IR-Messmodus"],
      ["wide_iso_code","Weitwinkel ISO-Code"],["zoom_iso_code","Tele ISO-Code"],
      ["wide_focus_mode_code","Weitwinkel Fokuscode"],["zoom_focus_mode_code","Tele Fokuscode"]
    ]){
      if(cam[key]!==null&&cam[key]!==undefined)
        cockpitItem(root,title+" · "+label,fmt?fmt(cam[key]):cockpitRawValue(cam[key]));
    }
    if(cam.ir_metering_point&&typeof cam.ir_metering_point.temperature_c==="number")
      cockpitItem(root,title+" · IR Punkt",cockpitNumber(cam.ir_metering_point.temperature_c,1,"°C"));
    const ir=cam.ir_metering_area;
    if(ir){
      cockpitItem(root,title+" · IR Mittel",cockpitNumber(ir.mean_temperature_c,1,"°C"));
      for(const [key,label] of [["min_temperature_point","Min"],["max_temperature_point","Max"]]){
        if(ir[key])cockpitItem(root,title+" · IR "+label,cockpitNumber(ir[key].temperature_c,1,"°C"));
      }
    }
  });
}
function cockpitRenderPayload(dev){
  const root=byId("cockpit-payload");root.replaceChildren();let count=0;
  const payloads=cockpitRead(dev,"cloud_details.payloads");
  if(payloads&&typeof payloads==="object"&&!Array.isArray(payloads)){
    Object.entries(payloads).slice(0,16).forEach(([index,p])=>{
      for(const [key,label,unit] of [
        ["gimbal_pitch_deg","Pitch","°"],["gimbal_roll_deg","Roll","°"],
        ["gimbal_yaw_deg","Yaw","°"],["zoom_factor","Zoom","×"]
      ]){
        const value=cockpitNumber(p&&p[key],1,unit);
        if(value!==null){cockpitItem(root,index+" · "+label,value);count++;}
      }
    });
  }
  const controls=cockpitRead(dev,"cloud_details.payload_control");
  if(Array.isArray(controls)){
    controls.slice(0,16).forEach((p,i)=>{
      const index=p.payload_index||"Nutzlast "+(i+1);
      const source=cockpitSourceLabel(p.control_source_category);
      if(source){cockpitItem(root,index+" · Steuerquelle",source);count++;}
      if(p.firmware_version){cockpitItem(root,index+" · Firmware",p.firmware_version);count++;}
    });
  }
  if(!count)cardEl(root,"p","cockpit-empty","Keine aktuellen Gimbal- oder Nutzlastwerte übertragen.");
}
function cockpitRenderSafety(dev){
  cockpitRowsFor("cockpit-safety",[
    ["Windgeschwindigkeit · DJI-Schätzung","cloud_details.wind_speed_mps",v=>cockpitNumber(v,1,"m/s")],
    ["Windrichtung (Code)","cloud_details.wind_direction_code"],
    ["Flughöhenlimit","cloud_details.height_limit_m",v=>cockpitNumber(v,0,"m")],
    ["Entfernungsgrenze (Statuscode)","cloud_details.distance_limit.state_code"],
    ["Entfernungsgrenze","cloud_details.distance_limit.distance_limit_m",v=>cockpitNumber(v,0,"m")],
    ["Nahe Entfernungsgrenze","cloud_details.distance_limit.near_limit",v=>v?"Ja":"Nein"],
    ["RTH-Rückkehrhöhe","cloud_details.rth_altitude_m",v=>cockpitNumber(v,0,"m")],
    ["RC-Verbindungsverlust (Code)","cloud_details.rc_lost_action_code"],
    ["Nahe Gebietsgrenze","cloud_details.near_area_limit",v=>v?"Ja":"Nein"],
    ["Nahe Höhenlimit","cloud_details.near_height_limit",v=>v?"Ja":"Nein"],
    ["Nachtbeleuchtung","cloud_details.night_lights_on",v=>v?"An":"Aus"],
    ["Hindernisse horizontal","cloud_details.obstacle_avoidance.horizon_enabled",v=>v?"Aktiv":"Inaktiv"],
    ["Hindernisse oben","cloud_details.obstacle_avoidance.upside_enabled",v=>v?"Aktiv":"Inaktiv"],
    ["Hindernisse unten","cloud_details.obstacle_avoidance.downside_enabled",v=>v?"Aktiv":"Inaktiv"],
    ["RTH-Modus (Code)","cloud_details.rth_mode_code"],
    ["Aktiver RTH-Modus","cloud_details.current_rth_mode_code"],
    ["Flugmodusgrund (Code)","cloud_details.flight_mode_reason_code"],
    ["Gang / Geschwindigkeitsstufe","cloud_details.gear_code"],
    ["Firmwarestatus (Code)","cloud_details.firmware_upgrade_status_code"],
    ["Kompatibilitätsstatus (Code)","cloud_details.firmware_compatible_status_code"],
  ],dev);
}
function cockpitRenderHms(dev){
  const root=byId("cockpit-hms");root.replaceChildren();
  const alerts=Array.isArray(dev.health)?dev.health.slice(0,16):[];
  if(!alerts.length)cardEl(root,"p","cockpit-empty",
    "Keine aktuellen HMS-Meldungen über diesen Datenpfad. Das bedeutet nicht HMS-Entwarnung.");
  else cardEl(root,"p","module-note","Aktueller HMS-Snapshot. MQTT-Eingangszeit ist nicht der Zeitpunkt des Fehlereintritts.");
  alerts.forEach(alert=>{
    const entry=cardEl(root,"div","hms-entry");
    const level=alert.level==="warning"?"Warnung":alert.level==="reminder"?"Hinweis":"Information";
    cardEl(entry,"b","",level+" · "+(alert.code||"DJI HMS"));
    cardEl(entry,"p","hms-description",alert.message||"DJI übermittelte keinen Beschreibungstext.");
    if(alert.imminent===true)cardEl(entry,"p","hms-secondary","Dringend laut DJI");
    if(alert.in_the_sky===true)cardEl(entry,"p","hms-secondary","Im Flug gemeldet");
    if(alert.module)cardEl(entry,"p","hms-secondary","Bereich: "+alert.module);
    if(alert.source==="dji-cloud-hms")
      cardEl(entry,"p","hms-secondary","DJI-Gateway-Meldung · Geräteklasse: "+(
        {aircraft:"Fluggerät",dock:"Dock",controller:"Fernsteuerung",payload:"Nutzlast"}[
          alert.device_domain]||"unbekanntes Gerät")+
        " · Seriennummer des auslösenden Geräts nicht bestätigt.");
    if(alert.message_source==="dji-hms-catalog-en")
      cardEl(entry,"p","hms-secondary","Englischer DJI-Katalogtext (keine deutsche Übersetzung)");
  });
  // The backend compares complete validated snapshots; never derive HMS
  // transitions from browser polling, which can miss intermediate states.
  const history=Array.isArray(dev.hms_history)?dev.hms_history.slice(0,12):[];
  cardEl(root,"h4","","HMS-Ereignishistorie · letzte "+history.length+" Änderungen");
  cardEl(root,"p","module-note",
    "AeroNexus-Empfangszeit in UTC; keine DJI-Flugfreigabe und keine bestätigte Fehlerbeginnzeit.");
  if(!history.length)cardEl(root,"p","cockpit-empty","Noch keine dokumentierten HMS-Änderungen.");
  const labels={appeared:"Aufgetreten",reappeared:"Wiederaufgetreten",
    resolved:"Nicht mehr gemeldet",updated:"Priorität/Bereich geändert",
    observed:"Nach Neustart erneut beobachtet"};
  history.forEach(item=>{
    const row=cardEl(root,"div","hms-entry");
    row.dataset.level=item.level||"unknown";
    cardEl(row,"b","",(labels[item.action]||"Änderung")+" · "+(item.code||"DJI HMS"));
    cardEl(row,"p","hms-secondary",item.observed_at||"Zeit unbekannt");
    if(item.message)cardEl(row,"p","hms-description",item.message);
    if(item.level)cardEl(row,"p","hms-secondary","Priorität: "+item.level);
  });
}
function cockpitRenderDiagnostics(dev){
  const root=byId("cockpit-diagnostics");root.replaceChildren();
  const rows=[
    ["Gerät",dev.name||"Unbekannt"],["Typ",dev.kind==="aircraft"?"Fluggerät":"Fernsteuerung"],
    ["Datenquelle",dev.provider],["Projekt",dev.project_id],["Gerätekennung",dev.device_id],
    ["Aktualität",statusLabel(dev.freshness)],["Online",dev.online===true?"Ja":dev.online===false?"Nein":"Unbekannt"],
    ["Eingangsalter",cockpitAge(dev)],["Letzter Empfang (UTC)",dev.received_at],
    ["Firmware",cockpitRead(dev,"cloud_details.firmware_version")],
    ["Modellhinweis",cockpitRead(dev,"cloud_details.aircraft_model_hint")],
  ];
  for(const [key,value] of rows)cockpitItem(root,key,value===null||value===undefined?"–":String(value));
  if(dev.field_status&&Object.keys(dev.field_status).length)
    cockpitItem(root,"DJI-Felder mit Zeitstatus",Object.keys(dev.field_status).length);
}
function cockpitRenderFields(dev){
  const root=byId("cockpit-fields");root.replaceChildren();
  const fields=dev.field_status||{};
  const entries=Object.entries(fields).sort((a,b)=>a[0].localeCompare(b[0],"de"));
  if(!entries.length){
    cardEl(root,"p","cockpit-empty","Diese Quelle liefert keine Einzel-Feld-Zeitstempel. Es gilt die Gerätefrische.");
    return;
  }
  entries.slice(0,250).forEach(([key,clock])=>{
    const row=cardEl(root,"div","cockpit-fieldrow");
    cardEl(row,"span","",key);
    const age=typeof clock.source_age_seconds==="number"?
      Math.max(clock.source_age_seconds,clock.age_seconds||0):clock.age_seconds;
    const expired=clock.freshness==="fresh"&&(typeof age!=="number"||age>cockpitLiveLimitSeconds);
    const state=clock.freshness==="stale"?"Veraltet":clock.freshness!=="fresh"?"Uhrfehler":
      expired?"Nicht live":"Aktuell";
    cardEl(row,"span",state==="Aktuell"?"fresh":state==="Uhrfehler"?"skew":"stale",state);
    cardEl(row,"span","muted",(clock.channel||"–").toUpperCase()+" · "+
      (typeof age==="number"?Math.floor(age)+" s":"–"));
  });
  if(entries.length>250)cardEl(root,"p","cockpit-empty","Weitere Felder in der technischen Tabelle.");
}
const cockpitFocusFields={
  controller:[
    ["Firmwareversion (Fernsteuerung)","cloud_details.firmware_version"],
    ["Cloud-Control-Autorisierungen (Anzahl)","cloud_details.cloud_control_authorization_count"],
    ["Verfügbare Livestreams","cloud_details.live_capacity.available_videos"],
    ["Gleichzeitige Livestreams","cloud_details.live_capacity.simultaneous_videos"]
  ],
  aircraft:[
    ["RTH-Modus (Code)","cloud_details.rth_mode_code"],
    ["Aktiver RTH-Modus (Code)","cloud_details.current_rth_mode_code"],
    ["Steuerquelle","cloud_details.control_source_category"],
    ["Firmwareversion (Fluggerät)","cloud_details.firmware_version"]
  ]
};
function cockpitRenderFieldFocus(dev){
  const root=byId("cockpit-field-focus");root.replaceChildren();
  if(dev.provider!=="dji-cloud-api"){
    cardEl(root,"p","cockpit-empty","Einzelfeld-Diagnose nur für DJI Cloud API verfügbar.");
    return;
  }
  for(const [label,path] of (cockpitFocusFields[dev.kind]||[])){
    const clock=cockpitClock(dev,path);
    const raw=cockpitPath(dev.last_known_telemetry||dev.telemetry||{},path);
    const known=cockpitRawValue(raw);
    const observed=Boolean(clock&&typeof clock==="object"&&known!==null);
    const current=observed?cockpitRawValue(cockpitRead(dev,path)):null;
    // Live status is exclusively decided by cockpitRead (online, 15 s,
    // server-side field freshness). Cached values never enter live modules.
    const state=current!==null?"live":observed?"last-known":"not-observed";
    const row=cardEl(root,"div","cockpit-focus-row");row.dataset.state=state;
    cardEl(row,"div","cockpit-focus-title",label);
    cardEl(row,"span","cockpit-focus-state",
      state==="live"?"Aktuell · Livewert":state==="last-known"?
      "Letzter bekannter Wert · NICHT LIVE":"Nicht beobachtet");
    cardEl(row,"b","",state==="live"?current:state==="last-known"?known:"–");
    if(!observed){
      cardEl(row,"small","","Kein Messwert mit verifiziertem Einzel-Feld-Empfangszeitpunkt.");
      continue;
    }
    const ages=[clock.age_seconds,clock.source_age_seconds]
      .filter(x=>typeof x==="number"&&Number.isFinite(x));
    const age=ages.length?Math.max(...ages):null;
    const channel=clock.channel==="osd"?"OSD":clock.channel==="state"?"STATE":"unbekannt";
    const stateNote=clock.freshness==="clock_skew"?" · Quellzeit unplausibel":
      clock.freshness==="stale"?" · serverseitig veraltet":"";
    cardEl(row,"small","",channel+" · Empfang: "+(clock.received_at||"unbekannt")+
      " · Feldalter: "+(age===null?"unbekannt":Math.floor(Math.max(0,age))+" s")+stateNote);
  }
}
function cockpitValidGps(lat,lon){
  return typeof lat==="number"&&Number.isFinite(lat)&&Math.abs(lat)<=90
    &&typeof lon==="number"&&Number.isFinite(lon)&&Math.abs(lon)<=180
    &&(lat!==0||lon!==0);
}
function cockpitMemory(dev){
  const key=cockpitKey(dev);
  if(!cockpitHistory.has(key))cockpitHistory.set(key,{battery:[],altitude:[],speed:[],positions:[]});
  return cockpitHistory.get(key);
}
function cockpitSample(dev,path,series,val){
  if(typeof val!=="number"||!Number.isFinite(val))return;
  const clock=cockpitClock(dev,path);
  const fingerprint=clock?
    (clock.source_timestamp_ms===null||clock.source_timestamp_ms===undefined?
      clock.received_at:String(clock.source_timestamp_ms)):dev.received_at;
  if(!fingerprint)return;
  if(series.length&&series[series.length-1].id===fingerprint)return;
  series.push({id:fingerprint,value:val});
  if(series.length>cockpitMaxSamples)series.shift();
}
function cockpitRecord(dev){
  if(!cockpitIsLive(dev))return;
  const memory=cockpitMemory(dev);
  cockpitSample(dev,"battery_percent",memory.battery,cockpitRead(dev,"battery_percent"));
  cockpitSample(dev,"elevation_m",memory.altitude,cockpitRead(dev,"elevation_m"));
  cockpitSample(dev,"horizontal_speed_mps",memory.speed,cockpitRead(dev,"horizontal_speed_mps"));
  const lat=cockpitRead(dev,"latitude"),lon=cockpitRead(dev,"longitude");
  if(!cockpitValidGps(lat,lon))return;
  const meta=cockpitClock(dev,"latitude");
  const fingerprint=meta?(meta.source_timestamp_ms===null||meta.source_timestamp_ms===undefined?
    meta.received_at:String(meta.source_timestamp_ms)):dev.received_at;
  if(!fingerprint)return;
  const positions=memory.positions;
  if(positions.length&&positions[positions.length-1].id===fingerprint)return;
  if(positions.length){
    const prev=positions[positions.length-1];
    const dx=(((lon-prev.lon+540)%360)-180)*111320*Math.cos(lat*Math.PI/180);
    const dy=(lat-prev.lat)*111320;
    if(Math.hypot(dx,dy)>50000)positions.length=0; // new track, no spurious 50 km leap
  }
  positions.push({lat,lon,id:fingerprint});
  if(positions.length>120)positions.shift();
}
function cockpitSvgElement(tag,attributes,root){
  const el=document.createElementNS("http://www.w3.org/2000/svg",tag);
  for(const [key,value] of Object.entries(attributes))el.setAttribute(key,String(value));
  root.appendChild(el);
  return el;
}
function cockpitRenderTrack(dev){
  const svg=byId("cockpit-track");svg.replaceChildren();
  if(!cockpitIsLive(dev)){
    byId("cockpit-track-info").textContent="Keine bestätigte Live-Verbindung. Verlauf ist pausiert.";
    return;
  }
  const positions=cockpitMemory(dev).positions;
  if(!positions.length){
    byId("cockpit-track-info").textContent="Noch keine gültigen Live-Positionspunkte empfangen.";
    return;
  }
  const zero=positions[0];
  const xy=positions.map(p=>({
    x:(((p.lon-zero.lon+540)%360)-180)*111320*Math.cos(zero.lat*Math.PI/180),
    y:(p.lat-zero.lat)*111320
  }));
  const xs=xy.map(p=>p.x),ys=xy.map(p=>p.y);
  const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
  const span=Math.max(maxX-minX,maxY-minY,30);
  const midX=(minX+maxX)/2,midY=(minY+maxY)/2;
  const projected=xy.map(p=>[240+(p.x-midX)*400/span,105-(p.y-midY)*175/span]);
  if(projected.length>1)cockpitSvgElement("polyline",{
    points:projected.map(p=>p.join(",")).join(" "),class:"trail"},svg);
  const last=projected[projected.length-1];
  cockpitSvgElement("circle",{cx:last[0],cy:last[1],r:6,class:"marker"},svg);
  byId("cockpit-track-info").textContent=positions.length+
    " gültige Punkte · relativer Verlauf, kein Kartenhintergrund · mindestens "+
    Math.round(span)+" m Darstellungsbreite";
}
function cockpitRenderTrends(dev){
  const root=byId("cockpit-trends");root.replaceChildren();
  if(!cockpitIsLive(dev)){
    cardEl(root,"p","cockpit-empty","Kein aktueller Live-Stream; Browser-Trends werden nicht fortgeschrieben.");
    return;
  }
  const memory=cockpitMemory(dev);
  for(const [key,title,unit] of [["battery","Akku","%"],["altitude","Höhe Startbezug","m"],
                                  ["speed","Horizontalgeschwindigkeit","m/s"]]){
    const series=memory[key],wrapper=cardEl(root,"div","");
    const heading=cardEl(wrapper,"div","cockpit-chart-title");
    cardEl(heading,"span","",title);
    cardEl(heading,"b","",series.length?cockpitNumber(series[series.length-1].value,1,unit):"–");
    const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
    svg.setAttribute("class","cockpit-chart");
    wrapper.appendChild(svg);
    svg.setAttribute("viewBox","0 0 420 70");
    svg.setAttribute("aria-label",title+" · bisherige Live-Messpunkte");
    if(series.length>1){
      const nums=series.map(p=>p.value),min=Math.min(...nums),max=Math.max(...nums);
      const scale=Math.max(max-min,1);
      const pts=nums.map((value,i)=>[8+i*404/(nums.length-1),60-(value-min)*48/scale]);
      cockpitSvgElement("path",{d:pts.map((p,i)=>(i?"L":"M")+p[0].toFixed(1)+","+
        p[1].toFixed(1)).join(" "),class:"trend"},svg);
    }
  }
}
function cockpitSelectRows(rows){
  cockpitRows=Array.isArray(rows)?rows:[];
  const select=byId("cockpit-device"),old=cockpitChosen||select.value;
  const ordered=[...cockpitRows].sort((a,b)=>
    (a.kind==="aircraft"?0:1)-(b.kind==="aircraft"?0:1)
    ||String(a.name||"").localeCompare(String(b.name||""),"de"));
  const signature=JSON.stringify(ordered.map(d=>[cockpitKey(d),d.name,d.kind]));
  if(signature!==cockpitOptionsSignature){
    select.replaceChildren();
    for(const dev of ordered){
      const opt=document.createElement("option");
      opt.value=cockpitKey(dev);
      opt.textContent=(dev.kind==="aircraft"?"Drohne · ":"RC · ")+
        (dev.name||"Unbenannt")+" · "+dev.provider;
      select.appendChild(opt);
    }
    if(!ordered.length){
      const opt=document.createElement("option");opt.value="";opt.textContent="Keine Geräte verfügbar";
      select.appendChild(opt);
    }
    cockpitOptionsSignature=signature;
  }
  if(!ordered.length){cockpitChosen="";return null;}
  cockpitChosen=ordered.some(x=>cockpitKey(x)===old)?old:cockpitKey(ordered[0]);
  select.value=cockpitChosen;
  return ordered.find(x=>cockpitKey(x)===cockpitChosen);
}
function cockpitUnavailable(reason){
  cockpitError=reason||"Geschützte Geräte-API nicht erreichbar";
  cockpitHistory.clear(); // Never bridge gaps in a relative GNSS trail after an API outage.
  cockpitSelectRows([]);
  cockpitPaint(null);
}
function cockpitPaint(dev){
  const live=cockpitIsLive(dev)&&!cockpitError;
  const tag=byId("cockpit-live");
  tag.dataset.state=cockpitError?"error":live?"live":dev&&dev.online===false?"offline":"stale";
  tag.textContent=dev?cockpitStatusText(dev):cockpitError?"API nicht erreichbar":"Keine Geräte";
  const banner=byId("cockpit-banner");
  banner.dataset.tone=live?"good":cockpitError?"bad":"warn";
  banner.textContent=cockpitError?"Keine Livewerte: "+cockpitError+". Bereits angezeigte Werte wurden zurückgesetzt.":
    !dev?"Keine angeschlossenen Geräte in der freigegebenen lokalen Telemetriequelle.":
    live?"Live-Telemetrie: "+(dev.name||"Gerät")+" · "+dev.provider+
      " · nur bestätigte, frische Messwerte.":
    cockpitStatusText(dev)+": Livewerte ausgeblendet; gespeicherte Werte bleiben nur in der technischen Historie.";
  const get=p=>dev?cockpitRead(dev,p):null;
  cockpitSetGauge("battery",cockpitNumber(get("battery_percent"),0,"%"),
    live?"Geräteakku · aktueller Empfang":"Kein bestätigter Livewert");
  cockpitSetGauge("mode",dev?cockpitMode(dev):null,
    live?"DJI-Statuscode zugeordnet":"Kein bestätigter Livewert");
  cockpitSetGauge("altitude",cockpitNumber(get("elevation_m"),1,"m"),
    live?"DJI Startbezug":"Kein bestätigter Livewert");
  cockpitSetGauge("speed",cockpitNumber(get("horizontal_speed_mps"),1,"m/s"),
    live?"Horizontal":"Kein bestätigter Livewert");
  cockpitSetGauge("rtk",dev?cockpitRtk(dev):null,
    live?"GNSS-Zustand · RTK nie aus Satelliten geschätzt":"Kein bestätigter Livewert");
  cockpitSetGauge("age",live?cockpitAge(dev):null,
    dev?"Frische: "+statusLabel(dev.freshness):"Noch kein Empfang");
  if(!dev){
    for(const id of ["cockpit-navigation","cockpit-energy","cockpit-radio","cockpit-camera",
      "cockpit-payload","cockpit-safety","cockpit-hms","cockpit-diagnostics","cockpit-fields",
      "cockpit-field-focus","cockpit-trends"]){
      const el=byId(id);el.replaceChildren();
      cardEl(el,"p","cockpit-empty","Keine gültigen Geräte-Livewerte.");
    }
    byId("cockpit-coordinates").textContent="Keine bestätigten aktuellen Koordinaten.";
    byId("cockpit-track").replaceChildren();
    byId("cockpit-track-info").textContent="Noch keine gültigen Live-Positionspunkte.";
    return;
  }
  if(!live)cockpitHistory.delete(cockpitKey(dev)); // Prevent false continuous trails after offline/stale.
  else cockpitRecord(dev);
  cockpitRenderNavigation(dev);
  cockpitRenderEnergy(dev);
  cockpitRenderRadio(dev);
  cockpitRenderCameras(dev);
  cockpitRenderPayload(dev);
  cockpitRenderSafety(dev);
  cockpitRenderHms(dev);
  cockpitRenderDiagnostics(dev);
  cockpitRenderFields(dev);
  cockpitRenderFieldFocus(dev);
  cockpitRenderTrack(dev);
  cockpitRenderTrends(dev);
}
function renderCockpit(rows){
  cockpitError=null;
  const selected=cockpitSelectRows(rows);
  cockpitPaint(selected);
}
byId("cockpit-device").onchange=function(){
  cockpitChosen=this.value;
  const chosen=cockpitRows.find(row=>cockpitKey(row)===cockpitChosen);
  cockpitPaint(chosen||null);
};
byId("cockpit-refresh").onclick=()=>updateDevices();

"""
