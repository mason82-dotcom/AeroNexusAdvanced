# Optionale Kreisbogen-Wendeskizzen und Polygon-Austrittsdiagnose

**Status:** Nur 2D-Geometrieexperiment; ausdrücklich keine flugfähige DJI-Mission.

Der bisherige Survey-Endpunkt `POST /api/v1/studio/survey/preview` erhält
zusätzlich die optionale Eigenschaft `route.turn_radius_m` (2–30 m).
Bei fehlendem `route` oder fehlendem Radius bleibt die bestehende Antwort
unverändert; es gibt weder DJI-Flugbefehle noch Speichern von Missionen.

## Geometrisches Modell

Pro Verbindung zwischen zwei benachbarten Messstreifen wird eine
tangentiale Kreisabrundung an beiden Ecken des Streifenendes und des
nächsten Streifenanfangs versucht. Die Bögen ersetzen kleine Teile
der jeweiligen Geraden (mathematisches Fillet).

- Ein Radius von z. B. 5 m bedeutet **nicht**, dass die Drohne diesen Radius
  dynamisch, mit der eingestellten Geschwindigkeit, sicher fliegen kann.
- Wenn der Radius, die Winkel oder die Restlängen keine nicht überlappenden
  Bögen zulassen, wird `geometry_available=false` gesetzt und die
  unvollständige Bogen-Zeitschätzung unterdrückt.
- Bei erfolgreicher Konstruktion werden Bögen im Mission Studio in Türkis
  gestrichelt dargestellt. Wenn ein Bogen beim 2D-Schnitt mit dem
  gespeicherten Polygon außerhalb liegt, wird er rot markiert.
- Ein nicht konstruierbarer Bogen erhält statt erfundener Kurvendaten
  eine rote, **ungeeignete** gerade Skizze.
- Polygonprüfungen erfolgen gegen chordweise abgetastete Bögen in einer
  lokalen ebenen Koordinatennäherung. Die Diagnose ist **kein Beweis**
  für Kollisionsfreiheit, minimale Abstände oder vollständige Geländefreiheit.
  Insbesondere liegen nicht erfasste Hindernisse auch innerhalb des
  Polygons.

## Strecke und Zeit

Für konstruierbare Bögen werden abgezogene Tangentenstücke der
ursprünglichen Geraden berücksichtigt. Die für einen Bogenübergang
ersetzte Länge ergibt sich aus beiden Kreisbögen und dem verbleibenden
geraden Verbindungsteil. Erst wenn **alle** Übergänge geometrisch
darstellbar sind, werden `curve_total_distance_m` und
`estimated_duration_s` ausgegeben.

Die Zeit bleibt eine konstante-Reisegeschwindigkeit-Rechnung mit
einer willkürlichen Pause je Verbindung. Sie beinhaltet ausdrücklich
**nicht** Beschleunigung, Geschwindigkeit in Kurven, Steigen/Sinken,
Start/Landung, Return-to-Home, Wind, Akkuverbrauch oder Reserven.
Daher gibt es keine realistische Akku-/Restflugzeitfreigabe.
Akkuzustand und Hindernisse sind nicht auf diesem Endpunkt verfügbar.

Auf jeder Antwort mit `route.turn_radius_m` bleiben
`ready_for_flight`, `terrain_verified`, `obstacles_verified`,
`battery_verified` und `rth_verified` immer `false`.

## Erwarteter Prüfablauf

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_survey_turn_geometry.py \
  tests/test_survey_route_preview.py \
  tests/test_survey_route_chromium.py \
  tests/test_survey_camera.py
```

Alle Tests laufen mit synthetischen, lokalen Koordinaten. Weitere
isolierte Pi-Chromium-Tests vor einem Merge erforderlich. Während
der Entwicklung bleibt der produktive Raspberry-Pi-Dienst unverändert.

## Raspberry-Pi-Integrationstest (nur separater Staging-Server)

Nach erfolgreicher CI im isolierten PR-Worktree:

```bash
cd ~/Projekte/AeroNexusAdvanced-pr74
export AERONEXUS_CHROMIUM_BIN=/usr/bin/chromium
export AERONEXUS_LEAFLET_TEST_ASSETS="$HOME/.cache/aeronexusadvanced/leaflet-1.9.4"

PY="$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python"
PYTHONPATH=src "$PY" -m pytest -q \
  tests/test_survey_turn_geometry.py \
  tests/test_survey_turn_chromium.py \
  tests/test_survey_route_preview.py

~/Projekte/AeroNexusAdvanced-browser-venv/bin/python \
  scripts/pi/studio_camera_staging_smoke.py \
  --server-python "$PY" \
  --route-preview --turn-radius 5 --require-tiles \
  --screenshot /tmp/aeronexus-turn-geometry-staging.png
```

Browser-Staging startet eine gesonderte FastAPI-Instanz ausschließlich auf
`127.0.0.1:18081` mit synthetischem Polygon und leerem Missionsspeicher.
Die Screenshot-/Kachelprüfung behält die 95-%-Rasterabdeckungsgrenze.
Die Auswertung kontrolliert echte Leaflet-SVG-Linien und alle negativen
Freigabestatus: Flug, Gelände, Hindernisse, Akku und RTH.
Der produktive Port 8000 und DJI-Sitzungen werden nicht verändert.
