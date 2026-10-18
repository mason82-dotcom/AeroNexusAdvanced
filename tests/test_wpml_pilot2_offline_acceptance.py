"""Synthetic Pilot 2 offline acceptance: no DJI upload, flight or credentials."""
from __future__ import annotations

from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
import json
import os
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pytest

from aeronexus.wpml_export import WPML_NS, export_kmz, import_kmz


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pi/wpml_pilot2_offline_acceptance.py"
spec = spec_from_file_location("wpml_pilot2_offline_acceptance", SCRIPT)
assert spec is not None and spec.loader is not None
offline = module_from_spec(spec)
spec.loader.exec_module(offline)
W = "{" + WPML_NS + "}"


def test_two_synthetic_m4_archives_and_private_manifest(tmp_path):
    out = tmp_path / "wpml-offline"
    result = offline.generate_samples(out)
    assert result["kind"] == "aeronexus-wpml-offline-acceptance-v1"
    assert result["upload_performed"] is False
    assert result["dji_pilot2_import_verified"] is False
    assert result["flight_readiness_verified"] is False
    assert [s["model"] for s in result["samples"]] == ["matrice4e", "matrice4t"]
    assert len(list(out.iterdir())) == 3
    recorded = json.loads((out / "offline-verification.json").read_text())
    assert recorded == result
    for row in recorded["samples"]:
        path = out / row["filename"]
        assert "OFFLINE_ONLY_DO_NOT_FLY" in path.name
        assert path.suffix == ".kmz"
        assert path.is_file()
        blob = path.read_bytes()
        assert sha256(blob).hexdigest() == row["sha256"]
        assert offline.verify_kmz(blob, offline.sample_mission(row["model"])) == row
        assert import_kmz(blob).model_dump() == offline.sample_mission(row["model"]).model_dump()
        with ZipFile(BytesIO(blob)) as kmz:
            assert set(kmz.namelist()) == {
                "wpmz/template.kml", "wpmz/waylines.wpml"}
            assert kmz.testzip() is None
            for name in kmz.namelist():
                root = ET.fromstring(kmz.read(name))
                functions = [el.text for el in root.findall(".//" + W + "actionActuatorFunc")]
                assert sorted(functions) == ["startRecord", "stopRecord", "takePhoto"]
    assert "49.1533" not in json.dumps(recorded)
    assert "8.584" not in json.dumps(recorded)


def test_new_private_directory_and_exclusive_create(tmp_path):
    directory = tmp_path / "new-private-dir"
    offline.generate_samples(directory)
    with pytest.raises(FileExistsError):
        offline.generate_samples(directory)
    if os.name == "posix":
        assert directory.stat().st_mode & 0o077 == 0
        for name in directory.iterdir():
            assert name.stat().st_mode & 0o077 == 0


def test_missing_parent_fails_without_creating_output(tmp_path):
    target = tmp_path / "no-parent" / "new-dir"
    with pytest.raises(FileNotFoundError):
        offline.generate_samples(target)
    assert not target.exists()


def test_invalid_lens_fields_fail_closed():
    mission = offline.sample_mission("matrice4t")
    blob = export_kmz(mission, timestamp_ms=offline.TIMESTAMP_MS)
    invalid = BytesIO()
    with ZipFile(BytesIO(blob)) as src, ZipFile(invalid, "w") as dest:
        for name in src.namelist():
            data = src.read(name)
            if name == "wpmz/waylines.wpml":
                root = ET.fromstring(data)
                lens = root.find(".//" + W + "payloadLensIndex")
                assert lens is not None
                lens.text = "ir"
                data = ET.tostring(root)
            dest.writestr(name, data)
    with pytest.raises(offline.OfflineAcceptanceError):
        offline.verify_kmz(invalid.getvalue(), mission)


def test_offline_cli_rejects_existing_directory(tmp_path, capsys):
    existing = tmp_path / "existing"
    existing.mkdir()
    assert offline.main(["--output-dir", str(existing)]) == 1
    assert "Refusing an existing output directory" in capsys.readouterr().err
    assert list(existing.iterdir()) == []


def test_offline_cli_writes_only_two_kmz_and_report(tmp_path, capsys):
    output = tmp_path / "new"
    assert offline.main(["--output-dir", str(output)]) == 0
    text = capsys.readouterr().out
    assert "OFFLINE ONLY" in text
    assert "Pilot 2 import: NOT TESTED" in text
    assert sorted(p.suffix for p in output.iterdir()) == [".json", ".kmz", ".kmz"]
