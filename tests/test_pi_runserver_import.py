"""The Pi gateway must not accidentally import an older adjacent checkout."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def test_run_server_ignores_foreign_pythonpath(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "deploy/pi/run-server.sh"
    root = tmp_path / "AeroNexusAdvanced"
    runner = root / "deploy/pi/run-server.sh"
    runner.parent.mkdir(parents=True)
    shutil.copyfile(source, runner)
    (root / "src").mkdir()

    env_file = root / ".env"
    env_file.write_text("PYTHONPATH=/tmp/other-checkout/src\\n", encoding="utf-8")
    env_file.chmod(0o600)

    fake_python = root / ".venv/bin/python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text(
        "#!" + sys.executable + "\\n"
        "import json, os, sys\\n"
        "print(json.dumps({'pythonpath': os.environ.get('PYTHONPATH'), "
        "'arguments': sys.argv[1:]}))\\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path / "stale-external-checkout" / "src")
    result = subprocess.run(
        ["bash", str(runner)], cwd=tmp_path, env=env,
        check=True, capture_output=True, text=True, timeout=10,
    )
    output = json.loads(result.stdout)
    assert output["pythonpath"] == str(root / "src")
    assert output["arguments"][:3] == ["-m", "uvicorn", "aeronexus.app:app"]
