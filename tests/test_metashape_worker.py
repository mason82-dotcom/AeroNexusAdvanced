"""Standalone worker contract, without installing or activating Metashape."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from aeronexus import metashape_bridge as bridge
from aeronexus import metashape_worker as worker
from test_metashape_bridge import CAPTURES, ortho


@pytest.fixture
def job(ortho, tmp_path):
    info = bridge.prepare_package(ortho, CAPTURES, "rgb")
    root = tmp_path / "job"
    with ZipFile(bridge.package_path(ortho, info["id"])) as archive:
        archive.extractall(root)
    return root


def test_changed_original_is_detected_before_engine_import(job):
    manifest = worker.validate_job(job)
    image = job / manifest["files"][0]["path"]
    image.write_bytes(b"x" * image.stat().st_size)
    with pytest.raises(worker.JobError, match="checksum"):
        worker.validate_job(job)


@pytest.mark.parametrize("mutation", ["path", "duplicate", "missing", "capture", "id"])
def test_manifest_cannot_escape_or_mix_captures(job, mutation):
    path = job / "manifest.json"
    manifest = json.loads(path.read_text())
    if mutation == "path":
        manifest["files"][0]["path"] = "../../outside.JPG"
    elif mutation == "duplicate":
        manifest["files"][1] = manifest["files"][0]
    elif mutation == "missing":
        manifest["files"].pop()
    elif mutation == "capture":
        manifest["files"][0]["capture_uuid"] = CAPTURES[1]
    else:
        manifest["id"] = "../../escape"
    path.write_text(json.dumps(manifest))
    with pytest.raises(worker.JobError):
        worker.validate_job(job)


def test_symlinked_input_is_refused(job, tmp_path):
    manifest = worker.validate_job(job)
    image = job / manifest["files"][0]["path"]
    other = tmp_path / "other.jpg"
    image.rename(other)
    image.symlink_to(other)
    with pytest.raises(worker.JobError, match="Symlink"):
        worker.validate_job(job)


def test_upstream_is_checked_before_execution(tmp_path, monkeypatch):
    root = tmp_path / "upstream"
    (root / "pipeline").mkdir(parents=True)
    blobs = {}
    for name in worker.UPSTREAM_BLOBS:
        source = b"raise RuntimeError('must not execute while verifying')\n"
        (root / name).write_bytes(source)
        blobs[name] = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
    monkeypatch.setattr(worker, "UPSTREAM_BLOBS", blobs)
    assert len(worker.upstream_sources(root)) == 2
    (root / "pipeline/utils.py").write_text("print('changed')")
    with pytest.raises(worker.JobError, match="pinned commit"):
        worker.upstream_sources(root)


def test_worker_check_does_not_start_processing(job, tmp_path, monkeypatch, capsys):
    engine = SimpleNamespace(app=SimpleNamespace(activated=True, enumGPUDevices=lambda: []))
    monkeypatch.setattr(worker, "upstream_sources", lambda root: {})
    monkeypatch.setattr(worker.importlib, "import_module", lambda name: engine if name == "Metashape" else object())
    monkeypatch.setattr(worker, "load_processor", lambda sources: pytest.fail("check started processing"))
    assert worker.main(["--job", str(job), "--upstream", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["ready"] is True
    assert engine.app.gpu_mask == 0 and engine.app.cpu_enable is True
    assert not (job / "results").exists()
    engine.app.activated = False
    assert worker.main(["--job", str(job), "--upstream", str(tmp_path)]) == 1
    assert not (job / "results").exists()


def test_gpu_selection_validates_available_devices():
    engine = SimpleNamespace(app=SimpleNamespace(enumGPUDevices=lambda: ["gpu0", "gpu1", "gpu2"]))
    worker.configure_device(engine, "all")
    assert engine.app.gpu_mask == 7
    engine.app.enumGPUDevices = lambda: []
    with pytest.raises(worker.JobError):
        worker.configure_device(engine, "0")
    worker.configure_device(engine, "cpu")
    assert engine.app.gpu_mask == 0


def fake_processor(*, fail=False, aligned=True):
    stages = []

    class Project:
        def __init__(self, path):
            self.project_path = path
            self.doc = SimpleNamespace(save=lambda p: Path(p).write_text("test project"))

        def add_chunk(self, name, photos):
            return SimpleNamespace(label=name, cameras=[SimpleNamespace(transform=1 if aligned else None,
                                   reference=SimpleNamespace(location=[49, 8, 100], enabled=True)) for p in photos],
                                   crs="EPSG::4326", transform=SimpleNamespace(scale=1))

    class Processor:
        def __init__(self, chunk):
            self.chunk = chunk

        def __getattr__(self, stage):
            if stage == "export_raster":
                def export(folder):
                    stages.append(stage)
                    Path(folder, self.chunk.label + "_orthomosaic.tif").write_bytes(b"II*\0FAKE_TIFF")
                return export

            def step():
                stages.append(stage)
                if fail and stage == "build_depth_maps":
                    raise RuntimeError("synthetic engine failure")
            return step

    return SimpleNamespace(MetashapeProject=Project, MetashapeChunkProcessor=Processor), stages


def test_pipeline_calls_upstream_stages_without_moving_originals(job):
    manifest = worker.validate_job(job)
    before = {r["path"]: worker.file_hash(job / r["path"]) for r in manifest["files"]}
    processor, stages = fake_processor()
    result = worker.run_job(job, manifest, object(), processor)
    assert result["status"] == "completed" and result["outputs"][0]["cog_validated"] is False
    assert stages == ["align_photos", "build_depth_maps", "build_model", "build_point_cloud",
                      "smooth_model", "build_orthomosaic", "export_raster"]
    assert before == {r["path"]: worker.file_hash(job / r["path"]) for r in manifest["files"]}
    with pytest.raises(FileExistsError):
        worker.run_job(job, manifest, object(), processor)


@pytest.mark.parametrize("failure", ["engine", "alignment"])
def test_partial_failures_are_never_reported_as_completed(job, failure):
    processor, stages = fake_processor(fail=failure == "engine", aligned=failure != "alignment")
    with pytest.raises((RuntimeError, worker.JobError)):
        worker.run_job(job, worker.validate_job(job), object(), processor)
    report = json.loads((job / "results/results.json").read_text())
    assert report["status"] == "failed" and report["outputs"] == []
    assert "export_raster" not in stages
