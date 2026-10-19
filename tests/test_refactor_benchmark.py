"""Synthetic read-only performance benchmark: no DJI, network or disk writes."""
import json
import subprocess
import sys
from pathlib import Path


def test_refactor_benchmark_runs_offline_and_keeps_reference_parity():
    script = Path(__file__).resolve().parents[1] / "scripts" / "maintenance" / "benchmark_refactor.py"
    result = subprocess.run(
        [sys.executable, str(script), "--devices", "7", "--events", "21",
         "--iterations", "2"],
        text=True, capture_output=True, timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["result_equivalence"] is True
    assert (data["devices"], data["hms_events"], data["iterations"]) == (7, 21, 2)
    assert data["fixture"] == "in-memory synthetic data only"
    for key in (
        "device_projection_full_ms", "device_projection_paged_ms",
        "hms_full_scan_ms", "hms_indexed_ms",
    ):
        assert isinstance(data[key], (int, float))
        assert data[key] >= 0
