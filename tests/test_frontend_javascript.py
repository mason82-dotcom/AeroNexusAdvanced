"""Parse *actual* embedded browser JS so a Chrome-wide syntax failure is caught.

This test would have caught the old missing parenthesis in the map longitude
calculation: Python endpoint tests cannot parse JavaScript.
"""
import re
import shutil
import subprocess

import pytest

from aeronexus.status_page import render_page
from aeronexus.studio_page import render_studio
from aeronexus.operations_page import render_operations


@pytest.mark.parametrize("page", ["studio", "status", "operations"])
def test_embedded_javascript_compiles_in_node(page):
    if shutil.which("node") is None:
        pytest.skip("Node.js is needed to validate embedded browser JavaScript")
    html = {"studio": render_studio, "status": lambda: render_page(30),
            "operations": render_operations}[page]()
    scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.DOTALL)
    assert len(scripts) == 1
    result = subprocess.run(
        ["node", "--check", "-"], input=scripts[0], text=True,
        capture_output=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr


def test_both_uis_have_no_login_forms_or_bearer_tokens():
    for html in (render_studio(), render_page(30), render_operations()):
        assert 'id="auth-token"' not in html
        assert 'id="token"' not in html
        assert 'id="login"' not in html
        assert 'id="connect"' not in html
        assert 'id="disconnect"' not in html
        assert "Authorization" not in html
        assert "Bearer " not in html
