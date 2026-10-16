"""Desktop-first Chrome mission and media studio.

Static HTML shell; direct trusted-HTTPS-LAN workspace access with no token
prompt. No flight commands, DJI upload or automatic geolocation sharing.
"""


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
.badge{border-radius:999px;border:1px solid #3c5875;color:#a9cbea;padding:3px 8px;font-size:11px}
#map{height:100%;min-height:600px;background:#192837}
.map-bar{position:absolute;z-index:500;top:16px;left:16px;right:16px;display:flex;gap:7px;align-items:center;flex-wrap:wrap;pointer-events:none}
.map-bar>*{pointer-events:auto;box-shadow:0 5px 20px #0006}.map-bar button,.map-bar select{background:#162b44;border:1px solid #466a8c}
.map-bar select{width:auto;max-width:160px}
.map-info{position:absolute;z-index:500;bottom:34px;left:12px;max-width:min(480px,80%);padding:9px 12px;border-radius:9px;background:#101d2ce8;color:#dceaff;font-size:12px;pointer-events:none}
.map-info.warning{border:1px solid #a87548;color:#ffe3b0;background:#34251de8}
.point-row{display:grid;grid-template-columns:30px minmax(0,1fr) auto;gap:8px;align-items:center;padding:9px 7px;border-radius:9px;border:1px solid #314961;margin:7px 0;background:#16263d}
.point-row.selected{border-color:#53acf3;background:#1b3954}
.point-index{border-radius:50%;background:#297cb2;color:#fff;width:27px;height:27px;display:grid;place-items:center;font-weight:700}
.point-row small{color:#adc2da;display:block;margin-top:4px}.point-row button{padding:5px 8px}
#point-list{max-height:380px;overflow-y:auto}
#point-editor{border:1px solid #385270;border-radius:11px;padding:12px;margin-top:10px}
#point-editor[hidden],#mission-panel[hidden],#media-panel[hidden],#fleet-panel[hidden],#geo-panel[hidden]{display:none}
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
#terrain-canvas{display:block;width:100%;height:auto;background:#0d2233;border-radius:9px;border:1px solid #39516c}
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
@media(max-width:700px){.auth-message{text-align:left}.layout{display:block;height:auto}.side{max-height:none}.content{height:65vh;min-height:440px}.pane-inner{padding:16px}#map{min-height:440px}.auth{min-width:100%;justify-content:stretch}header{padding:11px}.map-bar{top:8px;left:8px;right:8px}}
</style>
</head>
<body>
<header>
<div class="brand"><small>AERONEXUS ADVANCED</small>Mission Studio</div>
<nav aria-label="Arbeitsbereiche">
<button class="active" data-tab="map-pane">Karte & Missionen</button>
<button data-tab="geo-pane">Geo &amp; Gelände</button>
<button data-tab="media-pane">Medienbibliothek</button>
<button data-tab="fleet-pane">Flottenstatus</button>
<a href="/operations" style="color:#9edaff;padding:9px;text-decoration:none">Operations Center ↗</a>
<a href="/status" style="color:#9edaff;padding:9px;text-decoration:none">Live-Dashboard ↗</a>
</nav>
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
<label>Fluggerät<select id="mission-model"><option value="matrice4t">Matrice 4T</option><option value="matrice4e">Matrice 4E</option></select></label>
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
<div class="button-row"><button id="apply-point">Übernehmen</button><button id="remove-point" class="danger">Entfernen</button></div>
<div class="button-row"><button id="insert-midpoint">Zwischenpunkt danach</button><button id="copy-point">WGS84 kopieren</button></div>
</div>
<hr>
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
<canvas id="terrain-canvas" width="320" height="210" role="img" aria-label="Lokale vereinfachte perspektivische Höhenraster-Vorschau"></canvas>
<div id="terrain-message" class="note" role="status">Lokales GDAL erforderlich. Höhenmodell nur Visualisierung und 3D-Modell – nicht zur Flugfreigabe.</div>
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
<div class="map-bar">
<select id="map-layer" aria-label="Kartenstil"><option value="satellite" selected>Satellit (Esri)</option><option value="street">Straßenkarte (OSM)</option></select>
<button id="map-zoom-in">+</button><button id="map-zoom-out">−</button><button id="map-home" title="Karte auf 76694 Forst (Baden) zurücksetzen">76694 Forst</button><button id="map-fit">Mission zentrieren</button>
</div>
<div class="map-info" id="map-info" role="status" aria-live="polite">Startpunkt: 76694 Forst (Baden). Satellitenkarte: © Esri und Datenanbieter; Straßenkarte: © OpenStreetMap-Mitwirkende. Kartenkacheln extern, Missionen bleiben lokal auf dem Pi.</div>
</section>
<section class="pane" id="media-pane">
<div class="pane-inner">
<div class="page-head"><div><h1>Medienbibliothek</h1><p class="muted">Private Dateien auf deinem Raspberry Pi · Fotos & Videos</p></div>
<div class="filters"><input type="search" id="media-search" placeholder="Medien suchen…">
<button id="refresh-media">Aktualisieren</button></div></div>
<div class="gallery" id="gallery"><div class="empty">Lokale Medienbibliothek wird geladen…</div></div>
<div class="button-row"><button id="more-media" hidden>Weitere Medien anzeigen</button></div>
<footer>Vorschaubilder werden mit deinem Token geladen und nur als temporäre Browser-Objekte angezeigt. Kein externer Mediendienst.</footer>
</div>
</section>
<section class="pane" id="fleet-pane">
<div class="pane-inner">
<div class="page-head"><div><h1>Flottenstatus</h1><p class="muted">Matrice 4T und weitere DJI-Geräte · Echtzeitstatus aus FlightHub 2</p></div></div>
<div id="fleet-grid" class="fleet-grid"><div class="empty">Lokale Flottendaten werden geladen…</div></div>
</div>
</section>
</main>
</div>
<dialog id="media-dialog"><div class="flex between"><strong id="preview-name">Vorschau</strong><button id="preview-close">Schließen</button></div><div id="preview-content" style="margin-top:15px"></div></dialog>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
"use strict";
const $=id=>document.getElementById(id);
const els=(tag,cls,text)=>{const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=String(text);return el};
const EMPTY=()=>({name:"Neue Wegpunktmission",description:"",drone_model:"matrice4t",altitude_m:50,speed_mps:5,takeoff_security_height_m:20,rth_height_m:60,finish_action:"goHome",close_route:false,waypoints:[]});
let mission=EMPTY(),missionId=null,selected=-1,addMode=false,epoch=0,knownMissions=[],knownMedia=[],displayMedia=20,mediaUrls=[],previewUrl=null;
const FORM_IDS=["mission-name","mission-description","mission-model","mission-altitude",
  "mission-speed","mission-takeoff","mission-rth","mission-finish"];
const HISTORY_LIMIT=60;
let editHistory=[],editIndex=-1,editGroup=null,cleanSnapshot=null;
// Fixed initial view of Forst (Baden), postal code 76694, approximate town centre.
// Loading other saved missions does not modify this default for the next page load.
const HOME_VIEW=Object.freeze({label:"76694 Forst (Baden)",latitude:49.1533,longitude:8.58417,zoom:15});
let map=null,lines=null,waypointsLayer=null,deviceLayer=null,geoLayer=null,surveyLayer=null,photoLayer=null,mapTile=null,mapTiles={},streetTileErrors=0;
let geoObjects=[],geoDraft=[],geoDraw=false,geoEditingId=null,terrainGrid=null,studioSocket=null,studioFleetLoading=false;
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
  mapTiles.satellite=L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",{
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
  map.on("click",event=>{
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
function mapWarning(text){
  const banner=$("map-info");
  banner.textContent=text;
  banner.classList.add("warning");
}
function setMapLayer(kind){
  if(!map||!mapTiles[kind])return;
  if(mapTile)map.removeLayer(mapTile);
  streetTileErrors=0;
  mapTile=mapTiles[kind].addTo(map);
  $("map-layer").value=kind;
  const banner=$("map-info");
  banner.classList.remove("warning");
  banner.textContent=kind==="satellite"
    ?"Startpunkt: 76694 Forst (Baden) · Satellitenbilder © Esri und Datenanbieter. Es werden ausschließlich sichtbare Kartenkacheln geladen."
    :"Startpunkt: 76694 Forst (Baden) · Straßenkarte © OpenStreetMap-Mitwirkende. Nur die Seitenherkunft wird an den Kartenserver übertragen.";
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
  if(point){$("edit-index").textContent=selected+1;$("point-lat").value=point.latitude;$("point-lon").value=point.longitude;$("point-photo").checked=point.take_photo;}
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
function switchTab(id){
  document.querySelectorAll(".pane").forEach(el=>el.classList.toggle("active",el.id===id));
  document.querySelectorAll("nav button[data-tab]").forEach(el=>el.classList.toggle("active",el.dataset.tab===id));
  ["mission-panel","geo-panel","media-panel","fleet-panel"].forEach((key,i)=>$(key).hidden=(["map-pane","geo-pane","media-pane","fleet-pane"][i]!==id));
  const mapVisible=(id==="map-pane"||id==="geo-pane");
  $("map-pane").classList.toggle("active",mapVisible);
  if(mapVisible&&map)setTimeout(()=>map.invalidateSize(),80);
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
  await Promise.allSettled([loadMedia(),loadFleet(),loadGeoObjects()]);
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
function drawTerrainPreview(grid){
  const cv=$("terrain-canvas"),ctx=cv.getContext("2d");
  if(!ctx)return;
  const heights=grid.heights_m,h=heights.length,w=heights[0].length;
  ctx.clearRect(0,0,cv.width,cv.height);ctx.fillStyle="#0d2233";ctx.fillRect(0,0,cv.width,cv.height);
  const zmin=Math.min(...heights.flat()),zmax=Math.max(...heights.flat());
  const coords=(r,c)=>{
    const depth=(zmax===zmin?0:(heights[r][c]-zmin)/(zmax-zmin));
    return [160+(c/(w-1)-r/(h-1))*105,
      135+(c/(w-1)+r/(h-1)-1)*44-depth*62];
  };
  ctx.strokeStyle="#8ed7b8";ctx.lineWidth=1;
  for(let r=0;r<h;r+=Math.max(1,Math.floor(h/16))){
    ctx.beginPath();for(let c=0;c<w;c++){const p=coords(r,c);c?ctx.lineTo(...p):ctx.moveTo(...p);}ctx.stroke();
  }
  for(let c=0;c<w;c+=Math.max(1,Math.floor(w/16))){
    ctx.beginPath();for(let r=0;r<h;r++){const p=coords(r,c);r?ctx.lineTo(...p):ctx.moveTo(...p);}ctx.stroke();
  }
}
async function previewTerrain(){
  const file=$("terrain-file").files?.[0];
  if(!file)throw new Error("Zuerst DEM-GeoTIFF auswählen");
  if(file.size>8*1024*1024)throw new Error("GeoTIFF maximal 8 MiB");
  const r=await api("/api/v1/studio/terrain/geotiff",{
    method:"POST",headers:{"Content-Type":"image/tiff"},body:file});
  const data=await r.json();terrainGrid=data.grid;
  drawTerrainPreview(terrainGrid);$("terrain-export").disabled=false;
  $("terrain-message").textContent=data.overview.rows+" × "+data.overview.columns+
    " Zellen · Höhe "+data.overview.min_elevation_m+"–"+data.overview.max_elevation_m+
    " m. Schematische lokale Höhenvorschau, kein tatsächliches 3D-Kartenmodell oder Flugfreigabe.";
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
  $("delete-mission").addEventListener("click",()=>removeMission().catch(err=>notice(err.message,true)));
  $("close-route").addEventListener("change",e=>{
    mission.close_route=e.target.checked;
    redraw();historyRecord();
  });
  $("export-mission").addEventListener("click",()=>exportMission().catch(err=>notice(err.message,true)));
  $("import-mission").addEventListener("click",()=>importMission().catch(err=>notice(err.message,true)));
  $("add-mode").addEventListener("click",()=>{
    if(geoDraw)setGeoMode(false);
    addMode=!addMode;$("add-mode").textContent=addMode?"Klickmodus beenden":"+ Auf Karte setzen";
    $("add-mode").classList.toggle("primary",addMode);
  });
  $("fit-mission").addEventListener("click",fitMission);$("map-fit").addEventListener("click",fitMission);
  $("map-zoom-in").addEventListener("click",()=>map?.zoomIn());$("map-zoom-out").addEventListener("click",()=>map?.zoomOut());
  $("map-layer").addEventListener("change",e=>setMapLayer(e.target.value));
  $("map-home").addEventListener("click",centerOnForst);
  $("apply-point").addEventListener("click",()=>{
    const p=mission.waypoints[selected];if(!p)return;
    const lat=Number($("point-lat").value),lon=Number($("point-lon").value);
    if(!$("point-lat").value.trim()||!$("point-lon").value.trim()||
      !Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180||
      (lat===0&&lon===0)){notice("Ungültige WGS84-Koordinaten (0/0 ist kein GPS-Fix)",true);return;}
    mission.waypoints[selected]={latitude:+lat.toFixed(7),longitude:+lon.toFixed(7),take_photo:$("point-photo").checked};
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
  $("terrain-file").addEventListener("change",()=>{terrainGrid=null;$("terrain-export").disabled=true;});
  $("connect-events").addEventListener("click",connectStudioEvents);
  $("upload-media").addEventListener("click",()=>uploadMedia().catch(err=>$("media-notice").textContent=err.message));
  $("refresh-media").addEventListener("click",()=>loadMedia().catch(err=>$("media-notice").textContent=err.message));
  $("media-search").addEventListener("input",()=>{displayMedia=20;renderMedia().catch(()=>{});});
  $("more-media").addEventListener("click",()=>{displayMedia+=20;renderMedia().catch(()=>{});});
  $("preview-close").addEventListener("click",closePreview);$("media-dialog").addEventListener("close",closePreview);
  $("refresh-fleet").addEventListener("click",()=>loadFleet().catch(err=>$("fleet-notice").textContent=err.message));
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
    return HTML
