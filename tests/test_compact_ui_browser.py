"""Chromium layout audit for the compact production renderers.

The generated HTML is tested without credentials, network calls, or DJI hardware.
These are geometric UI assertions, not a live-Pi acceptance.
"""
import pytest

from aeronexus.dji_media_page import render_dji_media_page
from aeronexus.multispectral_page import render_multispectral_page
from aeronexus.operations_page import render_operations
from aeronexus.results_page import render_results_page
from aeronexus.status_page import render_page
from aeronexus.studio_page import render_studio
from aeronexus.thermal_page import render_thermal_page

PAGES = (
    ("status", lambda: render_page(30)),
    ("studio", render_studio),
    ("operations", render_operations),
    ("media", render_dji_media_page),
    ("thermal", render_thermal_page),
    ("multispectral", render_multispectral_page),
    ("results", render_results_page),
)
VIEWPORTS = ((390, 844), (760, 900), (1024, 768), (1440, 900))


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_compact_layout_in_real_chromium(width, height):
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as runtime:
            browser = runtime.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                for name, render in PAGES:
                    page = browser.new_page(
                        viewport={"width": width, "height": height},
                        reduced_motion="reduce",
                    )
                    # Never contact DJI, a LAN endpoint, CDN or third-party tiles.
                    page.route("**/*", lambda route: route.abort())
                    page.set_content(render(), wait_until="domcontentloaded")
                    assert page.locator("nav.app-nav").is_visible(), (name, width)
                    geometry = page.evaluate(
                        """() => ({
                            width: document.documentElement.scrollWidth,
                            available: window.innerWidth,
                            bodyWidth: document.body.getBoundingClientRect().width,
                        })"""
                    )
                    assert geometry["width"] <= geometry["available"] + 2, (
                        name, width, geometry,
                    )
                    assert geometry["bodyWidth"] <= width + 2, (
                        name, width, geometry,
                    )
                    if name == "status" and width == 1440:
                        cards = page.locator('.grid[aria-label="Flottenkennzahlen"] .metric')
                        assert cards.count() == 7
                        first, last = cards.first.bounding_box(), cards.last.bounding_box()
                        assert abs(first["y"] - last["y"]) < 2, (
                            "Live-KPIs must fit in one desktop row", first, last
                        )
                        assert first["height"] <= 100, first
                    if name == "studio" and width == 1440:
                        left = page.locator("#mission-panel").bounding_box()
                        map_panel = page.locator(".content").bounding_box()
                        inspector = page.locator("#mission-inspector").bounding_box()
                        assert left["x"] + left["width"] <= map_panel["x"] + 2
                        assert map_panel["x"] + map_panel["width"] <= inspector["x"] + 2
                    page.close()
            finally:
                browser.close()
    except playwright.Error as exc:
        pytest.fail(f"Chromium UI audit unavailable: {exc}")


def test_portal_compact_rail_in_real_chromium():
    playwright = pytest.importorskip("playwright.sync_api")
    from pathlib import Path

    html = (
        Path(__file__).resolve().parents[1]
        / "deploy/cloud-server/control-portal/index.html"
    ).read_text(encoding="utf-8")
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            for width, height in VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.route("**/*", lambda route: route.abort())
                page.set_content(html, wait_until="domcontentloaded")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
                if width == 1440:
                    assert page.locator(".rail").bounding_box()["width"] <= 220
                page.close()
        finally:
            browser.close()
