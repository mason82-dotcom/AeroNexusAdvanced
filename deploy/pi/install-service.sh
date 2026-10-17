#!/usr/bin/env bash
# Install/refresh the systemd *user* service (no sudo; boot start needs linger).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT="$UNIT_DIR/aeronexusadvanced.service"
case "$ROOT" in *[!A-Za-z0-9/._-]*) printf 'Unsupported characters in %s\n' "$ROOT" >&2; exit 2;; esac
mkdir -p "$UNIT_DIR"
sed "s#@ROOT@#$ROOT#g" "$ROOT/deploy/pi/aeronexusadvanced.service.in" > "$UNIT.tmp"
mv "$UNIT.tmp" "$UNIT"
SYNC_UNIT="$UNIT_DIR/aeronexusadvanced-media-sync.service"
sed "s#@ROOT@#$ROOT#g" "$ROOT/deploy/pi/aeronexusadvanced-media-sync.service.in" > "$SYNC_UNIT.tmp"
mv "$SYNC_UNIT.tmp" "$SYNC_UNIT"
systemctl --user daemon-reload
systemctl --user enable aeronexusadvanced.service >/dev/null
systemctl --user enable aeronexusadvanced-media-sync.service >/dev/null
printf 'Installed %s and %s\n' "$UNIT" "$SYNC_UNIT"
if [[ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != yes ]]; then
  printf 'NOTE: linger is off; the service starts only after login. Enable: loginctl enable-linger %s\n' "$USER"
fi
printf 'Start/restart: systemctl --user restart aeronexusadvanced aeronexusadvanced-media-sync\nLogs: journalctl --user -u aeronexusadvanced -u aeronexusadvanced-media-sync -f\n'
