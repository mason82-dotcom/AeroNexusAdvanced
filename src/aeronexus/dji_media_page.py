"""Standalone read-only DJI MinIO media index browser.

Never embeds MinIO credentials, presigned links or physical object paths.
Every list request is made against the local, access-controlled FastAPI API.
"""

HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="dark">
<title>AeroNexusAdvanced · DJI Medienindex</title>
<style>
:root{font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;color-scheme:dark;
  background:#0b1423;color:#e6f1ff}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(circle at top right,#1b3450,#0b1423 58%);min-height:100vh}
main{max-width:1260px;margin:auto;padding:22px}
header{display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:18px}
a{color:#a0d8ff}
nav{display:flex;gap:18px;flex-wrap:wrap}
.eyebrow{font-size:11px;letter-spacing:.16em;color:#80bff4;text-transform:uppercase}
h1{font-size:clamp(23px,4vw,34px);margin:3px 0}
h2{font-size:17px;margin:0 0 10px}
p{color:#bbcee4}
.card{background:#12243b;border:1px solid #3c5470;border-radius:13px;padding:17px;margin:14px 0}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.metric{background:#0e2035;border:1px solid #344d66;border-radius:9px;padding:12px}
.metric b{display:block;font-size:22px;overflow-wrap:anywhere}
.metric span{display:block;color:#aac3da;font-size:12px}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:end;margin:14px 0}
label{font-size:12px;color:#bbcee4;display:grid;gap:5px}
select,input,button{font:inherit;color:#ebf6ff;background:#1a3551;border:1px solid #52708c;
  border-radius:8px;padding:9px 11px}
input{min-width:min(100%,280px)}
button{cursor:pointer}button:disabled{opacity:.5;cursor:not-allowed}
:focus-visible{outline:2px solid #87d6ff;outline-offset:2px}
.scroller{overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:690px}
td,th{padding:12px 10px;text-align:left;border-bottom:1px solid #344b64;vertical-align:top}
th{font-size:12px;color:#bcd2eb}
td:first-child{max-width:430px;overflow-wrap:anywhere}
.sub{color:#a8c0d8;font-size:12px}
.tag{font-size:12px;padding:3px 7px;border:1px solid #4e6a84;border-radius:16px;white-space:nowrap}
.ok{color:#83e5ba}.warn{color:#f1ca82}.error{color:#ffb0bb}
.pager{display:flex;gap:12px;align-items:center;justify-content:end;padding-top:15px}
footer{color:#94adc7;font-size:12px;padding:10px 0}
</style>
</head>
<body>
<main>
<header>
<div><div class="eyebrow">AERONEXUS ADVANCED · PHASE 20</div>
<h1>DJI-MinIO-Medienindex</h1></div>
<nav aria-label="Bereiche"><a href="/operations">Operations Center</a>
<a href="/status">Live-Status</a><a href="/studio">Mission Studio</a></nav>
</header>
<p>Schreibgeschützter Index der DJI-Pilot-2-Uploads. Originale verbleiben in MinIO.
Aufnahmezeit, GPS-EXIF, Wärmebild- und Multispektraleigenschaften werden hier noch
nicht aus Datei-Inhalten ausgewertet. „Upload“ bezeichnet den Zeitstempel des Objektspeichers.</p>
<section class="card">
<div class="metrics">
<div class="metric"><span>Indexzustand</span><b id="index-state">Lade…</b></div>
<div class="metric"><span>Medienobjekte</span><b id="index-total">–</b></div>
<div class="metric"><span>Gesamtvolumen</span><b id="index-bytes">–</b></div>
<div class="metric"><span>Letzter Scan</span><b id="index-scanned" style="font-size:15px">–</b></div>
</div>
<div class="sub" id="kind-counts" aria-live="polite">Metadaten werden geladen…</div>
</section>
<section class="card">
<div class="eyebrow">MinIO · nur lesen</div>
<h2>Fotos, RAW, Videos und Begleitdateien</h2>
<div class="controls">
<label>Medientyp
<select id="kind">
<option value="">Alle</option>
<option value="image">Foto / TIFF</option>
<option value="raw">RAW / DNG</option>
<option value="video">Video</option>
<option value="audio">Audio</option>
<option value="sidecar">Begleitdatei</option>
</select></label>
<label>Dateiname
<input id="search" type="search" maxlength="200" placeholder="Dateiname suchen">
</label>
<button id="filter" type="button">Filtern</button>
<button id="refresh" type="button">Aktualisieren</button>
</div>
<div id="result-message" class="sub" role="status" aria-live="polite">Lade Medienliste…</div>
<div class="scroller"><table>
<thead><tr><th>Dateiname</th><th>Art</th><th>Größe</th><th>Upload (MinIO)</th></tr></thead>
<tbody id="media-rows"></tbody>
</table></div>
<div class="pager">
<button id="previous" type="button">Zurück</button>
<span id="page">–</span>
<button id="next" type="button">Weiter</button>
</div>
</section>
<footer>Der Index enthält nur Metadaten. Diese Ansicht lädt keine Medienbytes,
veröffentlicht keine Objektschlüssel und führt keine Schreiboperationen aus.</footer>
</main>
<script>
"use strict";
const $=id=>document.getElementById(id);
let offset=0,total=0,busy=false;
const limit=50;
function fmtBytes(n){
  if(typeof n!=="number"||!Number.isFinite(n)||n<0)return "–";
  if(n<1024)return n+" B";
  const units=["KiB","MiB","GiB","TiB"];
  let v=n,i=-1;
  do{v/=1024;i++;}while(v>=1024&&i<units.length-1);
  return v.toFixed(1)+" "+units[i];
}
function fmtTime(value){
  const ms=typeof value==="string"?Date.parse(value):NaN;
  return Number.isFinite(ms)?new Date(ms).toLocaleString("de-DE"):"Nicht übermittelt";
}
function labelKind(value){
  return {image:"Foto / TIFF",raw:"RAW / DNG",video:"Video",
    audio:"Audio",sidecar:"Begleitdatei"}[value]||"Sonstige";
}
async function getJSON(url){
  const res=await fetch(url,{cache:"no-store"});
  if(!res.ok)throw new Error("HTTP "+res.status);
  return res.json();
}
function td(row,value){
  const cell=document.createElement("td");
  cell.textContent=String(value??"–");row.appendChild(cell);
  return cell;
}
async function refresh(){
  if(busy)return;
  busy=true;$("refresh").disabled=true;$("filter").disabled=true;
  try{
    const params=new URLSearchParams({limit:String(limit),offset:String(offset)});
    if($("kind").value)params.set("kind",$("kind").value);
    if($("search").value.trim())params.set("q",$("search").value.trim());
    const [summary,data]=await Promise.all([
      getJSON("/api/v1/dji/media/summary"),
      getJSON("/api/v1/dji/media?"+params.toString())
    ]);
    $("index-state").textContent=summary.state==="ready"?"Bereit":"Noch nicht indiziert";
    $("index-state").className=summary.state==="ready"?"ok":"warn";
    $("index-total").textContent=String(summary.total??0);
    $("index-bytes").textContent=fmtBytes(summary.total_bytes);
    $("index-scanned").textContent=fmtTime(summary.scanned_at);
    $("kind-counts").textContent=Object.entries(summary.kinds||{}).map(
      ([kind,count])=>labelKind(kind)+": "+count).join(" · ")||"Keine Mediendateien indiziert";
    total=Number(data.total)||0;
    const rows=$("media-rows");rows.replaceChildren();
    for(const item of data.items||[]){
      const row=document.createElement("tr");
      td(row,item.name);
      td(row,labelKind(item.kind));
      td(row,fmtBytes(item.size_bytes));
      td(row,fmtTime(item.uploaded_at));
      rows.appendChild(row);
    }
    $("result-message").textContent=summary.state!=="ready"?
      "Noch kein MinIO-Index. Bitte Scan auf dem Pi starten.":
      total?total+" Dateien gefunden. Nur Metadaten, keine Downloads.":
      "Keine Dateien für diese Filter gefunden.";
    $("page").textContent=total?(offset+1)+"–"+Math.min(offset+limit,total)+" / "+total:"0 / 0";
    $("previous").disabled=offset===0;
    $("next").disabled=offset+limit>=total;
  }catch(error){
    $("result-message").textContent="Medienindex nicht erreichbar: "+error.message;
    $("result-message").className="error";
  }finally{
    busy=false;$("refresh").disabled=false;$("filter").disabled=false;
  }
}
$("filter").addEventListener("click",()=>{offset=0;refresh();});
$("refresh").addEventListener("click",refresh);
$("search").addEventListener("keydown",event=>{
  if(event.key==="Enter"){offset=0;refresh();}
});
$("previous").addEventListener("click",()=>{offset=Math.max(0,offset-limit);refresh();});
$("next").addEventListener("click",()=>{if(offset+limit<total){offset+=limit;refresh();}});
refresh();
window.setInterval(refresh,60000);
</script>
</body></html>"""


def render_dji_media_page() -> str:
    return HTML
