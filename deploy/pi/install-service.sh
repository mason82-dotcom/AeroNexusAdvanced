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
systemctl --user daemon-reload
systemctl --user enable aeronexusadvanced.service >/dev/null
printf 'Installed %s\n' "$UNIT"
if [[ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != yes ]]; then
  printf 'NOTE: linger is off; the service starts only after login. Enable: loginctl enable-linger %s\n' "$USER"
fi
printf 'Start/restart: systemctl --user restart aeronexusadvanced\nLogs: journalctl --user -u aeronexusadvanced -f\n'
