"""Desktop-first Chrome mission and media studio.

Static HTML shell; direct trusted-HTTPS-LAN workspace access with no token
prompt. No flight commands, DJI upload or automatic geolocation sharing.
"""
from html import escape

from .wpml_export import MODELS, MODEL_LABELS


HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="dark">
<title>AeroNexus Studio · Missionen & Medien</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<style>
:root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,"Segoe UI",sans-serif;--ink:#eaf3ff;--muted:#97aec7;--line:#2c425c;--bg:#0a111f;--pane:#111e31;--surface:#172740;--accent:#48a8f5;--good:#62dfb7}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);min-height:100vh;font-size:14px}
button,input,select,textarea{font:inherit}button{cursor:pointer;background:#254b75;color:#f1f7ff;border:1px solid #36678d;border-radius:9px;padding:9px 12px}
button:hover{background:#32638f}button:disabled{opacity:.4;cursor:not-allowed}
button.primary{background:#2e87cb;border-color:#459fdf}button.danger{background:#492b38;border-color:#824456;color:#ffb4bc}
input,select,textarea{color:#edf5ff;background:#0b1728;border:1px solid #3c526c;border-radius:9px;padding:10px;min-width:0;width:100%}
input:focus,select:focus,textarea:focus,button:focus-visible{outline:2px solid #7ccaff;outline-offset:1px}
header{display:flex;align-items:center;gap:18px;padding:13px 20px;background:#111d30;border-bottom:1px solid #29425e;flex-wrap:wrap}
.brand{font-size:20px;font-weight:800;letter-spacing:-.04em}.brand small{font-size:11px;color:#73b7e8;display:block;letter-spacing:.2em;font-weight:650}
nav{display:flex;gap:5px;flex-wrap:wrap}nav button{background:transparent;border:0;color:#b8c9dd}nav button.active{background:#23496b;color:#fff}
.auth{display:flex;gap:7px;align-items:center;flex:1;justify-content:flex-end;min-width:280px}

.auth-message{font-size:12px;flex-basis:100%;text-align:right;color:#c9d9ea;min-height:15px;overflow-wrap:anywhere}
.auth-message.error{color:#ffacb6}
.auth-message.ok{color:#9be8c8}

.dot{width:9px;height:9px;background:#6b7788;border-radius:50%;display:inline-block}
.dot.on{background:var(--good)}.muted{color:var(--muted)}.note{font-size:12px;color:#a6b9cc;line-height:1.5}
.layout{display:grid;grid-template-columns:365px minmax(0,1fr);height:calc(100vh - 73px);min-height:650px}
.side{overflow-y:auto;border-right:1px solid var(--line);background:var(--pane);padding:18px;min-width:0}
.content{min-width:0;overflow:hidden;position:relative}.pane{height:100%;display:none;overflow:auto}.pane.active{display:block}
h1{font-size:20px;margin:0 0 5px}h2{font-size:15px;margin:22px 0 12px;color:#d9eaff}
h3{font-size:14px;margin:14px 0 7px}.flex{display:flex;align-items:center;gap:9px}.wrap{flex-wrap:wrap}.grow{flex:1}.between{justify-content:space-between}
label{font-size:12px;color:#aec2d8;display:flex;flex-direction:column;gap:6px;margin:9px 0}
fieldset{border:0;padding:0;margin:0}.field-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.button-row{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}.button-row button{flex:1}
hr{border:0;border-top:1px solid #2b4159;margin:17px 0}
.status{padding:11px 13px;border-radius:9px;background:#152d46;border:1px solid #335573;color:#bedcff;margin:12px 0;line-height:1.5}
.status.error{color:#ffc1c8;border-color:#804d58;background:#351f2c}
.status.good{color:#b4ffdf;border-color:#346b59;background:#173c36}
.wayline-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:12px}
.wayline-card{background:var(--pane);border:1px solid var(--line);border-radius:9px;padding:14px;overflow-wrap:anywhere;min-width:0}
.wayline-card h2{margin:0 0 12px;font-size:16px}.wayline-card p{margin:7px 0;line-height:1.5}
.wayline-tools{display:flex;gap:8px;align-items:end;flex-wrap:wrap}.wayline-tools label{flex:1;min-width:160px}
#wayline-state{min-height:68px}#wayline-range{min-height:20px}#wayline-page{align-self:center}
#cloud-overview-panel{position:absolute;z-index:510;right:12px;top:75px;width:min(365px,calc(100% - 24px));max-height:min(70vh,640px);overflow:auto;background:#102238ee;border:1px solid #54758e;border-radius:12px;padding:12px;box-shadow:0 8px 28px #0008}
#cloud-overview-panel[hidden]{display:none}
#cloud-overview-panel .cloud-head{display:flex;gap:7px;align-items:center;justify-content:space-between}
#cloud-overview-panel .cloud-head button{padding:6px 8px}
#cloud-overview-list{display:grid;gap:8px;margin-top:9px}
.cloud-route-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px 8px;padding:9px;background:#1b3348;border:1px solid #456078;border-radius:9px}
.cloud-route-row label{display:flex;flex-direction:row;gap:7px;align-items:center;margin:0;min-width:0;color:#f2f7ff}
.cloud-route-row label input{width:auto;flex:0 0 auto}
.cloud-route-row label span{min-width:0;overflow-wrap:anywhere}
.cloud-route-row .swatch{width:12px;height:12px;flex:0 0 12px;border-radius:3px;border:1px solid #a6b6c6}
.cloud-route-row .cloud-route-detail{grid-column:1/-1;font-size:11px;color:#bad2e4;overflow-wrap:anywhere}
.cloud-route-row .cloud-route-metrics{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:5px;font-size:12px;color:#d7ecff}
.cloud-route-row .cloud-route-metrics span{background:#23445e;border-radius:5px;padding:3px 7px}
.cloud-route-row button{align-self:center;padding:6px 8px}
@media(max-width:600px){#cloud-overview-panel{top:110px;max-height:52vh}}
.badge{border-radius:999px;border:1px solid #3c5875;color:#a9cbea;padding:3px 8px;font-size:11px}
#map{height:100%;min-height:600px;background:#192837}
.map-bar{position:absolute;z-index:500;top:16px;left:16px;right:16px;display:flex;gap:7px;align-items:center;flex-wrap:wrap;pointer-events:none}
.map-bar>*{pointer-events:auto;box-shadow:0 5px 20px #0006}.map-bar button,.map-bar select{background:#162b44;border:1px solid #466a8c}
.map-bar select{width:auto;max-width:160px}
.map-bar [hidden]{display:none!important}
.map-bar .map-primary{font-weight:650}
#map-info[data-minimized="true"]{max-width:min(340px,calc(100% - 24px))}
#map-info[data-minimized="true"] #map-info-detail{display:none}
#map-info-chip{display:block;width:100%;max-width:100%;padding:0;border:0;background:transparent;color:inherit;box-shadow:none;font:inherit;text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.5;cursor:pointer}
#map-info-chip:hover{background:transparent}
#map-info-detail{display:block;max-height:31dvh;overflow-y:auto;margin-top:6px;line-height:1.45;overflow-wrap:anywhere}
#map-info-detail[hidden]{display:none}
#map-info:not([data-minimized="true"]){max-width:min(460px,calc(100% - 20px))}
@media(min-width:701px){#map-info-chip{display:none}}
#cloud-overview-panel[data-minimized="true"] #cloud-overview-list,
#cloud-overview-panel[data-minimized="true"] .cloud-overview-help{display:none}
body.map-focus-active{overflow:hidden}
body.map-focus-active .content{position:fixed;inset:0;z-index:1500;height:100dvh;min-height:0;width:100%;background:var(--bg)}
body.map-focus-active #map-pane{height:100%}
body.map-focus-active #map{height:100%;min-height:0}
@media(min-width:701px){#map-tools-toggle{display:none}}
@media(max-width:700px){
  .map-bar{top:9px;left:9px;right:9px;gap:6px}
  .map-bar button,.map-bar select{font-size:12px;padding:8px 10px;min-height:38px}
  .map-bar[data-compact="true"] .map-extra{display:none}
  .map-bar #wayline-preview-fit{max-width:48vw}
  #cloud-overview-panel{top:auto;right:9px;bottom:90px;width:min(355px,calc(100% - 18px));max-height:50dvh}
  #cloud-overview-panel[data-minimized="true"]{max-height:140px}
  .map-info{left:9px;bottom:calc(39px + env(safe-area-inset-bottom));max-width:calc(100% - 18px);font-size:12px;padding:8px 10px}
  #map-info[data-minimized="true"]{max-width:min(320px,calc(100% - 18px))}
  body.map-focus-active .map-bar{top:calc(9px + env(safe-area-inset-top))}
  body.map-focus-active #cloud-overview-panel{bottom:calc(75px + env(safe-area-inset-bottom))}
  body.map-focus-active .map-info{bottom:calc(39px + env(safe-area-inset-bottom))}
}
.map-info{position:absolute;z-index:500;bottom:calc(39px + env(safe-area-inset-bottom));left:12px;max-width:min(480px,80%);padding:9px 12px;border-radius:9px;background:#101d2ce8;color:#dceaff;font-size:12px;pointer-events:auto;box-shadow:0 3px 16px #0007}
.map-info.warning{border:1px solid #a87548;color:#ffe3b0;background:#34251de8}
.point-row{display:grid;grid-template-columns:30px minmax(0,1fr) auto;gap:8px;align-items:center;padding:9px 7px;border-radius:9px;border:1px solid #314961;margin:7px 0;background:#16263d}
.point-row.selected{border-color:#53acf3;background:#1b3954}
.point-index{border-radius:50%;background:#297cb2;color:#fff;width:27px;height:27px;display:grid;place-items:center;font-weight:700}
.point-row small{color:#adc2da;display:block;margin-top:4px}.point-row button{padding:5px 8px}
#point-list{max-height:380px;overflow-y:auto}
#point-editor{border:1px solid #385270;border-radius:11px;padding:12px;margin-top:10px}
#point-editor[hidden],#mission-panel[hidden],#media-panel[hidden],#fleet-panel[hidden],#geo-panel[hidden],#wayline-panel[hidden]{display:none}
#point-focus-params[hidden],#point-zoom-params[hidden],#point-pitch-params[hidden]{display:none}
.pane-inner{padding:25px;max-width:1500px;margin:0 auto}
.page-head{display:flex;justify-content:space-between;gap:15px;align-items:center;flex-wrap:wrap;margin-bottom:18px}
.page-head h1{font-size:28px}.filters{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.filters input{max-width:330px}
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:15px}
.media-card{border:1px solid #314a68;background:#14243a;border-radius:14px;padding:10px;min-width:0}
.media-cover{height:170px;border-radius:9px;background:#0a1829;display:grid;place-items:center;overflow:hidden}
.media-cover img{width:100%;height:100%;object-fit:cover}
.media-cover .video-icon{font-size:32px;color:#94b9d7}
.media-name{font-size:14px;font-weight:700;overflow-wrap:anywhere;margin:10px 0 5px}
.media-card button{font-size:12px;padding:7px}
dialog{max-width:min(900px,95vw);max-height:90vh;background:#102039;color:#fff;border:1px solid #436080;border-radius:15px;padding:18px}
dialog::backdrop{background:#000b}dialog img,dialog video{max-width:100%;max-height:68vh;display:block;margin:auto}
#csv-dialog{width:min(760px,95vw);padding:0;overflow:hidden}
#csv-dialog[open]{display:flex;flex-direction:column}
#csv-dialog [hidden]{display:none}
.csv-heading,.csv-actions{padding:14px 18px;flex:0 0 auto}
.csv-body{padding:0 18px;overflow-y:auto;min-height:0;overscroll-behavior:contain}
.csv-actions{border-top:1px solid var(--line);display:flex;gap:8px;flex-wrap:wrap}
.csv-actions button{flex:1}
#csv-map{height:220px;background:var(--bg);border:1px solid var(--line);border-radius:9px;margin:12px 0}
.csv-table{overflow:auto;max-height:250px;border:1px solid var(--line);border-radius:9px;scrollbar-gutter:stable;scrollbar-color:var(--muted) var(--bg);scrollbar-width:thin}
.csv-table table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:12px}
.csv-table th,.csv-table td{padding:8px;text-align:left;white-space:nowrap;border-bottom:1px solid var(--line)}
.csv-table th{position:sticky;top:0;background:var(--pane)}
#csv-errors{padding-left:24px;overflow-wrap:anywhere;color:#ffc1c8}
#csv-message{min-height:44px;overflow-wrap:anywhere}
.fleet-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.fleet-card{border:1px solid #3a5272;border-radius:13px;padding:17px;background:#142943}
.fleet-card h3{font-size:17px}.fleet-data{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.fleet-data>div{padding:10px;background:#0b1d2f;border-radius:7px}
.empty{padding:30px;border:1px dashed #45607f;border-radius:12px;color:#a5bad1}
.way-marker{width:27px;height:27px;border-radius:50%;background:#2f96db;border:2px solid #f2f9ff;display:grid;place-items:center;color:#fff;font-weight:700;box-shadow:0 3px 12px #0007}
.way-marker.selected{background:#f0b04b;color:#101520}
.route-option{display:flex;flex-direction:row;align-items:center;gap:10px;padding:12px;background:#172b43;border:1px solid #405c7c;border-radius:10px;cursor:pointer}
.route-option input{width:18px;height:18px;flex:0 0 auto;accent-color:#55b4f5}
.route-option span{color:#eaf3ff;font-weight:600;font-size:14px}
.route-explain{margin:7px 0 12px;color:#a6c4de;font-size:12px;line-height:1.5}
.route-status{padding:9px 11px;border-left:3px solid #5088b5;background:#10263d;border-radius:6px;color:#b7d9f4;font-size:12px;line-height:1.5;margin-bottom:10px}
.geo-list{display:flex;flex-direction:column;gap:6px;margin:12px 0}
.geo-row{display:flex;align-items:center;gap:8px;padding:8px;background:#142b42;border:1px solid #395a78;border-radius:8px}
.geo-row span{flex:1;min-width:0;overflow-wrap:anywhere}
.geo-vertex{display:grid;place-items:center;width:18px;height:18px;border-radius:50%;border:2px solid #ffffff;background:#ffad65;color:#142132;font-size:11px;font-weight:800;box-shadow:0 1px 6px #0007;cursor:move}
#terrain-canvas,#terrain-canvas-large{display:block;width:100%;height:auto;background:#0d2233;border-radius:9px;border:1px solid #39516c;touch-action:none;cursor:grab}
#terrain-canvas:active,#terrain-canvas-large:active{cursor:grabbing}
.terrain-stage{padding:18px;max-width:1300px;margin:auto}
.terrain-stage h1{margin-bottom:8px}
.terrain-controls{display:grid;grid-template-columns:repeat(4,minmax(135px,1fr));gap:7px 15px;margin:16px 0;padding:12px;background:#13263c;border:1px solid #344f68;border-radius:12px}
.terrain-controls label{margin:0}
.terrain-controls input[type=range]{padding:0;cursor:pointer}
.terrain-toggles{display:flex;flex-wrap:wrap;gap:15px;align-items:center;margin:8px 0 14px}
.terrain-toggles label{display:flex;flex-direction:row;align-items:center;gap:6px;margin:0}
.terrain-toggles input[type=checkbox]{width:auto}
.terrain-help{color:#a8c7dd;font-size:12px;line-height:1.6;margin:12px 0}
.terrain-location{padding:11px;border:1px solid #3b5879;background:#10273c;border-radius:9px;margin:10px 0;font-size:12px;line-height:1.5}
#terrain-profile-canvas{width:100%;max-height:190px;height:auto;display:block;background:#0d2233;border:1px solid #39516c;border-radius:8px}
.terrain-geo-tools{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:end;gap:12px;margin:12px 0}
.terrain-geo-tools label{margin:0}
.terrain-geo-tools button{white-space:nowrap}
@media(max-width:700px){.terrain-geo-tools{grid-template-columns:1fr}}
@media(max-width:700px){.terrain-controls{grid-template-columns:repeat(2,minmax(0,1fr))}.terrain-stage{padding:12px}}
.geo-buttons{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}.geo-buttons button{flex:1}
.editor-dirty{font-size:12px;padding:6px 9px;border-radius:7px;color:#a0efcf;background:#123e34;border:1px solid #316d56}
.editor-dirty.unsaved{color:#ffdeaa;background:#3a2c1a;border-color:#7c5a2b}
.editor-tools{display:flex;gap:7px;margin:9px 0;flex-wrap:wrap}
.editor-tools button{flex:1}
.coordinate-help{font-size:11px;color:#a9c6df;margin:6px 0 10px}
.route-analysis{padding:12px;border:1px solid #3b5879;background:#12283f;border-radius:11px;margin:12px 0}
.route-analysis h3{margin:0 0 10px;color:#d5eaff}
.analysis-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.analysis-grid>div{padding:9px;border-radius:7px;background:#091d32}
.analysis-grid small{font-size:11px;color:#afc9df;display:block}
.analysis-grid strong{font-size:17px;display:block;font-variant-numeric:tabular-nums;color:#f1f8ff;margin-top:3px}
.analysis-warning{color:#ffd0a4;font-size:12px;line-height:1.5;margin:9px 0 0}
.analysis-warning:empty{display:none}
footer{font-size:11px;color:#a3b6cc;margin:20px 0}
@media(max-width:1000px){.layout{grid-template-columns:320px minmax(0,1fr)}header{gap:9px}.auth{min-width:250px}}
@media(max-width:700px){.auth-message{text-align:left}.layout{display:block;height:auto}.side{max-height:none}.content{height:65vh;min-height:440px}.pane-inner{padding:16px}#map{min-height:440px}.auth{min-width:100%;justify-content:stretch}header{padding:11px}}
</style>
</head>
<body>
<header>
<div class="brand"><small>AERONEXUS ADVANCED</small>Mission Studio</div>
<nav aria-label="Arbeitsbereiche">
<button class="active" data-tab="map-pane">Karte & Missionen</button>
<button data-tab="geo-pane">Geo &amp; Gelände</button>
<button data-tab="terrain-pane">3D Gelände</button>
<button data-tab="media-pane">Medienbibliothek</button>
<button data-tab="waylines-pane" aria-controls="waylines-pane">Cloud-Routen</button>
<button data-tab="fleet-pane">Flottenstatus</button>
<a href="/operations" style="color:#9edaff;padding:9px;text-decoration:none">Operations Center ↗</a>
<a href="/status" style="color:#9edaff;padding:9px;text-decoration:none">Live-Dashboard ↗</a>
<a href="/thermal" style="color:#9edaff;padding:9px;text-decoration:none">Thermal ↗</a>
<a href="/multispectral" style="color:#9edaff;padding:9px;text-decoration:none">Multispektral ↗</a>
<a href="/results" style="color:#9edaff;padding:9px;text-decoration:none">Ergebnisraster ↗</a></nav>
<div class="auth"><span class="dot on" aria-hidden="true"></span>
<span id="auth-message" class="auth-message" role="status" aria-live="polite">Direkter LAN-Zugriff · Daten werden geladen…</span>
</div>
</header>
<div class="layout">
<aside class="side" id="mission-panel">
<div class="flex between"><div><h1>Missionsplanung</h1><div class="note">Offline-Entwurf · keine Flugausführung</div></div><span class="badge">WPML</span></div>
<div class="status" id="notice" role="status">Missionen werden automatisch vom Raspberry Pi geladen…</div>
<label>Gespeicherte Missionen<select id="mission-list"><option value="">Neuer Entwurf</option></select></label>
<div class="button-row"><button id="new-mission">Neu</button><button id="save-mission" class="primary">Speichern</button><button id="delete-mission" class="danger" disabled>Löschen</button></div>
<div class="editor-tools"><button id="undo-edit" disabled title="Strg+Z (außer in Eingabefeldern)">↶ Rückgängig</button><button id="redo-edit" disabled title="Strg+Umschalt+Z / Strg+Y">↷ Wiederherstellen</button></div>
<div id="editor-dirty" class="editor-dirty" role="status" aria-live="polite">Keine ungespeicherten Änderungen</div>
<fieldset id="mission-fields">
<label>Missionsname<input id="mission-name" maxlength="100" value="Neue Wegpunktmission"></label>
<label>Beschreibung<textarea id="mission-description" rows="2" maxlength="1000" placeholder="Aufgabe, Einsatzgebiet, Hinweise"></textarea></label>
<div class="field-row">
<label>Fluggerät<select id="mission-model">__MISSION_MODEL_OPTIONS__</select></label>
<label>Flughöhe über Start (m)<input id="mission-altitude" type="number" min="2" max="500" step="1" value="50"></label>
<label>Geschwindigkeit (m/s)<input id="mission-speed" type="number" min="0.1" max="15" step="0.5" value="5"></label>
<label>Sichere Starthöhe (m)<input id="mission-takeoff" type="number" min="1.2" max="1500" step="1" value="20"></label>
<label>RTH-Höhe (m)<input id="mission-rth" type="number" min="2" max="500" step="1" value="60"></label>
<label>Mission beenden<select id="mission-finish"><option value="goHome">Return-to-Home</option><option value="noAction">Keine Aktion</option></select></label>
</div>
</fieldset>
<h2>Wegpunkte <span id="point-count" class="badge">0</span></h2>
<div class="button-row"><button id="add-mode">+ Auf Karte setzen</button><button id="fit-mission">Route einpassen</button></div>
<div class="note">„Auf Karte setzen“ aktivieren, dann klicken. Punkte lassen sich ziehen, bearbeiten, sortieren und löschen.</div>
<label class="route-option" for="close-route">
<input id="close-route" type="checkbox">
<span>Route schließen (letzten Wegpunkt mit erstem verbinden)</span>
</label>
<p class="route-explain">Eine geschlossene Route fliegt wirklich zurück zum ersten Wegpunkt. Im DJI-WPML-Export wird dafür ein zusätzlicher Wegpunkt angelegt, nicht nur eine Linie gezeichnet. Die Return-to-Home-Einstellung bleibt unabhängig davon.</p>
<div id="route-status" class="route-status" role="status" aria-live="polite">Offene Route. Noch keine Wegpunkte.</div>
<section class="route-analysis" aria-labelledby="route-analysis-title">
<h3 id="route-analysis-title">Routenanalyse · theoretische Werte</h3>
<div class="analysis-grid">
<div><small>Wegstrecke (geradlinig)</small><strong id="route-distance">–</strong></div>
<div><small>Flugzeit bei Sollgeschwindigkeit</small><strong id="route-duration">–</strong></div>
<div><small>Flugsegmente</small><strong id="route-legs">0</strong></div>
<div><small>Rückweg zu WP 1</small><strong id="route-return">–</strong></div>
</div>
<p id="route-analysis-warning" class="analysis-warning" role="status" aria-live="polite"></p>
<p class="note">WGS84-Großkreisentfernungen zwischen Wegpunkten. Nur ideale horizontale Reisezeit; kein Start/Steigflug, Bremsen, Schweben, Wind, Hindernisse, Gelände, RTH, Landung oder Akkuverbrauch. Keine Freigabe zum Fliegen.</p>
</section>
<div id="point-list"></div>
<div id="point-editor" hidden>
<h3>Wegpunkt <span id="edit-index">1</span> bearbeiten</h3>
<div class="field-row">
<label>Breitengrad (WGS84)<input id="point-lat" type="number" min="-90" max="90" step="0.0000001" inputmode="decimal"></label>
<label>Längengrad (WGS84)<input id="point-lon" type="number" min="-180" max="180" step="0.0000001" inputmode="decimal"></label>
</div>
<p class="coordinate-help">Koordinaten auf 7 Dezimalstellen begrenzt (WGS84, Grad). Zwischenpunkt: Koordinatenmittelwert zwischen Auswahl und nächstem Wegpunkt – keine Hindernis- oder Geländeprüfung.</p>
<label style="flex-direction:row;align-items:center"><input id="point-photo" type="checkbox" style="width:auto"> Foto am Wegpunkt aufnehmen</label>
<section aria-labelledby="point-actions-title">
  <h3 id="point-actions-title">Kamera und Gimbal (offline)</h3>
  <p id="point-action-support" class="note">DJI WPML-Aktionsmatrix; keine Flugfreigabe.</p>
  <div id="point-action-list"></div>
  <label>Aktion wählen<select id="point-action-type">
    <option value="startRecord">Video starten</option><option value="stopRecord">Video stoppen</option>
    <option value="focus">Punktfokus</option><option value="zoom">Brennweite setzen</option>
    <option value="gimbalRotate">Gimbal-Neigung setzen</option>
    <option value="gimbalEvenlyRotate">Neigung im nächsten Flugsegment</option>
  </select></label>
  <div id="point-focus-params" class="field-row" hidden>
    <label>Fokus X (0–1)<input id="point-focus-x" type="number" min="0" max="1" step="0.01" value="0.5"></label>
    <label>Fokus Y (0–1)<input id="point-focus-y" type="number" min="0" max="1" step="0.01" value="0.5"></label>
  </div>
  <label id="point-zoom-params" hidden>Brennweite (mm)<input id="point-zoom-mm" type="number" min="0.1" max="500" step="0.1" value="24"></label>
  <label id="point-pitch-params" hidden>Gimbal-Neigung (-90° bis 0°)<input id="point-pitch-deg" type="number" min="-90" max="0" step="1" value="-45"></label>
  <button id="point-action-add" type="button">Aktion hinzufügen</button>
</section>
<div class="button-row"><button id="apply-point">Übernehmen</button><button id="remove-point" class="danger">Entfernen</button></div>
<div class="button-row"><button id="insert-midpoint">Zwischenpunkt danach</button><button id="copy-point">WGS84 kopieren</button></div>
</div>
<hr>
<button id="open-csv" style="width:100%">Wegpunkte aus CSV importieren</button>
<p class="note">CSV zuerst prüfen, dann Wegpunkte im aktuellen Entwurf ersetzen. Speichern bleibt ein eigener Schritt.</p>
<label>Eigene AeroNexus-KMZ wieder öffnen<input type="file" id="import-kmz" accept=".kmz,application/vnd.google-earth.kmz"></label>
<div class="button-row"><button id="import-mission">KMZ importieren & bearbeiten</button></div>
<div class="button-row"><button class="primary" id="export-mission">KMZ / DJI WPML exportieren</button></div>
<p class="note">Exportiert eine Datei mit <code>wpmz/template.kml</code> und <code>wpmz/waylines.wpml</code>. Flugmissionen müssen vor einem Einsatz in DJI Pilot 2 auf Kompatibilität, Höhen, Luftraum, RTH und Sicherheit geprüft werden. Kein automatischer Import zur Drohne.</p>
</aside>
<aside class="side" id="geo-panel" hidden>
<h1>Geo-Objekte &amp; Flächenplanung</h1><p class="note">Eigenständige lokale Planungsdaten. Keine DJI-Missionsausführung oder Änderung am WPML-Export.</p>
<label>Objektname<input id="geo-name" maxlength="100" value="Einsatzfläche"></label>
<div class="field-row">
<label>Geometrietyp<select id="geo-kind"><option value="polygon">Polygon / Fläche</option><option value="line">Linie</option><option value="point">Punkt</option><option value="circle">Kreis</option></select></label>
<label>Kreisradius (m)<input id="geo-radius" type="number" min="1" max="5000" value="50"></label>
</div>
<div class="geo-buttons"><button id="geo-draw">Punkte auf Karte setzen</button><button id="geo-undo-vertex">Letzten Punkt entfernen</button><button id="geo-reset">Entwurf verwerfen</button></div>
<div id="geo-draft-status" class="note" role="status">Noch keine Geo-Punkte gesetzt.</div>
<div id="geo-draft-points" class="geo-list" aria-label="Stützpunkte des Geo-Entwurfs"></div>
<p class="note">Eckpunkte auf der Karte verschieben oder einzeln aus der Liste entfernen. Gespeicherte Objekte werden erst durch „Speichern“ aktualisiert.</p>
<button id="geo-save" class="primary" style="width:100%">Geo-Objekt speichern</button>
<h2>Lokale Geo-Objekte</h2><div id="geo-list" class="geo-list"></div>
<hr><h2>Parallele Flugstreifen · Vorschau</h2>
<div class="field-row">
<label>Spurabstand (m)<input id="survey-spacing" type="number" min="2" max="200" value="20"></label>
<label>Flugrichtung (°)<input id="survey-bearing" type="number" min="0" max="359" value="0"></label>
</div>
<label>Fläche auswählen<select id="survey-object"><option value="">Polygon auswählen…</option></select></label>
<button id="survey-generate" class="primary" style="width:100%">Flugstreifen berechnen</button>
<div id="survey-message" class="note" role="status">Nur unabhängige parallele Flugstreifen, keine verbundenen Flugwege. Keine Hindernis- oder Geländefreigabe.</div>
<hr><h2>Gelände aus GeoTIFF</h2>
<label>DEM-GeoTIFF (max. 8 MiB)<input type="file" id="terrain-file" accept=".tif,.tiff,image/tiff"></label>
<div class="geo-buttons"><button id="terrain-preview" class="primary">3D-Vorschau</button><button id="terrain-export" disabled>STL exportieren</button></div>
<canvas id="terrain-canvas" width="320" height="210" role="img" aria-label="Drehbare schematische 3D-Höhenraster-Vorschau"></canvas>
<div class="geo-buttons">
<button id="terrain-open-large" disabled>Interaktive Großansicht öffnen</button>
<button id="terrain-show-map" disabled>Geländeausschnitt auf Karte</button>
</div>
<div id="terrain-message" class="note" role="status">Lokales GDAL erforderlich. Höhenmodell nur Visualisierung und 3D-Modell – nicht zur Flugfreigabe.</div>
</aside>
<aside class="side" id="wayline-panel" hidden>
<h1>Cloud-Routen</h1>
<p class="note">Vorhandene Flugrouten aus der lokalen Pilot-2-Cloud und dem geladenen FlightHub-Katalog.</p>
<p>Die Liste ist schreibgeschützt. Der offene Studio-Entwurf bleibt unverändert.</p>
<p class="note">Gleiche Namen sind nur Hinweise. Eine Übereinstimmung des Routeninhalts ist noch nicht geprüft.</p>
<p class="note">Lokale Pilot-2-KMZ lassen sich bei unterstützter Geometrie schreibgeschützt auf der Karte betrachten. Keine Bearbeitung und keine Flugfreigabe.</p>
</aside>
<aside class="side" id="media-panel" hidden>
<h1>Medienimport</h1><p class="note">Bilder und Videos werden ausschließlich im privaten Pi-Arbeitsbereich gespeichert. Maximal 25 MiB je Datei.</p>
<label>Bild-/Videodateien<input type="file" id="media-file" accept=".jpg,.jpeg,.png,.webp,.mp4,image/jpeg,image/png,image/webp,video/mp4" multiple></label>
<button id="upload-media" class="primary">Ausgewählte Medien hochladen</button>
<div class="status" id="media-notice">Medienbibliothek wird geladen…</div>
<hr><h2>GeoPhoto · Kameradaten</h2>
<p class="note">Aufnahmeort und Kameraausrichtung manuell eintragen. Metadaten werden nicht aus einer DJI-Aufnahme erfunden.</p>
<label>Foto auswählen<select id="geophoto-media"><option value="">Bild auswählen</option></select></label>
<div class="field-row">
<label>Breitengrad<input id="geophoto-lat" type="number" step="0.0000001" min="-90" max="90"></label>
<label>Längengrad<input id="geophoto-lon" type="number" step="0.0000001" min="-180" max="180"></label>
<label>Höhe (m, optional)<input id="geophoto-alt" type="number" step="0.1" min="-500" max="12000"></label>
<label>Blickrichtung (°, optional)<input id="geophoto-heading" type="number" step="0.1" min="0" max="359.9"></label>
<label>Kameraneigung (°, optional)<input id="geophoto-pitch" type="number" step="0.1" min="-90" max="90"></label>
<label>Roll (°, optional)<input id="geophoto-roll" type="number" step="0.1" min="-180" max="180"></label>
</div>
<label>Aufnahmezeit mit Zeitzone (ISO 8601)<input id="geophoto-captured" placeholder="2026-10-16T15:30:00+02:00"></label>
<label>Notizen<textarea id="geophoto-notes" maxlength="512" rows="2"></textarea></label>
<div class="geo-buttons"><button id="geophoto-save" class="primary">GeoPhoto speichern</button><button id="geophoto-show">Fotos auf Karte</button></div>
<div id="geophoto-status" class="note" role="status">Aufnahmeorte sind getrennt von geplanten Flugwegen.</div>
<hr><h3>Speicherort</h3><p class="note"><code>~/.local/share/aeronexusadvanced/media</code> auf dem Raspberry Pi. Unterstützt JPEG, PNG, WebP und MP4. Keine öffentliche Medienfreigabe.</p>
</aside>
<aside class="side" id="fleet-panel" hidden>
<h1>Live-Flotte</h1><p class="note">Liest ausschließlich die vorhandene AeroNexus-Status-API. DJI-Flugsteuerung bleibt gesperrt.</p>
<button id="refresh-fleet" class="primary">Flotte aktualisieren</button>
<div class="status" id="fleet-notice">Flottendaten werden geladen…</div>
<div class="geo-buttons"><button id="connect-events">Live-Ereignisse verbinden</button></div>
<div class="note" id="event-status" role="status">Lokale WebSocket-Ereignisse optional; auf dem Pi standardmäßig deaktiviert.</div>
<div class="button-row"><button id="show-fleet-map">Gerätepositionen auf Karte</button></div>
<p class="note">Die Kartenkacheln stammen von einem externen Kartenanbieter. Bei Darstellung des Einsatzgebiets kann der Anbieter den angeforderten Kartenausschnitt erkennen. Keine Telemetrie wird direkt an DJI gesendet.</p>
</aside>
<main class="content">
<section class="pane active" id="map-pane">
<div id="map" role="application" aria-label="Interaktive Missionskarte"></div>
<div class="map-bar" id="map-toolbar" data-compact="true">
<button id="map-focus-toggle" type="button" class="map-primary" aria-pressed="false">Kartenfokus</button>
<button id="map-tools-toggle" type="button" class="map-primary" aria-expanded="false" aria-controls="map-tools-details">Werkzeuge</button>
<button id="wayline-preview-fit" hidden type="button" class="map-primary">Route zentrieren</button>
<button id="cloud-overview-map-open" hidden type="button" class="map-primary" aria-pressed="false">Alle Cloud-Routen</button>
<div id="map-tools-details" class="map-extra" style="display:contents">
<select id="map-layer" class="map-extra" aria-label="Kartenstil"><option value="satellite" selected>Satellit (Esri)</option><option value="street">Straßenkarte (OSM)</option></select>
<button id="pilot2-map-toggle" class="map-extra" aria-pressed="false" title="Read-only Pilot-2-Kartenobjekte anzeigen">Pilot-2-Layer einblenden</button>
<button id="wayline-preview-clear" hidden class="map-extra">Cloud-Vorschau schließen</button>
<button id="map-zoom-in" class="map-extra">+</button><button id="map-zoom-out" class="map-extra">−</button>
<button id="map-home" class="map-extra" title="Karte auf 76694 Forst (Baden) zurücksetzen">76694 Forst</button>
<button id="map-fit" class="map-extra">Mission zentrieren</button>
<button id="map-info-toggle" class="map-extra" type="button" aria-expanded="false" aria-controls="map-info">Hinweis zeigen</button>
</div>
</div>
<section id="cloud-overview-panel" role="region" aria-label="Cloud-Waylines auf der Karte" hidden>
  <div class="cloud-head"><strong>Cloud-Routen · nur lesen</strong><button id="cloud-overview-expand" type="button" aria-expanded="false" aria-controls="cloud-overview-list">Routen anzeigen</button><button id="cloud-overview-close" type="button">Schließen</button></div>
  <p class="note" id="cloud-overview-status" role="status" aria-live="polite">Keine Cloud-Routen geladen.</p>
  <button id="cloud-overview-fit" type="button" disabled>Alle sichtbaren Routen zentrieren</button>
  <div id="cloud-overview-list" aria-label="Routen ein- oder ausblenden"></div>
  <p class="note cloud-overview-help">Linienlänge = horizontale WGS84-Segmentstrecke, keine Flugdistanz. Weiße Kreise: Linienanfang, farbige Kreise: Linienende. Keine Flugfreigabe oder Missionsänderung.</p>
</section>
<div class="map-info" id="map-info" role="status" aria-live="polite" data-minimized="false"><button id="map-info-chip" type="button" aria-expanded="false" aria-controls="map-info-detail">Karte · Hinweis anzeigen</button><span id="map-info-detail">Startpunkt: 76694 Forst (Baden). Satellitenkarte: © Esri und Datenanbieter; Straßenkarte: © OpenStreetMap-Mitwirkende. Kartenkacheln extern, Missionen bleiben lokal auf dem Pi.</span></div>
</section>
<section class="pane" id="terrain-pane">
<div class="terrain-stage">
<h1>Interaktive 3D-Geländeansicht</h1>
<p class="note">Lokales Höhenraster aus GeoTIFF, ausschließlich zur Veranschaulichung. Mit Maus oder Finger drehen/neigen; Mausrad zoomt. Die Ansicht ist orthografisch und kein georeferenziertes 3D-Kartenmodell.</p>
<div class="terrain-controls">
<label>Rotation <output id="terrain-azimuth-value">45°</output><input id="terrain-azimuth" type="range" min="-180" max="180" step="1" value="45"></label>
<label>Neigung <output id="terrain-tilt-value">45°</output><input id="terrain-tilt" type="range" min="15" max="80" step="1" value="45"></label>
<label>Zoom <output id="terrain-zoom-value">1,0×</output><input id="terrain-zoom" type="range" min="0.5" max="2.5" step="0.1" value="1"></label>
<label>Höhenüberhöhung <output id="terrain-exaggeration-value">2,0×</output><input id="terrain-exaggeration" type="range" min="1" max="6" step="0.5" value="2"></label>
</div>
<div class="terrain-toggles">
<label><input id="terrain-color" type="checkbox" checked> Höhenfarben</label>
<label><input id="terrain-slope" type="checkbox"> Hangneigung einfärben</label>
<label><input id="terrain-wire" type="checkbox" checked> Gitternetz</label>
<label><input id="terrain-geo-overlay" type="checkbox" checked> Geo-Objekte (nur EPSG:4326)</label>
<button id="terrain-reset-view">Ansicht zurücksetzen</button>
</div>
<div id="terrain-georef-info" class="terrain-location" role="status">Keine WGS84-Georeferenz geladen. Geländedarstellung weiterhin möglich.</div>
<div id="terrain-slope-info" class="terrain-location" role="status">Noch keine Hangneigungsanalyse. GeoTIFF laden, um die lokale DEM-Neigung auszuwerten.</div>
<canvas id="terrain-canvas-large" width="1000" height="590" role="img" aria-label="Interaktive orthografische Geländedarstellung"></canvas>
<div id="terrain-large-message" class="terrain-help" role="status">Noch kein Höhenraster geladen. Links unter „Gelände aus GeoTIFF“ eine Datei auswählen und „3D-Vorschau“ drücken.</div>
<div id="terrain-coordinate-probe" class="terrain-location" role="status">Klick auf die Geländeoberfläche: Rasterhöhe und WGS84-Position anzeigen (kein bekannter vertikaler Höhenbezug).</div>
<h2>Höhenprofil einer gespeicherten Linie</h2>
<div class="terrain-geo-tools">
<label>Geo-Linie auswählen<select id="terrain-profile-object"><option value="">Linie auswählen…</option></select></label>
<button id="terrain-profile-generate">Höhenprofil erzeugen</button>
</div>
<canvas id="terrain-profile-canvas" width="980" height="190" role="img" aria-label="Schematisches Profil der interpolierten DEM-Höhen"></canvas>
<div id="terrain-profile-message" class="terrain-help" role="status">Nur gespeicherte Linien, deren Punkte vollständig innerhalb des WGS84-Rasters liegen, können ausgewertet werden.</div>
<p class="terrain-help">Die Hangneigung wird aus benachbarten Original-Rasterhöhen und den angenäherten horizontalen Rasterabständen berechnet (ohne Höhenüberhöhung). Stark vereinfachte, resampelte DEM-Visualisierung: keine Böschungs-, Hindernis- oder Flugfreigabe.</p>
<p class="terrain-help">Schematische EPSG:4326-Punktzuordnung nur für kleine nordorientierte Raster. Höhenwerte bleiben in Metern, ihre vertikale Referenz (z. B. Geoid oder Ellipsoid) ist unbekannt. Überhöhung betrifft nur die Darstellung, niemals STL-Daten. Keine Hindernisprüfung oder DJI-Flugfreigabe.</p>
</div>
</section>
<section class="pane" id="media-pane">
<div class="pane-inner">
<div class="page-head"><div><h1>Medienbibliothek</h1><p class="muted">Private Dateien auf deinem Raspberry Pi · Fotos & Videos</p></div>
<div class="filters"><input type="search" id="media-search" placeholder="Medien suchen…">
<button id="refresh-media">Aktualisieren</button></div></div>
<div class="gallery" id="gallery"><div class="empty">Lokale Medienbibliothek wird geladen…</div></div>
<div class="button-row"><button id="more-media" hidden>Weitere Medien anzeigen</button></div>
<hr>
<div class="page-head">
  <div><h2>DJI-Medien aus MinIO</h2><p class="muted">Lesender, separater Objektkatalog · keine Kopien oder Löschfunktion</p></div>
  <div class="filters"><input type="search" id="dji-media-search" placeholder="DJI-Dateinamen suchen…">
  <button id="refresh-dji-media">DJI-Katalog laden</button></div>
</div>
<p class="note" id="dji-media-status" role="status">Noch keine MinIO-Medien geladen.</p>
<div class="gallery" id="dji-media-gallery"></div>
<div class="button-row"><button id="more-dji-media" hidden>Weitere DJI-Medien anzeigen</button></div>
<footer>Vorschaubilder werden mit deinem Token geladen und nur als temporäre Browser-Objekte angezeigt. Kein externer Mediendienst.</footer>
</div>
</section>
<section class="pane" id="waylines-pane">
<div class="pane-inner">
<div class="page-head"><div><h1>Wayline-Bibliothek</h1><p class="muted">Cloud-Routen und Abgleich mit gespeicherten Studio-Missionen</p></div><div class="button-row"><button id="wayline-overview-open" disabled>Alle lokalen Routen auf Karte (max. 8)</button><button id="refresh-waylines">Routen aktualisieren</button></div></div>
<div class="wayline-tools">
<label for="wayline-search">Routenname suchen<input id="wayline-search" type="search" autocomplete="off"></label>
<button id="clear-wayline-search" disabled>Suche löschen</button>
<label for="wayline-source">Quelle<select id="wayline-source"><option value="all">Alle Quellen</option><option value="pilot2-local-cloud">Lokale Pilot-2-Cloud</option><option value="flighthub-public-v2">FlightHub</option></select></label>
</div>
<div id="wayline-state" class="status" role="status" aria-live="polite">Cloud-Routen werden beim Öffnen geladen.</div>
<p id="wayline-range" class="note" role="status" aria-live="polite"></p>
<div id="wayline-grid" class="wayline-grid" role="region" aria-label="Cloud-Routen"></div>
<div class="button-row"><button id="wayline-prev" disabled>Vorherige Seite</button><span id="wayline-page">Seite 1</span><button id="wayline-next" disabled>Nächste Seite</button></div>
<section id="pilot2-action-summary" class="wayline-tools" aria-labelledby="pilot2-action-title" style="display:block;margin-top:22px">
  <div class="page-head"><div><h2 id="pilot2-action-title">Pilot-2-WPML-Diagnose (nur lesen)</h2><p class="muted">Anonyme Aktionszählung aus bis zu acht Cloud-Waylines. Kein Import, keine Ausführung und keine Flugfreigabe.</p></div>
  <button id="pilot2-action-load">Aktionsdiagnose laden</button></div>
  <p id="pilot2-action-status" class="status" role="status" aria-live="polite">Nur nach Klick: keine automatischen KMZ-Abrufe.</p>
  <div id="pilot2-action-results" class="wayline-grid" role="region" aria-label="Anonyme DJI-Aktionsdiagnose"></div>
</section>
</div>
</section>
<section class="pane" id="fleet-pane">
<div class="pane-inner">
<div class="page-head"><div><h1>Flottenstatus</h1><p class="muted">Matrice 4T und weitere DJI-Geräte · Echtzeitstatus aus FlightHub 2</p></div></div>
<div id="fleet-grid" class="fleet-grid"><div class="empty">Lokale Flottendaten werden geladen…</div></div>
<div class="page-head" style="margin-top:24px"><div><h2>Direkte Pilot-2-Gerätetopologie</h2><p class="muted">Drohnen, Fernsteuerungen und Zuordnung aus der lokalen Cloud · nur lesen</p></div><button id="pilot2-topology-refresh">Pilot-2-Geräte laden</button></div>
<div id="pilot2-topology-state" class="status" role="status" aria-live="polite">Daten werden nur nach Klick geladen.</div>
<div id="pilot2-topology-grid" class="fleet-grid"></div>
</div>
</section>
</main>
</div>
<dialog id="media-dialog"><div class="flex between"><strong id="preview-name">Vorschau</strong><button id="preview-close">Schließen</button></div><div id="preview-content" style="margin-top:15px"></div></dialog>
<dialog id="csv-dialog" aria-labelledby="csv-title" aria-describedby="csv-help">
<div class="csv-heading flex between"><h2 id="csv-title" style="margin:0">Wegpunkte aus CSV</h2><button id="csv-close" autofocus>Schließen</button></div>
<div class="csv-body">
<p id="csv-help" class="note">UTF-8, maximal 512 KiB und 500 ausführbare Wegpunkte. Pflichtspalten: latitude (Breitengrad), longitude (Längengrad), optional take_photo. Ausschließlich WGS84 in Grad; keine automatische Erkennung der Spaltenreihenfolge.</p>
<label for="csv-file">CSV-Datei<input id="csv-file" type="file" accept=".csv,text/csv" aria-describedby="csv-help csv-message"></label>
<div class="field-row">
<label for="csv-delimiter">Trennzeichen<select id="csv-delimiter"><option value="semicolon">Semikolon (;)</option><option value="comma">Komma (,)</option><option value="tab">Tabulator</option></select></label>
<label for="csv-decimal">Zahlenformat<select id="csv-decimal"><option value="dot">Dezimalpunkt · 49.1533</option><option value="comma">Dezimalkomma · 49,1533</option></select></label>
</div>
<p class="note">Foto: true/false, 1/0 oder ja/nein; leer bedeutet kein Foto. Koordinaten werden auf 7 Dezimalstellen gerundet. Höhe, Geschwindigkeit und weitere Missionswerte bleiben aus dem aktuellen Entwurf erhalten. Zusätzliche Spalten werden abgelehnt.</p>
<div class="button-row"><button id="csv-template">CSV-Beispiel herunterladen</button></div>
<div id="csv-message" class="status" role="status" aria-live="polite" tabindex="-1">Datei auswählen und Vorschau prüfen. Noch keine Wegpunkte übernommen.</div>
<ul id="csv-errors" hidden></ul>
<div id="csv-result" hidden>
<p class="note">Spaltenreihenfolge und Lage prüfen: plausible vertauschte Koordinaten lassen sich nicht automatisch erkennen. Kartenkacheln werden wie im Missionseditor beim bestehenden Kartenanbieter geladen.</p>
<div id="csv-map" role="region" aria-label="Kartenprüfung der CSV-Wegpunkte"></div>
<p id="csv-map-message" class="note" role="status"></p>
<div class="csv-table" tabindex="0" role="region" aria-label="CSV-Wegpunkttabelle">
<table><caption id="csv-range">Geprüfte Wegpunkte</caption><thead><tr><th scope="col">Zeile</th><th scope="col">Breitengrad</th><th scope="col">Längengrad</th><th scope="col">Foto</th></tr></thead><tbody id="csv-rows"></tbody></table>
</div>
<div class="button-row"><button id="csv-more" hidden>Weitere 50 Wegpunkte anzeigen</button></div>
</div>
<p class="note">„Wegpunkte ersetzen“ ersetzt alle Wegpunkte des aktuellen Entwurfs. Rückgängig ist möglich; gespeicherte Missionen ändern sich erst durch „Speichern“. Kein Upload zur Drohne.</p>
</div>
<div class="csv-actions"><button id="csv-check">Vorschau prüfen</button><button id="csv-apply" class="primary" disabled>Wegpunkte ersetzen</button></div>
</dialog>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
"use strict";
const $=id=>document.getElementById(id);
const els=(tag,cls,text)=>{const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=String(text);return el};
const EMPTY=()=>({name:"Neue Wegpunktmission",description:"",drone_model:"matrice4t",altitude_m:50,speed_mps:5,takeoff_security_height_m:20,rth_height_m:60,finish_action:"goHome",close_route:false,waypoints:[]});
const WPML_ACTION_TYPES=new Set(["startRecord","stopRecord","focus","zoom","gimbalRotate","gimbalEvenlyRotate"]);
const WPML_ACTION_LABELS={startRecord:"Video starten",stopRecord:"Video stoppen",focus:"Punktfokus",
zoom:"Brennweite",gimbalRotate:"Gimbal-Neigung",gimbalEvenlyRotate:"Segment-Neigung"};
const WPML_ACTION_MODELS=new Set(["matrice4e","matrice4t","mavic3e","mavic3t","mavic3m"]);
let mission=EMPTY(),missionId=null,selected=-1,addMode=false,epoch=0,knownMissions=[],knownMedia=[],displayMedia=20,mediaUrls=[],previewUrl=null;
const FORM_IDS=["mission-name","mission-description","mission-model","mission-altitude",
  "mission-speed","mission-takeoff","mission-rth","mission-finish"];
const HISTORY_LIMIT=60;
let editHistory=[],editIndex=-1,editGroup=null,cleanSnapshot=null;
// Fixed initial view of Forst (Baden), postal code 76694, approximate town centre.
// Loading other saved missions does not modify this default for the next page load.
const HOME_VIEW=Object.freeze({label:"76694 Forst (Baden)",latitude:49.1533,longitude:8.58417,zoom:15});
const SATELLITE_TILE_URL="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
let map=null,lines=null,waypointsLayer=null,deviceLayer=null,pilot2MapLayer=null,geoLayer=null,surveyLayer=null,photoLayer=null,terrainFootprintLayer=null,mapTile=null,mapTiles={},streetTileErrors=0;
let pilot2LayerVisible=false,pilot2LayerRequest=0,waylinePreviewLayer=null,waylinePreviewRequest=0,waylinePreviewBounds=null;
let cloudOverviewLayer=null,cloudOverviewGeneration=0,cloudOverviewController=null,cloudOverviewRoutes=[];
const CLOUD_OVERVIEW_COLORS=["#ffb74d","#60b5ff","#82d39a","#df9eff","#ff7993","#66d8d5","#f3dc6d","#b8abff"];
let geoObjects=[],geoDraft=[],geoDraw=false,geoEditingId=null,terrainGrid=null,terrainGeo=null,terrainLoadSerial=0,terrainProfile=null,studioSocket=null,studioFleetLoading=false;
function notice(text,error=false){$("notice").textContent=text;$("notice").className="status"+(error?" error":"");}
function statusMessage(text,error=false){
  $("auth-message").textContent=text;
  $("auth-message").className="auth-message"+(error?" error":" ok");
}
function errorMessage(error){
  const detail=String(error?.message||"Unbekannter Fehler");
  if(detail.includes("HTTP 401"))return "LAN-Zugriff nicht aktiviert (HTTP 401).";
  if(detail.includes("HTTP 403"))return "Zugriff nur direkt über das freigegebene HTTPS-Heimnetz (HTTP 403).";
  if(detail.includes("HTTP 503"))return "LAN-Konfiguration oder privater Missionsspeicher nicht bereit (HTTP 503).";
  if(detail.includes("Failed to fetch")||detail.includes("NetworkError")||detail.includes("Load failed"))
    return "Netzwerkfehler: HTTPS-Verbindung zum Pi prüfen.";
  return detail;
}
function clean(text){return text===null||text===undefined?"–":String(text)}
function cardText(parent,tag,cls,text){const el=els(tag,cls,text);parent.appendChild(el);return el}
async function api(path,options={}){
  const session=epoch;
  const opts={cache:"no-store",...options};
  const response=await fetch(path,opts);
  if(session!==epoch)throw new Error("Sitzung beendet");
  if(!response.ok){
    let msg="HTTP "+response.status;
    try{const j=await response.json();if(typeof j.detail==="string")msg+=" · "+j.detail}catch(_){}
    throw new Error(msg);
  }
  return response;
}
function syncForm(){
  $("mission-name").value=mission.name;$("mission-description").value=mission.description;
  $("mission-model").value=mission.drone_model;$("mission-altitude").value=mission.altitude_m;
  $("mission-speed").value=mission.speed_mps;$("mission-takeoff").value=mission.takeoff_security_height_m;
  $("mission-rth").value=mission.rth_height_m;$("mission-finish").value=mission.finish_action;
  $("close-route").checked=mission.close_route===true;
}
// Keep undo history in volatile browser memory only; no mission is autosaved.
// Snapshots preserve typed form text (including incomplete numeric values).
function editorSnapshot(){
  const form={};
  for(const id of FORM_IDS)form[id]=$(id).value;
  form["close-route"]=$("close-route").checked;
  // Canonicalize metadata in the snapshot, even before getForm() is called.
  // Saving must not add a phantom undo step with identical visible fields.
  const draft=JSON.parse(JSON.stringify(mission));
  draft.name=form["mission-name"].trim();
  draft.description=form["mission-description"];
  draft.drone_model=form["mission-model"];
  draft.finish_action=form["mission-finish"];
  draft.close_route=form["close-route"];
  for(const [id,key] of [
    ["mission-altitude","altitude_m"],["mission-speed","speed_mps"],
    ["mission-takeoff","takeoff_security_height_m"],["mission-rth","rth_height_m"]
  ]){
    if(form[id].trim()!==""){
      const value=Number(form[id]);
      if(Number.isFinite(value))draft[key]=value;
    }
  }
  return {mission:draft,form,selected};
}
function editorSignature(snapshot){
  return JSON.stringify({mission:snapshot.mission,form:snapshot.form});
}
function editorDirty(){
  return cleanSnapshot!==null&&editorSignature(editorSnapshot())!==cleanSnapshot;
}
function editorState(){
  const dirty=editorDirty();
  $("editor-dirty").textContent=dirty?"Ungespeicherte Änderungen":"Keine ungespeicherten Änderungen";
  $("editor-dirty").classList.toggle("unsaved",dirty);
  $("undo-edit").disabled=editIndex<=0;
  $("redo-edit").disabled=editIndex<0||editIndex>=editHistory.length-1;
}
function historyReset(){
  editHistory=[editorSnapshot()];
  editIndex=0;
  editGroup=null;
  cleanSnapshot=editorSignature(editHistory[0]);
  editorState();
}
function historyRecord(group=null){
  const current=editorSnapshot();
  if(editIndex>=0&&editorSignature(editHistory[editIndex])===editorSignature(current)){
    editHistory[editIndex].selected=selected;
    if(group===null)editGroup=null;
    editorState();
    return;
  }
  // Coalesce consecutive keystrokes in the same form control.
  if(group!==null&&group===editGroup&&editIndex===editHistory.length-1&&editIndex>0){
    editHistory[editIndex]=current;
  }else{
    editHistory=editHistory.slice(0,editIndex+1);
    editHistory.push(current);
    if(editHistory.length>HISTORY_LIMIT)editHistory.shift();
    editIndex=editHistory.length-1;
  }
  editGroup=group;
  editorState();
}
function historyApply(index){
  if(index<0||index>=editHistory.length)return false;
  const saved=editHistory[index];
  mission=JSON.parse(JSON.stringify(saved.mission));
  selected=saved.selected;
  for(const id of FORM_IDS)$(id).value=saved.form[id];
  $("close-route").checked=saved.form["close-route"];
  editIndex=index;
  editGroup=null;
  redraw();
  editorState();
  return true;
}
function undoEdit(){return historyApply(editIndex-1);}
function redoEdit(){return historyApply(editIndex+1);}
function historySaved(signature){
  cleanSnapshot=signature===undefined?editorSignature(editorSnapshot()):signature;
  editorState();
}
function allowDiscard(){
  return !editorDirty()||window.confirm(
    "Ungespeicherte Missionsänderungen verwerfen? Diese können nicht wiederhergestellt werden.");
}
function isTextEditing(target){
  if(!target)return false;
  if(target.isContentEditable)return true;
  const tag=String(target.tagName||"").toLowerCase();
  return tag==="input"||tag==="textarea"||tag==="select";
}
function midpointCoordinates(a,b){
  if(!a||!b||!Number.isFinite(a.latitude)||!Number.isFinite(a.longitude)||
     !Number.isFinite(b.latitude)||!Number.isFinite(b.longitude)||
     Math.abs(a.latitude)>90||Math.abs(b.latitude)>90||
     Math.abs(a.longitude)>180||Math.abs(b.longitude)>180)return null;
  const delta=(((b.longitude-a.longitude+540)%360)+360)%360-180;
  const lat=+((a.latitude+b.latitude)/2).toFixed(7);
  const lon=+(((((a.longitude+delta/2)+540)%360+360)%360)-180).toFixed(7);
  if(lat===0&&lon===0)return null;
  return {latitude:lat,longitude:lon,take_photo:false};
}
function insertMidpoint(){
  if(selected<0||selected>=mission.waypoints.length-1)return false;
  if(resolvedWaypoints().length>=500){
    notice("Maximal 500 ausführbare WPML-Wegpunkte erlaubt.",true);return false;
  }
  const point=midpointCoordinates(mission.waypoints[selected],mission.waypoints[selected+1]);
  if(!point){notice("Zwischenpunkt aus ungültigen Koordinaten.",true);return false;}
  mission.waypoints.splice(selected+1,0,point);
  selected++;
  redraw();historyRecord();
  notice("Zwischenpunkt eingefügt · vor dem Flug Wegführung prüfen.");
  return true;
}
function getForm(){
  mission.name=$("mission-name").value.trim();
  mission.description=$("mission-description").value;
  mission.drone_model=$("mission-model").value;
  mission.altitude_m=Number($("mission-altitude").value);
  mission.speed_mps=Number($("mission-speed").value);
  mission.takeoff_security_height_m=Number($("mission-takeoff").value);
  mission.rth_height_m=Number($("mission-rth").value);
  mission.finish_action=$("mission-finish").value;
  mission.close_route=$("close-route").checked;
  const resolved=resolvedWaypoints();
  if(resolved.length>500)throw new Error("Geschlossene Missionen dürfen höchstens 500 ausführbare Wegpunkte haben.");
  if(mission.close_route&&mission.waypoints.length>=2&&
     new Set(mission.waypoints.map(p=>p.latitude+","+p.longitude)).size<3)
    throw new Error("Route schließen erfordert mindestens 3 unterschiedliche Wegpunkte.");
  if(!mission.name||mission.name.length>100)throw new Error("Bitte gültigen Missionsnamen eingeben.");
  for(const [key,min,max] of [["altitude_m",2,500],["speed_mps",0.1,15],["takeoff_security_height_m",1.2,1500],["rth_height_m",2,500]]){
    if(!Number.isFinite(mission[key])||mission[key]<min||mission[key]>max)throw new Error("Ungültiger Wert: "+key);
  }
  return mission;
}
function getMap(){
  if(map)return;
  if(!window.L){
    notice("Kartenbibliothek nicht geladen. Browser-Internetverbindung und CDN-Zugriff prüfen.",true);
    $("map").textContent="Die interaktive Karte benötigt Leaflet 1.9.4 (Internetverbindung im Browser).";
    return;
  }
  map=L.map("map",{zoomControl:false,worldCopyJump:true}).setView(
    [HOME_VIEW.latitude,HOME_VIEW.longitude],HOME_VIEW.zoom);
  // The page keeps no-referrer for private pages; OSM requires a Referer
  // on its own tile requests. Send only the origin via Leaflet's tile option.
  // Never proxy or forge requests to bypass OSM server restrictions.
  mapTiles.street=L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{
    maxZoom:19,maxNativeZoom:19,referrerPolicy:"strict-origin-when-cross-origin",
    attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>'
  });
  mapTiles.satellite=L.tileLayer(SATELLITE_TILE_URL,{
    maxZoom:19,maxNativeZoom:19,attribution:"Tiles &copy; Esri and data providers"
  });
  // OSM may return a 403 warning *as an image* with HTTP 200. Start with
  // satellite imagery so a rejected OSM tile does not obstruct planning.
  mapTile=mapTiles.satellite.addTo(map);
  $("map-layer").value="satellite";
  mapTiles.street.on("tileerror",()=>{
    if(mapTile!==mapTiles.street)return;
    streetTileErrors++;
    if(streetTileErrors>=2){
      setMapLayer("satellite");
      mapWarning("Straßenkarten-Kacheln nicht verfügbar. Automatisch zur Satellitenkarte gewechselt. Bei einer OSM-403-Sperrbildkachel bitte manuell Satellit auswählen.");
    }
  });
  mapTiles.satellite.on("tileerror",()=>{
    if(mapTile===mapTiles.satellite)
      mapWarning("Satellitenbilder derzeit nicht abrufbar. Kartenanbieter/Internetverbindung prüfen; geplante Wegpunkte bleiben erhalten.");
  });
  waypointsLayer=L.layerGroup().addTo(map);deviceLayer=L.layerGroup().addTo(map);
  geoLayer=L.layerGroup().addTo(map);surveyLayer=L.layerGroup().addTo(map);photoLayer=L.layerGroup().addTo(map);
  terrainFootprintLayer=L.layerGroup().addTo(map);
  pilot2MapLayer=L.layerGroup(); // Off by default. Never mutates editable mission layers.
  waylinePreviewLayer=L.layerGroup(); // Read-only cloud preview, separate from mission.
  cloudOverviewLayer=L.layerGroup(); // Independently toggleable read-only cloud routes.
  map.on("click",event=>{
    if((waylinePreviewLayer&&map.hasLayer(waylinePreviewLayer))||
       (cloudOverviewLayer&&map.hasLayer(cloudOverviewLayer)))return; // no edits during either preview
    if(geoDraw){
      const lat=+event.latlng.lat.toFixed(7),lon=+(((((event.latlng.lng+540)%360)+360)%360)-180).toFixed(7);
      if(!Number.isFinite(lat)||Math.abs(lat)>90||!Number.isFinite(lon))return;
      if(geoDraft.length>=128)return;
      geoDraft.push({latitude:lat,longitude:lon});
      redrawGeo();return;
    }
    if(!addMode)return;
    const lat=+event.latlng.lat.toFixed(7);
    const lon=Number(((((event.latlng.lng+540)%360)-180)).toFixed(7));
    if(!Number.isFinite(lat)||!Number.isFinite(lon)||(lat===0&&lon===0))return;
    mission.waypoints.push({latitude:lat,longitude:lon,take_photo:false});
    selected=mission.waypoints.length-1;redraw();historyRecord();
  });
}
function mapStatusSummary(text){
  const message=String(text);
  const routePrefix="Schreibgeschützte Cloud-Vorschau: ";
  if(message.startsWith(routePrefix)){
    const name=message.slice(routePrefix.length).split(" · ")[0];
    return "Cloud-Vorschau: "+name;
  }
  if(message.includes("Cloud-Waylines in der Kartenübersicht"))return message.split(".")[0];
  return message.split(".")[0];
}
function mapInfoMessage(text,warning=false){
  // Keep full accessible details without a line-clamped box over Leaflet attribution.
  const message=String(text);
  const banner=$("map-info");
  $("map-info-detail").textContent=message;
  $("map-info-chip").textContent="ℹ "+mapStatusSummary(message)+
    (banner.dataset.minimized==="true"?" · Details":" · Weniger");
  banner.classList.toggle("warning",warning);
}
function mapWarning(text){
  mapInfoMessage(text,true);
}
function setMapLayer(kind){
  if(!map||!mapTiles[kind])return;
  if(mapTile)map.removeLayer(mapTile);
  streetTileErrors=0;
  mapTile=mapTiles[kind].addTo(map);
  $("map-layer").value=kind;
  mapInfoMessage(kind==="satellite"
    ?"Startpunkt: 76694 Forst (Baden) · Satellitenbilder © Esri und Datenanbieter. Es werden ausschließlich sichtbare Kartenkacheln geladen."
    :"Startpunkt: 76694 Forst (Baden) · Straßenkarte © OpenStreetMap-Mitwirkende. Nur die Seitenherkunft wird an den Kartenserver übertragen.",false);
}
async function togglePilot2MapLayer(){
  if(!map||!pilot2MapLayer)throw new Error("Karte nicht verfügbar");
  pilot2LayerVisible=!pilot2LayerVisible;
  const request=++pilot2LayerRequest;
  const button=$("pilot2-map-toggle");
  button.setAttribute("aria-pressed",String(pilot2LayerVisible));
  button.textContent=pilot2LayerVisible?"Pilot-2-Layer ausblenden":"Pilot-2-Layer einblenden";
  if(!pilot2LayerVisible){
    pilot2MapLayer.clearLayers();map.removeLayer(pilot2MapLayer);
    mapWarning("Pilot-2-Layer ausgeblendet. Lokale Geo-Objekte und Missionen unverändert.");
    return;
  }
  pilot2MapLayer.clearLayers();
  pilot2MapLayer.addTo(map);
  button.disabled=true;
  try{
    const response=await api("/api/v1/local-cloud/map-elements");
    const data=await response.json();
    if(request!==pilot2LayerRequest||!pilot2LayerVisible)return;
    if(data.state!=="connected")throw new Error("Pilot-2-Layer: "+clean(data.state));
    if(!Array.isArray(data.features))throw new Error("Ungültige Pilot-2-Kartenantwort");
    // WGS84 GeoJSON from a bounded, validated and allowlisted server endpoint.
    // Noninteractive: clicking Pilot marks must never add mission waypoints.
    for(const feature of data.features){
      if(!feature||!feature.geometry)continue;
      L.geoJSON({type:"Feature",geometry:feature.geometry,properties:{}},{
        interactive:false,
        pointToLayer:(_feature,latlng)=>L.circleMarker(latlng,{radius:7,interactive:false})
      }).addTo(pilot2MapLayer);
    }
    const groups=Array.isArray(data.groups)?data.groups:[];
    const emptyGroups=groups.filter(group=>group.source_elements===0).length;
    const emptyMessage=data.features.length===0&&Number(data.skipped_unsupported)===0
      ?" Keine Kartengeometrien gemeldet.":"";
    mapWarning("Pilot-2-Kartenebene: "+groups.length+" Gruppen, "+data.features.length+
      " Objekte (nur lesen). "+emptyGroups+" leere Gruppen. "+
      clean(data.skipped_unsupported)+" nicht unterstützte Objekte ausgelassen."+
      emptyMessage+" Lokale Missionen bleiben unverändert.");
  }catch(error){
    if(request!==pilot2LayerRequest)return;
    pilot2LayerVisible=false;
    button.setAttribute("aria-pressed","false");
    button.textContent="Pilot-2-Layer einblenden";
    pilot2MapLayer.clearLayers();map.removeLayer(pilot2MapLayer);
    mapWarning("Pilot-2-Kartenebene nicht verfügbar: "+errorMessage(error));
  }finally{
    if(request===pilot2LayerRequest)button.disabled=false;
  }
}
function centerOnForst(){
  if(!map)return;
  map.setView([HOME_VIEW.latitude,HOME_VIEW.longitude],HOME_VIEW.zoom);
}
function waypointIcon(n,active){
  return L.divIcon({className:"",html:'<div class="way-marker'+(active?' selected':'')+'">'+(n+1)+'</div>',iconSize:[28,28],iconAnchor:[14,14]});
}
function closingAddsWaypoint(){
  const points=mission.waypoints;
  if(!mission.close_route||points.length<2)return false;
  const first=points[0],last=points[points.length-1];
  return first.latitude!==last.latitude||first.longitude!==last.longitude;
}
function resolvedWaypoints(){
  const points=mission.waypoints.slice();
  if(closingAddsWaypoint()){
    // Return point must never inherit a camera action from waypoint 1.
    points.push({...points[0],take_photo:false});
    points[points.length-1].actions=[];
  }
  return points;
}
// Planning estimates use only local WGS84 coordinates, never live DJI flight data.
function geoDistanceMeters(a,b){
  if(!a||!b)return null;
  const valid=p=>Number.isFinite(p.latitude)&&Number.isFinite(p.longitude)&&
    Math.abs(p.latitude)<=90&&Math.abs(p.longitude)<=180&&
    !(p.latitude===0&&p.longitude===0);
  if(!valid(a)||!valid(b))return null;
  const rad=Math.PI/180;
  const latA=a.latitude*rad,latB=b.latitude*rad;
  const dLat=(b.latitude-a.latitude)*rad;
  // Trigonometric haversine gives the shortest arc over the antimeridian.
  const dLon=(b.longitude-a.longitude)*rad;
  const h=Math.sin(dLat/2)**2+
    Math.cos(latA)*Math.cos(latB)*Math.sin(dLon/2)**2;
  return 2*6371008.8*Math.asin(Math.sqrt(Math.min(1,Math.max(0,h))));
}
function routeMetrics(points,closeRoute,speedMps){
  const invalid={valid:false,segments:[],distanceMeters:null,seconds:null,
    returnMeters:null,executedPoints:0};
  if(!Array.isArray(points)||!points.length)return invalid;
  const route=points.slice();
  if(closeRoute&&points.length>=2){
    const first=points[0],last=points[points.length-1];
    if(first.latitude!==last.latitude||first.longitude!==last.longitude)
      route.push(first);
  }
  let distance=0,returnMeters=null;
  const segments=[];
  for(let n=1;n<route.length;n++){
    const meters=geoDistanceMeters(route[n-1],route[n]);
    if(meters===null)return invalid;
    segments.push({from:n,to:n+1,meters});
    distance+=meters;
    if(closeRoute&&n===route.length-1&&route.length>=3&&
       route[n].latitude===route[0].latitude&&
       route[n].longitude===route[0].longitude)
      returnMeters=meters;
  }
  if(route.length===1&&geoDistanceMeters(route[0],route[0])===null)
    return invalid;
  const speedOK=Number.isFinite(speedMps)&&speedMps>=0.1&&speedMps<=15;
  return {valid:true,segments,distanceMeters:distance,
    seconds:speedOK&&segments.length?distance/speedMps:null,
    returnMeters,executedPoints:route.length};
}
function formatRouteDistance(metres){
  if(metres===null||!Number.isFinite(metres))return "–";
  return metres<1000?Math.round(metres).toLocaleString("de-DE")+" m":
    (metres/1000).toLocaleString("de-DE",{minimumFractionDigits:2,maximumFractionDigits:2})+" km";
}
function formatRouteDuration(seconds){
  if(seconds===null||!Number.isFinite(seconds))return "–";
  const rounded=Math.ceil(seconds);
  const hours=Math.floor(rounded/3600),mins=Math.floor(rounded%3600/60),secs=rounded%60;
  return hours?hours+" h "+String(mins).padStart(2,"0")+" min":
    mins?mins+" min "+String(secs).padStart(2,"0")+" s":secs+" s";
}
function updateRouteAnalysis(){
  const speedRaw=$("mission-speed").value;
  const speed=speedRaw.trim()===""?NaN:Number(speedRaw);
  const data=routeMetrics(mission.waypoints,mission.close_route===true,speed);
  $("route-distance").textContent=formatRouteDistance(data.distanceMeters);
  $("route-duration").textContent=formatRouteDuration(data.seconds);
  $("route-legs").textContent=String(data.segments.length);
  $("route-return").textContent=formatRouteDistance(data.returnMeters);
  const unique=new Set(mission.waypoints.map(p=>p.latitude+","+p.longitude)).size;
  const problems=[];
  if(!data.valid)problems.push("Keine auswertbaren gültigen WGS84-Wegpunkte.");
  else if(data.executedPoints<2)problems.push("Mindestens zwei Wegpunkte für den KMZ-Export erforderlich.");
  if(data.executedPoints>500)problems.push("Mehr als 500 ausführbare Wegpunkte.");
  if(mission.close_route&&(mission.waypoints.length<3||unique<3))
    problems.push("Geschlossene Route: mindestens drei verschiedene Koordinaten erforderlich.");
  if(!Number.isFinite(speed)||speed<0.1||speed>15)
    problems.push("Sollgeschwindigkeit muss 0,1 bis 15 m/s betragen.");
  $("route-analysis-warning").textContent=problems.join(" ");
  return data;
}
function updateRouteStatus(){
  const count=mission.waypoints.length;
  const info=$("route-status");
  if(!mission.close_route){
    info.textContent="Offene Route: "+count+" Wegpunkte · kein Rückflugsegment eingeplant.";
    return;
  }
  const distinct=new Set(mission.waypoints.map(p=>p.latitude+","+p.longitude)).size;
  if(count<3||distinct<3){
    info.textContent="Route schließen ausgewählt: mindestens 3 unterschiedliche Wegpunkte für den Export erforderlich.";
    return;
  }
  const extra=closingAddsWaypoint();
  const total=count+(extra?1:0);
  info.textContent=extra
    ?"Geschlossene Route: "+count+" Wegpunkte + 1 echter Rückkehr-Wegpunkt im DJI-WPML-Export ("+total+" insgesamt)."
    :"Geschlossene Route: der letzte Wegpunkt liegt bereits auf Wegpunkt 1 ("+total+" insgesamt).";
  if(total>500)info.textContent+=" Maximale WPML-Wegpunktzahl überschritten.";
}
function actionControls(){
  const type=$("point-action-type").value;
  $("point-focus-params").hidden=type!=="focus";
  $("point-zoom-params").hidden=type!=="zoom";
  $("point-pitch-params").hidden=!["gimbalRotate","gimbalEvenlyRotate"].includes(type);
  const ok=WPML_ACTION_MODELS.has($("mission-model").value);
  $("point-action-add").disabled=!ok||selected<0;
  $("point-action-support").textContent=ok
    ?"DJI WPML-Aktion dokumentiert, reales Payload/Firmware-Verhalten ungeprüft."
    :"DJI-WPML-Aktionsmatrix nennt dieses Modell nicht ausdrücklich; Export zusätzlicher Aktionen gesperrt.";
}
function addWaypointAction(){
  const point=mission.waypoints[selected],type=$("point-action-type").value;
  if(!point||!WPML_ACTION_TYPES.has(type))return;
  if(!WPML_ACTION_MODELS.has($("mission-model").value)){
    notice("DJI-WPML-Matrix belegt keine Aktion für dieses Modell.",true);return;
  }
  if((point.actions||[]).length>=8){notice("Maximal 8 zusätzliche Aktionen.",true);return;}
  if(type==="gimbalEvenlyRotate"&&selected>=resolvedWaypoints().length-1){
    notice("Diese Aktion benötigt einen folgenden Flugabschnitt.",true);return;
  }
  const action={type};
  if(type==="focus"){
    action.focus_x=Number($("point-focus-x").value);
    action.focus_y=Number($("point-focus-y").value);
    if(![action.focus_x,action.focus_y].every(v=>Number.isFinite(v)&&v>=0&&v<=1)){
      notice("Fokus X/Y müssen jeweils zwischen 0 und 1 liegen.",true);return;
    }
  }
  if(type==="zoom"){
    action.focal_length_mm=Number($("point-zoom-mm").value);
    if(!Number.isFinite(action.focal_length_mm)||action.focal_length_mm<=0||action.focal_length_mm>500){
      notice("Ungültige Brennweite.",true);return;
    }
  }
  if(type==="gimbalRotate"||type==="gimbalEvenlyRotate"){
    action.pitch_deg=Number($("point-pitch-deg").value);
    if(!Number.isFinite(action.pitch_deg)||action.pitch_deg< -90||action.pitch_deg>0){
      notice("Gimbal-Neigung muss zwischen -90° und 0° liegen.",true);return;
    }
  }
  point.actions=[...(point.actions||[]),action];
  redraw();historyRecord();
}
function drawWaypointActions(point){
  const list=$("point-action-list");list.replaceChildren();
  (point.actions||[]).forEach((action,n)=>{
    const row=els("div","point-row");
    const desc=els("div","");
    cardText(desc,"b","",WPML_ACTION_LABELS[action.type]||"Unbekannt");
    const details=action.type==="focus"?"X="+action.focus_x+" Y="+action.focus_y:
      action.type==="zoom"?action.focal_length_mm+" mm":
      action.pitch_deg!==undefined?action.pitch_deg+"°":"";
    cardText(desc,"small","",details);row.appendChild(desc);
    const del=els("button","danger","Entfernen");del.type="button";
    del.addEventListener("click",()=>{point.actions.splice(n,1);redraw();historyRecord();});
    row.appendChild(del);list.appendChild(row);
  });
}
function redraw(){
  $("point-count").textContent=mission.waypoints.length;
  updateRouteStatus();
  const analysis=updateRouteAnalysis();
  const body=$("point-list");body.replaceChildren();
  mission.waypoints.forEach((p,n)=>{
    const row=cardText(body,"div","point-row"+(n===selected?" selected":""));
    cardText(row,"div","point-index",n+1);
    const desc=cardText(row,"div","");
    cardText(desc,"b","",p.take_photo?"📷 Foto-Wegpunkt":"Wegpunkt "+(n+1));
    if(p.actions?.length)cardText(desc,"small","",p.actions.length+" Kamera/Gimbal-Aktionen");
    cardText(desc,"small","",p.latitude.toFixed(7)+", "+p.longitude.toFixed(7));
    if(n>0&&analysis.valid){
      const leg=analysis.segments[n-1];
      if(leg)cardText(desc,"small","","Von WP "+n+": "+formatRouteDistance(leg.meters));
    }
    desc.addEventListener("click",()=>{selected=n;redraw();map.setView([p.latitude,p.longitude],Math.max(map.getZoom(),15));});
    const tools=cardText(row,"div","flex");
    for(const [label,delta] of [["↑",-1],["↓",1]]){
      const button=cardText(tools,"button","",label);button.title="Wegpunkt verschieben";
      button.disabled=(n+delta<0||n+delta>=mission.waypoints.length);
      button.addEventListener("click",()=>{
        const to=n+delta;[mission.waypoints[n],mission.waypoints[to]]=[mission.waypoints[to],mission.waypoints[n]];
        selected=to;redraw();historyRecord();
      });
    }
  });
  if(selected>=mission.waypoints.length)selected=mission.waypoints.length-1;
  const point=mission.waypoints[selected];
  $("point-editor").hidden=!point;
  if(point){$("edit-index").textContent=selected+1;$("point-lat").value=point.latitude;$("point-lon").value=point.longitude;$("point-photo").checked=point.take_photo;drawWaypointActions(point);}
  else $("point-action-list").replaceChildren();
  actionControls();
  if(!map)return;
  waypointsLayer.clearLayers();
  if(lines)map.removeLayer(lines);
  lines=null;
  mission.waypoints.forEach((p,n)=>{
    L.marker([p.latitude,p.longitude],{icon:waypointIcon(n,n===selected),draggable:true}).on("dragend",event=>{
      const latlng=event.target.getLatLng();
      const lat=+latlng.lat.toFixed(7);
      const lon=+(((((latlng.lng+540)%360)+360)%360)-180).toFixed(7);
      if(!Number.isFinite(lat)||Math.abs(lat)>90||!Number.isFinite(lon)||
         (lat===0&&lon===0)){notice("Ungültige GPS-Koordinaten.",true);redraw();return;}
      mission.waypoints[n]={...mission.waypoints[n],latitude:lat,longitude:lon};
      selected=n;redraw();historyRecord();
    }).on("click",()=>{selected=n;redraw();}).addTo(waypointsLayer);
  });
  if(mission.waypoints.length>=2){
    // Solid lines are regular waypoints; dashed segment 4 → 1 is an actual
    // return leg in WPML, not only a decorative polygon stroke.
    lines=L.layerGroup().addTo(map);
    L.polyline(mission.waypoints.map(p=>[p.latitude,p.longitude]),
      {color:"#44aaf8",weight:4,opacity:.9}).addTo(lines);
    if(closingAddsWaypoint()){
      const first=mission.waypoints[0],last=mission.waypoints[mission.waypoints.length-1];
      L.polyline([[last.latitude,last.longitude],[first.latitude,first.longitude]],{
        color:"#ffce74",weight:4,dashArray:"10 9",opacity:1
      }).bindTooltip("Rückflug zum ersten Wegpunkt · echter DJI-WPML-Wegpunkt")
        .addTo(lines);
    }
  }
}
function fitMission(){
  if(!map||!mission.waypoints.length)return;
  if(mission.waypoints.length===1){map.setView([mission.waypoints[0].latitude,mission.waypoints[0].longitude],16);return;}
  map.fitBounds(L.latLngBounds(mission.waypoints.map(p=>[p.latitude,p.longitude])),{padding:[55,55],maxZoom:17});
}
function updateMissionSelect(){
  const select=$("mission-list");select.replaceChildren();
  const opt=els("option","", "Neuer Entwurf");opt.value="";select.appendChild(opt);
  knownMissions.forEach(item=>{const option=els("option","",item.name+" · "+item.waypoints+" WP");option.value=item.id;select.appendChild(option)});
  select.value=missionId||"";
  $("delete-mission").disabled=!missionId;
}
async function loadMissions(){
  const res=await api("/api/v1/studio/missions");knownMissions=(await res.json()).missions;
  updateMissionSelect();
}
async function loadMission(id,{skipConfirm=false}={}){
  if(id===(missionId||"")){updateMissionSelect();return true;}
  if(!skipConfirm&&!allowDiscard()){updateMissionSelect();return false;}
  if(!id){newMission({skipConfirm:true});return true;}
  const startSignature=editorSignature(editorSnapshot());
  const res=await api("/api/v1/studio/missions/"+encodeURIComponent(id));
  const data=await res.json();
  // A late network response must never overwrite edits made during loading.
  if(editorSignature(editorSnapshot())!==startSignature){
    updateMissionSelect();
    throw new Error("Entwurf wurde während des Ladens geändert; Mission nicht übernommen.");
  }
  mission=data.mission;missionId=data.id;selected=-1;
  syncForm();updateMissionSelect();redraw();fitMission();historyReset();
  notice("Mission geladen: "+mission.name);
  return true;
}
function newMission({skipConfirm=false}={}){
  if(!skipConfirm&&!allowDiscard()){updateMissionSelect();return false;}
  mission=EMPTY();missionId=null;selected=-1;
  syncForm();updateMissionSelect();redraw();historyReset();
  notice("Neuer Entwurf. Klicke auf die Karte, um Wegpunkte hinzuzufügen.");
  return true;
}
async function saveMission(){
  getForm();
  historyRecord();
  const saveSignature=editorSignature(editorSnapshot());
  const startingId=missionId;
  const editing=!!missionId;
  const path="/api/v1/studio/missions"+(editing?"/"+encodeURIComponent(missionId):"");
  const response=await api(path,{method:editing?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(mission)});
  const saved=await response.json();
  // A late save must not bind another newly opened draft to the wrong ID.
  if(missionId!==startingId||
     (startingId===null&&editorSignature(editorSnapshot())!==saveSignature)){
    await loadMissions();
    notice("Ältere Mission gespeichert. Der aktuell offene Entwurf blieb unverändert.");
    return;
  }
  missionId=saved.id;
  // Do not mark concurrent edits clean: baseline is the submitted snapshot.
  historySaved(saveSignature);
  await loadMissions();notice("Gespeichert auf dem Pi: "+mission.name);
}
async function removeMission(){
  if(!missionId||!allowDiscard()||
     !window.confirm("Mission wirklich dauerhaft löschen?"))return;
  await api("/api/v1/studio/missions/"+encodeURIComponent(missionId),{method:"DELETE"});
  newMission({skipConfirm:true});await loadMissions();notice("Mission gelöscht");
}
let csvPreview=null,csvSerial=0,csvAbort=null,csvMap=null,csvShown=0;
function csvInvalidate(message="Datei oder Format geändert. Vorschau erneut prüfen."){
  csvSerial++;
  csvAbort?.abort();csvAbort=null;csvPreview=null;
  if(csvMap){csvMap.remove();csvMap=null;}
  $("csv-apply").disabled=true;$("csv-check").disabled=false;
  $("csv-check").textContent="Vorschau prüfen";
  $("csv-dialog").setAttribute("aria-busy","false");
  $("csv-result").hidden=true;$("csv-errors").hidden=true;
  $("csv-errors").replaceChildren();$("csv-rows").replaceChildren();
  $("csv-file").removeAttribute("aria-invalid");
  $("csv-message").className="status";$("csv-message").textContent=message;
}
function openCsvImport(){
  csvInvalidate("Datei auswählen und Vorschau prüfen. Noch keine Wegpunkte übernommen.");
  $("csv-dialog").showModal();
}
function csvMoreRows(){
  if(!csvPreview)return;
  const end=Math.min(csvShown+50,csvPreview.rows.length);
  for(const row of csvPreview.rows.slice(csvShown,end)){
    const tr=els("tr");
    for(const value of [row.line,row.latitude.toFixed(7),row.longitude.toFixed(7),row.take_photo?"Ja":"Nein"])
      tr.appendChild(els("td","",value));
    $("csv-rows").appendChild(tr);
  }
  csvShown=end;
  $("csv-range").textContent=csvShown+" von "+csvPreview.rows.length+" Wegpunkten · Dateireihenfolge";
  $("csv-more").hidden=csvShown>=csvPreview.rows.length;
}
function csvShowMap(){
  $("csv-map-message").textContent="";
  if(!window.L){
    $("csv-map-message").textContent="Kartenbibliothek nicht verfügbar. Lage anhand der Koordinatentabelle prüfen.";
    return;
  }
  csvMap=L.map("csv-map").setView([HOME_VIEW.latitude,HOME_VIEW.longitude],15);
  L.tileLayer(SATELLITE_TILE_URL,{maxZoom:19,maxNativeZoom:19,
    attribution:"Tiles &copy; Esri and data providers"}).on("tileerror",()=>{
      $("csv-map-message").textContent="Kartenbilder nicht verfügbar. Wegpunkte und Tabelle bleiben prüfbar.";
    }).addTo(csvMap);
  const points=csvPreview.waypoints.map(p=>[p.latitude,p.longitude]);
  L.polyline(points,{color:"#48a8f5",weight:3}).addTo(csvMap);
  if($("close-route").checked){
    L.polyline([points[points.length-1],points[0]],{color:"#ffce74",dashArray:"8 6"}).addTo(csvMap);
  }
  csvPreview.rows.forEach((p,n)=>L.circleMarker([p.latitude,p.longitude],{radius:5,color:"#48a8f5"})
    .bindTooltip("WP "+(n+1)+" · CSV-Zeile "+p.line).addTo(csvMap));
  csvMap.fitBounds(L.latLngBounds(points),{padding:[20,20],maxZoom:17});
}
async function previewCsv(){
  csvInvalidate("CSV wird geprüft…");
  const serial=csvSerial,file=$("csv-file").files?.[0];
  const signature=editorSignature(editorSnapshot());
  const controller=new AbortController();csvAbort=controller;
  let timeout;
  try{
    if(!file)throw new Error("Bitte eine CSV-Datei auswählen.");
    if(!file.size||file.size>512*1024)throw new Error("CSV muss 1 Byte bis 512 KiB groß sein.");
    $("csv-check").disabled=true;$("csv-check").textContent="Wird geprüft…";
    $("csv-dialog").setAttribute("aria-busy","true");
    const params=new URLSearchParams({delimiter:$("csv-delimiter").value,
      decimal:$("csv-decimal").value,close_route:String($("close-route").checked)});
    timeout=setTimeout(()=>controller.abort(),30000);
    const response=await api("/api/v1/studio/missions/preview.csv?"+params,{
      method:"POST",headers:{"Content-Type":"text/csv;charset=utf-8"},body:file,signal:controller.signal});
    const data=await response.json();
    if(serial!==csvSerial)return;
    if(!data.valid){
      $("csv-file").setAttribute("aria-invalid","true");
      $("csv-message").className="status error";
      $("csv-message").textContent=data.error_count+" Fehler. Keine Wegpunkte übernommen.";
      $("csv-errors").hidden=false;
      for(const issue of data.errors){
        const prefix=issue.line?"Zeile "+issue.line:"Route";
        $("csv-errors").appendChild(els("li","",prefix+(issue.column?" · "+issue.column:"")+": "+issue.message));
      }
      if(data.error_count>data.errors.length)
        $("csv-errors").appendChild(els("li","","Es werden die ersten 50 Fehler angezeigt."));
      $("csv-message").focus();return;
    }
    csvPreview={...data,signature};csvShown=0;
    $("csv-result").hidden=false;csvMoreRows();
    $("csv-message").className="status good";
    $("csv-message").textContent=data.waypoints.length+" Wegpunkte geprüft. Lage und Reihenfolge kontrollieren, dann übernehmen.";
    $("csv-apply").disabled=false;
    try{csvShowMap();}catch(_){
      $("csv-map-message").textContent="Kartenvorschau nicht verfügbar. Lage anhand der Koordinatentabelle prüfen.";
    }
  }catch(error){
    if(serial!==csvSerial)return;
    $("csv-message").className="status error";
    $("csv-message").textContent=error.name==="AbortError"?
      "Zeitlimit erreicht. Verbindung prüfen und Vorschau erneut starten.":errorMessage(error);
    $("csv-message").focus();
  }finally{
    clearTimeout(timeout);
    if(serial===csvSerial){
      csvAbort=null;$("csv-check").disabled=false;$("csv-check").textContent="Vorschau prüfen";
      $("csv-dialog").setAttribute("aria-busy","false");
    }
  }
}
function applyCsv(){
  if(!csvPreview||$("csv-apply").disabled)return;
  if(editorSignature(editorSnapshot())!==csvPreview.signature){
    csvInvalidate("Missionsentwurf geändert. Vorschau erneut prüfen.");return;
  }
  historyRecord();
  mission.waypoints=csvPreview.waypoints.map(p=>({...p}));selected=-1;
  redraw();historyRecord();fitMission();
  const count=mission.waypoints.length;
  $("csv-dialog").close();
  notice(count+" CSV-Wegpunkte übernommen. Rückgängig möglich; zum Behalten Mission speichern.");
}
function downloadCsvTemplate(){
  const blob=new Blob(["latitude;longitude;take_photo\n49.1533000;8.5841700;true\n49.1535000;8.5844000;false\n"],{type:"text/csv;charset=utf-8"});
  const url=URL.createObjectURL(blob),a=els("a");a.href=url;a.download="AeroNexus-Wegpunkte-Beispiel.csv";
  document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);
}
async function importMission(){
  if(!allowDiscard())return;
  const file=$("import-kmz").files?.[0];
  if(!file)throw new Error("Bitte eine AeroNexus-KMZ-Datei auswählen");
  if(file.size>2*1024*1024)throw new Error("KMZ darf maximal 2 MiB groß sein");
  const response=await api("/api/v1/studio/missions/import.kmz",{
    method:"POST",headers:{"Content-Type":"application/vnd.google-earth.kmz"},body:file
  });
  const record=await response.json();
  $("import-kmz").value="";
  await loadMissions();
  await loadMission(record.id,{skipConfirm:true});
  notice("AeroNexus-KMZ als bearbeitbare Mission importiert. Änderungen vor dem Flug prüfen.");
}
async function exportMission(){
  getForm();
  if(mission.waypoints.length<2)throw new Error("Mindestens zwei Wegpunkte für WPML nötig.");
  if(!missionId){await saveMission();}
  else{await saveMission();}
  const res=await api("/api/v1/studio/missions/"+encodeURIComponent(missionId)+"/export.kmz");
  const blob=await res.blob();const href=URL.createObjectURL(blob);
  const a=els("a");a.href=href;a.download="aeronexus-"+mission.name.replace(/[^A-Za-z0-9_-]/g,"_")+".kmz";
  document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(href),2000);
  notice("KMZ erstellt. Vor jedem Flug in DJI Pilot 2 und vor Ort überprüfen.");
}
// Read-only library: no KMZ import, editor mutation or cloud commands.
let waylineData=null,waylinePage=1,waylineSerial=0,waylineAbort=null;
const WAYLINE_PAGE_SIZE=12;
function waylineModel(key){
  const names={"0-77-0":"Mavic 3E","0-77-1":"Mavic 3T","0-77-2":"Mavic 3M","0-77-3":"Mavic 3TA",
    "0-99-0":"Matrice 4E","0-99-1":"Matrice 4T",
    "2-144-0":"DJI RC Pro Enterprise","2-174-0":"DJI RC Plus 2"};
  return Object.prototype.hasOwnProperty.call(names,key)?names[key]:key||"Modell nicht übermittelt";
}
function waylineSource(provider){return provider==="pilot2-local-cloud"?"Lokale Pilot-2-Cloud":provider==="flighthub-public-v2"?"FlightHub":provider||"Unbekannte Quelle";}
function waylineType(route){
  const known={waypoint:"Wegpunktmission",mapping_2d:"Flächenroute (2D)",mapping_3d:"Mapping (3D)",mapping_strip:"Streifenroute"};
  const names=(route.template_types||[]).map(type=>known[type]||type);
  for(const code of route.template_type_codes||[])if(![0,1,2,3].includes(code))names.push("Geometrie-/Template-Code "+code);
  return names.join(", ")||"Routentyp nicht übermittelt";
}
function waylineTime(route){
  const ms=route.updated_at_ms??(typeof route.updated_at==="number"?route.updated_at*1000:null);
  if(typeof ms!=="number"||!Number.isFinite(ms)||ms<=0)return "nicht übermittelt";
  const date=new Date(ms);if(!Number.isFinite(date.getTime()))return "nicht übermittelt";
  return date.toLocaleString("de-DE",{timeZone:"Europe/Berlin",timeZoneName:"short"});
}
function waylineCheck(route){
  const matches=(waylineData?.missions||[]).flatMap(m=>
    (m.candidates||[]).filter(c=>c.provider===route.provider&&c.project_id===route.project_id&&c.wayline_id===route.wayline_id));
  if(matches.some(c=>c.model_match===false))return "Modellkonflikt bei gleichem Namen · Inhalt ungeprüft";
  if(matches.length>1)return "Mehrere unbestätigte Namenszuordnungen · Inhalt ungeprüft";
  if(matches.length)return "Unbestätigte Namenszuordnung · Inhalt ungeprüft";
  if((waylineData?.missions||[]).some(m=>m.candidate_count>(m.candidates||[]).length))return "Namensabgleich begrenzt · Inhalt ungeprüft";
  return "Keine Namenszuordnung · Inhalt ungeprüft";
}
function renderWaylines(){
  const grid=$("wayline-grid");grid.replaceChildren();
  const query=$("wayline-search").value.trim().toLocaleLowerCase("de-DE"),source=$("wayline-source").value;
  $("clear-wayline-search").disabled=!$("wayline-search").value;
  const routes=(waylineData?.waylines||[]).filter(r=>(source==="all"||r.provider===source)&&String(r.name||"").toLocaleLowerCase("de-DE").includes(query));
  const pages=Math.max(1,Math.ceil(routes.length/WAYLINE_PAGE_SIZE));if(waylineData)waylinePage=Math.max(1,Math.min(waylinePage,pages));
  const start=(waylinePage-1)*WAYLINE_PAGE_SIZE;
  for(const route of routes.slice(start,start+WAYLINE_PAGE_SIZE)){
    const card=els("article","wayline-card","");card.appendChild(els("h2","",route.name||"Unbenannte Route"));
    for(const value of [waylineModel(route.device_model_key),waylineType(route),waylineSource(route.provider),
      "Projekt / Workspace: "+clean(route.workspace_id||route.project_id),"Geändert: "+waylineTime(route),waylineCheck(route)])
      card.appendChild(els("p","",value));
    if(route.provider==="pilot2-local-cloud"&&route.wayline_id){
      const button=els("button","","Vorschau auf Karte (nur lesen)");
      button.onclick=()=>previewCloudWayline(route,button);
      card.appendChild(button);
    }
    grid.appendChild(card);
  }
  if(waylineData&&!routes.length)grid.appendChild(els("p","empty",query||source!=="all"?"Keine Route passt zur Suche oder Quelle.":"Im aktuellen Datenstand sind keine Cloud-Routen enthalten. Quellenstatus oben beachten."));
  $("wayline-range").textContent=waylineData?(routes.length?`${start+1}–${Math.min(start+WAYLINE_PAGE_SIZE,routes.length)} von ${routes.length} Routen im geladenen Datenstand`:"0 Routen im gewählten Ausschnitt"):"";
  $("wayline-page").textContent=waylineData?`Seite ${waylinePage} von ${pages}`:"Seite –";
  $("wayline-prev").disabled=!waylineData||waylinePage<=1;$("wayline-next").disabled=!waylineData||waylinePage>=pages;
  $("wayline-overview-open").disabled=!(waylineData?.local_pilot?.state==="connected"&&
    waylineData.local_pilot.pagination_complete===true&&
    waylineData.waylines.some(route=>route.provider==="pilot2-local-cloud"));
  syncCloudOverviewShortcut();
}
// Leaflet must measure the newly revealed map on mobile before computing fit zoom.
function fitWaylineMapBounds(bounds,isCurrent){
  if(!bounds||!bounds.isValid())return;
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    if(!isCurrent()||!map||!$("map-pane").classList.contains("active"))return;
    map.invalidateSize({pan:false});
    const container=map.getContainer();
    if(!container||container.clientWidth<60||container.clientHeight<60)return;
    map.fitBounds(bounds.pad(.18),{maxZoom:17,animate:false});
  }));
}
function centerCloudWaylinePreview(){
  fitWaylineMapBounds(waylinePreviewBounds,()=>waylinePreviewBounds!==null&&
    waylinePreviewLayer!==null&&map.hasLayer(waylinePreviewLayer));
}
function clearCloudWaylinePreview(){
  ++waylinePreviewRequest;
  waylinePreviewBounds=null;
  $("wayline-preview-fit").hidden=true;
  if(waylinePreviewLayer){waylinePreviewLayer.clearLayers();if(map)map.removeLayer(waylinePreviewLayer);}
  $("wayline-preview-clear").hidden=true;
  if(map)mapWarning("Cloud-Wayline-Vorschau ausgeblendet. Keine Missionsdaten verändert.");
}
async function previewCloudWayline(route,button){
  closeCloudOverview(true);
  const request=++waylinePreviewRequest;
  waylinePreviewBounds=null;
  $("wayline-preview-fit").hidden=true;
  if(waylinePreviewLayer){waylinePreviewLayer.clearLayers();if(map)map.removeLayer(waylinePreviewLayer);}
  $("wayline-preview-clear").hidden=true;
  button.disabled=true;
  $("wayline-state").className="status";
  $("wayline-state").textContent="KMZ-Vorschau wird schreibgeschützt gelesen…";
  try{
    const response=await api("/api/v1/local-cloud/waylines/"+
      encodeURIComponent(route.wayline_id)+"/preview");
    const data=await response.json();
    if(request!==waylinePreviewRequest)return;
    if(data.state!=="connected")throw new Error("Vorschau nicht verfügbar: "+clean(data.state));
    if(!Array.isArray(data.features)||!data.features.length)throw new Error("Keine darstellbare KMZ-Geometrie");
    switchTab("map-pane");getMap();
    if(!map||!waylinePreviewLayer)throw new Error("Karte nicht verfügbar");
    waylinePreviewLayer.clearLayers();waylinePreviewLayer.addTo(map);
    for(const item of data.features){
      if(!item||!item.geometry)continue;
      L.geoJSON({type:"Feature",geometry:item.geometry,properties:{}},{
        interactive:false,
        style:()=>({color:"#ffb74d",weight:5,opacity:1}),
        pointToLayer:(_item,latlng)=>L.circleMarker(latlng,{
          radius:7,color:"#ffb74d",fillColor:"#fff",fillOpacity:1,interactive:false})
      }).addTo(waylinePreviewLayer);
    }
    $("wayline-preview-clear").hidden=false;
    const bounds=waylinePreviewLayer.getLayers().flatMap(layer=>
      typeof layer.getBounds==="function"?[layer.getBounds()]:[]);
    if(bounds.length){
      const merged=L.latLngBounds([]);
      for(const bound of bounds)if(bound.isValid())merged.extend(bound);
      if(merged.isValid()){
        waylinePreviewBounds=merged;
        $("wayline-preview-fit").hidden=false;
        fitWaylineMapBounds(merged,()=>request===waylinePreviewRequest&&
          waylinePreviewBounds===merged&&map.hasLayer(waylinePreviewLayer));
      }
    }
    mapWarning("Schreibgeschützte Cloud-Vorschau: "+clean(data.name)+" · "+
      data.features.length+" Geometrie(n) aus "+clean(data.source)+
      ". Keine Bearbeitung, keine Flugfreigabe.");
  }catch(error){
    if(request!==waylinePreviewRequest)return;
    $("wayline-state").className="status error";
    $("wayline-state").textContent=errorMessage(error)+
      " · Cloud-KMZ bleibt unverändert. Kein Import in den Editor.";
  }finally{
    button.disabled=false;
  }
}


function cloudOverviewLineStats(features){
  // Never join separate WPML folders or count polygon boundaries as flight paths.
  // Horizontal great-circle distance between neighboring points only.
  const rad=Math.PI/180,earth=6371008.8;
  let metres=0,segments=0,lines=0;
  const endpoints=[];
  const valid=point=>Array.isArray(point)&&point.length>=2&&
    Number.isFinite(point[0])&&Number.isFinite(point[1])&&
    Math.abs(point[0])<=180&&Math.abs(point[1])<=90;
  for(const feature of features){
    const geom=feature?.geometry;
    if(geom?.type!=="LineString"||!Array.isArray(geom.coordinates))continue;
    const coords=geom.coordinates;
    if(coords.length<2||coords.length>1000||!coords.every(valid))continue;
    lines++;
    endpoints.push([coords[0],coords[coords.length-1]]);
    for(let i=1;i<coords.length;i++){
      const a=coords[i-1],b=coords[i];
      const dLat=(b[1]-a[1])*rad,dLon=(b[0]-a[0])*rad;
      const h=Math.sin(dLat/2)**2+Math.cos(a[1]*rad)*Math.cos(b[1]*rad)*Math.sin(dLon/2)**2;
      metres+=2*earth*Math.asin(Math.sqrt(Math.min(1,Math.max(0,h))));
      segments++;
    }
  }
  return {distanceMeters:lines?metres:null,segmentCount:segments,lineCount:lines,endpoints};
}
function cloudOverviewFormatDistance(distance){
  if(!Number.isFinite(distance)||distance<0)return "keine Linienlänge";
  if(distance>=1000)return (distance/1000).toLocaleString("de-DE",{maximumFractionDigits:2})+" km";
  return Math.round(distance)+" m";
}
function syncCloudOverviewShortcut(){
  const button=$("cloud-overview-map-open");
  const inventory=waylineData?.local_pilot;
  const routes=(waylineData?.waylines||[]).filter(route=>
    route.provider==="pilot2-local-cloud"&&route.wayline_id);
  const available=inventory?.state==="connected"&&inventory.pagination_complete===true&&routes.length>0;
  button.hidden=!available;
  if(!available)return;
  const showing=!$("cloud-overview-panel").hidden;
  button.setAttribute("aria-pressed",String(showing));
  button.textContent=showing?"Übersicht schließen":"Alle Cloud-Routen ("+Math.min(8,routes.length)+")";
}
function setCloudOverviewMinimized(minimized){
  const panel=$("cloud-overview-panel"),button=$("cloud-overview-expand");
  panel.dataset.minimized=String(minimized);
  button.setAttribute("aria-expanded",String(!minimized));
  button.textContent=minimized?"Routen anzeigen":"Routen verbergen";
}
function setMapToolsExpanded(expanded){
  const toolbar=$("map-toolbar"),button=$("map-tools-toggle");
  toolbar.dataset.compact=String(!expanded);
  button.setAttribute("aria-expanded",String(expanded));
  button.textContent=expanded?"Weniger":"Werkzeuge";
}
function setMapInfoExpanded(expanded){
  $("map-info").dataset.minimized=String(!expanded);
  $("map-info-detail").hidden=!expanded;
  $("map-info-chip").setAttribute("aria-expanded",String(expanded));
  $("map-info-chip").textContent="ℹ "+mapStatusSummary($("map-info-detail").textContent)+
    (expanded?" · Weniger":" · Details");
  $("map-info-toggle").setAttribute("aria-expanded",String(expanded));
  $("map-info-toggle").textContent=expanded?"Hinweis kürzen":"Hinweis zeigen";
}
function refreshMobileMapSize(){
  if(!map)return;
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    if(map)map.invalidateSize({pan:false});
  }));
}
function setMapFocus(enabled){
  document.body.classList.toggle("map-focus-active",enabled);
  const button=$("map-focus-toggle");
  button.setAttribute("aria-pressed",String(enabled));
  button.textContent=enabled?"Kartenfokus beenden":"Kartenfokus";
  if(enabled&&$("map-pane").classList.contains("active")===false)switchTab("map-pane");
  refreshMobileMapSize();
}
function closeCloudOverview(quiet=false){
  ++cloudOverviewGeneration;
  if(cloudOverviewController)cloudOverviewController.abort();
  cloudOverviewController=null;
  cloudOverviewRoutes=[];
  if(cloudOverviewLayer){
    cloudOverviewLayer.clearLayers();
    if(map)map.removeLayer(cloudOverviewLayer);
  }
  $("cloud-overview-list").replaceChildren();
  $("cloud-overview-panel").hidden=true;
  $("cloud-overview-fit").disabled=true;
  syncCloudOverviewShortcut();
  setCloudOverviewMinimized(true);
  if(!quiet&&map)mapWarning("Cloud-Routenübersicht geschlossen. Missionen unverändert.");
}
function fitCloudRoutes(entry=null){
  if(!map)return;
  const items=entry?[entry]:cloudOverviewRoutes.filter(route=>route.visible&&route.layer);
  const valid=items.map(route=>route.layer?.getBounds()).filter(bounds=>bounds&&bounds.isValid());
  if(!valid.length)return;
  const bounds=L.latLngBounds([]);
  for(const item of valid)bounds.extend(item);
  // Share the mobile map-size guard with single KMZ previews. No stale fit after closing.
  if(bounds.isValid()){
    const generation=cloudOverviewGeneration;
    fitWaylineMapBounds(bounds,()=>generation===cloudOverviewGeneration&&
      cloudOverviewLayer!==null&&map.hasLayer(cloudOverviewLayer)&&
      (!entry||entry.visible));
  }
}
function renderCloudOverview(){
  const list=$("cloud-overview-list");list.replaceChildren();
  let loaded=0,failed=0,visible=0,points=0,totalLength=0,measured=0;
  const loading=cloudOverviewRoutes.find(route=>route.state==="loading");
  for(const entry of cloudOverviewRoutes){
    if(entry.state==="connected"){
      loaded++;points+=entry.pointCount;if(entry.visible)visible++;
      if(Number.isFinite(entry.distanceMeters)){totalLength+=entry.distanceMeters;measured++;}
    }
    else if(entry.state!=="loading")failed++;
    const card=els("div","cloud-route-row");
    const label=els("label");
    const checkbox=els("input");checkbox.type="checkbox";
    checkbox.checked=entry.visible;checkbox.disabled=entry.state!=="connected";
    checkbox.onchange=()=>{
      entry.visible=checkbox.checked;
      if(entry.visible)cloudOverviewLayer.addLayer(entry.layer);
      else cloudOverviewLayer.removeLayer(entry.layer);
      renderCloudOverview();
    };
    label.appendChild(checkbox);
    const color=els("span","swatch");color.style.backgroundColor=entry.color;
    color.setAttribute("aria-hidden","true");label.appendChild(color);
    label.appendChild(els("span","",entry.name));
    card.appendChild(label);
    const zoom=els("button","","Zoom");
    zoom.type="button";zoom.disabled=entry.state!=="connected";
    zoom.onclick=()=>{
      if(!entry.visible){entry.visible=true;cloudOverviewLayer.addLayer(entry.layer);}
      fitCloudRoutes(entry);renderCloudOverview();
    };
    card.appendChild(zoom);
    const detail=entry.state==="connected"
      ?entry.pointCount+" Punkte · "+entry.featureCount+" Geometrien"
      :entry.state==="loading"?"KMZ wird geladen…":"Nicht verfügbar: "+entry.state;
    card.appendChild(els("div","cloud-route-detail",detail));
    if(entry.state==="connected"){
      const metrics=els("div","cloud-route-metrics");
      metrics.appendChild(els("span","",entry.lineCount+" Linien · "+entry.segmentCount+" Segmente"));
      metrics.appendChild(els("span","","Horizontale Linienlänge: "+
        cloudOverviewFormatDistance(entry.distanceMeters)));
      card.appendChild(metrics);
    }
    list.appendChild(card);
  }
  $("cloud-overview-fit").disabled=visible===0;
  $("cloud-overview-status").textContent=loaded+"/"+cloudOverviewRoutes.length+
    " Routen gelesen · "+visible+" sichtbar · "+points+" Punkte gelesen"+
    (measured?" · Σ Linienlängen: "+cloudOverviewFormatDistance(totalLength):"")+
    (failed?" · "+failed+" nicht verfügbar":"")+
    (loading?" · Lade: "+loading.name:"")+".";
}
async function openCloudOverview(){
  // No automatic requests: use only a verified, fully enumerated local inventory.
  const pilot=waylineData?.local_pilot;
  if(pilot?.state!=="connected"||pilot.pagination_complete!==true){
    $("wayline-state").className="status error";
    $("wayline-state").textContent="Vollständiger Pilot-2-Bestand erforderlich. Routen aktualisieren.";
    return;
  }
  const seen=new Set();
  const routes=waylineData.waylines.filter(route=>{
    if(route.provider!=="pilot2-local-cloud"||!route.wayline_id||seen.has(route.wayline_id))return false;
    seen.add(route.wayline_id);return true;
  }).slice(0,8);
  if(!routes.length)return;
  closeCloudOverview(true);
  clearCloudWaylinePreview();
  switchTab("map-pane");getMap();
  if(!map||!cloudOverviewLayer){
    $("wayline-state").className="status error";
    $("wayline-state").textContent="Kartenbibliothek nicht verfügbar.";
    return;
  }
  const generation=++cloudOverviewGeneration;
  const controller=new AbortController();
  cloudOverviewController=controller;
  cloudOverviewRoutes=routes.map((route,index)=>({
    id:route.wayline_id,name:route.name||"Unbenannte Route",
    color:CLOUD_OVERVIEW_COLORS[index],state:"loading",
    pointCount:0,featureCount:0,distanceMeters:null,lineCount:0,segmentCount:0,visible:false,layer:null
  }));
  cloudOverviewLayer.clearLayers();cloudOverviewLayer.addTo(map);
  $("cloud-overview-panel").hidden=false;
  syncCloudOverviewShortcut();
  setCloudOverviewMinimized(typeof window!=="undefined"&&window.matchMedia("(max-width:700px)").matches);
  renderCloudOverview();
  for(const entry of cloudOverviewRoutes){
    if(generation!==cloudOverviewGeneration||controller.signal.aborted)break;
    const timer=setTimeout(()=>controller.abort(),26000);
    try{
      const response=await api("/api/v1/local-cloud/waylines/"+
        encodeURIComponent(entry.id)+"/preview",{signal:controller.signal});
      const data=await response.json();
      if(generation!==cloudOverviewGeneration||controller.signal.aborted)break;
      if(data.state!=="connected")throw new Error(clean(data.state));
      if(!Array.isArray(data.features)||!data.features.length||data.features.length>32)
        throw new Error("Keine darstellbare Geometrie");
      const stats=cloudOverviewLineStats(data.features);
      const layer=L.featureGroup();
      for(const feature of data.features){
        if(!feature||!feature.geometry)throw new Error("Ungültige Kartengeometrie");
        L.geoJSON({type:"Feature",geometry:feature.geometry,properties:{}},{
          interactive:false,
          style:()=>({color:entry.color,weight:4,opacity:.9}),
          pointToLayer:(_feature,latlng)=>L.circleMarker(latlng,{
            color:entry.color,fillColor:entry.color,radius:6,interactive:false})
        }).addTo(layer);
      }
      // Endpoint symbols describe WPML geometry segments, NOT takeoff or landing.
      for(const [start,end] of stats.endpoints){
        L.circleMarker([start[1],start[0]],{radius:5,color:entry.color,
          fillColor:"#ffffff",fillOpacity:1,weight:2,interactive:false}).addTo(layer);
        L.circleMarker([end[1],end[0]],{radius:7,color:entry.color,
          fillColor:entry.color,fillOpacity:1,weight:2,interactive:false}).addTo(layer);
      }
      entry.distanceMeters=stats.distanceMeters;
      entry.segmentCount=stats.segmentCount;
      entry.lineCount=stats.lineCount;
      entry.layer=layer;
      entry.pointCount=Number.isInteger(data.point_count)?data.point_count:0;
      entry.featureCount=data.features.length;
      entry.state="connected";entry.visible=true;
      cloudOverviewLayer.addLayer(layer);
    }catch(error){
      if(generation!==cloudOverviewGeneration)break;
      entry.state=controller.signal.aborted?"aborted":errorMessage(error);
    }finally{
      clearTimeout(timer);
      if(generation===cloudOverviewGeneration)renderCloudOverview();
    }
  }
  if(generation!==cloudOverviewGeneration)return;
  cloudOverviewController=null;
  const count=cloudOverviewRoutes.filter(route=>route.state==="connected").length;
  if(count)fitCloudRoutes();
  $("cloud-overview-status").textContent+=controller.signal.aborted
    ?" Abruf abgebrochen oder Zeitlimit erreicht.":" Ansicht ausschließlich schreibgeschützt.";
  mapWarning(count+"/"+routes.length+" Cloud-Waylines in der Kartenübersicht verfügbar. "+
    "Routen einzeln schaltbar; keine Flugfreigabe.");
}

let pilot2ActionController=null,pilot2ActionRequest=0;
function clearPilot2ActionSummary(){
  ++pilot2ActionRequest;
  pilot2ActionController?.abort();
  pilot2ActionController=null;
  $("pilot2-action-load").disabled=false;
  $("pilot2-action-results").replaceChildren();
  $("pilot2-action-status").className="status";
  $("pilot2-action-status").textContent="Nur nach Klick: keine automatischen KMZ-Abrufe.";
}
async function loadPilot2ActionSummary(){
  const button=$("pilot2-action-load");
  const status=$("pilot2-action-status");
  const list=$("pilot2-action-results");
  if(button.disabled)return;
  const serial=++pilot2ActionRequest;
  const controller=new AbortController();
  pilot2ActionController=controller;
  const timer=setTimeout(()=>controller.abort(),95000);
  button.disabled=true;list.replaceChildren();
  status.className="status";status.textContent="Anonyme WPML-Aktionsdiagnose wird lesend abgerufen…";
  try{
    const response=await api("/api/v1/studio/pilot2/action-summary",{signal:controller.signal});
    const data=await response.json();
    // A tab switch may cancel the scan after HTTP headers were received.
    if(serial!==pilot2ActionRequest||controller.signal.aborted)return;
    if(data?.state!=="connected"){
      status.className="status error";
      status.textContent="Pilot-2-Diagnose nicht verfügbar ("+clean(data?.state)+"). Es wurden keine Flugaktionen ausgeführt.";
      return;
    }
    if(data.read_only!==true||data.flight_compatibility_verified!==false||
       data.wpml_semantics_verified!==false||data.full_content_verified!==false||
       !Array.isArray(data.anonymous_types)||!Array.isArray(data.waylines)||
       !Number.isInteger(data.checked)||data.checked<1||data.checked>8||
       data.total!==data.checked||data.waylines.length!==data.checked||
       !Number.isSafeInteger(data.recognized_actions)||data.recognized_actions<0||
       !Number.isSafeInteger(data.unknown_actions)||data.unknown_actions<0){
      throw new Error("Diagnoseformat unvollständig oder nicht schreibgeschützt.");
    }
    const count=Number(data.checked)||0;
    const identified=Array.isArray(data.identified_types)?data.identified_types:[];
    const identifiedCount=data.identified_actions===undefined?0:data.identified_actions;
    const unresolvedCount=data.unresolved_actions===undefined
      ?data.unknown_actions:data.unresolved_actions;
    if(!Number.isSafeInteger(identifiedCount)||identifiedCount<0||
       !Number.isSafeInteger(unresolvedCount)||unresolvedCount<0||
       identifiedCount+unresolvedCount!==data.unknown_actions||
       identified.length>7){
      throw new Error("Unvollständige DJI-Aktionsklassifizierung.");
    }
    status.className="status";
    status.textContent=count+" Waylines geprüft · "+clean(data.recognized_actions)+
      " dokumentierte Aktionsvorkommen · "+clean(identifiedCount)+
      " bekannte Pilot-2-Bezeichner (nur lesend) · "+clean(unresolvedCount)+
      " unbekannte Vorkommen. WPML-Semantik und Flugkompatibilität nicht bestätigt.";
    if(Array.isArray(data.documented_types)&&data.documented_types.length){
      const docCard=els("article","wayline-card");
      cardText(docCard,"h2","","DJI WPML: dokumentierte Aktionstypen");
      for(const entry of data.documented_types.slice(0,14)){
        cardText(docCard,"p","muted",clean(entry.label)+" ("+clean(entry.name)+"): "+clean(entry.occurrences));
      }
      list.appendChild(docCard);
    }
    for(const entry of identified){
      const card=els("article","wayline-card");
      cardText(card,"h2","",clean(entry.label)+" · "+clean(entry.name));
      cardText(card,"p","",clean(entry.occurrences)+" Vorkommen · "+clean(entry.file_count)+" Cloud-Dateien");
      cardText(card,"p","muted","Pilot-2-WPML-Bezeichner identifiziert · Parameter und Flugkompatibilität ungeprüft");
      list.appendChild(card);
    }
    for(const entry of data.anonymous_types.slice(0,128)){
      const card=els("article","wayline-card");
      cardText(card,"h2","",clean(entry.alias));
      cardText(card,"p","",clean(entry.occurrences)+" Vorkommen · "+clean(entry.file_count)+" Cloud-Dateien");
      const triggers=entry.triggers&&typeof entry.triggers==="object"
        ?Object.entries(entry.triggers).map(([key,val])=>key+": "+val).join(" · "):"–";
      cardText(card,"p","muted","Auslöser: "+triggers);
      list.appendChild(card);
    }
    cardText(list,"p","note","Dokumentierte und beobachtete DJI-Bezeichner sind keine Export- oder Flugfreigabe. Keine Roh-WPML, Koordinaten oder Parameterwerte.");
  }catch(err){
    if(serial!==pilot2ActionRequest)return;
    status.className="status error";
    status.textContent=controller.signal.aborted
      ?"Diagnose-Zeitlimit erreicht.":errorMessage(err);
  }finally{
    clearTimeout(timer);
    if(serial===pilot2ActionRequest){
      button.disabled=false;
      pilot2ActionController=null;
    }
  }
}
function waylineSourceState(data){
  const state=data.local_pilot?.state||"not_configured";
  const labels={not_configured:"nicht eingerichtet",awaiting_browser_session:"wartet auf vorhandene Cloud-Sitzung",configuration_error:"Konfiguration prüfen",
    authentication_required:"Sitzung nicht gültig",business_error:"Server lehnt Anfrage ab",upstream_error:"Serverfehler",unavailable:"nicht erreichbar",invalid_response:"Antwort nicht lesbar",inventory_changed:"Bestand während Abruf geändert – erneut aktualisieren"};
  const local=state==="connected"?"verbunden"+(data.local_pilot.pagination_complete?" · alle gemeldeten Seiten gelesen":" · Teilbestand am Abruflimit"):(labels[state]||"Zustand unbekannt");
  const fh=data.coverage?.flighthub_cache_available?"Cache geladen":"kein Katalog geladen";
  const incomplete=(data.projects||[]).some(p=>p.waylines_readable===false||p.waylines_at_limit);
  const total=(data.waylines||[]).length;
  return `Lokale Cloud: ${local}. FlightHub: ${fh}. ${total} Routen im Datenstand.`+
    " Lokaler Abruf: "+waylineTime({updated_at_ms:Date.parse(data.local_pilot?.updated_at||"")})+"."+
    (incomplete?" Mindestens eine Sammlung ist nicht lesbar oder begrenzt.":"")+" Routeninhalt ungeprüft; keine vollständige Inventur bestätigt.";
}
async function loadWaylines(){
  const serial=++waylineSerial;waylineAbort?.abort();const controller=new AbortController();waylineAbort=controller;
  const timer=setTimeout(()=>controller.abort(),20000);
  waylineData=null;renderWaylines();$("refresh-waylines").disabled=true;$("wayline-grid").setAttribute("aria-busy","true");
  $("wayline-state").className="status";$("wayline-state").textContent="Cloud-Routen werden geladen…";
  try{
    const response=await api("/api/v1/studio/missions/reconciliation",{signal:controller.signal});const data=await response.json();
    if(serial!==waylineSerial)return;
    if(!Array.isArray(data.waylines)||!Array.isArray(data.missions))throw new Error("Routenliste ist nicht lesbar.");
    waylineData=data;renderWaylines();$("wayline-state").textContent=waylineSourceState(data);
  }catch(err){
    if(serial!==waylineSerial)return;
    waylineData=null;renderWaylines();$("wayline-state").className="status error";
    $("wayline-state").textContent=(controller.signal.aborted?"Zeitlimit beim Laden erreicht.":errorMessage(err))+" Über Routen aktualisieren erneut versuchen.";
  }finally{clearTimeout(timer);if(serial===waylineSerial){$("refresh-waylines").disabled=false;$("wayline-grid").setAttribute("aria-busy","false");waylineAbort=null;}}
}
function switchTab(id){
  if(id!=="waylines-pane")clearPilot2ActionSummary();
  if(id!=="map-pane"&&id!=="geo-pane"&&document.body.classList.contains("map-focus-active"))setMapFocus(false);
  document.querySelectorAll(".pane").forEach(el=>el.classList.toggle("active",el.id===id));
  document.querySelectorAll("nav button[data-tab]").forEach(el=>el.classList.toggle("active",el.dataset.tab===id));
  ["mission-panel","geo-panel","media-panel","fleet-panel","wayline-panel"].forEach((key,i)=>{
    const current=["map-pane","geo-pane","media-pane","fleet-pane","waylines-pane"][i];
    $(key).hidden=(current!==id&&!(key==="geo-panel"&&id==="terrain-pane"));
  });
  const mapVisible=(id==="map-pane"||id==="geo-pane");
  $("map-pane").classList.toggle("active",mapVisible);
  if(mapVisible&&map){
    // Recompute the visible map size before any new route fit; never pan on resize.
    map.invalidateSize({pan:false});
    setTimeout(()=>map?.invalidateSize({pan:false}),80);
  }
  if(id==="waylines-pane"&&!waylineData&&!waylineAbort)loadWaylines();
}
async function loadWorkspace(){
  statusMessage("LAN-Verbindung wird geprüft…");
  try{
    const missions=await loadMissions();
    notice("Lokaler Missionsarbeitsbereich bereit.");
    statusMessage("LAN-Verbindung aktiv");
  }catch(err){
    const msg=errorMessage(err);
    notice("Missionsspeicher nicht verfügbar: "+msg,true);
    statusMessage("Missionsspeicherfehler: "+msg,true);
  }
  await Promise.allSettled([loadMedia(),loadDjiMedia(),loadFleet(),loadGeoObjects()]);
}
function revokeMedia(){mediaUrls.forEach(url=>URL.revokeObjectURL(url));mediaUrls=[];}
function closePreview(){const dlg=$("media-dialog");if(dlg.open)dlg.close();$("preview-content").replaceChildren();if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null;}}
async function uploadMedia(){
  const files=Array.from($("media-file").files||[]);if(!files.length)throw new Error("Keine Dateien gewählt");
  for(const f of files){
    if(f.size>25*1024*1024)throw new Error(f.name+": über 25 MiB");
    if(!["image/jpeg","image/png","image/webp","video/mp4"].includes(f.type))throw new Error(f.name+": Dateityp nicht unterstützt");
    $("media-notice").textContent="Lade "+f.name+" hoch...";
    await api("/api/v1/studio/media",{method:"POST",headers:{"Content-Type":f.type,"X-Filename":encodeURIComponent(f.name)},body:f});
  }
  $("media-file").value="";$("media-notice").textContent=files.length+" Datei(en) gespeichert";
  await loadMedia();
}
let djiMediaItems=[],djiMediaTotal=0,djiMediaOffset=0;
async function loadDjiMedia(reset=true){
  if(reset){djiMediaOffset=0;djiMediaItems=[];}
  const search=$("dji-media-search").value.trim();
  const params=new URLSearchParams({q:search,limit:"40",offset:String(djiMediaOffset)});
  const result=await api("/api/v1/studio/dji-media?"+params.toString());
  const data=await result.json();
  djiMediaItems.push(...data.media);djiMediaTotal=data.total;
  djiMediaOffset+=data.media.length;
  const stamp=data.last_scanned_at?new Date(data.last_scanned_at).toLocaleString("de-DE"):"noch nie";
  $("dji-media-status").textContent=
    djiMediaTotal+" DJI-Medien indiziert · letzter vollständiger Scan: "+stamp+
    ". Neue Uploads werden erst nach erneutem Pi-Scan sichtbar.";
  renderDjiMedia();
}
function renderDjiMedia(){
  const grid=$("dji-media-gallery");grid.replaceChildren();
  $("more-dji-media").hidden=djiMediaItems.length>=djiMediaTotal;
  if(!djiMediaItems.length){
    cardText(grid,"div","empty","Keine indizierten DJI-Medien vorhanden.");
    return;
  }
  for(const m of djiMediaItems){
    const card=cardText(grid,"article","media-card");
    cardText(card,"div","media-cover",m.mime.startsWith("image/")?"DJI · Foto":"DJI · Video/Datei");
    cardText(card,"div","media-name",m.name);
    const stamp=m.modified_at?new Date(m.modified_at).toLocaleString("de-DE"):"ohne Zeitstempel";
    cardText(card,"div","note",m.mime+" · "+(m.size_bytes/1048576).toFixed(1)+" MiB · "+stamp);
    const buttons=cardText(card,"div","button-row");
    if(m.previewable){
      const preview=cardText(buttons,"button","","Ansehen");
      preview.addEventListener("click",()=>previewDjiMedia(m).catch(
        err=>$("dji-media-status").textContent=errorMessage(err)));
    }
    const save=cardText(buttons,"button","","Herunterladen");
    save.addEventListener("click",()=>downloadDjiMedia(m).catch(
      err=>$("dji-media-status").textContent=errorMessage(err)));
  }
}
async function previewDjiMedia(m){
  closePreview();
  const result=await api("/api/v1/studio/dji-media/"+m.id+"/file");
  previewUrl=URL.createObjectURL(await result.blob());
  $("preview-name").textContent=m.name;
  const image=els("img");image.alt=m.name;image.src=previewUrl;
  $("preview-content").appendChild(image);$("media-dialog").showModal();
}
async function downloadDjiMedia(m){
  const url="/api/v1/studio/dji-media/"+m.id+"/file?download=true";
  // Large media is streamed by the server. In direct trusted-LAN mode,
  // navigate instead of allocating huge videos in JavaScript memory.
  if(m.size_bytes>128*1048576){
    const a=els("a");a.href=url;a.download=m.name;
    document.body.appendChild(a);a.click();a.remove();return;
  }
  const result=await api(url);
  const temp=URL.createObjectURL(await result.blob());
  const a=els("a");a.href=temp;a.download=m.name;
  document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(temp),5000);
}
async function loadMedia(){
  const r=await api("/api/v1/studio/media");knownMedia=(await r.json()).media;displayMedia=20;await renderMedia();
}
async function mediaBlob(meta){
  const r=await api("/api/v1/studio/media/"+encodeURIComponent(meta.id)+"/file");
  return r.blob();
}
async function renderMedia(){
  revokeMedia();
  const grid=$("gallery");grid.replaceChildren();
  const needle=$("media-search").value.trim().toLowerCase();
  updateGeoPhotoSelect();
  const found=knownMedia.filter(m=>m.name.toLowerCase().includes(needle));
  const visible=found.slice(0,displayMedia);
  $("more-media").hidden=found.length<=displayMedia;
  if(!found.length){cardText(grid,"div","empty","Keine passenden Dateien gefunden.");return;}
  const session=epoch;
  for(const meta of visible){
    if(session!==epoch)return;
    const card=cardText(grid,"article","media-card");
    const cover=cardText(card,"div","media-cover");
    if(meta.mime.startsWith("image/")){
      try{
        const blob=await mediaBlob(meta);if(session!==epoch)return;
        const url=URL.createObjectURL(blob);mediaUrls.push(url);
        const img=cardText(cover,"img");img.alt=meta.name;img.src=url;img.loading="lazy";
      }catch(_){cover.textContent="Vorschau nicht verfügbar";}
    }else{cardText(cover,"div","video-icon","▶ Video");}
    cardText(card,"div","media-name",meta.name);
    cardText(card,"div","note",new Date(meta.created_at).toLocaleString("de-DE")+" · "+(meta.size_bytes/1024/1024).toFixed(1)+" MB");
    const tools=cardText(card,"div","button-row");
    if(meta.mime.startsWith("image/")){
      const locate=cardText(tools,"button","","GeoPhoto");
      locate.addEventListener("click",()=>{switchTab("media-pane");$("geophoto-media").value=meta.id;showGeoPhotoFields();});
    }
    const view=cardText(tools,"button","","Ansehen");view.addEventListener("click",()=>previewMedia(meta).catch(err=>$("media-notice").textContent=err.message));
    const remove=cardText(tools,"button","danger","Löschen");remove.addEventListener("click",async()=>{
      if(!confirm("Datei auf dem Pi dauerhaft löschen?"))return;
      try{await api("/api/v1/studio/media/"+encodeURIComponent(meta.id),{method:"DELETE"});await loadMedia();}
      catch(err){$("media-notice").textContent=err.message}
    });
  }
}
async function previewMedia(meta){
  closePreview();const blob=await mediaBlob(meta);
  previewUrl=URL.createObjectURL(blob);$("preview-name").textContent=meta.name;
  const el=els(meta.mime.startsWith("image/")?"img":"video");
  el.src=previewUrl;
  if(el.tagName==="VIDEO")el.controls=true;
  $("preview-content").appendChild(el);$("media-dialog").showModal();
}
async function loadFleet(){
  const r=await api("/api/v1/status/devices?limit=200");const data=await r.json();
  const body=$("fleet-grid");body.replaceChildren();
  $("fleet-notice").textContent=data.total+" Gerät(e) im AeroNexus-Statusbestand.";
  if(!data.devices.length)cardText(body,"div","empty","Keine Geräte registriert.");
  for(const d of data.devices){
    const card=cardText(body,"article","fleet-card");
    cardText(card,"h3","",d.name||d.device_id);
    cardText(card,"div","note",d.kind+" · "+d.freshness+" · "+d.device_id);
    const grid=cardText(card,"div","fleet-data");
    for(const [name,value] of [["Online",d.online===true?"Ja":d.online===false?"Nein":"Unbekannt"],
      ["Akku",d.telemetry?.battery_percent==null?"–":d.telemetry.battery_percent+" %"],
      ["GPS-Satelliten",d.telemetry?.gps_satellites??"–"],
      ["Empfangsalter",d.age_seconds==null?"–":d.age_seconds+" s"]]){
      const line=cardText(grid,"div");cardText(line,"div","note",name);cardText(line,"b","",value);
    }
  }
  return data.devices;
}
async function loadPilot2Topology(){
  const status=$("pilot2-topology-state"),grid=$("pilot2-topology-grid"),button=$("pilot2-topology-refresh");
  button.disabled=true;grid.replaceChildren();
  status.className="status";status.textContent="Lokale Pilot-2-Topologie wird abgefragt…";
  try{
    const response=await api("/api/v1/local-cloud/topology");
    const data=await response.json();
    if(data.state!=="connected")throw new Error("Pilot-2-Geräte: "+clean(data.state));
    if(!Array.isArray(data.devices)||!Array.isArray(data.links))throw new Error("Ungültige Geräte-Topologie");
    const online=data.devices.filter(device=>device.online===true).length;
    const offline=data.devices.filter(device=>device.online===false).length;
    const unknown=data.devices.length-online-offline;
    status.className="status"+(offline===0&&unknown===0?" good":"");
    status.textContent=data.devices.length+" Geräte: "+online+" online, "+offline+
      " offline, "+unknown+" unbekannt · "+data.links.length+
      " Zuordnungen · Stand: "+clean(data.updated_at)+
      " · Cloud-Momentaufnahme, keine automatische Flugsteuerung";
    for(const item of data.devices){
      const card=cardText(grid,"article","wayline-card");
      cardText(card,"h2","",item.callsign||"DJI-Gerät");
      cardText(card,"p","",item.role==="aircraft"?"Fluggerät":"Fernsteuerung");
      const modelLabel=waylineModel(item.device_model_key);
      cardText(card,"p","",clean(item.serial_number)+" · "+modelLabel+
        (item.device_model_key&&modelLabel!==item.device_model_key?" ("+item.device_model_key+")":""));
      cardText(card,"p","",item.online===true?"Online":item.online===false?"Offline":"Online-Status unbekannt");
      const related=data.links.filter(link=>item.role==="aircraft"
        ?link.aircraft_sn===item.serial_number
        :link.controller_sn===item.serial_number);
      const counterpartRole=item.role==="aircraft"?"controller":"aircraft";
      const names=related.map(link=>{
        const serial=counterpartRole==="controller"?link.controller_sn:link.aircraft_sn;
        const match=data.devices.find(device=>device.role===counterpartRole&&device.serial_number===serial);
        return match?.callsign||match?.device_model_key||serial;
      });
      cardText(card,"p","note",names.length?"Zugeordnet: "+names.join(", "):"Keine Zuordnung gemeldet");
    }
    if(!data.devices.length)cardText(grid,"div","empty","Keine Geräte in der lokalen Pilot-2-Topologie gemeldet.");
  }catch(err){
    grid.replaceChildren();status.className="status error";
    status.textContent=errorMessage(err)+" · Prüfung der Sitzung und lokalen Cloud erforderlich.";
  }finally{button.disabled=false;}
}
async function showFleetOnMap(){
  const devices=await loadFleet();
  switchTab("map-pane");getMap();if(!map||!deviceLayer)throw new Error("Karte nicht verfügbar");deviceLayer.clearLayers();
  const locs=[];
  for(const d of devices){
    const t=d.telemetry||{};
    if(d.freshness!=="fresh"||typeof t.latitude!=="number"||typeof t.longitude!=="number"||!Number.isFinite(t.latitude)||!Number.isFinite(t.longitude))continue;
    if(t.latitude===0&&t.longitude===0)continue;
    locs.push([t.latitude,t.longitude]);
    L.circleMarker([t.latitude,t.longitude],{radius:8,color:"#7feac9",fillOpacity:.9})
      .bindTooltip(d.name||"Drohne").addTo(deviceLayer);
  }
  if(locs.length)map.fitBounds(L.latLngBounds(locs).pad(.3),{maxZoom:16});
  notice(locs.length?locs.length+" aktuelle Geräteposition(en) angezeigt.":"Keine aktuelle GPS-Position verfügbar.");
}

// Geo-objects are separate from waypoint missions and never enter WPML.
function setGeoMode(enabled){
  geoDraw=enabled;
  if(enabled){addMode=false;$("add-mode").textContent="+ Auf Karte setzen";$("add-mode").classList.remove("primary");}
  $("geo-draw").textContent=enabled?"Kartenmodus beenden":"Punkte auf Karte setzen";
  $("geo-draw").classList.toggle("primary",enabled);
  if(enabled)switchTab("geo-pane");
}
function redrawGeo(){
  $("geo-draft-status").textContent=geoDraft.length+" Koordinaten im Entwurf · "+$("geo-kind").value+
    ". Zum Speichern Kartenmodus beenden.";
  const list=$("geo-draft-points");list.replaceChildren();
  geoDraft.forEach((point,index)=>{
    const row=cardText(list,"div","geo-row");
    cardText(row,"span","",String(index+1)+": "+point.latitude.toFixed(7)+", "+point.longitude.toFixed(7));
    const remove=cardText(row,"button","danger","Entfernen");
    remove.addEventListener("click",()=>{geoDraft.splice(index,1);redrawGeo();});
  });
  $("geo-undo-vertex").disabled=geoDraft.length===0;
  if(!geoLayer||!map)return;
  geoLayer.clearLayers();
  const draw=(points,kind,label,draft=false,radius=0)=>{
    const coords=points.map(p=>[p.latitude,p.longitude]);
    const style={color:draft?"#ffc878":"#74debb",weight:3,fillOpacity:.14};
    let shape=null;
    if(kind==="polygon"&&coords.length>=3)shape=L.polygon(coords,style);
    else if(kind==="line"&&coords.length>=2)shape=L.polyline(coords,style);
    else if(kind==="circle"&&coords.length===1)shape=L.circle(coords[0],{...style,radius});
    else if(coords.length===1)shape=L.circleMarker(coords[0],{...style,radius:6});
    if(shape)shape.bindTooltip(label).addTo(geoLayer);
    if(draft)coords.forEach((p,index)=>{
      // Draggable draft vertices only; saved geometry stays unchanged until save.
      L.marker(p,{draggable:true,autoPan:true,
        icon:L.divIcon({className:"geo-vertex",html:"+" ,iconSize:[18,18],iconAnchor:[9,9]})})
        .bindTooltip("Eckpunkt "+(index+1)+" verschieben")
        .on("dragend",event=>{
          const moved=event.target.getLatLng();
          const lat=+moved.lat.toFixed(7);
          const lon=+(((((moved.lng+540)%360)+360)%360)-180).toFixed(7);
          if(!Number.isFinite(lat)||Math.abs(lat)>90||!Number.isFinite(lon)){
            redrawGeo();return;
          }
          geoDraft[index]={latitude:lat,longitude:lon};
          redrawGeo();
        }).addTo(geoLayer);
    });
  };
  for(const row of geoObjects){
    if(row.id===geoEditingId)continue;
    const obj=row.object;
    draw(obj.vertices,obj.kind,obj.name,false,obj.radius_m||0);
  }
  const kind=$("geo-kind").value;
  const radius=Number($("geo-radius").value)||50;
  draw(geoDraft,kind,"Geo-Entwurf",true,radius);
}
async function loadGeoObjects(){
  const r=await api("/api/v1/studio/geo-objects");
  geoObjects=(await r.json()).objects;
  terrainRefreshProfileOptions();
  terrainRedrawSoon();
  const list=$("geo-list");list.replaceChildren();
  const pick=$("survey-object");const chosen=pick.value;pick.replaceChildren();
  const empty=els("option","","Polygon auswählen…");empty.value="";pick.appendChild(empty);
  for(const item of geoObjects){
    const obj=item.object;
    const row=cardText(list,"div","geo-row");
    cardText(row,"span","",obj.name+" · "+obj.kind+" · "+obj.vertices.length+" Punkte");
    const edit=cardText(row,"button","","Bearbeiten");
    edit.addEventListener("click",()=>{
      if(geoDraft.length&&(!geoEditingId||geoEditingId!==item.id)&&
         !window.confirm("Ungespeicherten Geo-Entwurf verwerfen?"))return;
      geoEditingId=item.id;
      $("geo-name").value=obj.name;
      $("geo-kind").value=obj.kind;
      $("geo-radius").value=obj.radius_m??50;
      geoDraft=obj.vertices.map(p=>({...p}));
      setGeoMode(false);redrawGeo();
      $("geo-draft-status").textContent="Geo-Objekt bearbeiten: "+obj.name;
    });
    const del=cardText(row,"button","danger","×");
    del.title="Geo-Objekt löschen";
    del.addEventListener("click",async()=>{
      if(!confirm("Lokales Geo-Objekt löschen?"))return;
      await api("/api/v1/studio/geo-objects/"+encodeURIComponent(item.id),{method:"DELETE"});
      if(geoEditingId===item.id){geoEditingId=null;geoDraft=[];}
      await loadGeoObjects();
    });
    if(obj.kind==="polygon"){
      const opt=els("option","",obj.name);opt.value=item.id;pick.appendChild(opt);
    }
  }
  pick.value=geoObjects.some(x=>x.id===chosen&&x.object.kind==="polygon")?chosen:"";
  redrawGeo();
}
async function saveGeoObject(){
  const kind=$("geo-kind").value;
  const obj={name:$("geo-name").value.trim(),kind,vertices:geoDraft.slice(),
    radius_m:kind==="circle"?Number($("geo-radius").value):null};
  const editingId=geoEditingId;
  const saveSignature=JSON.stringify([geoDraft,$("geo-name").value,
    $("geo-kind").value,$("geo-radius").value]);
  const path="/api/v1/studio/geo-objects"+(editingId?"/"+encodeURIComponent(editingId):"");
  const r=await api(path,{
    method:editingId?"PUT":"POST",
    headers:{"Content-Type":"application/json"},body:JSON.stringify(obj)});
  const saved=await r.json();
  // A completed request must not wipe points drawn while the save was pending.
  if(geoEditingId!==editingId||JSON.stringify([geoDraft,$("geo-name").value,
      $("geo-kind").value,$("geo-radius").value])!==saveSignature){
    await loadGeoObjects();
    $("geo-draft-status").textContent="Gespeicherte frühere Version. Der aktuelle Geo-Entwurf blieb erhalten.";
    return;
  }
  geoDraft=[];geoEditingId=null;setGeoMode(false);await loadGeoObjects();
  if(kind==="polygon")$("survey-object").value=saved.id;
  $("geo-draft-status").textContent="Geo-Objekt gespeichert (nur lokal).";
}
async function surveyPreview(){
  const row=geoObjects.find(x=>x.id===$("survey-object").value);
  if(!row||row.object.kind!=="polygon")throw new Error("Polygon auswählen");
  const r=await api("/api/v1/studio/survey/preview",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({polygon:row.object,spacing_m:Number($("survey-spacing").value),
      bearing_deg:Number($("survey-bearing").value)})});
  const data=await r.json();
  if(map&&surveyLayer){
    surveyLayer.clearLayers();
    data.legs.forEach(segment=>L.polyline(segment.map(p=>[p.latitude,p.longitude]),{
      color:"#ffab70",weight:3,dashArray:"5 5"}).addTo(surveyLayer));
    if(data.legs.length)map.fitBounds(L.latLngBounds(data.legs.flat().map(p=>[p.latitude,p.longitude])),{
      padding:[50,50],maxZoom:17});
  }
  $("survey-message").textContent=data.leg_count+" getrennte Flugstreifen · "+
    formatRouteDistance(data.distance_m)+
    ". Nur geometrische Vorschau ohne Wendemanöver, Gelände-/Hindernisprüfung oder WPML-Export.";
}
function updateGeoPhotoSelect(){
  const el=$("geophoto-media"),old=el.value;
  el.replaceChildren();
  const empty=els("option","","Bild auswählen");empty.value="";el.appendChild(empty);
  for(const m of knownMedia.filter(m=>m.mime.startsWith("image/"))){
    const opt=els("option","",m.name);opt.value=m.id;el.appendChild(opt);
  }
  el.value=knownMedia.some(m=>m.id===old)?old:"";
}
function showGeoPhotoFields(){
  const m=knownMedia.find(row=>row.id===$("geophoto-media").value);
  const fields=[["lat","latitude"],["lon","longitude"],["alt","altitude_m"],
    ["heading","heading_deg"],["pitch","pitch_deg"],["roll","roll_deg"],
    ["captured","captured_at"],["notes","notes"]];
  for(const [id,key] of fields)$("geophoto-"+id).value=m?.[key]??"";
}
async function saveGeoPhoto(){
  const id=$("geophoto-media").value;
  if(!id)throw new Error("Zuerst ein Foto auswählen");
  const number=id=>{const val=$("geophoto-"+id).value.trim();return val===""?null:Number(val);};
  const body={latitude:number("lat"),longitude:number("lon"),
    altitude_m:number("alt"),heading_deg:number("heading"),
    pitch_deg:number("pitch"),roll_deg:number("roll"),
    captured_at:$("geophoto-captured").value.trim()||null,
    notes:$("geophoto-notes").value};
  if((body.latitude===null)!==(body.longitude===null))throw new Error("Breite und Länge zusammen eingeben.");
  await api("/api/v1/studio/media/"+encodeURIComponent(id)+"/geo",{
    method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  await loadMedia();
  $("geophoto-status").textContent="GeoPhoto-Kameradaten lokal gespeichert.";
}
function showGeoPhotos(){
  if(!map||!photoLayer){$("geophoto-status").textContent="Karte nicht verfügbar.";return;}
  photoLayer.clearLayers();const spots=[];
  for(const m of knownMedia){
    if(!m.mime.startsWith("image/")||!Number.isFinite(m.latitude)||!Number.isFinite(m.longitude))continue;
    const p=[m.latitude,m.longitude];spots.push(p);
    L.circleMarker(p,{color:"#fa8cbd",radius:7,fillOpacity:.85})
      .bindTooltip(m.name+(m.heading_deg==null?"":" · Blick "+m.heading_deg+"°")).addTo(photoLayer);
  }
  switchTab("map-pane");
  if(spots.length)map.fitBounds(L.latLngBounds(spots),{padding:[40,40],maxZoom:17});
  notice(spots.length+" gespeicherte Aufnahmeorte auf Karte; keine Bildabdeckung behauptet.");
}
// Phase 18: local 2D-canvas rasterizer of an orthographic 3D height field.
// No WebGL, external 3D library, DJI flight path, map tiles or new backend API.
// Never mutate the validated TerrainGrid: the STL uses original metre values.
const TERRAIN_DEFAULT_VIEW=Object.freeze({
  azimuth:45,tilt:45,zoom:1,exaggeration:2,color:true,wire:true,slope:false,geoOverlay:true
});
let terrainView={...TERRAIN_DEFAULT_VIEW},terrainDrag=null,terrainDrawQueued=false;
function terrainClamp(value,min,max){
  return Math.max(min,Math.min(max,value));
}
function terrainColor(value){
  const colors=[[23,78,94],[38,112,112],[99,155,112],[194,177,105],[235,210,156]];
  const index=terrainClamp(value,0,1)*(colors.length-1);
  const start=Math.min(colors.length-2,Math.floor(index));
  const t=index-start,from=colors[start],to=colors[start+1];
  return "rgb("+from.map((channel,i)=>Math.round(channel+(to[i]-channel)*t)).join(",")+")";
}
// Phase 20: derive local DEM inclination from *unexaggerated* raster heights.
// The bilinear partial derivatives use horizontal grid spacing in metres.
// The result is a display-only angle, not a safe flight/terrain assessment.
function terrainSlopeAt(grid,row,col){
  if(!grid||!Number.isFinite(row)||!Number.isFinite(col))return null;
  const z=grid.heights_m;
  if(!Array.isArray(z)||z.length<2||!Array.isArray(z[0])||z[0].length<2||
     !(grid.x_step_m>0)||!(grid.y_step_m>0))return null;
  const nr=z.length,nc=z[0].length;
  if(row<0||col<0||row>nr-1||col>nc-1)return null;
  const r=Math.min(nr-2,Math.floor(row)),c=Math.min(nc-2,Math.floor(col));
  const ty=row-r,tx=col-c;
  const dx=((1-ty)*(z[r][c+1]-z[r][c])+
    ty*(z[r+1][c+1]-z[r+1][c]))/grid.x_step_m;
  const dy=((1-tx)*(z[r+1][c]-z[r][c])+
    tx*(z[r+1][c+1]-z[r][c+1]))/grid.y_step_m;
  const degrees=Math.atan(Math.hypot(dx,dy))*180/Math.PI;
  return Number.isFinite(degrees)?degrees:null;
}
function terrainSlopeStatistics(grid){
  if(!grid||!Array.isArray(grid.heights_m)||grid.heights_m.length<2||
     !Array.isArray(grid.heights_m[0]))return null;
  const rows=grid.heights_m.length,cols=grid.heights_m[0].length;
  let min=Infinity,max=-Infinity,sum=0,count=0,steep=0;
  for(let r=0;r<rows-1;r++){
    for(let c=0;c<cols-1;c++){
      const deg=terrainSlopeAt(grid,r+0.5,c+0.5);
      if(deg===null)return null;
      min=Math.min(min,deg);max=Math.max(max,deg);sum+=deg;count++;
      if(deg>=30)steep++;
    }
  }
  return count?{min_deg:min,max_deg:max,mean_deg:sum/count,
    steep_cells:steep,total_cells:count}:null;
}
function terrainSlopeColor(degrees){
  if(degrees===null||!Number.isFinite(degrees))return "#456677";
  if(degrees<8)return "#3da989";
  if(degrees<15)return "#b5bf5b";
  if(degrees<30)return "#e4a354";
  return "#d95c63";
}
function terrainUpdateSlopeInfo(grid){
  const stats=terrainSlopeStatistics(grid);
  $("terrain-slope-info").textContent=stats?
    "DEM-Hangneigung (resampelte Zellen, keine Flugfreigabe): Mittel "+
    stats.mean_deg.toFixed(1)+"°, Maximum "+stats.max_deg.toFixed(1)+
    "° · ≥30°: "+stats.steep_cells+"/"+stats.total_cells+
    " Zellen. Farben: Grün <8°, Gelb 8–15°, Orange 15–30°, Rot ≥30°. "+
    "Rastergradient ohne Darstellungsüberhöhung; Höhenbezug ungeprüft.":
    "Noch keine Hangneigungsanalyse. GeoTIFF laden, um die lokale DEM-Neigung auszuwerten.";
}
function terrainProjection(grid,view,width,height){
  const heights=grid.heights_m;
  const rows=heights.length,cols=heights[0].length;
  const zmin=Math.min(...heights.flat()),zmax=Math.max(...heights.flat());
  const xextent=(cols-1)*grid.x_step_m,yextent=(rows-1)*grid.y_step_m;
  const extent=Math.max(xextent,yextent,1e-9);
  const radians=Math.PI/180,yaw=view.azimuth*radians,tilt=view.tilt*radians;
  const cy=Math.cos(yaw),sy=Math.sin(yaw),sp=Math.sin(tilt),cp=Math.cos(tilt);
  const scale=Math.min(width,height)*0.66*view.zoom;
  const originX=width/2,originY=height*0.58;
  const project=(r,c,elevation)=>{
    const x=(c*grid.x_step_m-xextent/2)/extent;
    const y=(r*grid.y_step_m-yextent/2)/extent;
    // Display clip only: never alter original DEM values.
    const z=terrainClamp((elevation-zmin)/extent,0,1.5)*view.exaggeration;
    const rx=x*cy-y*sy,ry=x*sy+y*cy;
    return {x:originX+rx*scale,y:originY+(ry*sp-z*cp)*scale,
      depth:ry*cp+z*sp,elevation,row:r,col:c};
  };
  const vertices=heights.map((row,r)=>row.map((elevation,c)=>
    project(r,c,elevation)));
  const cells=[];
  for(let r=0;r<rows-1;r++){
    for(let c=0;c<cols-1;c++){
      const points=[vertices[r][c],vertices[r][c+1],
        vertices[r+1][c+1],vertices[r+1][c]];
      cells.push({points,depth:points.reduce((sum,p)=>sum+p.depth,0)/4,
        elevation:points.reduce((sum,p)=>sum+p.elevation,0)/4});
    }
  }
  cells.sort((a,b)=>a.depth-b.depth);
  return {cells,zmin,zmax,rows,cols,project};
}
// Phase 19: WGS84 sample centres, bounded; never infer lat/lon from a
// projected CRS or attach unknown vertical datums to elevation values.
function terrainGeoBounds(grid,geo){
  if(!grid||!geo||geo.crs!=="EPSG:4326")return null;
  const rows=grid.heights_m.length,cols=grid.heights_m[0].length;
  const south=geo.north_lat+(rows-1)*geo.lat_step_deg;
  const east=geo.west_lon+(cols-1)*geo.lon_step_deg;
  if(![south,east,geo.north_lat,geo.west_lon].every(Number.isFinite))return null;
  return [[south,geo.west_lon],[geo.north_lat,east]];
}
function terrainDrawMapFootprint(){
  if(!map||!terrainFootprintLayer)return;
  terrainFootprintLayer.clearLayers();
  const bounds=terrainGeoBounds(terrainGrid,terrainGeo);
  if(!bounds)return;
  L.rectangle(bounds,{color:"#ffd282",weight:2,fillOpacity:0.04,dashArray:"6 6"})
    .bindTooltip("GeoTIFF: WGS84-Rasterpunktmitten (nicht volle Pixelränder)")
    .addTo(terrainFootprintLayer);
}
function terrainShowOnMap(){
  const bounds=terrainGeoBounds(terrainGrid,terrainGeo);
  if(!bounds){$("terrain-message").textContent="Für dieses Raster fehlen geeignete EPSG:4326-Koordinaten.";return;}
  switchTab("map-pane");
  getMap();
  if(!map)return;
  terrainDrawMapFootprint();
  map.fitBounds(L.latLngBounds(bounds).pad(0.15),{maxZoom:18});
  notice("GeoTIFF-Rasterpunktmitten auf Karte hervorgehoben. Nur geografische Vorschau.");
}
function terrainGridPoint(grid,geo,location){
  if(!grid||!geo||geo.crs!=="EPSG:4326"||!location)return null;
  if(!Number.isFinite(location.latitude)||!Number.isFinite(location.longitude)||
     !(geo.lon_step_deg>0)||!(geo.lat_step_deg<0))return null;
  const col=(location.longitude-geo.west_lon)/geo.lon_step_deg;
  const row=(location.latitude-geo.north_lat)/geo.lat_step_deg;
  const lastRow=grid.heights_m.length-1,lastCol=grid.heights_m[0].length-1;
  if(!Number.isFinite(col)||!Number.isFinite(row)||
     row < -1e-7 || col < -1e-7 || row>lastRow+1e-7 || col>lastCol+1e-7)return null;
  return terrainHeightAt(grid,terrainClamp(row,0,lastRow),terrainClamp(col,0,lastCol));
}
function terrainHeightAt(grid,row,col){
  if(!grid||!Number.isFinite(row)||!Number.isFinite(col))return null;
  const heights=grid.heights_m,rows=heights.length,cols=heights[0].length;
  if(row<0||col<0||row>rows-1||col>cols-1)return null;
  const r0=Math.min(rows-2,Math.floor(row)),c0=Math.min(cols-2,Math.floor(col));
  const ry=row-r0,cx=col-c0;
  const z=(1-ry)*((1-cx)*heights[r0][c0]+cx*heights[r0][c0+1])+
        ry*((1-cx)*heights[r0+1][c0]+cx*heights[r0+1][c0+1]);
  return {row,col,elevation:z};
}
function terrainGeoFromGrid(geo,row,col){
  if(!geo||geo.crs!=="EPSG:4326")return null;
  return {latitude:geo.north_lat+row*geo.lat_step_deg,
    longitude:geo.west_lon+col*geo.lon_step_deg};
}
function terrainOverlayGeometry(obj){
  if(!obj||!Array.isArray(obj.vertices)||!obj.vertices.length)return null;
  if(obj.kind==="circle"){
    if(obj.vertices.length!==1||!Number.isFinite(obj.radius_m))return null;
    const centre=obj.vertices[0],cosine=Math.cos(centre.latitude*Math.PI/180);
    if(cosine<0.01)return null;
    const circle=[];
    for(let i=0;i<33;i++){
      const angle=2*Math.PI*i/32;
      circle.push({latitude:centre.latitude+Math.cos(angle)*obj.radius_m/111132,
        longitude:centre.longitude+Math.sin(angle)*obj.radius_m/(111320*cosine)});
    }
    return circle;
  }
  if(!["point","line","polygon"].includes(obj.kind))return null;
  return obj.vertices;
}
function terrainGeoPolyline(obj,grid,geo){
  const vertices=terrainOverlayGeometry(obj);
  if(!vertices||vertices.length>129)return null;
  const points=vertices.map(loc=>terrainGridPoint(grid,geo,loc));
  if(points.some(p=>p===null))return null; // Never draw out-of-bounds segments.
  if(obj.kind==="polygon"&&points.length>2)points.push({...points[0]});
  return points;
}
// Piecewise bilinear DEM interpolation makes a 3D GeoObject line follow
// the displayed terrain instead of connecting only its elevated vertices.
// Bound work even for many saved shapes; never mutate original GeoObjects.
function terrainDrapePolyline(points,grid){
  if(!Array.isArray(points)||points.length<1||points.length>130)return null;
  if(points.length===1)return [{...points[0]}];
  const maxSegments=1024;
  const lengths=points.slice(1).map((point,i)=>
    Math.hypot(point.row-points[i].row,point.col-points[i].col));
  // Use an even subdivision count so midpoint terrain peaks are not
  // systematically skipped when the straight segment crosses a summit.
  const wanted=lengths.map(len=>len===0?1:Math.max(2,2*Math.ceil(len*1.5)));
  const totalWanted=wanted.reduce((sum,count)=>sum+count,0);
  let remaining=maxSegments;
  const result=[{...points[0]}];
  for(let i=0;i<lengths.length;i++){
    const remainingEdges=lengths.length-i-1;
    const limit=remaining-remainingEdges;
    const count=Math.max(1,Math.min(wanted[i],limit,
      Math.floor(wanted[i]*maxSegments/Math.max(maxSegments,totalWanted))));
    const first=points[i],last=points[i+1];
    for(let k=1;k<=count;k++){
      const t=k/count;
      const r=first.row+(last.row-first.row)*t;
      const c=first.col+(last.col-first.col)*t;
      const sampled=terrainHeightAt(grid,terrainClamp(r,0,grid.heights_m.length-1),
        terrainClamp(c,0,grid.heights_m[0].length-1));
      if(!sampled)return null;
      result.push(sampled);
    }
    remaining-=count;
  }
  return result;
}
function terrainDrawOverlays(ctx,projection,grid,geo,objects,view){
  if(!geo||!view.geoOverlay||!Array.isArray(objects))return;
  ctx.lineWidth=2.4;
  for(const item of objects){
    const obj=item.object;
    const points=terrainGeoPolyline(obj,grid,geo);
    if(!points||!points.length)continue;
    const draped=terrainDrapePolyline(points,grid);
    if(!draped||!draped.length)continue;
    ctx.beginPath();
    for(let i=0;i<draped.length;i++){
      const p=draped[i],screen=projection.project(p.row,p.col,p.elevation);
      if(i===0)ctx.moveTo(screen.x,screen.y);
      else ctx.lineTo(screen.x,screen.y);
    }
    if(draped.length===1){
      const p=draped[0],screen=projection.project(p.row,p.col,p.elevation);
      ctx.arc(screen.x,screen.y,4,0,2*Math.PI);
    }
    ctx.strokeStyle="#ff7c8d";
    ctx.stroke();
  }
}
function terrainPolylineProfile(obj,grid,geo){
  if(!obj||obj.kind!=="line")return null;
  const points=terrainGeoPolyline(obj,grid,geo);
  if(!points||points.length<2)return null;
  const distances=[0];
  for(let i=1;i<points.length;i++){
    const dx=(points[i].col-points[i-1].col)*grid.x_step_m;
    const dy=(points[i].row-points[i-1].row)*grid.y_step_m;
    distances.push(distances[i-1]+Math.hypot(dx,dy));
  }
  const total=distances[distances.length-1];
  if(!Number.isFinite(total)||total<=0)return null;
  const result=[];
  let leg=1;
  for(let i=0;i<=128;i++){
    const d=total*i/128;
    while(leg<distances.length-1&&distances[leg]<d)leg++;
    const span=distances[leg]-distances[leg-1];
    const t=span>0?(d-distances[leg-1])/span:0;
    const row=points[leg-1].row+t*(points[leg].row-points[leg-1].row);
    const col=points[leg-1].col+t*(points[leg].col-points[leg-1].col);
    const sample=terrainHeightAt(grid,row,col);
    if(!sample)return null;
    result.push({distance_m:d,...sample});
  }
  return {samples:result,distance_m:total,
    min_m:Math.min(...result.map(p=>p.elevation)),
    max_m:Math.max(...result.map(p=>p.elevation))};
}
function terrainDrawProfile(profile){
  const canvas=$("terrain-profile-canvas"),ctx=canvas.getContext("2d");
  if(!ctx)return;
  ctx.clearRect(0,0,canvas.width,canvas.height);
  ctx.fillStyle="#0d2233";ctx.fillRect(0,0,canvas.width,canvas.height);
  if(!profile)return;
  const margin=35,width=canvas.width-2*margin,height=canvas.height-2*margin;
  const range=Math.max(1,profile.max_m-profile.min_m);
  ctx.beginPath();
  for(const [i,p] of profile.samples.entries()){
    const x=margin+p.distance_m/profile.distance_m*width;
    const y=margin+(1-(p.elevation-profile.min_m)/range)*height;
    if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
  }
  ctx.strokeStyle="#75e5cb";ctx.lineWidth=2.5;ctx.stroke();
}
function terrainDrawCanvas(canvas,grid,view){
  const ctx=canvas.getContext("2d");
  if(!ctx)return;
  const width=canvas.width,height=canvas.height;
  ctx.clearRect(0,0,width,height);
  ctx.fillStyle="#0d2233";
  ctx.fillRect(0,0,width,height);
  if(!grid)return;
  const projected=terrainProjection(grid,view,width,height);
  for(const cell of projected.cells){
    ctx.beginPath();
    cell.points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));
    ctx.closePath();
    const fraction=(cell.elevation-projected.zmin)/
      Math.max(projected.zmax-projected.zmin,1e-9);
    const slope=view.slope?terrainSlopeAt(grid,cell.points[0].row+0.5,
      cell.points[0].col+0.5):null;
    ctx.fillStyle=view.slope?terrainSlopeColor(slope):
      view.color?terrainColor(fraction):"#456677";
    ctx.fill();
    if(view.wire){
      ctx.strokeStyle="rgba(210,239,250,0.42)";
      ctx.lineWidth=width>500?0.8:0.5;
      ctx.stroke();
    }
  }
  if(canvas.id==="terrain-canvas-large")
    terrainDrawOverlays(ctx,projected,grid,terrainGeo,geoObjects,view);
}
function drawTerrainPreview(grid){
  terrainDrawCanvas($("terrain-canvas"),grid,terrainView);
  terrainDrawCanvas($("terrain-canvas-large"),grid,terrainView);
}
function terrainSyncControls(){
  for(const key of ["azimuth","tilt","zoom","exaggeration"]){
    $("terrain-"+key).value=String(terrainView[key]);
  }
  $("terrain-color").checked=terrainView.color;
  $("terrain-wire").checked=terrainView.wire;
  $("terrain-slope").checked=terrainView.slope;
  $("terrain-geo-overlay").checked=terrainView.geoOverlay;
  $("terrain-azimuth-value").textContent=Math.round(terrainView.azimuth)+"°";
  $("terrain-tilt-value").textContent=Math.round(terrainView.tilt)+"°";
  $("terrain-zoom-value").textContent=terrainView.zoom.toFixed(1).replace(".",",")+"×";
  $("terrain-exaggeration-value").textContent=
    terrainView.exaggeration.toFixed(1).replace(".",",")+"×";
}
function terrainRedrawSoon(){
  if(!terrainGrid||terrainDrawQueued)return;
  terrainDrawQueued=true;
  const request=window.requestAnimationFrame||((fn)=>fn());
  request(()=>{
    terrainDrawQueued=false;
    if(terrainGrid)drawTerrainPreview(terrainGrid);
  });
}
function terrainResetView(){
  terrainView={...TERRAIN_DEFAULT_VIEW};
  terrainSyncControls();
  terrainRedrawSoon();
}
function terrainControlChanged(){
  const numeric={azimuth:[-180,180],tilt:[15,80],zoom:[0.5,2.5],
    exaggeration:[1,6]};
  for(const [key,[min,max]] of Object.entries(numeric)){
    const input=Number($("terrain-"+key).value);
    if(Number.isFinite(input))terrainView[key]=terrainClamp(input,min,max);
  }
  terrainView.color=$("terrain-color").checked;
  terrainView.wire=$("terrain-wire").checked;
  terrainView.slope=$("terrain-slope").checked;
  terrainView.geoOverlay=$("terrain-geo-overlay").checked;
  terrainSyncControls();
  terrainRedrawSoon();
}
// Screen-space triangle pick: use only the visually rendered terrain surface.
function terrainTriangleWeights(a,b,c,x,y){
  const det=(b.y-c.y)*(a.x-c.x)+(c.x-b.x)*(a.y-c.y);
  if(Math.abs(det)<1e-9)return null;
  const u=((b.y-c.y)*(x-c.x)+(c.x-b.x)*(y-c.y))/det;
  const v=((c.y-a.y)*(x-c.x)+(a.x-c.x)*(y-c.y))/det;
  const w=1-u-v;
  return u>=-1e-7&&v>=-1e-7&&w>=-1e-7?[u,v,w]:null;
}
function terrainProbeAt(grid,view,x,y,width,height){
  if(!grid||!Number.isFinite(x)||!Number.isFinite(y))return null;
  const projection=terrainProjection(grid,view,width,height);
  for(let i=projection.cells.length-1;i>=0;i--){
    const q=projection.cells[i].points;
    for(const [a,b,c] of [[0,1,2],[0,2,3]]){
      const weights=terrainTriangleWeights(q[a],q[b],q[c],x,y);
      if(!weights)continue;
      const mix=key=>weights[0]*q[a][key]+weights[1]*q[b][key]+
        weights[2]*q[c][key];
      return terrainHeightAt(grid,mix("row"),mix("col"));
    }
  }
  return null;
}
function terrainShowProbe(canvas,event){
  if(!terrainGrid||typeof canvas.getBoundingClientRect!=="function")return;
  const rect=canvas.getBoundingClientRect();
  if(rect.width<=0||rect.height<=0)return;
  const x=(event.clientX-rect.left)*canvas.width/rect.width;
  const y=(event.clientY-rect.top)*canvas.height/rect.height;
  const hit=terrainProbeAt(terrainGrid,terrainView,x,y,canvas.width,canvas.height);
  const target=$("terrain-coordinate-probe");
  if(!hit){
    target.textContent="Kein Geländepunkt getroffen. Auf die gezeichnete Oberfläche klicken.";
    return;
  }
  const geo=terrainGeoFromGrid(terrainGeo,hit.row,hit.col);
  const slope=terrainSlopeAt(terrainGrid,hit.row,hit.col);
  target.textContent="Rasterhöhe (vertikaler Bezug unbekannt): "+
    hit.elevation.toFixed(2)+" m · "+(geo?
      "WGS84 "+geo.latitude.toFixed(7)+", "+geo.longitude.toFixed(7):
      "GPS-Position nicht verfügbar (CRS oder Rasterausdehnung ungeeignet)")+
    (slope===null?"":" · lokale DEM-Hangneigung "+slope.toFixed(1)+"° (ungeprüft)");
}
function terrainRefreshProfileOptions(){
  const select=$("terrain-profile-object"),old=select.value;
  select.replaceChildren();
  const empty=els("option","","Linie auswählen…");empty.value="";
  select.appendChild(empty);
  if(terrainGrid&&terrainGeo){
    for(const row of geoObjects){
      if(row.object.kind!=="line"||
         !terrainGeoPolyline(row.object,terrainGrid,terrainGeo))continue;
      const option=els("option","",row.object.name);
      option.value=row.id;
      select.appendChild(option);
    }
  }
  select.value=geoObjects.some(row=>row.id===old&&row.object.kind==="line"&&
    terrainGeoPolyline(row.object,terrainGrid,terrainGeo))?old:"";
  if(!select.value)terrainProfile=null;
  terrainDrawProfile(terrainProfile);
}
function terrainGenerateProfile(){
  const row=geoObjects.find(item=>item.id===$("terrain-profile-object").value);
  if(!row||!terrainGrid||!terrainGeo){
    $("terrain-profile-message").textContent="WGS84-Raster und vollständig enthaltene Geo-Linie auswählen.";
    return;
  }
  const profile=terrainPolylineProfile(row.object,terrainGrid,terrainGeo);
  if(!profile){
    $("terrain-profile-message").textContent="Profil nicht möglich: Linie außerhalb des Rasters.";
    return;
  }
  terrainProfile=profile;
  terrainDrawProfile(profile);
  $("terrain-profile-message").textContent="Profil "+row.object.name+
    " · "+profile.distance_m.toFixed(1)+" m · Höhen "+
    profile.min_m.toFixed(2)+"–"+profile.max_m.toFixed(2)+
    " m (interpolierte DEM-Werte, Höhenbezug unbekannt; keine Flugfreigabe).";
}
function terrainBindPointer(canvas){
  canvas.addEventListener("pointerdown",event=>{
    if(!terrainGrid||event.button>0)return;
    terrainDrag={canvas,pointerId:event.pointerId,x:event.clientX,y:event.clientY,
      startX:event.clientX,startY:event.clientY};
    if(canvas.setPointerCapture)canvas.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  canvas.addEventListener("pointermove",event=>{
    const drag=terrainDrag;
    if(!terrainGrid||!drag||drag.canvas!==canvas||drag.pointerId!==event.pointerId)return;
    const dx=event.clientX-drag.x,dy=event.clientY-drag.y;
    drag.x=event.clientX;drag.y=event.clientY;
    terrainView.azimuth=((terrainView.azimuth+dx*0.5+540)%360)-180;
    terrainView.tilt=terrainClamp(terrainView.tilt+dy*0.3,15,80);
    terrainSyncControls();
    terrainRedrawSoon();
    event.preventDefault();
  });
  const stop=event=>{
    if(terrainDrag&&terrainDrag.canvas===canvas&&
       terrainDrag.pointerId===event.pointerId){
      const distance=Math.hypot(event.clientX-terrainDrag.startX,
        event.clientY-terrainDrag.startY);
      if(event.type==="pointerup"&&distance<=4)terrainShowProbe(canvas,event);
      terrainDrag=null;
    }
  };
  canvas.addEventListener("pointerup",stop);
  canvas.addEventListener("pointercancel",stop);
  canvas.addEventListener("lostpointercapture",stop);
  canvas.addEventListener("wheel",event=>{
    if(!terrainGrid)return;
    terrainView.zoom=terrainClamp(terrainView.zoom*(event.deltaY>0?0.9:1.1),0.5,2.5);
    terrainSyncControls();
    terrainRedrawSoon();
    event.preventDefault();
  },{passive:false});
}
async function previewTerrain(){
  const loadSerial=++terrainLoadSerial;
  const file=$("terrain-file").files?.[0];
  if(!file)throw new Error("Zuerst DEM-GeoTIFF auswählen");
  if(file.size>8*1024*1024)throw new Error("GeoTIFF maximal 8 MiB");
  const r=await api("/api/v1/studio/terrain/geotiff",{
    method:"POST",headers:{"Content-Type":"image/tiff"},body:file});
  const data=await r.json();
  // An old upload must not overwrite a newly selected DEM in the viewer.
  if(loadSerial!==terrainLoadSerial)return;
  terrainGrid=data.grid;
  terrainGeo=data.geo||null;
  $("terrain-show-map").disabled=!terrainGeo;
  terrainDrawMapFootprint();
  terrainProfile=null;
  terrainRefreshProfileOptions();
  terrainDrawProfile(null);
  terrainUpdateSlopeInfo(terrainGrid);
  drawTerrainPreview(terrainGrid);
  $("terrain-georef-info").textContent=terrainGeo?
    "EPSG:4326 / WGS84 · georeferenzierte Rasterpunktmitten · Nordwest: "+
      terrainGeo.north_lat.toFixed(7)+", "+terrainGeo.west_lon.toFixed(7)+
      " · Vertikaler Höhenbezug unbekannt.":
    "Keine verifizierten WGS84-Rasterkoordinaten verfügbar (z. B. projiziertes CRS oder zu große Fläche). Geo-Overlays, Positionsabfrage und Profil deaktiviert.";
  $("terrain-export").disabled=false;
  $("terrain-open-large").disabled=false;
  $("terrain-large-message").textContent=data.overview.rows+" × "+data.overview.columns+
    " Zellen · "+data.overview.min_elevation_m+"–"+data.overview.max_elevation_m+
    " m (orthografische Visualisierung; keine Vermessungs-/Flugfreigabe).";
  $("terrain-message").textContent=data.overview.rows+" × "+data.overview.columns+
    " Zellen · Höhe "+data.overview.min_elevation_m+"–"+data.overview.max_elevation_m+
    " m. Interaktive schematische Höhenansicht, keine georeferenzierte 3D-Karte oder Flugfreigabe.";
}
async function exportTerrain(){
  if(!terrainGrid)throw new Error("Zuerst GeoTIFF auswerten");
  const r=await api("/api/v1/studio/terrain/export.stl",{
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(terrainGrid)});
  const blob=await r.blob(),url=URL.createObjectURL(blob),a=els("a");
  a.href=url;a.download="aeronexus-terrain.stl";document.body.appendChild(a);
  a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);
}
function connectStudioEvents(){
  if(studioSocket&&studioSocket.readyState<=1)return;
  if(location.protocol!=="https:"&&location.hostname!=="localhost"){
    $("event-status").textContent="Live-Ereignisse benötigen HTTPS.";return;
  }
  const scheme=location.protocol==="https:"?"wss:":"ws:";
  const ws=new WebSocket(scheme+"//"+location.host+"/api/v1/studio/events");
  studioSocket=ws;
  $("event-status").textContent="Verbinde mit lokalem Ereigniskanal…";
  ws.onopen=()=>{$("event-status").textContent="Lokaler Live-Ereigniskanal verbunden.";};
  ws.onmessage=event=>{
    let message;try{message=JSON.parse(event.data)}catch(_){return;}
    if(message?.type==="fleet_changed"&&!studioFleetLoading){
      studioFleetLoading=true;
      loadFleet().catch(()=>{}).finally(()=>{studioFleetLoading=false;});
    }
  };
  ws.onerror=()=>{$("event-status").textContent="Ereigniskanal nicht verfügbar (Pi-Konfiguration prüfen).";};
  ws.onclose=()=>{$("event-status").textContent="Ereigniskanal getrennt. Verbinden bei Bedarf erneut.";};
}
function wire(){
  document.querySelectorAll("nav button[data-tab]").forEach(el=>el.addEventListener("click",()=>switchTab(el.dataset.tab)));
  $("mission-list").addEventListener("change",e=>loadMission(e.target.value).catch(err=>notice(err.message,true)));
  $("new-mission").addEventListener("click",()=>newMission());
  $("undo-edit").addEventListener("click",undoEdit);
  $("redo-edit").addEventListener("click",redoEdit);
  for(const id of FORM_IDS){
    $(id).addEventListener("input",()=>{
      if(id==="mission-speed")updateRouteAnalysis();
      historyRecord("typing:"+id);
    });
    $(id).addEventListener("change",()=>historyRecord());
  }
  window.addEventListener("beforeunload",e=>{
    if(!editorDirty()&&geoDraft.length===0&&geoEditingId===null)return;
    e.preventDefault();
    e.returnValue="";
  });
  window.addEventListener("keydown",e=>{
    if(isTextEditing(e.target)||e.altKey||!(e.ctrlKey||e.metaKey))return;
    const key=String(e.key||"").toLowerCase();
    if(key==="z"||key==="y"){
      e.preventDefault();
      if(key==="y"||e.shiftKey)redoEdit();else undoEdit();
    }
  });
  $("save-mission").addEventListener("click",()=>saveMission().catch(err=>notice(err.message,true)));
  $("refresh-waylines").addEventListener("click",loadWaylines);
  $("pilot2-action-load").addEventListener("click",()=>loadPilot2ActionSummary());
  $("wayline-overview-open").addEventListener("click",()=>openCloudOverview().catch(err=>{
    $("wayline-state").className="status error";$("wayline-state").textContent=errorMessage(err);
  }));
  $("cloud-overview-map-open").addEventListener("click",()=>{
    if(!$("cloud-overview-panel").hidden){closeCloudOverview();return;}
    openCloudOverview().catch(err=>mapWarning("Cloud-Übersicht: "+errorMessage(err)));
  });
  $("cloud-overview-close").addEventListener("click",()=>closeCloudOverview());
  $("cloud-overview-expand").addEventListener("click",()=>setCloudOverviewMinimized(
    $("cloud-overview-panel").dataset.minimized!=="true"));
  $("map-tools-toggle").addEventListener("click",()=>setMapToolsExpanded(
    $("map-toolbar").dataset.compact==="true"));
  $("map-info-toggle").addEventListener("click",()=>setMapInfoExpanded(
    $("map-info").dataset.minimized==="true"));
  $("map-info-chip").addEventListener("click",()=>setMapInfoExpanded(
    $("map-info").dataset.minimized==="true"));
  $("map-focus-toggle").addEventListener("click",()=>setMapFocus(
    !document.body.classList.contains("map-focus-active")));
  setMapInfoExpanded(!window.matchMedia("(max-width:700px)").matches);
  setMapToolsExpanded(false);
  $("cloud-overview-fit").addEventListener("click",()=>fitCloudRoutes());
  $("wayline-search").addEventListener("input",()=>{waylinePage=1;renderWaylines();});
  $("wayline-source").addEventListener("change",()=>{waylinePage=1;renderWaylines();});
  $("clear-wayline-search").addEventListener("click",()=>{$("wayline-search").value="";waylinePage=1;renderWaylines();$("wayline-search").focus();});
  $("wayline-prev").addEventListener("click",()=>{waylinePage--;renderWaylines();});
  $("wayline-next").addEventListener("click",()=>{waylinePage++;renderWaylines();});
  $("delete-mission").addEventListener("click",()=>removeMission().catch(err=>notice(err.message,true)));
  $("close-route").addEventListener("change",e=>{
    mission.close_route=e.target.checked;
    redraw();historyRecord();
  });
  $("point-action-type").addEventListener("change",actionControls);
  $("mission-model").addEventListener("change",actionControls);
  $("point-action-add").addEventListener("click",addWaypointAction);
  $("export-mission").addEventListener("click",()=>exportMission().catch(err=>notice(err.message,true)));
  $("import-mission").addEventListener("click",()=>importMission().catch(err=>notice(err.message,true)));
  $("open-csv").addEventListener("click",openCsvImport);
  $("csv-close").addEventListener("click",()=>$("csv-dialog").close());
  $("csv-dialog").addEventListener("close",()=>{csvInvalidate();$("open-csv").focus();});
  for(const id of ["csv-file","csv-delimiter","csv-decimal"])
    $(id).addEventListener("change",()=>csvInvalidate());
  $("csv-check").addEventListener("click",previewCsv);
  $("csv-apply").addEventListener("click",applyCsv);
  $("csv-more").addEventListener("click",csvMoreRows);
  $("csv-template").addEventListener("click",downloadCsvTemplate);
  $("add-mode").addEventListener("click",()=>{
    if(geoDraw)setGeoMode(false);
    addMode=!addMode;$("add-mode").textContent=addMode?"Klickmodus beenden":"+ Auf Karte setzen";
    $("add-mode").classList.toggle("primary",addMode);
  });
  $("fit-mission").addEventListener("click",fitMission);$("map-fit").addEventListener("click",fitMission);
  $("map-zoom-in").addEventListener("click",()=>map?.zoomIn());$("map-zoom-out").addEventListener("click",()=>map?.zoomOut());
  $("map-layer").addEventListener("change",e=>setMapLayer(e.target.value));
  $("map-home").addEventListener("click",centerOnForst);
  $("wayline-preview-clear").addEventListener("click",clearCloudWaylinePreview);
  $("wayline-preview-fit").addEventListener("click",centerCloudWaylinePreview);
  $("pilot2-map-toggle").addEventListener("click",()=>togglePilot2MapLayer().catch(err=>mapWarning(errorMessage(err))));
  $("apply-point").addEventListener("click",()=>{
    const p=mission.waypoints[selected];if(!p)return;
    const lat=Number($("point-lat").value),lon=Number($("point-lon").value);
    if(!$("point-lat").value.trim()||!$("point-lon").value.trim()||
      !Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180||
      (lat===0&&lon===0)){notice("Ungültige WGS84-Koordinaten (0/0 ist kein GPS-Fix)",true);return;}
    mission.waypoints[selected]={...p,latitude:+lat.toFixed(7),longitude:+lon.toFixed(7),take_photo:$("point-photo").checked};
    redraw();historyRecord();
  });
  $("remove-point").addEventListener("click",()=>{
    if(selected<0)return;mission.waypoints.splice(selected,1);selected=-1;redraw();historyRecord();
  });
  $("insert-midpoint").addEventListener("click",insertMidpoint);
  $("copy-point").addEventListener("click",async()=>{
    const p=mission.waypoints[selected];if(!p)return;
    try{
      await navigator.clipboard.writeText(p.latitude.toFixed(7)+", "+p.longitude.toFixed(7));
      notice("WGS84-Koordinaten kopiert.");
    }catch(_){notice("Kopieren nicht möglich. Koordinaten im Editor markieren.",true);}
  });
  $("geo-draw").addEventListener("click",()=>setGeoMode(!geoDraw));
  $("geo-reset").addEventListener("click",()=>{
    if(geoDraft.length&&!window.confirm("Ungespeicherten Geo-Entwurf verwerfen?"))return;
    geoDraft=[];geoEditingId=null;setGeoMode(false);redrawGeo();
  });
  $("geo-undo-vertex").addEventListener("click",()=>{geoDraft.pop();redrawGeo();});
  $("geo-save").addEventListener("click",()=>saveGeoObject().catch(err=>$("geo-draft-status").textContent=err.message));
  $("geo-kind").addEventListener("change",redrawGeo);
  $("survey-generate").addEventListener("click",()=>surveyPreview().catch(err=>$("survey-message").textContent=err.message));
  $("geophoto-media").addEventListener("change",showGeoPhotoFields);
  $("geophoto-save").addEventListener("click",()=>saveGeoPhoto().catch(err=>$("geophoto-status").textContent=err.message));
  $("geophoto-show").addEventListener("click",showGeoPhotos);
  $("terrain-preview").addEventListener("click",()=>previewTerrain().catch(err=>$("terrain-message").textContent=err.message));
  $("terrain-export").addEventListener("click",()=>exportTerrain().catch(err=>$("terrain-message").textContent=err.message));
  $("terrain-file").addEventListener("change",()=>{
    terrainLoadSerial++;
    terrainGrid=null;
    terrainGeo=null;
    terrainDrawMapFootprint();
    terrainProfile=null;
    terrainRefreshProfileOptions();
    $("terrain-coordinate-probe").textContent="Noch kein Geländepunkt ausgewählt.";
    $("terrain-georef-info").textContent="Keine WGS84-Georeferenz geladen.";
    terrainUpdateSlopeInfo(null);
    $("terrain-profile-message").textContent="Noch kein Höhenprofil geladen.";
    $("terrain-export").disabled=true;
    $("terrain-open-large").disabled=true;
    $("terrain-show-map").disabled=true;
    $("terrain-large-message").textContent="Noch kein Höhenraster geladen. Bitte 3D-Vorschau starten.";
    drawTerrainPreview(null);
  });
  $("terrain-open-large").addEventListener("click",()=>switchTab("terrain-pane"));
  $("terrain-show-map").addEventListener("click",terrainShowOnMap);
  $("terrain-reset-view").addEventListener("click",terrainResetView);
  for(const key of ["azimuth","tilt","zoom","exaggeration","color","wire","slope","geo-overlay"]){
    $("terrain-"+key).addEventListener("input",terrainControlChanged);
    $("terrain-"+key).addEventListener("change",terrainControlChanged);
  }
  $("terrain-profile-generate").addEventListener("click",terrainGenerateProfile);
  terrainBindPointer($("terrain-canvas"));
  terrainBindPointer($("terrain-canvas-large"));
  terrainSyncControls();
  $("connect-events").addEventListener("click",connectStudioEvents);
  $("upload-media").addEventListener("click",()=>uploadMedia().catch(err=>$("media-notice").textContent=err.message));
  $("refresh-media").addEventListener("click",()=>loadMedia().catch(err=>$("media-notice").textContent=err.message));
  $("refresh-dji-media").addEventListener("click",()=>loadDjiMedia(true).catch(
    err=>$("dji-media-status").textContent=errorMessage(err)));
  $("dji-media-search").addEventListener("change",()=>loadDjiMedia(true).catch(
    err=>$("dji-media-status").textContent=errorMessage(err)));
  $("more-dji-media").addEventListener("click",()=>loadDjiMedia(false).catch(
    err=>$("dji-media-status").textContent=errorMessage(err)));
  $("media-search").addEventListener("input",()=>{displayMedia=20;renderMedia().catch(()=>{});});
  $("more-media").addEventListener("click",()=>{displayMedia+=20;renderMedia().catch(()=>{});});
  $("preview-close").addEventListener("click",closePreview);$("media-dialog").addEventListener("close",closePreview);
  $("refresh-fleet").addEventListener("click",()=>loadFleet().catch(err=>$("fleet-notice").textContent=err.message));
  $("pilot2-topology-refresh").addEventListener("click",loadPilot2Topology);
  $("show-fleet-map").addEventListener("click",()=>showFleetOnMap().catch(err=>notice(err.message,true)));
  getMap();redraw();historyReset();
}
wire();
loadWorkspace();
</script>
</body>
</html>"""


def render_studio() -> str:
    """The shell includes no credentials or mission content."""
    options = "".join(f'<option value="{escape(model, quote=True)}">{escape(MODEL_LABELS[model])}</option>'
                      for model in MODELS)
    return HTML.replace("__MISSION_MODEL_OPTIONS__", options)
