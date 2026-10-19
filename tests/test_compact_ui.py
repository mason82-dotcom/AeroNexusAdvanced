"""Read-only regression contracts for compact AeroNexus UI presentation.

Keep the renderers, navigation, telemetry sources and map-inspector layout
unchanged while tightening visual density.
"""

from pathlib import Path

import pytest

from aeronexus.dji_media_page import render_dji_media_page
from aeronexus.multispectral_page import render_multispectral_page
from aeronexus.operations_page import render_operations
from aeronexus.results_page import render_results_page
from aeronexus.status_page import render_page
from aeronexus.studio_page import render_studio
from aeronexus.thermal_page import render_thermal_page
from aeronexus.ui_theme import COCKPIT_CSS


@pytest.mark.parametrize(
    "render",
    [
        lambda: render_page(30),
        render_studio,
        render_operations,
        render_dji_media_page,
        render_thermal_page,
        render_multispectral_page,
        render_results_page,
    ],
)
def test_compact_tokens_and_navigation_in_all_workspaces(render):
    html = render()
    assert "--compact-gap:8px" in html
    assert 'nav.app-nav a[aria-current="page"]' in html
    assert "prefers-reduced-motion" in html
    assert "focus-visible" in html
    assert html.count('class="app-nav"') == 1
    assert "__APP_NAVIGATION__" not in html


def test_live_cockpit_compact_styling_keeps_real_data_states():
    html = render_page(30)
    assert "#cockpit .cockpit-gauge" in html
    assert "#cockpit .cockpit-panel" in html
    assert 'id="poll-health"' in html
    assert 'id="feed"' in html
    assert 'id="health"' in html
    assert "Veraltete Telemetrie" in html


def test_studio_three_column_map_inspector_is_not_replaced():
    assert ".layout:has(.side){grid-template-columns" not in COCKPIT_CSS
    html = render_studio()
    assert "mission-inspector" in html
    assert ".layout{grid-template-columns:280px minmax(0,1fr) 300px" in html
    assert "cloud-preview" in html


def test_portal_density_changes_do_not_create_new_dji_actions():
    html = (
        Path(__file__).resolve().parents[1]
        / "deploy/cloud-server/control-portal/index.html"
    ).read_text(encoding="utf-8")
    assert "Compact control portal" in html
    assert ".feature{min-height:128px" in html
    assert 'fetch("/pilot-login",{method:"HEAD"' in html
    assert "localStorage" not in html
    assert 'data-app="operations"' in html
    assert 'data-app="studio"' in html
