#!/usr/bin/env bash
# Start the AeroNexusAdvanced gateway (used by the systemd user service).
# Exit 2 = missing configuration, 3 = refused configuration (service does not loop).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$ROOT/.env"
PY="$ROOT/.venv/bin/python"
[[ -f "$ENV_FILE" ]] || { printf 'Missing %s (template: .env.example)\n' "$ENV_FILE" >&2; exit 2; }
[[ -x "$PY" ]] || { printf 'Missing virtualenv %s\n' "$PY" >&2; exit 2; }
if [[ "$(stat -c %a "$ENV_FILE")" != 600 ]]; then
  printf 'REFUSED: %s must be chmod 600 (contains credentials).\n' "$ENV_FILE" >&2
  exit 3
fi
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a
BIND="${AERONEXUS_BIND:-127.0.0.1}"
PORT="${AERONEXUS_PORT:-8000}"
ARGS=(-m uvicorn aeronexus.app:app --host "$BIND" --port "$PORT"
      --env-file "$ENV_FILE" --no-server-header)
if [[ -n "${AERONEXUS_TLS_CERT:-}" || -n "${AERONEXUS_TLS_KEY:-}" ]]; then
  for file in "${AERONEXUS_TLS_CERT:-}" "${AERONEXUS_TLS_KEY:-}"; do
    [[ -r "$file" ]] || { printf 'TLS file not readable: %s\n' "$file" >&2; exit 2; }
  done
  ARGS+=(--ssl-certfile "$AERONEXUS_TLS_CERT" --ssl-keyfile "$AERONEXUS_TLS_KEY")
elif [[ "$BIND" != 127.0.0.1 && "$BIND" != localhost && "${AERONEXUS_ALLOW_PLAIN_HTTP_LAN:-}" != 1 ]]; then
  printf 'REFUSED: %s is not loopback and no TLS is configured.\n' "$BIND" >&2
  printf 'Run deploy/pi/tls-create-cert.sh or set AERONEXUS_ALLOW_PLAIN_HTTP_LAN=1.\n' >&2
  exit 3
fi
cd "$ROOT"
exec "$PY" "${ARGS[@]}"
