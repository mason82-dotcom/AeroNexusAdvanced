"""Genuine Leaflet 1.9.4 visual test of opt-in schematic connections."""
import importlib.util
import json
from pathlib import Path

import pytest

from aeronexus.geo_planning import GeoObject, SurveyPlanRequest, generate_survey_preview
from aeronexus.survey_route import SurveyRouteOptions


REAL_PATH = Path(__file__).resolve().parents[1] / "scripts/pi/studio_leaflet_chromium_smoke.py"
SPEC = importlib.util.spec_from_file_location("route_preview_real_leaflet", REAL_PATH)
real = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(real)
BASE_BUILD_FIXTURE = real.build_fixture


ROUTE_CHECK = r"""
  rCheck(!document.getElementById('survey-route-enabled').checked,
    'Schematic route must stay disabled by default');
  document.getElementById('survey-route-enabled').click();
  rCheck(!document.getElementById('survey-route-fields').hidden,
    'Optional route inputs did not become visible');
  document.getElementById('survey-route-speed').value='5';
  document.getElementById('survey-route-hold').value='5';
  const priorFetch=window.fetch;
  window.fetch=async (url,opts={})=>{
    if(String(url)==='/api/v1/studio/survey/preview' &&
       String(opts.method).toUpperCase()==='POST'){
      const payload=JSON.parse(opts.body);
      rCheck(payload.route&&payload.route.speed_mps===5&&
        payload.route.turn_delay_s===5, 'Schematic options not sent');
      window.__surveyCalls.push('POST schematic preview');
      return new Response(JSON.stringify(__ROUTE_RESULT__),{
        status:200,headers:{'Content-Type':'application/json'}});
    }
    return priorFetch(url,opts);
  };
  document.getElementById('survey-generate').click();
  for(let i=0;i<16;i++)await rTick();
  const connected=surveyLayer.getLayers();
  rCheck(connected.length===7,'Expected 4 strips plus 3 schematic connections');
  const links=connected.filter(layer=>layer.options.dashArray==='2 8');
  rCheck(links.length===3,'Missing three dashed schematic connections');
  rCheck(links.every(layer=>layer instanceof L.Polyline &&
    layer._path&&layer._path.ownerSVGElement),
    'Schematic links not drawn by genuine Leaflet SVG');
  rCheck(!document.getElementById('survey-route-metrics').hidden &&
    document.getElementById('survey-route-metrics').textContent.includes('ungeprüfte Verbindungen') &&
    document.getElementById('survey-route-metrics').textContent.includes('Rechenzeit'),
    'Route duration/warning not rendered');
  rCheck(mission.waypoints.length===0,'Sketch modified real mission model');
  rCheck(window.__surveyCalls.join(',')===
    'POST geo,POST preview,POST schematic preview',
    'Unexpected write-like request in route sketch');
  // Reverting to the default mode must remove links on next preview.
  window.fetch=priorFetch;
  document.getElementById('survey-route-enabled').click();
  rCheck(document.getElementById('survey-route-fields').hidden,
    'Disabling route sketch failed to hide inputs');
  document.getElementById('survey-generate').click();
  for(let i=0;i<16;i++)await rTick();
  rCheck(surveyLayer.getLayers().length===4,'Stale sketch links persisted');
  rCheck(document.getElementById('survey-route-metrics').hidden,
    'Stale route estimate remained visible');
  rCheck(mission.waypoints.length===0,'Editable mission changed');
  rCheck(window.__uiErrors.length===0,'Browser errors in route mode');
"""


def build_route_fixture():
    source = BASE_BUILD_FIXTURE()
    original = real.CHECKS.replace("__RECTANGLE__", json.dumps(real.base.RECTANGLE))
    if source.count(original) != 1:
        raise AssertionError("One real Leaflet harness expected")
    poly = GeoObject(name="Synthetisches Rechteck",
                     kind="polygon", vertices=real.base.RECTANGLE)
    result = generate_survey_preview(SurveyPlanRequest(
        polygon=poly, spacing_m=20, bearing_deg=0, route=SurveyRouteOptions()))
    assert result["leg_count"] == 4
    added = ROUTE_CHECK.replace("__ROUTE_RESULT__", json.dumps(result))
    marker = "  return strips.length;\n}"
    if original.count(marker) != 1:
        raise AssertionError("Real Leaflet harness completion marker changed")
    return source.replace(original, original.replace(marker, added + "\n" + marker))


@pytest.mark.parametrize("size", [(1440, 900), (420, 860)])
def test_schematic_route_is_opt_in_with_real_leaflet_svg(monkeypatch, size):
    if real.assets_dir() is None or real.base.base.browser_binary() is None:
        pytest.skip("Verified Leaflet assets or Chromium missing")
    monkeypatch.setattr(real, "build_fixture", build_route_fixture)
    state, reason = real.run_smoke(width=size[0], height=size[1])
    assert state == "pass", reason


def test_schematic_browser_fixture_preserves_real_assets_and_csp():
    html = build_route_fixture()
    assert html.count('<script src="leaflet.js"></script>') == 1
    assert html.count('<link rel="stylesheet" href="leaflet.css">') == 1
    assert "Unexpected write-like request in route sketch" in html
    assert "innerHTML" not in html
