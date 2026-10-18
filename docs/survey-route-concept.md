# Schematische Verbindungen und Zeitabschätzung (nur Vorschau)

## Status

**Entwicklungsvorschau; keine flugfähige Mission.** Die Funktion erweitert
`POST /api/v1/studio/survey/preview` nur bei einer expliziten
`route`-Option. Ohne `route` ist die bisherige API-Antwort byte-/strukturgleich.
Kein Missionsspeichern, WPML-/KMZ-Export, DJI-SDK-Aufruf oder Flugkommando.
Mission Studio zeigt unverändert OpenStreetMap als Startkarte.

Die schon vorhandenen abwechselnd orientierten und an das Polygon geclippten
Messstreifen werden NICHT neu sortiert. Ein schematischer Verbindungsstrich
wird zwischen dem Endpunkt eines Streifens und dem Anfang des nächsten
gezeichnet. Diese geraden Verbindungen sind **keine** Kurven,
Drehkreisplanung oder hindernisfreien Flugwege. Insbesondere können sie
das Polygon verlassen oder Hindernisse überqueren. Sie haben
`clearance_verified=false`; der gesamte Entwurf ist
`mission_ready=false`.

## Optionen

In **Geo & Gelände** die neue Checkbox „Schematische Wegpunkt- und
Verbindungsstrecken anzeigen“ aktivieren und unter dem bestehenden Polygon
optional eine DJI-Kamera wählen.

| Option | Standard | Bereich |
| --- | ---: | ---: |
| `route.speed_mps` | 5 m/s | 1–15 m/s |
| `route.turn_delay_s` | 5 s | 0–60 s |

Andere, negative oder nichtendliche Werte weist das API-Modell ab.

Beispiel-Payload (synthetisch, kein Flugauftrag):

```json
{
  "polygon": {
    "name": "Testpolygon",
    "kind": "polygon",
    "vertices": [
      {"latitude": 49.1533, "longitude": 8.5840},
      {"latitude": 49.1533, "longitude": 8.5849},
      {"latitude": 49.1541, "longitude": 8.5849},
      {"latitude": 49.1541, "longitude": 8.5840}
    ]
  },
  "spacing_m": 20,
  "bearing_deg": 0,
  "route": {"speed_mps": 5, "turn_delay_s": 5}
}
```

Mit `route` enthält die Antwort zusätzlich `route_preview`:
schematische nummerierte Streifen-Anfangs-/Endpunkte,
ungeprüfte Verbindungslinien, getrennte Streifen- und
Verbindungslängen sowie die geschätzte Zeit.

Formel:

```text
Zeit_s = ceil((Messstreifen_m + Verbindungen_m) / Geschwindigkeit_m_s
              + Anzahl_Verbindungen × Rechenpause_s)
```

Die Streifenlänge stammt aus der bestehenden lokalen
Tangentialebenenberechnung, Verbindungen aus der entsprechenden lokalen
Ebenennäherung. Die Zeit ist keine Akkureichweiten- oder Flugdauerfreigabe.
Start/Landung, Steig-/Sinkflug, Kurvendynamik, Hindernisse, GPS-/Winddrift,
Kameraverschluss, Return-to-Home und Sicherheitsreserve fehlen.
Es wird weder eine tatsächlich fliegbare Wende- noch eine Kollisionsfreiheit
behauptet.

Die schematischen Verbindungslinien werden in Lila gestrichelt dargestellt,
Messstreifen weiterhin Orange. Ein erneutes Berechnen ohne Checkbox
entfernt die Verbindungslinien. Ein aktivierter Kameramodus bleibt opt-in.

## Qualitätsprüfung

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_survey_route_preview.py \
  tests/test_survey_camera.py \
  tests/test_survey_planning_regression.py \
  tests/test_map_street_defaults.py
```

Tests benötigen ausschließlich synthetische Polygone,
verändern keine Benutzer-Missionen und verbinden sich nicht mit DJI.
Der neue PR bleibt bis zu isolierten Chromium-/Pi-Prüfungen ein Draft.
