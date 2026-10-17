#!/usr/bin/env python3
"""Create a least-privilege MinIO reader for AeroNexusAdvanced (one-time, explicit).

Uses the existing *local* cloud-server root identity only for provisioning.
Never prints, persists or sends administrator secrets outside localhost.
A private temporary MC_CONFIG_DIR prevents saving administrator credentials
in ~/.mc. Only an explicitly scoped read-only MinIO user and the private
gateway .env are changed. Does not modify media objects or the Docker stack.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import quote


def _ensure_private_env(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Private environment file missing or symlinked")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise RuntimeError("Gateway .env must have mode 0600")


def configure(root: Path, mc_binary: str) -> str:
    # python-dotenv is a dependency of the gateway; preserve .env formatting.
    from dotenv import dotenv_values

    main_env = root / ".env"
    cloud_env = root / "cloud-server/edge/.env"
    _ensure_private_env(main_env)
    _ensure_private_env(cloud_env)
    current = dotenv_values(main_env)
    keys = ("AERONEXUS_MINIO_ENDPOINT", "AERONEXUS_MINIO_BUCKET",
            "AERONEXUS_MINIO_ACCESS_KEY", "AERONEXUS_MINIO_SECRET_KEY")
    if any(current.get(key) for key in keys):
        raise RuntimeError("Gateway MinIO settings already exist; refusing to overwrite")

    cloud = dotenv_values(cloud_env)
    admin = cloud.get("MINIO_ROOT_USER")
    admin_secret = cloud.get("MINIO_ROOT_PASSWORD")
    bucket = cloud.get("MINIO_BUCKET")
    if not admin or not admin_secret or bucket != "dji-cloud":
        raise RuntimeError("Expected MinIO administrator credentials and dji-cloud bucket missing")

    # Unique names eliminate accidental overwrite of existing MinIO IAM data.
    username = "anxmedia" + secrets.token_hex(6)
    password = secrets.token_urlsafe(40)
    policy_name = "anx-dji-read-" + secrets.token_hex(7)
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow",
             "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
             "Resource": ["arn:aws:s3:::dji-cloud"]},
            {"Effect": "Allow",
             "Action": ["s3:GetObject"],
             "Resource": ["arn:aws:s3:::dji-cloud/*"]},
        ],
    }
    with tempfile.TemporaryDirectory(prefix="anx-minio-setup-") as tmp:
        os.chmod(tmp, 0o700)
        policy_path = Path(tmp) / "policy.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        os.chmod(policy_path, 0o600)

        env = dict(os.environ)
        env["MC_CONFIG_DIR"] = tmp
        # Temporary in-memory MinIO client alias; no credentials on disk
        # and none written into command argument strings or shell history.
        env["MC_HOST_anxadmin"] = (
            "http://" + quote(admin, safe="") + ":" +
            quote(admin_secret, safe="") + "@127.0.0.1:9000"
        )
        env["MC_QUIET"] = "1"
        env["MC_NO_COLOR"] = "1"

        def run_mc(step: str, *args: str) -> None:
            try:
                result = subprocess.run(
                    [mc_binary, *args], env=env, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, check=False, timeout=35,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise RuntimeError(f"MinIO admin step '{step}' failed") from exc
            if result.returncode:
                raise RuntimeError(f"MinIO admin step '{step}' failed")

        run_mc("policy-create", "admin", "policy", "create",
               "anxadmin", policy_name, str(policy_path))
        # Only the newly generated *reader* secret occurs in these argv values.
        # It is never logged or printed.
        run_mc("user-add", "admin", "user", "add",
               "anxadmin", username, password)
        run_mc("policy-attach", "admin", "policy", "attach",
               "anxadmin", policy_name, "--user", username)

    # Validate that the newly-created user can list and HEAD objects.
    # No S3 writes are performed at any time.
    try:
        from minio import Minio
        client = Minio("127.0.0.1:9000", access_key=username,
                       secret_key=password, secure=False)
        first = next(iter(client.list_objects("dji-cloud", recursive=True)), None)
        if first is not None:
            client.stat_object("dji-cloud", first.object_name)
    except Exception as exc:
        raise RuntimeError("Reader account verification failed; .env left unchanged") from exc

    # Append only once, preserving contents, owner and mode of the current .env.
    # The generated secrets are URL-safe, with no shell metacharacters.
    new_lines = (
        "\n# Read-only DJI MinIO catalogue (Phase 21)\n"
        "AERONEXUS_MINIO_ENDPOINT=http://127.0.0.1:9000\n"
        "AERONEXUS_MINIO_BUCKET=dji-cloud\n"
        f"AERONEXUS_MINIO_ACCESS_KEY={username}\n"
        f"AERONEXUS_MINIO_SECRET_KEY={password}\n"
    ).encode("utf-8")
    _ensure_private_env(main_env)
    flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(main_env, flags)
    try:
        os.write(fd, new_lines)
        os.fsync(fd)
    finally:
        os.close(fd)

    return "Read-only MinIO credentials configured; restart gateway service"


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    mc = shutil.which("mc")
    if mc is None:
        candidate = Path.home() / "minio-binaries/mc"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            mc = str(candidate)
    if mc is None:
        print("Official MinIO mc client missing (install ARM64 binary first)")
        return 1
    try:
        print(configure(root, mc))
    except RuntimeError as exc:
        print(f"MinIO setup stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
