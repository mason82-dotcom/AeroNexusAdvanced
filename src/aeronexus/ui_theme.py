"""AeroNexus cockpit styling, independently authored for existing workspaces.

OpenDroneKit is a visual/workflow reference only; no upstream code or assets
are embedded. This layer owns shared chrome; module viewers own their content.
"""

COCKPIT_CSS = """
:root{--bg:#10151c;--pane:#171e28;--surface:#202b39;--ink:#eaf3ff;--muted:#a6b4c5;--sub:#a6b4c5;--line:#344151;--accent:#48a8f5}
body{background:var(--bg);color:var(--ink)}
body>header,main>header{background:#141b24;border-bottom:1px solid var(--line);padding:9px 14px;gap:12px}
header .brand,header .logo{font-size:16px;letter-spacing:0;font-weight:700}
header .brand small,header .logo small{font-size:10px;letter-spacing:.12em;color:var(--muted)}
nav.app-nav{gap:2px;font-size:13px}
nav.app-nav a,nav.app-nav summary{padding:8px 10px;border-radius:3px;font-weight:500}
nav.app-nav a:hover,nav.app-nav summary:hover{background:var(--surface)}
nav.app-nav a[aria-current="page"],nav.app-nav details[data-current] summary{background:#1d344b;border-color:transparent;border-bottom-color:var(--accent)}
nav.app-nav .app-nav-menu{background:var(--pane);border-color:var(--line);border-radius:3px}
button,input,select,textarea{border-radius:4px}
input,select,textarea{background:#111923;color:var(--ink);border-color:#425267}
button{border-color:#425267}
button:disabled{cursor:not-allowed}
.side,.panel,.media-card,.fleet-card,.wayline-card{background:var(--pane);border-color:var(--line)}
.panel,.media-card,.fleet-card,.wayline-card,.status,.studio-disclosure,.point-row{border-radius:4px}
.side h1{font-size:17px}.side h2,.panel h2{font-size:14px}
.side .note{line-height:1.45}
header .studio-tabs{padding-top:6px}
header .studio-tabs button{border-radius:3px;padding:7px 9px}
header .studio-tabs button.active{background:#1d344b;border-bottom:2px solid var(--accent)}
.side .button-row button,.side .editor-tools button{padding:8px 7px;font-size:12px}
.side .field-row{gap:8px}.side .studio-disclosure{padding:10px}
.side .route-option{padding:10px;border-radius:4px}
.side .route-option span{font-size:13px}
.side #point-editor{background:#111923;border-color:var(--line);border-radius:4px}
@media(max-width:700px){
 body>header,main>header{padding:10px}
 nav.app-nav a,nav.app-nav summary{min-height:42px;display:flex;align-items:center}
 header .studio-tabs button{min-height:40px}
 .side .button-row button,.side .editor-tools button{min-height:40px}
}
@media(forced-colors:active){nav.app-nav a[aria-current="page"],header .studio-tabs button.active{border:2px solid Highlight}}

/* Compact operations density: presentation only; data and device contracts stay untouched. */
:root{--compact-gap:8px;--compact-radius:6px;--compact-focus:#7ccaff;--compact-positive:#75e3bd}
html{scrollbar-color:#536579 var(--bg);scrollbar-width:thin}
html:focus-within{scroll-behavior:auto}
body{background:var(--bg);color:var(--ink)}
body>header,main>header{padding:7px 12px;gap:8px}
header .brand,header .logo{font-size:15px;line-height:1.2}
nav.app-nav{gap:3px;font-size:12px;align-items:center}
nav.app-nav a,nav.app-nav summary{padding:6px 9px;line-height:1.25;border-radius:5px}
nav.app-nav a[aria-current="page"],nav.app-nav details[data-current] summary{background:#1b3648;border:1px solid #497086;color:#f4fbff}
nav.app-nav .app-nav-menu{min-width:170px;padding:4px;box-shadow:0 8px 20px #0007}
:where(button,input,select,textarea){font-size:13px}
:where(button,select,input:not([type="checkbox"]):not([type="radio"]),textarea){padding:6px 9px}
:where(button,a,summary,input,select,textarea):focus-visible{outline:2px solid var(--compact-focus);outline-offset:2px}
.panel,.media-card,.fleet-card,.wayline-card{border-radius:var(--compact-radius)}
.panel{padding:10px;box-shadow:none}
.panel h2,.side h2{font-size:14px;line-height:1.3}
.panel h3,.side h3{margin-top:10px}
:where(.grid,.device-grid,.catalog-grid,.cockpit-modules,.wayline-grid,.metrics){gap:8px}
.side{padding:12px}
.side h1{font-size:16px}
.side h2{margin:12px 0 7px}
.side label{gap:4px;margin:6px 0}
.side .field-row{gap:6px}
.side .button-row{margin:8px 0;gap:5px}
.side .button-row button,.side .editor-tools button{padding:6px 7px}
.side .studio-disclosure{padding:8px}
.side .route-option,.wayline-card{padding:8px}
.status{padding:8px 10px;margin:8px 0}
.layout:has(.side){grid-template-columns:minmax(280px,310px) minmax(0,1fr)}
body:has(#operations-map) .layout,body:has(#thermal-map) .layout{
 gap:8px;padding:8px;grid-template-columns:minmax(208px,255px) minmax(320px,1fr) minmax(240px,300px)
}
body:has(#operations-map) .column,body:has(#thermal-map) .column{gap:8px}
body:has(#operations-map) .kpi-grid{gap:5px;margin:7px 0}
body:has(#operations-map) .kpi{padding:6px}
body:has(#operations-map) .kpi strong{font-size:18px;line-height:1.2}
body:has(#operations-map) .list-card,body:has(#operations-map) .controller-card{padding:7px;margin:5px 0;border-radius:5px}
body:has(#operations-map) .cockpit>div{padding:7px;border-radius:5px}
body:has(#operations-map) .cockpit>div b{font-size:15px;margin-top:2px}
body:has(#operations-map) .cockpit-summary{gap:5px;margin-bottom:6px}
body:has(#thermal-map) .item,body:has(#thermal-map) .flight{padding:6px;margin:4px 0}
body:has(#thermal-map) .stats{gap:4px}
body:has(#thermal-map) .stat{padding:5px}
body:has(#ms-map) .panel{padding:10px}
body:has(#map[role="region"]) .layout{gap:8px;padding:8px;grid-template-columns:minmax(240px,280px) minmax(0,1fr)}
body:has(#map[role="region"]) .item{margin:4px 0;padding:7px}
main:has(>header nav.app-nav){max-width:1680px}
main:has(>header nav.app-nav)>header{margin-bottom:8px}
main:has(>header nav.app-nav)>header h1{font-size:clamp(19px,2.5vw,25px);line-height:1.2}
main:has(>header nav.app-nav)>.card{padding:11px;margin:9px 0;border-radius:6px;box-shadow:none}
main:has(>header nav.app-nav)>.card .metrics{gap:7px}
main:has(>header nav.app-nav)>.card .metric{padding:8px}
main:has(>header nav.app-nav)>.card .metric b{font-size:18px;line-height:1.25}
main:has(>header nav.app-nav)>.card .controls{gap:7px;margin:8px 0}
main:has(>header nav.app-nav)>.card td,main:has(>header nav.app-nav)>.card th{padding:7px 8px}
main:has(>header nav.app-nav)>.card .chips{gap:4px;margin:6px 0}
main:has(>header nav.app-nav)>.card .chip{padding:5px 9px}
body:has(#cockpit) {padding:10px}
body:has(#cockpit) main{max-width:1680px}
body:has(#cockpit) .grid[aria-label="Flottenkennzahlen"]{gap:7px;margin-top:8px}
body:has(#cockpit) .metric{padding:8px 10px;border-radius:6px}
body:has(#cockpit) .metric b{font-size:20px;margin-top:3px;line-height:1.2;font-variant-numeric:tabular-nums}
body:has(#cockpit) .metric span{font-size:11px}
body:has(#cockpit) #poll-health{margin-top:7px}
#cockpit.cockpit-shell{margin:10px 0 12px;padding:12px;border-radius:7px;background:#122333;box-shadow:none}
#cockpit .cockpit-top{gap:8px;align-items:center}
#cockpit .cockpit-top h2{font-size:20px;margin:1px 0 3px}
#cockpit .cockpit-caption{line-height:1.35}
#cockpit .cockpit-live{padding:5px 9px}
#cockpit .cockpit-toolbar{gap:7px;margin:9px 0;align-items:end}
#cockpit .cockpit-toolbar label{min-width:150px;gap:3px}
#cockpit .cockpit-toolbar select,#cockpit .cockpit-toolbar button{min-height:36px;padding:6px 9px}
#cockpit .cockpit-banner{padding:6px 9px;margin:6px 0}
#cockpit .cockpit-hero{gap:6px;margin:9px 0}
#cockpit .cockpit-gauge{padding:8px;border-radius:6px}
#cockpit .cockpit-gauge strong{margin:4px 0 1px;font-size:clamp(17px,1.8vw,23px)}
#cockpit .cockpit-layout{gap:8px}
#cockpit .cockpit-panel{padding:9px;border-radius:6px}
#cockpit .cockpit-panel h3{margin-bottom:7px;font-size:13px}
#cockpit .cockpit-items{gap:5px}
#cockpit .cockpit-item{padding:6px;border-radius:5px}
#cockpit .cockpit-item b{margin-top:2px;font-size:13px}
#cockpit .cockpit-item small{margin-top:2px}
#cockpit .cockpit-pills{gap:5px;margin:7px 0}
#cockpit .cockpit-pill{padding:3px 6px;border-radius:5px}
#cockpit .cockpit-modules{gap:8px;margin-top:8px}
#cockpit .cockpit-track{height:170px}
#cockpit .cockpit-chart{height:62px}
#cockpit .cockpit-chart-wrap{gap:6px}
#cockpit .cockpit-fieldlist{gap:4px;max-height:230px}
#cockpit .cockpit-fieldrow{padding:5px 2px}
#cockpit .cockpit-field-focus{gap:5px;margin:8px 0}
#cockpit .cockpit-focus-row{padding:7px;border-radius:5px;gap:3px}
#cockpit .cockpit-legend{margin-top:9px}
body:has(#cockpit) .legacy-status{margin:9px 0}
body:has(#cockpit) .legacy-status>summary{padding:8px 10px;border-radius:5px;font-size:13px}
body:has(#cockpit) .device-grid{gap:7px;margin:8px 0}
body:has(#cockpit) .device-card{padding:9px;border-radius:6px}
body:has(#cockpit) .device-values{gap:5px}
body:has(#cockpit) .device-value{padding:6px}
body:has(#cockpit) .device-battery{margin:7px 0}
body:has(#cockpit) .hms-entry{padding:7px}
@media(min-width:1400px){
 body:has(#cockpit) .grid[aria-label="Flottenkennzahlen"]{grid-template-columns:repeat(7,minmax(0,1fr))}
}
@media(max-width:1150px) and (min-width:761px){
 body:has(#operations-map) .layout,body:has(#thermal-map) .layout{grid-template-columns:minmax(205px,245px) minmax(0,1fr)}
 body:has(#operations-map) .right,body:has(#thermal-map) .right{grid-column:1/-1}
 .layout:has(.side){grid-template-columns:minmax(265px,300px) minmax(0,1fr)}
}
@media(max-width:900px){
 body:has(#operations-map) .layout,body:has(#thermal-map) .layout,body:has(#map[role="region"]) .layout{grid-template-columns:minmax(0,1fr)}
}
@media(max-width:700px){
 body>header,main>header{padding:8px}
 nav.app-nav{gap:3px;width:100%}
 nav.app-nav a,nav.app-nav summary{min-height:40px;display:flex;align-items:center;padding:8px 9px}
 :where(button,select,input:not([type="checkbox"]):not([type="radio"])){min-height:36px}
 .layout:has(.side){display:block;min-height:0;height:auto}
 .side{padding:10px}
 body:has(#cockpit) {padding:8px}
 #cockpit.cockpit-shell{padding:9px}
 #cockpit .cockpit-toolbar{align-items:stretch}
 #cockpit .cockpit-toolbar select,#cockpit .cockpit-toolbar button{min-height:40px}
 #cockpit .cockpit-hero{grid-template-columns:repeat(2,minmax(0,1fr))}
 #cockpit .cockpit-layout,#cockpit .cockpit-modules{grid-template-columns:minmax(0,1fr)}
 main:has(>header nav.app-nav)>.card{padding:9px}
}
@media(prefers-reduced-motion:reduce){nav.app-nav a,nav.app-nav summary{transition:none}}
"""
