"""Camera/Gimbal Editor remains local-only and does not leak into flight endpoints."""
from aeronexus.studio_page import render_studio


def test_editor_exposes_all_six_actions_with_strict_model_notice():
    page = render_studio()
    for name in ("startRecord", "stopRecord", "focus", "zoom",
                 "gimbalRotate", "gimbalEvenlyRotate"):
        assert f'<option value="{name}">' in page
    for field in ("point-action-list", "point-action-type", "point-action-add",
                  "point-focus-x", "point-focus-y", "point-zoom-mm",
                  "point-pitch-deg", "point-action-support"):
        assert f'id="{field}"' in page
    assert "WPML_ACTION_MODELS" in page
    assert "mavic3ta" not in page[page.index("const WPML_ACTION_MODELS="):
                                  page.index("let mission=EMPTY()",page.index("const WPML_ACTION_MODELS="))]
    assert "point.actions=[...(point.actions||[]),action]" in page
    assert 'mission.waypoints[selected]={...p,latitude:' in page
    assert 'points[points.length-1].actions=[]' in page


def test_no_dji_write_or_upload_bypass_for_extra_camera_actions():
    page = render_studio()
    block = page[page.index("function addWaypointAction()"):
                 page.index("function redraw()", page.index("function addWaypointAction()"))]
    for danger in ("fetch(", "mqtt", "publish(", "flight-control", "api(", "startMission"):
        assert danger not in block
