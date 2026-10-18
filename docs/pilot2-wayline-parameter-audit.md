# Pilot 2: WPML-Parameterprüfung (Cloud API 1.18)

Das lokale, optionale CLI vergleicht eine gespeicherte Studio-Mission
mit maximal acht indizierten KMZ-Dateien einer vollständig paginierten
Pilot-2-Bibliothek.

~~~bash
cd ~/Projekte/AeroNexusAdvanced-pr46
PYTHONPATH="$PWD/src" \
  "$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" \
  -m aeronexus.pilot2_wayline_parameters \
  --mission 'STUDIO-MISSION-UUID' --limit 8
~~~

**Schreibgeschützt:** Wiederverwendung des abgesicherten Loopback-Backends
und des größenbegrenzten, signierten MinIO-Downloads der Kartenvorschau.
Kein Missions-Upload, keine Ausführung, kein MQTT-Publish, kein O4, keine
lokalen Änderungen.

Das Modul gibt ausschließlich eingeschränkte Status-/Modellinformationen,
Zähler und boolesche Vergleiche aus. Keine Namen, UUIDs, Koordinaten,
Signaturen, Roh-KMZ oder Zugangsdaten. Eingabe-UUIDs können allerdings in
der Shell-Historie und Prozessliste sichtbar sein.

Je KMZ:

- route_count, route_point_counts: separate ausführbare Folder-Routen und
  Placemark-Zahlen (niemals ungeprüft zusammenführen).
- height_modes: erkannte Höhenreferenzen oder unknown.
- wpml_model_key, cloud_model_key: Modelle aus XML und Bibliotheksmetadaten,
  inklusive eventueller Abweichung.
- photo_action_count, other_action_count, route_start_actions_present:
  begrenzte und ausdrücklich unvollständige Aktionen-Übersicht.
- geometry_result: vorhandener Koordinatenvergleich.

parameter_matches ist nur bei einer einzelnen, geometrisch identischen
Route ohne Modell-Metadatenkonflikt verfügbar. Verglichen werden
Startflugmodus, Abschlussaktion, RC-Verlustverhalten, RTH, Start-Sicherheitshöhe,
Übergangsgeschwindigkeit, Routengeschwindigkeit, Höhenreferenz,
Wegpunkthöhen und -geschwindigkeiten sowie einfache takePhoto-Positionen.

Fehlende Felder werden mit null markiert. Höhen werden niemals zwischen
unterschiedlichen Höhenreferenzen numerisch verglichen. Die möglichen
Parameterzustände sind not_comparable, differences_detected,
incomplete_fields und supported_fields_equal.

**supported_fields_equal bedeutet ausdrücklich NICHT, dass die gesamten
WPML-Missionen gleich sind.** Andere Kameraparameter, komplexe Aktionen,
Startbedingungen, RTK-/Geländefunktionen, Nutzlasten und Firmware bleiben
ungeprüft. full_content_verified und flight_compatibility_verified
bleiben stets false.

Auch eine echte Cloud-Route mit z. B. 22 bis 296 Punkten ist im Vergleich
zu einer lokalen 5-Punkte-Mission voraussichtlich not_comparable.
Trotzdem werden Anzahl der ausführbaren Routen, Höhenreferenzen und
Metadaten-/WPML-Modellwidersprüche sichtbar.

## Test

~~~bash
PYTHONPATH="$PWD/src" \
  "$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" \
  -m pytest -q \
  tests/test_pilot2_wayline_preview.py \
  tests/test_pilot2_wayline_compare.py \
  tests/test_pilot2_wayline_parameters.py
~~~

Die Tests verwenden synthetische KMZ-Dateien und simulierte HTTP-Aufrufe.
Ein kontrollierter Live-Test am Pi bleibt erforderlich.

Offizielle WPML-Spezifikation:

- https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/waylines-wpml.html
- https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/template-kml.html

## Sichere Strukturdiagnose bei unsupported_geometry

Einige reale, von Pilot 2 erzeugte KMZ-Dateien liefern bei der bisherigen
strikten WPML-Parameterprüfung unsupported_geometry, obwohl die Karten-
Geometrievorschau die Wegpunkte erfolgreich lesen kann. Deshalb nicht
vorschnell andere XML-Namensräume oder Dateistrukturen als äquivalent
interpretieren.

Die neue Diagnose benötigt keine Studio-Mission und gibt ausschließlich
anonymisierte Strukturmerkmale aus:

~~~bash
cd ~/Projekte/AeroNexusAdvanced-pr46
PYTHONPATH="$PWD/src" \
  "$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" \
  -m aeronexus.pilot2_wayline_parameters \
  --structure-only --limit 8
~~~

Ausgabe: KML-/WPML-Namensraumkategorien (standard, unqualified,
nonstandard), ob Document, missionConfig und Folder direkt oder geschachtelt
vorliegen, Anzahl von Placemark-/Point-/Koordinaten-XML-Elementen,
strict_parser_gate und strict_header_compatible.

Die Ausgabe enthält keine XML-Inhalte, Roh-Namensräume, Namen, UUIDs,
Koordinaten, Geräte-Seriennummern oder Tokens. Das CLI verwendet denselben
abgesicherten GET-Pfad wie die Kartenansicht, führt keine Schreibzugriffe aus
und lädt nicht automatisch Missionen anderer Workspaces.

Mit diesem Befund kann gezielt die fehlschlagende Parser-Annahme angepasst
werden, ohne eine fremde XML-Variante voreilig als voll valide DJI-Mission
zu akzeptieren.
