#!/usr/bin/env bash
# Phase 17 Pi readiness check. Read-only: no git pull, service restart,
# DJI requests, mission writes, dotenv evaluation, or production file changes.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
PY="${PHASE17_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  printf 'ERROR: Python venv fehlt: %s\n' "$PY" >&2
  exit 2
fi

printf '\n=== AeroNexusAdvanced Phase 17 · Pi Diagnose ===\n'
printf 'Projekt: %s\n' "$ROOT"
printf 'Git SHA: '
git rev-parse --short HEAD
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo 'HINWEIS: Es gibt lokale Änderungen an verfolgten Dateien. Nichts wird überschrieben.'
fi

printf '\n[1/5] Python / Dependencies\n'
"$PY" --version
"$PY" -m pip check

printf '\n[2/5] Isolierte Phase-17-Tests (ohne produktive .env-Daten)\n'
"$PY" -m pytest -q \
  tests/test_geo_preview.py tests/test_geo_api.py \
  tests/test_studio_events.py tests/test_studio_page.py \
  tests/test_frontend_javascript.py

printf '\n[3/5] GDAL + NumPy im *selben* Python prüfen\n'
"$PY" - <<'PY'
import importlib
for name in ("osgeo.gdal", "numpy"):
    try:
        m = importlib.import_module(name)
        print(f"{name}: OK | version={getattr(m, '__version__', 'n/a')}")
    except (ImportError, RuntimeError) as exc:
        print(f"{name}: NICHT VERFÜGBAR ({type(exc).__name__})")
        print("  GeoTIFF-Import bleibt optional/deaktiviert, bis GDAL+NumPy zur venv passen.")
PY

printf '\n[4/5] Dienststatus (keine Änderungen)\n'
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user is-active aeronexusadvanced || true
else
  echo 'systemctl nicht verfügbar'
fi

printf '\n[5/5] Optionale TLS-LAN-Prüfung\n'
if [[ "${PHASE17_CHECK_LIVE:-0}" != "1" ]]; then
  echo 'Übersprungen. Aktivieren mit: PHASE17_CHECK_LIVE=1 bash scripts/pi/phase17-smoke.sh'
else
  HOST="${PHASE17_LAN_HOST:-192.168.178.63}"
  PORT="${PHASE17_LAN_PORT:-8000}"
  if [[ ! "$HOST" =~ ^[0-9.]+$ || ! "$PORT" =~ ^[0-9]{1,5}$ ]]; then
    echo 'Ungültiger Pi-Host oder Port' >&2
    exit 2
  fi
  CA="$ROOT/config/pki/ca.crt"
  if [[ ! -r "$CA" ]]; then
    echo "Fehlende lokale CA: $CA" >&2
    exit 3
  fi
  BASE="https://${HOST}:${PORT}"
  echo 'HTTPS /health (Zertifikatsprüfung mit Projekt-CA):'
  curl --fail --silent --show-error --max-time 10 --cacert "$CA" "$BASE/health"
  echo
  echo 'HTTPS /studio (nur statische HTML-Seite, keine DJI-Daten):'
  BODY="$(curl --fail --silent --show-error --max-time 10 --cacert "$CA" "$BASE/studio")"
  if [[ "$BODY" == *'id="geo-panel"'* && "$BODY" == *'id="terrain-canvas"'* && "$BODY" == *'id="geophoto-media"'* ]]; then
    echo 'OK: Phase-17-UI in laufender Version gefunden'
  else
    echo 'FEHLER: Der laufende Dienst liefert noch nicht die Phase-17-Oberfläche.' >&2
    exit 4
  fi
fi

printf '\nAbgeschlossen: keine Konfigurations-/Dienst-/DJI-Änderungen vorgenommen.\n'
