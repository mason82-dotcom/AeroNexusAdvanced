"""Premium FH2 portal remains a real, secure navigation shell, not a fake cockpit."""
from html.parser import HTMLParser
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
PORTAL = ROOT / "deploy/cloud-server/control-portal/index.html"


class PortalParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = []
        self.titles = []
        self.headings = []
        self.ids = []
        self.mains = 0

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "a":
            self.anchors.append(data)
        if tag == "h1":
            self.headings.append(data)
        if tag == "main":
            self.mains += 1
        if data.get("id"):
            self.ids.append(data["id"])


def page():
    return PORTAL.read_text(encoding="utf-8")


def test_real_navigation_and_dji_services_are_distinct():
    html = page()
    tree = PortalParser()
    tree.feed(html)
    assert tree.mains == 1 and len(tree.headings) == 1
    assert len(tree.ids) == len(set(tree.ids))
    assert 'href="/pilot-login"' in html
    assert 'href="/project"' in html
    for destination in ("operations", "status", "studio", "media",
                        "thermal", "multispectral", "results", "fh2-components"):
        assert any(a.get("data-app") == destination for a in tree.anchors)
    assert '"https://"+host+":8000/"' in html
    assert 'link.target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "Cloud API und FlightHub 2 sind unterschiedliche Plattformen" in html
    assert "Datenwege &amp; Systeme" in html
    assert "kein Live-Kartenbild" in html


def test_only_real_pilot_webserver_probe_no_token_or_fake_telemetry():
    html = page()
    assert 'fetch("/pilot-login",{method:"HEAD"' in html
    assert "Pilot-2-Webserver erreichbar" in html
    assert "Keine Aussage über Flug- oder MQTT-Verbindung" in html
    assert "status.dataset.state" not in html  # no undifferentiated green status
    assert "localStorage" not in html and "sessionStorage" not in html
    assert "x-user-token" not in html
    assert "DJI_APP_LICENSE" not in html and "DJI_APP_KEY" not in html
    assert not re.search(r"eyJ[a-zA-Z0-9_-]{24,}\.", html)
    assert "paas.js" not in html  # only the HTTPS-only component page loads it
    assert "fetch(" in html and html.count("fetch(") == 1
    assert "Webseite erreichbar" in html


def test_design_tokens_come_from_project_design_contract():
    html = page()
    for expected in ("--bg:#10151c", "--surface:#171e28",
                     "--line:#344151", "--ink:#eaf3ff",
                     "--muted:#a6b4c5", "--mint:#75e3bd"):
        assert expected in html
    assert 'lang="de"' in html
    assert "prefers-reduced-motion" in html
    assert "forced-colors" in html
    assert "focus-visible" in html
    assert "@media(max-width:520px)" in html
    assert 'aria-current="page"' in html
    assert 'aria-live="polite"' in html


def test_browser_desktop_and_mobile_without_horizontal_overflow():
    playwright = pytest.importorskip("playwright.sync_api")
    html = re.sub(r"<script>[\s\S]*?</script>", "", page())
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(
                headless=True, args=["--no-sandbox"]
            )
        except playwright.Error:
            pytest.skip("Playwright Chromium unavailable")
        try:
            for width, height in ((1440, 900), (1024, 800),
                                  (760, 720), (390, 844), (320, 700)):
                page_obj = browser.new_page(
                    viewport={"width": width, "height": height}
                )
                page_obj.set_content(html, wait_until="domcontentloaded")
                assert not page_obj.evaluate(
                    "document.documentElement.scrollWidth > innerWidth + 1"
                ), f"Horizontal overflow at width {width}"
                assert page_obj.get_by_role("heading", name="Einsatzzentrale").is_visible()
                assert page_obj.locator('a[href="/pilot-login"]').count() >= 1
                if width <= 900:
                    assert page_obj.locator(".mobile-nav").is_visible()
                else:
                    assert page_obj.locator(".rail-nav").first.is_visible()
                page_obj.close()
        finally:
            browser.close()
