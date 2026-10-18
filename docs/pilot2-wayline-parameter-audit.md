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

## Explizite WPML-Namensräume

Die strukturelle Pilot-2-Prüfung hat für alle acht KMZ-Dateien einen von
DJIs dokumentiertem Beispielschema abweichenden WPML-Namensraum gezeigt.
Der Parser akzeptiert für die **lesende** XML-Diagnose deshalb ausschließlich
folgende exakten Namensräume:

- DJI WPML 1.0.2: http://www.dji.com/wpmz/1.0.2 (DJI-API-Beispiel)
- DJI WPML 1.0.6: http://www.dji.com/wpmz/1.0.6 (in neueren WPML-KMZ bekannt)

Unbekannte, manipulierte oder nur lokalnamengleiche XML-Namensräume bleiben
gesperrt. Welche Version im realen Pilot-2-Inventar vorliegt, zeigt
--structure-only im Feld recognized_wpml_schema_version. Bei einer
unbekannten Version werden keine Parameterinterpretionen freigegeben.

DJI WPML 1.0.6 wird zunächst **nur zur Auswertung von erlaubten, groben
Merkmalen** berücksichtigt. Solange die Feldsemantik nicht gesondert gegen
den neuen WPML-Stand belegt ist, lautet wpml_schema_semantics_verified=false,
parameter_state=not_comparable und full_content_verified=false – selbst wenn
die Wegpunktkoordinaten identisch sein sollten.

## WPML-Aktionsstatistik (nur lesend)

Ab der erweiterten Parameterdiagnose werden zusätzlich folgende aggregierte
Zähler je KMZ ausgegeben:

- action_type_counts: Häufigkeit der ausdrücklich dokumentierten DJI-Aktionsnamen
  in den Wegpunkten, beispielsweise orientedShoot, panoShot, gimbalRotate,
  takePhoto, startRecord und stopRecord.
- unrecognized_action_count: Anzahl anderer, nicht eindeutig zugeordneter
  Aktionstypen. **Unbekannte Aktionstexte werden nicht ausgegeben.**
- start_action_type_counts: gesonderte Zählung dokumentierter Aktionen in
  startActionGroup.
- start_action_count und unrecognized_start_action_count: Umfang und unbekannte
  Einträge der Startaktionsgruppen.

Die zuvor ausgewiesene Zahl other_action_count zählt ausschließlich andere
als takePhoto-Funktionen innerhalb der Wegpunkte. Darunter können DJI-
Fotoaktionen wie orientedShoot fallen: photo_action_count=0 besagt daher
NICHT, dass keine Aufnahmen vorgesehen sind.

Es handelt sich ausschließlich um eine Klassifikation der Aktionsnamen.
Reihenfolge, Auslöser, Kamera- und Nutzlastparameter sowie
Firmware-Kompatibilität werden nicht validiert. Die WPML-1.0.6-Semantik
bleibt ungeprüft; kein automatischer Upload oder Flugsteuerungsbefehl.
Die Liste der bekannten Aktionsnamen stammt aus DJI WPML Common Element:
https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html

## Anonymisierte Analyse unbekannter Aktionen und Trigger

DJI WPML 1.0.6 aus der Pilot-2-Cloud kann Aktionswerte enthalten, die
in der dokumentierten DJI Cloud-API-Aktionsliste nicht beschrieben sind.
Sie werden ausdrücklich NICHT in bekannte Befehle umgedeutet.

Neue Diagnosefelder je Cloud-KMZ:

- unknown_action_distinct_by_route: Zahl verschiedener nicht erkannter
  Aktionswerte pro ausführbarer Folder-Route (ohne Werte selbst).
- unknown_action_shapes_by_route: pro Route aggregierte Formklassen
  missing, identifier (ASCII-Bezeichner), numeric, other.
- unknown_start_action_distinct_by_route und
  unknown_start_action_shapes_by_route: entsprechend für startActionGroup.
- waypoint_action_group_count: Anzahl von wpml:actionGroup bei Wegpunkten.
- action_trigger_counts: ausschließlich dokumentierte und erkannte
  Trigger reachPoint, betweenAdjacentPoints, multipleTiming und
  multipleDistance.
- unknown_action_trigger_count: unbekannte oder fehlende Trigger.

Die Formklassen liefern nur Hinweise für die nächste Schema-Recherche,
nicht die Semantik der Aktionswerte. Insbesondere identifiziert
identifier keine Kameraaktion. Keinerlei unbekannte Aktionstexte,
Hashes, Parameter, Koordinaten, Missionstitel oder UUIDs werden in
Diagnoseausgaben übernommen.

Originalaktionen werden weder umgeschrieben noch veröffentlicht,
hochgeladen oder auf einer Drohne ausgeführt. Übertragbarkeit von
WPML-1.0.6-Aktionen bleibt ungeprüft.

## Anonyme Korrelation über das ganze Pilot-2-Inventar

Für die vielen unbekannten DJI-WPML-1.0.6-Aktoren existiert ein **separater**,
explizit gestarteter, lesender Prüfbefehl:

~~~bash
cd ~/Projekte/AeroNexusAdvanced-pr46
PYTHONPATH="$PWD/src" \
  "$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" \
  -m aeronexus.pilot2_wayline_action_vocabulary --limit 8
~~~

Er benötigt keine lokale Studio-Mission. Er lädt KMZ-Dateien nur aus dem
vollständigen, bereits autorisierten Pilot-2-Inventar des verbundenen
Workspaces über denselben überprüften lokalen GET-/MinIO-Pfad wie die
Kartenvorschau. Keine Zugriffe auf den Flugcontroller, keine Uploads.

**Ausgabe:** unbekannte Aktionsbezeichner werden nur innerhalb dieses einen
CLI-Laufs durch neutrale Bezeichnungen A01, A02, … ersetzt. Gleichlautende
unbekannte Aktionsbezeichner in verschiedenen KMZ-Dateien bekommen dieselbe
anonyme Kennung. Gezählt werden Auftreten je KMZ/Folder, Start- gegenüber
Wegpunktaktion, Auslöser (nur dokumentierte Trigger wie reachPoint und
betweenAdjacentPoints) sowie Anzahl verschiedener Dateien je Kennung.

Das Format enthält keine echten Aktionsnamen, Hashes, ursprünglichen
Parameter, Koordinaten, Namen, UUIDs, Seriennummern, signierten URLs oder
Tokens. Die Zuordnung verbleibt ausschließlich im Arbeitsspeicher und wird
beim Programmende verworfen. Die Aliasnamen sind nicht stabil über
verschiedene Läufe; sie sind **keine DJI-Aktionsnamen**.

Die Ergebnisse verraten keine Funktion der unbekannten Aktionen. Ebenso
wird keine semantische DJI-WPML-1.0.6-Kompatibilität zertifiziert. Alle
Flug- und Schreibbefehle und O4 bleiben ausdrücklich ausgeschlossen.

## Optionale, anonymisierte Parameter-Hinweise zu unbekannten Aktionen

Die erste Live-Korrelation fand nur 7 verschiedene unbekannte Aktionswerte,
davon 554/579 Vorkommen in zwei häufigen Typen (anonyme Kennungen A02/A03).
Trigger allein belegen jedoch KEINE DJI-Aktionssemantik.

Deshalb ergänzt der spezielle Diagnosebefehl optional:

~~~bash
cd ~/Projekte/AeroNexusAdvanced-pr46
PYTHONPATH="$PWD/src" \
  "$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" \
  -m aeronexus.pilot2_wayline_action_vocabulary \
  --limit 8 --parameter-hints
~~~

Pro neutraler Aktionskennung erscheinen bei Bedarf nur
parameter_container_counts (z. B. absent/present/empty) und
parameter_category_counts. Letztere zählen **vorhandene** Felder aus
einer fest codierten kleinen Liste offizieller DJI-WPML-Feldnamen;
Kategorien sind z. B. gimbal, camera_lens, payload, media_naming,
focus, zoom, hover, aircraft. Alle nicht klassifizierten Feldnamen
werden zusammenfassend als unclassified_fields_present gezählt.

**Weder Werte noch unbekannte Feld-/Aktionsnamen, Hashes, XML,
Koordinaten, Standortdaten, IDs oder Tokens gelangen in die Ausgabe.**
Die Ausgabe ist ein Präsenzmuster ohne garantierte Funktionszuordnung:
beispielsweise kommt payloadPositionIndex in mehreren DJI-Aktionsarten
vor. Die Zuordnung der WPML-1.0.6-Semantik bleibt unbestätigt; niemals
daraus selbstständig Aktionen ausführen, Konfigurationsänderungen
vornehmen oder Missionen hochladen.

Ohne --parameter-hints bleibt das vorherige JSON-Format unverändert.

DJI-Felddefinitionen:
https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html

### Zusätzliche offizielle WPML-Feldnamen

Die anonymisierte Option --parameter-hints enthält jetzt auch die
Präsenz-Kategorien action_tracking, media_reference, image_dimensions
und camera_model. Dazu wurden die in DJI WPML Common Elements
dokumentierten Felder actionUUID, orientedFilePath, imageWidth,
imageHeight, orientedCameraType, AFPos, gimbalPort, focalLength und
weitere Gimbal-Rotationsfelder aufgenommen.

Ausgewertet wird weiterhin **ausschließlich das Vorhandensein von
XML-Feldnamen**. Insbesondere werden actionUUID, Medienpfade,
Fokus-/Bildpositionen, Kameramodellwerte, Nutzlastwerte und
Kameraparameter selbst niemals ausgegeben. Eine zusätzliche
Feldkategorie erlaubt KEINEN Schluss auf die Identität eines
unbekannten DJI-WPML-1.0.6-Aktors.

Quellen: https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html
