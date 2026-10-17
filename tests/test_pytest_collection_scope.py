"""Regression: pytest on the Pi must not inspect Docker-owned databases."""
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib


def test_pytest_default_and_explicit_root_skip_docker_data(tmp_path):
    project = Path(__file__).resolve().parents[1]
    config = tomllib.loads((project / "pyproject.toml").read_text())
    options = config["tool"]["pytest"]["ini_options"]
    assert options["testpaths"] == ["tests"]
    assert "cloud-server" in options["norecursedirs"]

    # Simulate the Pi deployment: cloud-server contains a MySQL volume that
    # the normal user cannot enter. Neither command should discover its files.
    shutil.copyfile(project / "pyproject.toml", tmp_path / "pyproject.toml")
    suite = tmp_path / "tests"
    suite.mkdir()
    (suite / "test_smoke.py").write_text(
        "def test_dummy():\n    assert True\n", encoding="utf-8")
    protected = tmp_path / "cloud-server/edge/data/mysql/cloud_sample"
    protected.mkdir(parents=True)
    (protected / "conftest.py").write_text(
        "raise AssertionError('Private MySQL files must never be imported')\n",
        encoding="utf-8")
    protected.chmod(0o000)
    try:
        for args in (("-q",), ("-q", ".")):
            result = subprocess.run(
                [sys.executable, "-m", "pytest", *args],
                cwd=tmp_path, text=True, capture_output=True, timeout=25,
                check=False,
            )
            assert result.returncode == 0, (
                f"pytest {args} must stay inside tests/: "
                f"{result.stdout}\n{result.stderr}")
            assert "1 passed" in result.stdout
            assert "Private MySQL" not in result.stdout + result.stderr
    finally:
        protected.chmod(0o700)
