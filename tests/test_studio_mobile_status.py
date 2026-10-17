"""Mobile Cloud-Wayline status is tappable and does not overlap attribution."""
import shutil
import subprocess

import pytest

from aeronexus.studio_page import render_studio


def test_mobile_cloud_map_hint_is_expandable_and_above_leaflet_attribution():
    page = render_studio()
    assert 'id="map-info-chip" type="button" aria-expanded="false"' in page
    assert 'id="map-info-detail"' in page
    assert 'id="map-info" role="status"' in page
    assert '#map-info[data-minimized="true"] #map-info-detail{display:none}' in page
    assert '#map-info-detail[hidden]{display:none}' in page
    assert '#map-info-chip{display:block;width:100%;' in page
    assert 'body.map-focus-active .map-info{bottom:calc(39px + env(safe-area-inset-bottom))}' in page
    assert 'bottom:calc(39px + env(safe-area-inset-bottom))' in page
    assert 'addEventListener("click",()=>setMapInfoExpanded(' in page
    assert 'function mapStatusSummary(text)' in page
    assert 'function mapInfoMessage(text,warning=false)' in page
    assert 'banner.textContent=text;' not in page
    assert 'banner.classList.toggle("warning",warning)' in page


def test_mobile_map_hint_preserves_full_route_message_and_toggles_details():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    page = render_studio()
    status_code = page[page.index("function mapStatusSummary(text)"):
                       page.index("function togglePilot2MapLayer()")]
    expand_code = page[page.index("function setMapInfoExpanded(expanded)"):
                       page.index("function refreshMobileMapSize()")]
    program = r"""
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(0,'utf8');
const elements=new Map();
const $=id=>{
 if(!elements.has(id))elements.set(id,{
   id,dataset:{minimized:"true"},textContent:"",hidden:false,attrs:{},
   classList:{classes:new Set(),toggle(name,on){
      if(on)this.classes.add(name);else this.classes.delete(name);
   },contains(name){return this.classes.has(name)}},
   setAttribute(key,val){this.attrs[key]=val}
 });
 return elements.get(id);
};
const first=source.slice(0,source.indexOf('function setMapInfoExpanded(expanded)'));
const second=source.slice(source.indexOf('function setMapInfoExpanded(expanded)'));
const controller=new Function('$',first+second+
 '\nreturn {mapInfoMessage,setMapInfoExpanded,mapStatusSummary};')($);
const name='<img src=x onerror=alert(1)> Kapelle1';
const full='Schreibgeschützte Cloud-Vorschau: '+name+
 ' · 2 Geometrie(n) aus waylines.wpml. Keine Bearbeitung, keine Flugfreigabe.';
controller.mapInfoMessage(full,true);
assert.equal($('map-info-detail').textContent,full);
assert.equal($('map-info').classList.contains('warning'),true);
assert.match($('map-info-chip').textContent,/Cloud-Vorschau:/);
assert.ok($('map-info-chip').textContent.includes(name));
assert.ok(!$('map-info-chip').textContent.includes('Keine Flugfreigabe'));
controller.setMapInfoExpanded(false);
assert.equal($('map-info-detail').hidden,true);
assert.equal($('map-info').dataset.minimized,'true');
assert.equal($('map-info-chip').attrs['aria-expanded'],'false');
assert.equal($('map-info-toggle').attrs['aria-expanded'],'false');
controller.setMapInfoExpanded(true);
assert.equal($('map-info-detail').hidden,false);
assert.equal($('map-info').dataset.minimized,'false');
assert.equal($('map-info-chip').attrs['aria-expanded'],'true');
assert.equal($('map-info-detail').textContent,full);
controller.mapInfoMessage('Startpunkt: 76694 Forst · Satellit.',false);
assert.equal($('map-info').classList.contains('warning'),false);
assert.equal($('map-info-detail').textContent,'Startpunkt: 76694 Forst · Satellit.');
console.log('Mobile Cloud status chip passed');
"""
    result = subprocess.run([node, "-e", program],
                            input=status_code + expand_code,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
