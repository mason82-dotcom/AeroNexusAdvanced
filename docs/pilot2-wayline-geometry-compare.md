# Pilot 2: lesender Wegpunktkoordinaten-Abgleich (Cloud API 1.18)

## Zweck und Grenzen

Das optionale CLI vergleicht zwei explizit ausgewählte UUIDs: eine lokal
gespeicherte AeroNexus-Studio-Mission und eine in der vollständig paginierten
Pilot-2-Cloud-Bibliothek nachgewiesene KMZ-Wayline. Beide Quellen bleiben
unverändert. Der Datenpfad nutzt ausschließlich die vorhandenen sicheren GET-
Adapter aus PR #45 (lokales DJI-Backend auf Loopback, signierte MinIO-URL über
festes Loopback-Socket); keine neue MQTT-Berechtigung, kein POST, keine
Missionausführung und keine Browser-Schreibfunktion.

**Wichtig:** Geprüft wird ausschließlich die geordnete Liste von
WGS84-Wegpunktkoordinaten, so wie AeroNexus sie auf sieben Nachkommastellen
in WPML exportiert. Nicht geprüft werden Höhe, Geschwindigkeit, RTK-Modus,
Kameraaktionen, RTH, Gimbal, Firmware, Gültigkeit und Flugfreigabe.
Darum bleiben die Felder full_content_verified und flight_compatibility_verified
in jedem Ergebnis false.

Ein passender Name allein gilt weiterhin nicht als Inhaltsnachweis.
Es erfolgt keine automatische Gleichsetzung in der globalen
/api/v1/studio/missions/reconciliation-API; dies ist ein bewusst manueller,
privater Abgleich, der keine Positionsdaten, Namen oder IDs ausgibt.

## Ausführung auf dem Raspberry Pi 5

Voraussetzungen: Code aus PR #45 einschließlich
pilot2_wayline_preview.py, private Pilot-2-Sitzung und Studio-Mission.

~~~bash
cd ~/Projekte/AeroNexusAdvanced
PYTHONPATH="$PWD/src" .venv/bin/python -m aeronexus.pilot2_wayline_compare \
  --mission '<STUDIO-UUID>' --wayline '<PILOT2-WAYLINE-UUID>'
~~~

UUIDs werden nicht in der CLI-Ausgabe ausgegeben. Sie können allerdings
in Shell-Historie und Prozessliste sichtbar sein: nur lokal in
vertrauenswürdiger Umgebung ausführen. Keine Tokens oder signierten URLs
in Chat-Ausgaben kopieren.

Beispielstruktur (synthetisch; kein Live-Nachweis):

~~~json
{
  "state": "connected",
  "geometry_result": "coordinates_equal",
  "model_match": true,
  "studio_point_count": 4,
  "cloud_point_count": 4,
  "cloud_feature_count": 1,
  "full_content_verified": false,
  "flight_compatibility_verified": false
}
~~~

Geometrie-Ergebnisse:

- coordinates_equal: eine einzelne Cloud-Wayline hat dieselben exportierten
  Wegpunktkoordinaten in derselben Reihenfolge.
- matching_segment_with_extras: mindestens ein passendes Segment, aber
  zusätzliche Cloud-Geometrien vorhanden; kein vollständiger Match.
- multipart_order_matches: mehrere Segmente ergeben hintereinander die
  geplante Koordinatenfolge; Segment-Ausführungssemantik ungeprüft.
- coordinates_different: kein identischer Wegpunktverlauf.
- model_conflict: Koordinaten gleich, aber andere Fluggeräte-Modellmetadaten.
- unsupported_geometry: etwa nur Kartenpolygon aus template.kml oder
  ungültige Geometrie.

model_match null bedeutet unbekanntes Cloud-Geräteprofil.
state connected bedeutet erfolgreiche Abfrage und nicht automatisch
inhaltliche Übereinstimmung.

Unvollständige Bibliothekslisten und unbekannte UUIDs verhindern einen
KMZ-Download. Fehler enthalten nur abstrakte Zustände. Es wird nichts
gespeichert oder konfiguriert.

## Tests

~~~bash
PYTHONPATH="$PWD/src" .venv/bin/python -m pytest -q \
  tests/test_pilot2_wayline_compare.py \
  tests/test_pilot2_wayline_preview.py
~~~

Alle Tests sind synthetisch beziehungsweise HTTP-gemockt. Ein realer,
kontrollierter Pi-Test ist separat nötig. Die bisher beobachteten
zwei Geometrie-Features je Pilot-2-KMZ werden nicht ungeprüft als eine
einzige ausgeführte Mission interpretiert.

## Cloud API 1.18, HMS und O4

DJI Cloud API 1.18 wurde am 13.10.2026 veröffentlicht. Die
O4-Ground-Station-Integration ist für AeroNexus ausdrücklich ausgeschlossen.
Dock-2-/Dock-3-Kameraeinstellungen und Dock-3-FTS sind keine
Pilot-2-Wayline-Funktionen für M3/M4.

Die dokumentierte HMS-MQTT-Eventfunktion (method=hms) gehört zu
Dock-to-Cloud. Eine Pilot-2-HMS-Subscription für Mavic 3 / Matrice 4 ist
damit nicht belegt. Es werden keine neuen Event-Subscriptions oder
automatischen Event-Antworten eingeführt.

Offizielle Referenzen:

- https://developer.dji.com/doc/cloud-api-tutorial/cn/
- https://developer.dji.com/doc/cloud-api-tutorial/en/feature-set/pilot-feature-set/pilot-wayline-management.html
- https://developer.dji.com/doc/cloud-api-tutorial/en/feature-set/dock-feature-set/hms.html
