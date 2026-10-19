# DJI WPML 1.0.2 – zusätzliche Heading-/Turn-Einstellungen (Offline-Prototyp)

Stand: 19.10.2026. Quelle: [DJI WPML Common Elements](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html).

**Nur Entwicklung im Draft-PR.** Weder DJI Pilot 2 noch Matrice-4-Firmware
wurden für die neuen Einstellungen real getestet. Kein Cloud-Upload,
kein Drohnensteuerungsaufruf, keine automatische Bereitstellung.

## Ausdrücklich unterstützte Optionswerte

| Feld in `WaypointMission` | Wert | Wirkung |
| --- | --- | --- |
| `heading_mode` | `followWayline` | Vorhandene Standard-Flugrichtung, unverändertes XML |
| `heading_mode` | `smoothTransition` | Explizite individuelle Winkel pro Wegpunkt |
| `heading_path_mode` | `clockwise`, `counterClockwise`, `followBadArc` | Rotationsweg des Yaw, nur zusammen mit `smoothTransition` |
| `turn_mode` | `toPointAndStopWithDiscontinuityCurvature` | Vorhandener Standard: gerader Anflug mit Stopp |
| `turn_mode` | `toPointAndStopWithContinuityCurvature` | Kontinuierlicher Kurvenanflug **mit Stopp**, niemals Durchflug |
| `waypoints[].heading_angle_deg` | -180 bis 180° | Muss bei `smoothTransition` an **jedem** Wegpunkt stehen |

Kanonische Implementierung:
- `template.kml`: bei neuem Winkelmodus wird `useGlobalHeadingParam=0`
  und ein eigener `waypointHeadingParam` am jeweiligen Wegpunkt geschrieben;
  `globalWaypointTurnMode` trägt den expliziten Kurvenmodus.
- `waylines.wpml`: die entsprechenden Wegpunkt-Heading-/Turn-Parameter
  werden explizit geschrieben.
- Der Import vergleicht weiterhin beide XML-Dokumente vollständig mit
  kanonisch neu exportierten Dokumenten. Abweichungen werden abgewiesen.
- Bei unveränderten Standardeinstellungen bleiben die alten WPML-Elemente
  und die bisherige JSON-Ausgabeform erhalten.

## Nicht freigegeben

Die übrigen Modi (`fixed`, `manually`, `towardPOI`,
`coordinateTurn`, `toPointAndPassWithContinuityCurvature`) und
`waypointTurnDampingDist > 0` bleiben außerhalb des unterstützten
Datenmodells. Der Übergang mit Dämpfungsabstand würde zusätzlich
Abstand und Summe der Kurvenabschnitte je Segment erfordern.
Auch bei `close_route=true` werden manuell vorgegebene Heading-Winkel
nicht stillschweigend auf den automatisch erzeugten Rückkehrpunkt kopiert:
die Kombination wird abgewiesen.

**Keine Flugfreigabe:** Eine bestandene KMZ-Export- und Reimportprüfung
beweist ausschließlich, dass die geplanten WPML-Parameter beim
AeroNexus-Roundtrip nicht verloren gehen. Ein Pilot-2-Importtest und
ein kontrollierter gerätespezifischer Review sind vor Verwendung nötig.

## Offline-Test auf dem Pi

```bash
cd ~/Projekte/AeroNexusAdvanced-wpml-heading-turn
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" \
  "$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" \
  -m pytest -q -p no:cacheprovider \
  tests/test_wpml_heading_turn.py \
  tests/test_wpml_export.py \
  tests/test_wpml_conformance.py \
  tests/test_studio_api.py
```

*Im bestehenden Produktionscheckout keine Konfigurationsänderungen vornehmen
und den Dienst nicht neu starten.*
