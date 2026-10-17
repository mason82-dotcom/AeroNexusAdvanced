"""Standalone worker bundled with an AeroNexus Metashape export.

This file uses only the standard library until an explicitly requested worker
check/run. GeoSense's processor is installed separately and verified before use.
It is deliberately not run through main.py/process_folders: those move inputs,
rename folders, and can report success even after a processing failure.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
import types


SCHEMA = "aeronexus.metashape-job/v1"
UPSTREAM_URL = "https://github.com/GeoSense-Freiburg/metashape_ortho"
UPSTREAM_COMMIT = "101bc4e235982b34b3607eb035d84cc2448491ea"
UPSTREAM_BLOBS = {
    "pipeline/utils.py": "56cb171290772bc584d9045f69a935445a759bcd",
    "pipeline/metashape_processor.py": "4529adb7c55d30be7d4202894edb41d0652e786f",
}
CHANNELS = {"rgb": ("RGB",), "multispectral": ("G", "R", "RE", "NIR")}
MAX_CAPTURES = 100
MAX_BYTES = 4 * 1024 ** 3
MAX_FILE_BYTES = 64 * 1024 ** 2
PHOTO_DIR = "input/aeronexus_unprocessed/photos/flight"
_UUID = re.compile(r"[0-9a-f]{32}\Z")


class JobError(ValueError):
    pass


def photo_name(capture_uuid: str, channel: str) -> str:
    if not isinstance(capture_uuid, str) or not _UUID.fullmatch(capture_uuid):
        raise JobError("Invalid capture identifier")
    if channel not in ("RGB", "G", "R", "RE", "NIR"):
        raise JobError("Invalid channel")
    suffix = "_D.JPG" if channel == "RGB" else f"_MS_{channel}.TIF"
    return f"{PHOTO_DIR}/DJI_{capture_uuid}{suffix}"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def _regular(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or any(p in ("", ".", "..") for p in relative.split("/")):
        raise JobError("Invalid job path")
    current = root
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink():
            raise JobError("Symlinked job content refused")
    if not path.is_file():
        raise JobError("Job file missing")
    return path


def validate_job(root: Path) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise JobError("Job must be an extracted directory, not a symlink")
    manifest_path = _regular(root, "manifest.json")
    if manifest_path.stat().st_size > 512 * 1024:
        raise JobError("Manifest too large")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise JobError("Unsupported job schema")
    if not isinstance(manifest.get("id"), str) or not _UUID.fullmatch(manifest["id"]):
        raise JobError("Invalid job identifier")
    mode = manifest.get("mode")
    if mode not in CHANNELS:
        raise JobError("Unsupported job mode")
    captures, records = manifest.get("capture_uuids"), manifest.get("files")
    if (not isinstance(captures, list) or not 3 <= len(captures) <= MAX_CAPTURES
            or any(not isinstance(c, str) or not _UUID.fullmatch(c) for c in captures)
            or len(set(captures)) != len(captures) or not isinstance(records, list)):
        raise JobError("A job requires 3–100 distinct captures")
    expected = {photo_name(c, ch) for c in captures for ch in CHANNELS[mode]}
    if len(records) != len(expected):
        raise JobError("Job file set incomplete")
    seen, total = set(), 0
    for record in records:
        if not isinstance(record, dict):
            raise JobError("Invalid file record")
        relative = record.get("path")
        if not isinstance(relative, str) or relative not in expected or relative in seen:
            raise JobError("Unexpected or duplicate input file")
        seen.add(relative)
        if (record.get("capture_uuid") not in captures or record.get("channel") not in CHANNELS[mode]
                or relative != photo_name(record["capture_uuid"], record["channel"])):
            raise JobError("Input capture/channel mismatch")
        path = _regular(root, relative)
        size = path.stat().st_size
        if not 0 < size <= MAX_FILE_BYTES or size != record.get("size_bytes"):
            raise JobError("Input size mismatch")
        total += size
        if total > MAX_BYTES:
            raise JobError("Job exceeds 4 GiB")
        if file_hash(path) != record.get("sha256"):
            raise JobError("Input checksum mismatch")
    return manifest


def upstream_sources(root: Path) -> dict[str, bytes]:
    """Verify source bytes before executing any upstream code (no .pyc loading)."""
    sources = {}
    for name, expected in UPSTREAM_BLOBS.items():
        path = _regular(root, name)
        if path.stat().st_size > 128 * 1024:
            raise JobError("Unexpected upstream source size")
        source = path.read_bytes().replace(b"\r\n", b"\n")
        blob = b"blob " + str(len(source)).encode("ascii") + b"\0" + source
        if hashlib.sha1(blob).hexdigest() != expected:
            raise JobError("Upstream source differs from pinned commit " + UPSTREAM_COMMIT)
        sources[name] = source
    return sources


def load_processor(sources: dict[str, bytes]):
    # Compile the verified source, avoiding upstream __init__.py and cached
    # bytecode. No source code or commercial module is downloaded automatically.
    package = types.ModuleType("pipeline")
    package.__path__ = []
    sys.modules["pipeline"] = package
    for name in ("utils", "metashape_processor"):
        key = f"pipeline/{name}.py"
        module = types.ModuleType("pipeline." + name)
        sys.modules[module.__name__] = module
        exec(compile(sources[key], key, "exec"), module.__dict__)
    return sys.modules["pipeline.metashape_processor"]


def configure_device(ms, gpu: str) -> None:
    devices = ms.app.enumGPUDevices()
    if gpu == "cpu":
        mask = 0
    elif gpu == "all":
        if not devices:
            raise JobError("No GPU available; use --gpu cpu")
        mask = (1 << len(devices)) - 1
    else:
        index = int(gpu)
        if index >= len(devices):
            raise JobError("Selected GPU unavailable")
        mask = 1 << index
    ms.app.gpu_mask = mask
    ms.app.cpu_enable = True


def run_job(root: Path, manifest: dict, ms, processor, *, output_name: str = "results") -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", output_name) or output_name in ("input", "pipeline"):
        raise JobError("Invalid results directory name")
    output = root / output_name
    output.mkdir(mode=0o700, exist_ok=False)
    results = {"schema": "aeronexus.metashape-results/v1", "status": "running",
               "source_job": manifest["id"], "mode": manifest["mode"],
               "upstream_commit": UPSTREAM_COMMIT, "outputs": [],
               "radiometry": "uncalibrated_dn" if manifest["mode"] == "multispectral" else "rgb",
               "warning": "Independent band mosaics are not co-registered reflectance or NDVI products."}
    try:
        with (output / "worker.log").open("x", encoding="utf-8") as log:
            with redirect_stdout(log), redirect_stderr(log):
                for channel in CHANNELS[manifest["mode"]]:
                    project = processor.MetashapeProject(str(output / f"{channel}.psx"))
                    photos = [str(_regular(root, photo_name(c, channel))) for c in manifest["capture_uuids"]]
                    chunk = project.add_chunk("aeronexus_" + channel, photos)
                    stages = processor.MetashapeChunkProcessor(chunk)
                    # Save through Document, never the upstream save helper that
                    # removes lockfiles. Only new files under output are written.
                    project.doc.save(project.project_path)
                    stages.align_photos()
                    aligned = sum(c.transform is not None for c in chunk.cameras)
                    located = sum(c.transform is not None and c.reference.location is not None
                                  and c.reference.enabled for c in chunk.cameras)
                    if aligned < 3 or located < 3 or chunk.crs is None or chunk.transform.scale is None:
                        raise JobError("Insufficient aligned/georeferenced cameras in " + channel)
                    stages.build_depth_maps()
                    stages.build_model()
                    stages.build_point_cloud()
                    stages.smooth_model()
                    stages.build_orthomosaic()
                    stages.export_raster(str(output))
                    project.doc.save(project.project_path)
                    path = _regular(output, f"aeronexus_{channel}_orthomosaic.tif")
                    with path.open("rb") as stream:
                        magic = stream.read(4)
                    if magic not in (b"II*\0", b"MM\0*", b"II+\0", b"MM\0+"):
                        raise JobError("Worker did not export a TIFF")
                    results["outputs"].append({"path": f"{output_name}/{path.name}", "channel": channel,
                                               "size_bytes": path.stat().st_size, "sha256": file_hash(path),
                                               "format": "tiled_geotiff", "cog_validated": False})
        results["status"] = "completed"
    except Exception:
        results["status"] = "failed"
        raise
    finally:
        (output / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a copied AeroNexus job with separately installed Metashape")
    parser.add_argument("--job", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--upstream", type=Path, required=True, help="Pinned GeoSense metashape_ortho checkout")
    parser.add_argument("--gpu", choices=("cpu", "0", "1", "all"), default="cpu")
    parser.add_argument("--output", default="results", help="New directory name within job; never overwritten")
    parser.add_argument("--run", action="store_true", help="Explicitly start reconstruction; otherwise only check")
    args = parser.parse_args(argv)
    try:
        manifest = validate_job(args.job)
        sources = upstream_sources(args.upstream)
        importlib.import_module("yaml")
        ms = importlib.import_module("Metashape")
        if not getattr(ms.app, "activated", False):
            raise JobError("Metashape license is not activated")
        configure_device(ms, args.gpu)
        if not args.run:
            print(json.dumps({"ready": True, "captures": len(manifest["capture_uuids"]),
                              "mode": manifest["mode"], "gpu": args.gpu,
                              "upstream_commit": UPSTREAM_COMMIT}))
            return 0
        processor = load_processor(sources)
        print(json.dumps(run_job(args.job, manifest, ms, processor, output_name=args.output)))
        return 0
    except ImportError:
        print("Install the licensed Metashape Python module and PyYAML on the worker.", file=sys.stderr)
    except JobError as exc:
        print("Metashape job: " + str(exc), file=sys.stderr)
    except FileExistsError:
        print("Results directory already exists; use a new --output name for another attempt.", file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError):
        print("Metashape job failed validation or processing; check job inputs, license and results status.", file=sys.stderr)
    except Exception:
        print("Metashape processing failed; completed products are not guaranteed. Check results.json.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
