#!/usr/bin/env python3
"""Allow the existing AeroNexusAdvanced MinIO reader to subscribe to bucket events.

One-time and explicit. Adds a *separate* minimal policy that only grants
``s3:ListenBucketNotification`` on ``dji-cloud`` and attaches it to the reader
user configured in the private gateway ``.env``. The existing read policy is
not modified; no write, delete or admin rights are granted.

The local cloud-server root identity (``cloud-server/edge/.env``) is used only
for this provisioning call against 127.0.0.1 and is never printed or stored.
"""
from __future__ import annotations

from pathlib import Path
import secrets
import stat
import sys
import threading


POLICY_PREFIX = "anx-dji-listen-"


def _private(path: Path) -> None:
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise RuntimeError(f"{path.name} must be a private 0600 file")


def listen_allowed(endpoint: str, access_key: str, secret_key: str, bucket: str,
                   *, seconds: float = 4.0) -> bool:
    """True when the reader can open the notification stream (no event needed)."""
    from minio import Minio
    client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
    outcome: dict = {}

    def run() -> None:
        try:
            with client.listen_bucket_notification(bucket, events=["s3:ObjectCreated:*"]) as events:
                for _ in events:
                    break
            outcome["ok"] = True
        except Exception as exc:  # AccessDenied arrives as an S3Error from the stream
            outcome["error"] = type(exc).__name__

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(seconds)
    return thread.is_alive() or outcome.get("ok", False)  # still streaming = allowed


def grant(root: Path) -> str:
    from dotenv import dotenv_values
    from minio.credentials import StaticProvider
    from minio.minioadmin import MinioAdmin

    gateway_env, cloud_env = root / ".env", root / "cloud-server/edge/.env"
    _private(gateway_env)
    _private(cloud_env)
    gateway, cloud = dotenv_values(gateway_env), dotenv_values(cloud_env)
    reader = gateway.get("AERONEXUS_MINIO_ACCESS_KEY")
    reader_secret = gateway.get("AERONEXUS_MINIO_SECRET_KEY")
    bucket = gateway.get("AERONEXUS_MINIO_BUCKET") or "dji-cloud"
    if not reader or not reader_secret or bucket != "dji-cloud":
        raise RuntimeError("Gateway MinIO reader is not configured (run configure_minio_readonly.py)")
    if listen_allowed("127.0.0.1:9000", reader, reader_secret, bucket):
        return "Reader can already listen for bucket events; nothing changed"
    admin, admin_secret = cloud.get("MINIO_ROOT_USER"), cloud.get("MINIO_ROOT_PASSWORD")
    if not admin or not admin_secret or cloud.get("MINIO_BUCKET") != bucket:
        raise RuntimeError("Local MinIO administrator credentials missing")

    name = POLICY_PREFIX + secrets.token_hex(6)
    policy = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["s3:ListenBucketNotification"],
         "Resource": [f"arn:aws:s3:::{bucket}"]}]}
    try:
        admin_client = MinioAdmin(endpoint="127.0.0.1:9000",
                                  credentials=StaticProvider(admin, admin_secret), secure=False)
        admin_client.policy_add(name, policy=policy)
        admin_client.attach_policy([name], user=reader)
    except Exception as exc:  # never echo responses that could contain identities
        raise RuntimeError("MinIO admin request failed (policy not attached)") from exc
    if not listen_allowed("127.0.0.1:9000", reader, reader_secret, bucket):
        raise RuntimeError("Policy attached but listening is still denied")
    return f"Listen policy {name} attached to the reader; restart the media watcher"


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    try:
        print(grant(root))
        return 0
    except (RuntimeError, OSError) as exc:
        print("MinIO listen setup failed: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

