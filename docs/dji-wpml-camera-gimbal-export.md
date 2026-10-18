# Offline Kamera-/Gimbalaktionen: aktuelle DJI-Cloud-API-WPML-Matrix

Grundlage: aktuelle Live-Dokumentation `Common Elements` (Stand: 2026-10-18)
https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html
und Modell-/Payload-IDs:
https://developer.dji.com/doc/cloud-api-tutorial/en/overview/product-support.html

**Nicht die alte archivierte GitHub-Master-Matrix verwenden**, da dort
die neuen Matrice-4-Modelle nicht vollständig aufgeführt sind.
Das offizielle DJI-Portal benennt die WPML-Aktionsparameter von
`M4E/M4T` und `M3E/M3T/M3M` ausdrücklich.

## Aktuell ergänzter, konservativer Offline-KMZ-Subset

- `takePhoto` (wie bisher)
- `startRecord`, `stopRecord`: Videoaufnahme starten/beenden;
  `startRecord` mit `fileSuffix` und Payload-Position
- `focus`: Punktfokus mit `isPointFocus=1`, normalisierten
  `focusX`, `focusY`, `isInfiniteFocus=0`
- `zoom`: `focalLength` (in mm, > 0; UI-Schranke höchstens 500)
- `gimbalRotate`: konservativer Pitch-Bereich [-90°,0°],
  andere Achsen deaktiviert, absolutes Koordinatensystem
- `gimbalEvenlyRotate`: Pitch-Drehung entlang des **folgenden**
  Wayline-Segments, Auslöser `betweenAdjacentPoints`.
  Nicht am letzten ausführbaren Wegpunkt erlaubt.

## Modellmatrix

| Projektprofil | WPML-Matrix | Zusatzaktionen lokal exportierbar |
| --- | --- | --- |
| Matrice 4E | M4E | Ja, mit Firmware-Vorbehalt |
| Matrice 4T | M4T | Ja, mit Firmware-Vorbehalt |
| Mavic 3E | M3E | Ja, mit Firmware-Vorbehalt |
| Mavic 3T | M3T | Ja, mit Firmware-Vorbehalt |
| Mavic 3M | M3M | Ja, mit Firmware-Vorbehalt |
| Mavic 3TA | nur Produkt-/Payload-Enum explizit, **nicht** die WPML-Aktionszeilen | Nein; Foto wie zuvor |

Eine namentlich vorhandene Aktion beweist **keine Unterstützung der ausgewählten
Kamera-/Objektivvariante, Firmware oder DJI-Pilot-2-Version**. Die vom Studio
verwendeten Werte sind konservative Planungsparameter, keine kalibrierten
physikalischen Fähigkeiten aller Nutzlasten. Zoom- und Videofunktionen müssen
vor praktischer Verwendung anhand der tatsächlich verwendeten Kamera geprüft
werden. Das gilt besonders für Multispektral- und Wärmebildmodelle.

Nur vom Backend validierte, strikt modellgeprüfte Aktionen werden in den
lokalen KMZ-Export übernommen; der Reimport der **eigenen AeroNexus-KMZ**
verifiziert die vollständige kanonische XML-Struktur und verwirft unbekannte
Aktionen/Parameter. Keine automatische Übernahme beliebiger Pilot-2-KMZ.

**Keine** DJI-Cloud-Schreibbefehle, Missionsuploads, Ausführung oder
Flugkompatibilitätsfreigabe. Noch erforderlich: Pi-Live-Abnahme, Kontrolle
mit DJI Pilot 2 bei jedem tatsächlich verwendeten Modell/Payload/Firmware,
separater Abnahmeschritt vor produktivem Rollout.
