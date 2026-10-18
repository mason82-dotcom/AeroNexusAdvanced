"""Genuine Leaflet desktop/mobile regression for opt-in 2D turn fillets."""
import importlib.util
import json
from pathlib import Path

import pytest

from aeronexus.geo_planning import GeoObject, SurveyPlanRequest, generate_survey_preview
from aeronexus.survey_route import SurveyRouteOptions


REAL_PATH = Path(__file__).resolve().parents[1] / "scripts/pi/studio_leaflet_chromium_smoke.py"
SPEC = importlib.util.spec_from_file_location("turn_geometry_real_leaflet", REAL_PATH)
real = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(real)
BASE_BUILD_FIXTURE = real.build_fixture


TURN_CHECK = r"""
  rCheck(!document.getElementById('survey-route-enabled').checked,
    'Legacy mode must stay the default');
  rCheck(document.getElementById('survey-turn-enabled').disabled,
    'Turn mode should be disabled without route mode');
  document.getElementById('survey-route-enabled').click();
  document.getElementById('survey-turn-enabled').click();
  rCheck(!document.getElementById('survey-turn-options').hidden,
    'Turn-radius field hidden after explicit opt-in');
  document.getElementById('survey-turn-radius').value='5';
  const priorFetch=window.fetch;
  window.fetch=async(url,options={})=>{
    if(String(url)==='/api/v1/studio/survey/preview' &&
       String(options.method).toUpperCase()==='POST'){
      const payload=JSON.parse(options.body);
      rCheck(payload.route&&payload.route.turn_radius_m===5,
        'Turn radius missing from preview payload');
      window.__surveyCalls.push('POST turn preview');
      return new Response(JSON.stringify(__TURN_RESULT__),{
        status:200,headers:{'Content-Type':'application/json'}});
    }
    return priorFetch(url,options);
  };
  document.getElementById('survey-generate').click();
  for(let i=0;i<16;i++)await rTick();
  const all=surveyLayer.getLayers();
  rCheck(all.length===7,'Expected 4 survey strips and 3 transitions');
  const curves=all.filter(layer=>layer.options.color==='#58cee7');
  rCheck(curves.length===3,'Three visible circular fillets required');
  rCheck(curves.every(layer=>layer instanceof L.Polyline &&
    layer._path&&layer._path.ownerSVGElement),
    'Turn geometry not rendered by genuine Leaflet SVG');
  rCheck(document.getElementById('survey-turn-metrics').hidden===false,
    'Turn results hidden');
  const metrics=document.getElementById('survey-turn-metrics').textContent;
  rCheck(metrics.includes('Geometrische 2D-Bögen') &&
    metrics.includes('Keine Kollisions-') && metrics.includes('theoretische Zeit'),
    'Turn metrics or warnings missing');
  rCheck(window.__surveyCalls.join(',')==='POST geo,POST preview,POST turn preview',
    'Unexpected mutating API request');
  rCheck(mission.waypoints.length===0,'Turn preview changed mission waypoints');
  window.fetch=priorFetch;
  document.getElementById('survey-turn-enabled').click();
  document.getElementById('survey-route-enabled').click();
  document.getElementById('survey-generate').click();
  for(let i=0;i<16;i++)await rTick();
  rCheck(surveyLayer.getLayers().length===4,
    'Turn overlay persisted after opting out');
  rCheck(document.getElementById('survey-turn-metrics').hidden,
    'Old turn metrics persisted after opting out');
  rCheck(mission.waypoints.length===0,'Survey test mutated editable mission');
  rCheck(window.__uiErrors.length===0,'Turn browser JS error');
"""


def build_turn_fixture():
    source = BASE_BUILD_FIXTURE()
    original=real.CHECKS.replace("__RECTANGLE__",json.dumps(real.base.RECTANGLE))
    if source.count(original)!=1:
        raise AssertionError("Expected a single real Leaflet smoke script")
    poly=GeoObject(name="Synthetic turns",kind="polygon",vertices=real.base.RECTANGLE)
    response=generate_survey_preview(SurveyPlanRequest(
        polygon=poly,spacing_m=20,bearing_deg=0,
        route=SurveyRouteOptions(turn_radius_m=5)))
    turns=response["route_preview"]["turn_geometry"]
    assert turns["geometry_available_count"]==3
    assert turns["polygon_exit_count"]==0
    extra=TURN_CHECK.replace("__TURN_RESULT__",json.dumps(response))
    marker="  return strips.length;\n}"
    if original.count(marker)!=1:
        raise AssertionError("Original Leaflet completion marker missing")
    return source.replace(original,original.replace(marker,extra+"\n"+marker))


@pytest.mark.parametrize("size",[(1440,900),(420,860)])
def test_turn_preview_real_leaflet_svg_and_opt_out(monkeypatch,size):
    if real.assets_dir() is None or real.base.base.browser_binary() is None:
        pytest.skip("Pinned Leaflet assets or Chromium unavailable")
    monkeypatch.setattr(real,"build_fixture",build_turn_fixture)
    state,reason=real.run_smoke(width=size[0],height=size[1])
    assert state=="pass",reason


def test_fixture_uses_pinned_real_leaflet_assets_and_no_new_script():
    html=build_turn_fixture()
    assert html.count('<script src="leaflet.js"></script>')==1
    assert html.count('<link rel="stylesheet" href="leaflet.css">')==1
    assert 'Expected 4 survey strips and 3 transitions' in html
    assert "innerHTML" not in html
