"""Regression checks for DJI HMS catalog installation; no network requests."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pi" / "install_dji_hms_catalog.py"
_SPEC = importlib.util.spec_from_file_location("install_dji_hms_catalog", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
installer = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(installer)


def _valid_entries(count: int = 100) -> dict:
    return {
        f"fpv_tip_0x{0x16100000 + index:08X}": {"en": "DJI status"}
        for index in range(count)
    }


def test_validate_skips_non_hms_keys_and_untranslated_values():
    entries = _valid_entries()
    entries["metadata"] = {"en": "not a DJI HMS key"}
    entries["fpv_tip_0x16100100"] = {"en": "   ", "de": None}
    entries["dock_tip_0x19110001"] = ["not a language mapping"]
    entries["dock_tip_0xINVALID"] = {"de": "not a code"}
    assert installer.validate(json.dumps(entries).encode("utf-8")) == 100


def test_validate_rejects_too_few_usable_keys_without_type_error():
    entries = _valid_entries(99)
    entries["metadata"] = {"de": "not a DJI HMS key"}
    with pytest.raises(ValueError, match="too few usable"):
        installer.validate(json.dumps(entries).encode("utf-8"))


def test_install_writes_validated_catalog_with_private_permissions(tmp_path, monkeypatch):
    raw = json.dumps({**_valid_entries(), "metadata": {"en": "ignored"}}).encode()

    class Response(io.BytesIO):
        status = 200

    class FakeOpener:
        def open(self, request, timeout):
            assert request.full_url == installer.OFFICIAL_URL
            assert timeout == 25
            return Response(raw)

    monkeypatch.setattr(installer, "build_opener", lambda *args: FakeOpener())
    target = tmp_path / "private" / "hms.json"
    assert installer.install(target) == 100
    assert target.read_bytes() == raw
    assert target.stat().st_mode & 0o777 == 0o600
