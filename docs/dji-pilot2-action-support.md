# DJI WPML-Aktionskatalog: dokumentiert / Pilot 2 beobachtet

## Grenzen der Unterstützung

Das Studio importiert oder führt keine fremden DJI-Missionen aus.
**Für den lokalen KMZ-Export sind jetzt takePhoto, startRecord, stopRecord,
focus, zoom, gimbalRotate und gimbalEvenlyRotate modellabhängig integriert.**
Details und Modellvorbehalte: [Offline-Exportmatrix](dji-wpml-camera-gimbal-export.md).
M3TA ist zwar ein gültiger DJI-Produktcode, aber in den spezifischen
WPML-Aktionszeilen nicht explizit aufgeführt; zusätzliche Aktionen bleiben
für M3TA gesperrt.
Der vollständige Katalog dient der GET-only Diagnose und der Einordnung
bereits gespeicherter DJI-Pilot-2-WPML-1.0.6-Missionen.

- DJI dokumentierte Namen (14): takePhoto, startRecord, stopRecord, focus,
  zoom, customDirName, gimbalRotate, rotateYaw, hover, gimbalEvenlyRotate,
  accurateShoot (veraltet), orientedShoot, panoShot, recordPointCloud.
- Pilot-2-WPML-1.0.6-Beobachtungen (7): setFocusType,
  startSmartOblique, stopSmartOblique, startContinuousShooting,
  stopContinuousShooting, startTimeLapse, stopTimeLapse.
- Beobachtete, nicht zugeordnete Feldnamen: cameraFocusType,
  smartObliqueCycleMode, smartObliquePoint, minShootInterval.

**Real beobachtete Bestandsstatistik (nur ein Snapshot):**
8 KMZs; 70 dokumentierte Aktionsvorkommen; 579 weitere identifizierte
Pilot-2-Vorkommen; 0 aktuell unbenannte Aktionsvorkommen.
Diese Werte sind keine Konstanten und werden bei jeder GET-only Prüfung
neu erhoben.

Die read-only API erhält aus Abwärtskompatibilitätsgründen das alte Feld
`unknown_actions` als **nicht in der bisher dokumentierten DJI-Liste**
(inklusive der identifizierten Pilot-2-Aktionen) und ergänzt
`identified_actions`, `unresolved_actions` und `identified_types`.
Nur fest im Quellcode definierte Aktionsnamen dürfen zur Studio-UI
gelangen. Roh-WPML, IDs, Positionsdaten, Parameterwerte und Tokens
werden nicht durchgereicht.

Die sieben beobachteten Namen beweisen weder den WPML-1.0.6-Parametersatz
noch die Ausführung auf einer bestimmten Drohne/Firmware. Für alle
Studio-Aktionsberichte gilt:
`wpml_semantics_verified=false`,
`flight_compatibility_verified=false`,
`full_content_verified=false`.
Keine DJI-Schreibbefehle, kein Upload, kein Missionsstart, kein O4.
Die weitere Erweiterung des Exports benötigt separat spezifizierte
Parameter, Modellfreigaben, Interoperabilitäts- und Roundtrip-Tests.

Herstellerreferenz:
https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html

## Bekannte Pilot-2-Parameterfelder (Präsenzdiagnose)

Die vier tatsächlich beobachteten Originalnamen `cameraFocusType`,
`smartObliqueCycleMode`, `smartObliquePoint` und `minShootInterval`
haben ab dieser Änderung explizite **unverified**-Feldkategorien.
Es werden weiterhin ausschließlich Feldpräsenzen ausgegeben, keine Werte.
Wiederholte `smartObliquePoint`-Elemente geben keine Ausführungspunkte,
Abfolge oder DJI-Kompatibilität frei. Sie entfallen aus dem Zähler völlig
unbekannter Pxx-Feldnamen; frühere P01/P02/P03-Aliase sind flüchtig und
werden nicht rückwirkend als Firmwarebefehle gedeutet.
