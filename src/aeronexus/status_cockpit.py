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
      <p class="module-note">Zeitstempel und Kanal pro DJI-Eigenschaft; keine erneute Aktivierung abgelaufener Werte.</p>
      <div class="cockpit-fieldlist" id="cockpit-fields"></div></section>
  </div>
  <p class="cockpit-legend">„Live“ bedeutet: Daten aktuell laut Backend und Gerät aktuell als online bestätigt.
    Ohne gültige Positionsdaten wird keine Position gezeichnet. HMS kann aus einem anderen Datenpfad stammen;
    eine OSD-Verbindung bestätigt keine flugsichere Verbindung.</p>
</section>
"""

COCKPIT_JS = r"""
"""
