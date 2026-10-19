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
"""
