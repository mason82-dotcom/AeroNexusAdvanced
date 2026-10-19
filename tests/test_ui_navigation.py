"""Cross-workspace navigation and disclosure regression coverage."""
from html.parser import HTMLParser
import importlib.util
from pathlib import Path

import pytest

from aeronexus.dji_media_page import render_dji_media_page
from aeronexus.multispectral_page import render_multispectral_page
from aeronexus.operations_page import render_operations
from aeronexus.results_page import render_results_page
from aeronexus.status_page import render_page
from aeronexus.studio_page import render_studio
from aeronexus.thermal_page import render_thermal_page

PAGES = {
    "studio": render_studio,
    "status": lambda: render_page(30),
    "operations": render_operations,
    "media": render_dji_media_page,
    "thermal": render_thermal_page,
    "multispectral": render_multispectral_page,
    "results": render_results_page,
}


class NavigationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav":
            self.inside = attrs.get("class") == "app-nav"
        if self.inside and tag == "a":
            self.links.append(attrs)

    def handle_endtag(self, tag):
        if tag == "nav":
            self.inside = False


@pytest.mark.parametrize("current", PAGES)
def test_every_workspace_has_same_destinations_and_one_current_page(current):
    parser = NavigationParser()
    html = PAGES[current]()
    parser.feed(html)
    assert [link["href"] for link in parser.links] == [
        "/status", "/studio", "/media", "/operations", "/thermal",
        "/multispectral", "/results",
    ]
    assert [link["href"] for link in parser.links if link.get("aria-current") == "page"] == [f"/{current}"]
    assert "__APP_NAVIGATION__" not in html


def test_studio_disclosures_preserve_values_and_keyboard_navigation_in_browser():
    playwright = pytest.importorskip("playwright.sync_api")
    spec = importlib.util.spec_from_file_location(
        "studio_ui_fixture", Path(__file__).resolve().parents[1]
        / "scripts/pi/studio_full_ui_chromium_smoke.py")
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    source = smoke.CDN.sub("", render_studio()).replace(
        smoke.SCRIPT_START, smoke.PRELUDE + "\n" + smoke.SCRIPT_START, 1)
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True, args=["--no-sandbox"])
        except playwright.Error:
            pytest.skip("Playwright Chromium is not installed")
        try:
            for width, height in ((1440, 900), (390, 844), (760, 650)):
                page = browser.new_page(viewport={"width": width, "height": height})
                page.route("**/*", lambda route: route.abort())
                page.set_content(source, wait_until="domcontentloaded")
                page.wait_for_function("document.getElementById('auth-message').textContent.includes('aktiv')")
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                left = page.locator("#mission-panel").bounding_box()
                canvas = page.locator(".content").bounding_box()
                right = page.locator("#mission-inspector").bounding_box()
                if width > 1000:
                    assert left["x"] + left["width"] <= canvas["x"] + 1
                    assert canvas["x"] + canvas["width"] <= right["x"] + 1
                    assert abs(left["y"] - right["y"]) < 1
                elif width > 700:
                    assert left["y"] + left["height"] <= right["y"] + 1
                    assert right["x"] + right["width"] <= canvas["x"] + 1
                details = page.locator("#mission-settings")
                assert not details.evaluate("el => el.open")
                summary = details.locator("summary")
                summary.focus()
                page.keyboard.press("Enter")
                page.locator("#mission-description").fill("Einsatzgebiet Nord")
                summary.click()
                summary.click()
                assert page.locator("#mission-description").input_value() == "Einsatzgebiet Nord"
                assert "unsaved" in page.locator("#editor-dirty").get_attribute("class")
                menu = page.locator("nav.app-nav details")
                menu.locator("summary").focus()
                page.keyboard.press("Enter")
                assert menu.locator('a[href="/thermal"]').is_visible()
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                menu.locator("summary").click()
                page.locator('button[data-tab="geo-pane"]').click()
                assert not page.locator("#mission-inspector").is_visible()
                page.locator('button[data-tab="map-pane"]').click()
                assert page.locator("#mission-inspector").is_visible()
                assert page.locator("#mission-description").input_value() == "Einsatzgebiet Nord"
                page.evaluate("managerRouteKey=managerKey(waylineData.waylines[0]);updateMissionSelect()")
                assert not page.locator("#mission-fields").is_visible()
                assert "Schreibgeschützte Cloud-Vorschau" in page.locator("#inspector-context").inner_text()
                page.evaluate('managerRouteKey="";updateMissionSelect()')
                assert page.locator("#mission-fields").is_visible()
                assert page.locator("#mission-description").input_value() == "Einsatzgebiet Nord"
                # A source failure must reveal the full message without another click.
                page.evaluate('missionManagerState("Quelle nicht erreichbar", true)')
                assert page.locator("#mission-manager-state").is_visible()
                assert page.locator("#manager-source-details").evaluate("el => el.open")
                page.close()
        finally:
            browser.close()
