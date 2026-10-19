"""Regression checks for cheap, immutable web-page rendering."""

import subprocess
import sys

import pytest

from aeronexus.multispectral_page import render_multispectral_page
from aeronexus.status_page import render_page
from aeronexus.studio_page import render_studio


def test_large_static_pages_are_rendered_once_per_worker():
    studio = render_studio()
    multispectral = render_multispectral_page()
    assert render_studio() is studio
    assert render_multispectral_page() is multispectral
    assert "__MISSION_MODEL_OPTIONS__" not in studio
    assert "__MS_REPORT_CSV_FIELDS__" not in multispectral


def test_cockpit_cache_is_keyed_by_validated_refresh_interval():
    five = render_page(5)
    thirty = render_page(30)
    assert render_page(5) is five
    assert render_page(30) is thirty
    assert five != thirty
    assert "__COCKPIT_HTML__" not in thirty

    # Validation must happen before cache lookup: 5.0 and 5 must not alias.
    for invalid in (True, 5.0, "5", 4, 3601):
        with pytest.raises(ValueError, match="Invalid refresh interval"):
            render_page(invalid)


def test_app_import_does_not_eagerly_load_page_templates():
    script = (
        "import sys; import aeronexus.app; "
        "assert not ({'aeronexus.studio_page', "
        "'aeronexus.status_page', "
        "'aeronexus.operations_page', "
        "'aeronexus.thermal_page', "
        "'aeronexus.multispectral_page', "
        "'aeronexus.results_page', "
        "'aeronexus.dji_media_page'} & set(sys.modules))"
    )
    run = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode == 0, run.stderr
