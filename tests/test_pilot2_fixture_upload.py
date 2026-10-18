"""Upload fixture preflight tests: network is simulated; no real Cloud POST."""
import asyncio
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import os
from uuid import UUID

import httpx
import pytest

from aeronexus.local_waylines import Credentials
from aeronexus import pilot2_fixture_upload as pu

WID = "12345678-1234-4234-8234-123456789012"
CREDS = Credentials(WID, "private-fake-test-auth-token")
OFFLINE_SCRIPT = (Path(__file__).resolve().parents[1] /
                  "scripts/pi/wpml_pilot2_offline_acceptance.py")
spec = spec_from_file_location("offline_wpml_samples", OFFLINE_SCRIPT)
assert spec and spec.loader
offline = module_from_spec(spec)
spec.loader.exec_module(offline)


@pytest.fixture
def samples(tmp_path):
    folder = tmp_path / "offline"
    offline.generate_samples(folder)
    return folder


def test_fixture_is_exactly_the_generated_one(samples):
    for model in pu.MODELS_ALLOWED:
        plan = pu.prepare(samples, model)
        assert plan.model == model
        assert plan.filename.startswith("AeroNexus_WPML_OFFLINE_ONLY_DO_NOT_FLY_")
        assert plan.kmz[:2] == b"PK"
        assert plan.sha256 == sha256(plan.kmz).hexdigest()
        assert plan.cloud_name.endswith(model.upper())
        assert plan.model_key == ("0-99-0" if model == "matrice4e" else "0-99-1")
        assert "49.153" not in repr(plan)


def test_disallows_arbitrary_model_without_reading_files(samples):
    with pytest.raises(pu.FixtureUploadError, match="unsupported_model"):
        pu.prepare(samples, "mavic3m")


def test_forged_manifest_digest_fails_closed(samples):
    p = samples / "offline-verification.json"
    data = json.loads(p.read_text())
    data["samples"][1]["sha256"] = "0" * 64
    p.write_text(json.dumps(data))
    with pytest.raises(pu.FixtureUploadError, match="fixture_checksum_mismatch"):
        pu.prepare(samples, "matrice4t")


def test_swapped_binary_fails_checksum(samples):
    target = samples / (pu.FILE_PREFIX + "MATRICE4T.kmz")
    original = target.read_bytes()
    target.write_bytes(original + b"not-in-manifest")
    with pytest.raises(pu.FixtureUploadError, match="fixture_checksum_mismatch"):
        pu.prepare(samples, "matrice4t")


def test_private_permissions_enforced(samples):
    if os.name != "posix":
        pytest.skip("File ownership and mode checks require POSIX")
    (samples / "offline-verification.json").chmod(0o644)
    with pytest.raises(pu.FixtureUploadError, match="invalid_private_fixture"):
        pu.prepare(samples, "matrice4t")


def test_symlinked_fixture_rejected(samples, tmp_path):
    target = samples / (pu.FILE_PREFIX + "MATRICE4T.kmz")
    target.unlink()
    target.symlink_to(tmp_path / "arbitrary")
    with pytest.raises(pu.FixtureUploadError, match="invalid_fixture"):
        pu.prepare(samples, "matrice4t")


def test_original_directory_replaced_with_symlink_rejected(samples, tmp_path):
    alt = tmp_path / "link"
    alt.symlink_to(samples, target_is_directory=True)
    with pytest.raises(pu.FixtureUploadError, match="invalid_fixture_directory"):
        pu.prepare(alt, "matrice4t")


def test_local_dry_run_never_loads_cloud_session(samples, monkeypatch, capsys):
    monkeypatch.setattr(pu, "load_credentials", lambda *_: (_ for _ in ()).throw(
        AssertionError("Dry-run accessed credentials")))
    assert pu.main(["--source-dir", str(samples), "--model", "matrice4t"]) == 0
    output = capsys.readouterr().out
    assert "LOKALER DRY-RUN" in output
    assert "49.153" not in output


def response_inventory(plan, *, uploaded=False, wrong_model=False):
    entries = []
    if uploaded:
        entries = [{"id": str(UUID(int=123)), "name": plan.cloud_name,
                    "drone_model_key": "0-99-0" if wrong_model else plan.model_key,
                    "template_types": [0], "update_time": 1792368000000}]
    return {"code": 0, "data": {
        "list": entries,
        "pagination": {"total": len(entries), "page": 1, "page_size": 50},
    }}


def cloud_transport(plan, calls, *, duplicate=False, wrong_model=False,
                    fail_post=False, bad_session=False):
    def handler(request):
        calls.append((request.method, request.url.path))
        assert request.url.host == "127.0.0.1"
        assert request.headers.get("x-auth-token") == CREDS.access_token
        if request.url.path == "/manage/api/v1/users/current":
            return httpx.Response(200, json={"code": 0, "data": {
                "workspace_id": WID, "user_type": 99 if bad_session else 1}})
        if request.method == "GET":
            assert request.url.path == f"/wayline/api/v1/workspaces/{WID}/waylines"
            is_posted = any(method == "POST" for method, _ in calls)
            return httpx.Response(
                200, json=response_inventory(plan, uploaded=duplicate or is_posted,
                                             wrong_model=wrong_model))
        assert request.method == "POST"
        assert request.url.path == f"/wayline/api/v1/workspaces/{WID}/waylines/file/upload"
        assert plan.filename.encode() in request.content
        assert plan.kmz in request.content
        if fail_post:
            raise httpx.ReadTimeout("PRIVATE_CLOUD_RESPONSE")
        return httpx.Response(200, json={"code": 0, "message": "PRIVATE_CLOUD_RESPONSE"})
    return httpx.MockTransport(handler)


def test_cloud_readonly_checks_existing_session_and_inventory(samples):
    plan = pu.prepare(samples, "matrice4t")
    calls = []
    result = asyncio.run(pu.check_cloud(plan, CREDS, transport=cloud_transport(plan, calls)))
    assert result["reported_total"] == 0
    assert [c[0] for c in calls] == ["GET", "GET"]


def test_duplicate_name_does_not_post(samples, monkeypatch):
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    plan = pu.prepare(samples, "matrice4t")
    calls = []
    with pytest.raises(pu.FixtureUploadError, match="cloud_name_already_exists"):
        asyncio.run(pu.upload(plan, CREDS, transport=cloud_transport(
            plan, calls, duplicate=True)))
    assert [c[0] for c in calls] == ["GET", "GET"]


def test_missing_env_gate_blocks_every_request(samples, monkeypatch):
    monkeypatch.delenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", raising=False)
    plan = pu.prepare(samples, "matrice4t")
    calls = []
    with pytest.raises(pu.FixtureUploadError, match="upload_disabled"):
        asyncio.run(pu.upload(plan, CREDS, transport=cloud_transport(plan, calls)))
    assert calls == []


def test_successful_single_post_and_readback(samples, monkeypatch):
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    plan = pu.prepare(samples, "matrice4t")
    calls = []
    result = asyncio.run(pu.upload(plan, CREDS, transport=cloud_transport(plan, calls)))
    assert result == {"state": "registered", "model": "matrice4t",
                      "name": plan.cloud_name, "verified": True}
    assert [c[0] for c in calls] == ["GET", "GET", "POST", "GET"]


def test_invalid_session_never_post(samples, monkeypatch):
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    plan = pu.prepare(samples, "matrice4t")
    calls = []
    with pytest.raises(pu.FixtureUploadError, match="cloud_preflight_unavailable"):
        asyncio.run(pu.upload(plan, CREDS, transport=cloud_transport(
            plan, calls, bad_session=True)))
    assert [c[0] for c in calls] == ["GET"]


def test_wrong_model_after_post_does_not_claim_success(samples, monkeypatch):
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    plan = pu.prepare(samples, "matrice4t")
    calls = []
    result = asyncio.run(pu.upload(plan, CREDS, transport=cloud_transport(
        plan, calls, wrong_model=True)))
    assert result["state"] == "submitted_unverified"
    assert result["verified"] is False
    assert [c[0] for c in calls].count("POST") == 1


def test_uncertain_post_result_never_retries(samples, monkeypatch):
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    plan = pu.prepare(samples, "matrice4t")
    calls = []
    with pytest.raises(pu.FixtureUploadError, match="upload_outcome_unknown"):
        asyncio.run(pu.upload(plan, CREDS, transport=cloud_transport(
            plan, calls, fail_post=True)))
    assert [c[0] for c in calls].count("POST") == 1


def test_apply_needs_a_terminal_even_with_gate(samples, monkeypatch, capsys):
    monkeypatch.setenv("AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED", "1")
    monkeypatch.setattr(pu, "load_credentials", lambda *_: CREDS)
    class NotTerminal:
        def isatty(self):
            return False
    monkeypatch.setattr(pu.sys, "stdin", NotTerminal())
    assert pu.main(["--source-dir", str(samples), "--model", "matrice4t",
                    "--apply"]) == 1
    assert "interactive_confirmation_required" in capsys.readouterr().err
