# DJI WPML: rein lesender Offline-Konformitätsaudit

Stand: 19.10.2026. Diese Änderung ergänzt ausschließlich ein eigenständiges
Python-Modul mit automatisierten Tests. **Kein** DJI-Cloud-Upload, kein
MQTT-Publish, keine Flugbefehle, kein Eingriff in den Pi-Produktivdienst.

## Geltungsbereich

Der Audit bewertet, ob eine KMZ **exakt und verlustfrei** durch das bestehende
AeroNexus-Wegpunktmodell bearbeitbar ist. Er zertifiziert **nicht** das gesamte
DJI-WPML-Format, die Gerätesoftware, DJI Pilot 2 oder die Flugtauglichkeit.

- `supported_subset`: Beide XML-Dokumente entsprechen nach strengem
  Reimport dem aktuellen oder einem vollständig unterstützten älteren
  AeroNexus-Exportformat. Die gemeinsamen Felder und Aktionsgruppen werden
  zusätzlich kontrolliert. Eine semantische DJI-Freigabe ist das nicht.
- `unsupported`: Potenziell gültiges DJI-WPML, aber nicht verlustfrei
  darstellbar, z. B. WPML 1.0.6 oder fremde Aktionsparameter.
- `invalid`: Beschädigte, unerlaubt große oder nicht sicher lesbare
  ZIP-/XML-Struktur.

Ein Warnbefund `HEADING_PATH_MODE_INTEROP_UNVERIFIED` wird ausgegeben,
weil das offizielle DJI-Feldverzeichnis diesen Parameter als erforderlich
aufführt, während Beispiele und ältere lokale Exportdaten ihn nicht
durchgehend enthalten. Der Audit ergänzt diesen Wert nicht selbst und
erklärt den Export nicht allein deshalb für ungültig.

## Nutzung auf einer isolierten Arbeitskopie

    cd ~/Projekte/AeroNexusAdvanced-wpml-conformance
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
      ~/Projekte/AeroNexusAdvanced/.venv/bin/python \
      -m pytest -q -p no:cacheprovider tests/test_wpml_conformance.py
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
      ~/Projekte/AeroNexusAdvanced/.venv/bin/python \
      -m aeronexus.wpml_conformance /pfad/zur/lokalen/datei.kmz

Exitcode 0 bedeutet ausschließlich `editable_in_aeronexus=true`;
Exitcode 2 bedeutet nicht bearbeitbar, beschädigt oder nicht lesbar.
Es werden nur fest definierte Befundcodes, Status, Zähler und Schema-Klassen
ausgegeben. **Keine** Missionsnamen, Koordinaten, IDs, Kamera-Parameterwerte
oder Ursprungsdateipfade. Die Aktionszahlen zählen Vorkommen in **beiden**
XML-Dokumenten, nicht tatsächlich ausgeführte Flugaktionen.

Sicherheitsgrenzen: maximal 2 MiB ZIP, pro Mitglied maximal 1 MiB,
exakt zwei erwartete Mitglieder, keine Duplikate, Symlinks, verschlüsselten
Mitglieder oder XML-DTD. Ein reparierender oder allgemeiner DJI-Import
ist absichtlich nicht vorhanden.

## Explizite Grenzen

- Neuere DJI-Pilot-2-WPML-1.0.6-Missionen bleiben `unsupported`, auch
  wenn deren grobe Struktur lesend in anderen Modulen untersucht werden kann.
- Die Funktion prüft den konservativen vorhandenen Exportumfang:
  Foto, Video-Start/Stopp, Punktfokus, Zoom, Gimbal-Pitch und gleichmäßige
  Gimbal-Pitch-Drehung. Alle anderen DJI-Aktionen bleiben gesperrt.
- Zu jedem Resultat sind
  `flight_compatibility_verified=false`,
  `dji_pilot2_import_verified=false` und
  `full_dji_wpml_conformance_verified=false` fest vorgegeben.
- Die Regeln sind zusätzliche Plausibilitätsprüfungen gegen den
  **AeroNexus-eigenen** kanonischen Import, kein unabhängiger DJI-Schema-Validator.
- Ein realer DJI-Pilot-2-Import, manuelle Sichtprüfung auf RC Plus 2 und eine
  separat genehmigte Flugabnahme sind weiterhin erforderlich.

## Referenzen

- https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html
- https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/template-kml.html
- https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/waylines-wpml.html
- docs/dji-wpml-camera-action-conformance.md
