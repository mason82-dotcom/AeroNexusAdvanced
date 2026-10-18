"""Real Leaflet camera-mode browser regression with synthetic in-memory APIs.

No production Pi, DJI endpoints or photo captures. Extends the existing
verified-asset Chromium fixture, retaining its real Leaflet JS and original
manual preview smoke before exercising the optional camera mode.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from aeronexus.geo_planning import GeoObject, SurveyPlanRequest, generate_survey_preview
from aeronexus.survey_camera import SurveyCameraRequest


REAL_PATH = Path(__file__).resolve().parents[1] / "scripts/pi/studio_leaflet_chromium_smoke.py"
SPEC = importlib.util.spec_from_file_location("survey_real_leaflet_camera", REAL_PATH)
real = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(real)
BASE_BUILD_FIXTURE = real.build_fixture


CAMERA_CHECK = r"""
  // Keep the prior manual flight-strip preview intact before changing modes.
  const selector=document.getElementById('survey-camera');
  rCheck(selector.value==='','Existing manual-mode default changed');
  const previousManualSpacing=document.getElementById('survey-spacing').value;
  selector.value='matrice-4e-wide';
  selector.dispatchEvent(new Event('change',{bubbles:true}));
  rCheck(document.getElementById('survey-spacing').disabled,
    'Automatic camera spacing must disable manual input');
  rCheck(!document.getElementById('survey-camera-fields').hidden,
    'Camera fields did not become visible');
  document.getElementById('survey-height-agl').value='60';
  document.getElementById('survey-side-overlap').value='70';
  document.getElementById('survey-front-overlap').value='80';

  // Only the non-persisting preview call is intercepted; all other requests
  // keep the original in-memory-only allowlist.
  const previousFetch=window.fetch;
  window.fetch=async (url,options={})=>{
    if(String(url)==='/api/v1/studio/survey/preview' &&
       String(options.method).toUpperCase()==='POST'){
      const body=JSON.parse(options.body);
      rCheck(body.camera&&body.camera.profile_id==='matrice-4e-wide',
        'Camera profile was not passed to preview API');
      rCheck(body.camera.height_agl_m===60&&body.camera.side_overlap_pct===70&&
        body.camera.front_overlap_pct===80,'Camera settings lost');
      window.__surveyCalls.push('POST camera preview');
      return new Response(JSON.stringify(__CAMERA_RESULT__),{
        status:200,headers:{'Content-Type':'application/json'}});
    }
    return previousFetch(url,options);
  };
  document.getElementById('survey-generate').click();
  for(let i=0;i<16;i++)await rTick();
  const cameraStrips=surveyLayer.getLayers();
  rCheck(cameraStrips.length===__CAMERA_LEGS__,
    'Camera-derived flight strip count differs from backend optics');
  rCheck(cameraStrips.every(layer=>layer instanceof L.Polyline&&
    layer._path&&layer._path.ownerSVGElement),
    'Camera preview missing real Leaflet SVG vectors');
  rCheck(document.getElementById('survey-camera-metrics').hidden===false,
    'Camera GSD panel is hidden');
  rCheck(document.getElementById('survey-camera-metrics').textContent.includes('GSD') &&
    document.getElementById('survey-camera-metrics').textContent.includes('Fotos'),
    'Camera GSD and photo count are not rendered');
  rCheck(window.__surveyCalls.join(',')===
    'POST geo,POST preview,POST camera preview','Unexpected mutating API calls');
  rCheck(mission.waypoints.length===0,'Camera preview mutated waypoint mission');
  rCheck(window.__uiErrors.length===0,'Camera mode browser error');
  // Switching back restores the original manual workflow without a page reload.
  selector.value='';
  selector.dispatchEvent(new Event('change',{bubbles:true}));
  rCheck(!document.getElementById('survey-spacing').disabled,
    'Camera mode failed to restore manual spacing input');
  rCheck(document.getElementById('survey-spacing').value===previousManualSpacing,
    'Camera mode overwrote the operator manual spacing');
"""


def build_camera_fixture():
    source = BASE_BUILD_FIXTURE()
    original_check = real.CHECKS.replace("__RECTANGLE__", json.dumps(real.base.RECTANGLE))
    if source.count(original_check) != 1:
        raise AssertionError("Expected a single existing real Leaflet smoke script")
    polygon = GeoObject(name="Synthetic camera plot", kind="polygon",
                        vertices=real.base.RECTANGLE)
    camera = SurveyCameraRequest(
        profile_id="matrice-4e-wide", height_agl_m=60,
        side_overlap_pct=70, front_overlap_pct=80)
    result = generate_survey_preview(SurveyPlanRequest(polygon=polygon, camera=camera))
    extra = (CAMERA_CHECK.replace("__CAMERA_RESULT__", json.dumps(result))
                         .replace("__CAMERA_LEGS__", str(result["leg_count"])))
    match = "  return strips.length;\n}"
    if original_check.count(match) != 1:
        raise AssertionError("Leaflet smoke completion marker changed")
    modified_check = original_check.replace(match, extra + "\n" + match)
    return source.replace(original_check, modified_check)


@pytest.mark.parametrize("size", [(1440, 900), (420, 860)])
def test_camera_survey_uses_real_leaflet_and_keeps_manual_mode(monkeypatch, size):
    if real.assets_dir() is None or real.base.base.browser_binary() is None:
        pytest.skip("Pinned Leaflet assets or Chromium unavailable")
    monkeypatch.setattr(real, "build_fixture", build_camera_fixture)
    outcome, reason = real.run_smoke(width=size[0], height=size[1])
    assert outcome == "pass", reason


def test_camera_fixture_preserves_real_leaflet_assets_and_source():
    fixture = build_camera_fixture()
    assert fixture.count('<script src="leaflet.js"></script>') == 1
    assert fixture.count('<link rel="stylesheet" href="leaflet.css">') == 1
    assert "Camera profile was not passed to preview API" in fixture
    assert "innerHTML" not in fixture
