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

### Temporäre Feld-Aliase für unbekannte WPML-1.0.6-Parameter

Der jüngste echte Pilot-2-Test ließ für A01 und A02 weiterhin
unclassified_fields_present bestehen. Auch erweiterte, offiziell
dokumentierte Feldlisten konnten diese XML-Feldnamen nicht zuordnen.

Für eine streng optionale, anonymisierte Feld-Korrelation:

~~~bash
cd ~/Projekte/AeroNexusAdvanced-pr46
PYTHONPATH="$PWD/src" \
  "$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" \
  -m aeronexus.pilot2_wayline_action_vocabulary \
  --limit 8 --parameter-hints --field-aliases
~~~

Dabei erhalten identische **unbekannte Feldnamen im erlaubten DJI-WPML-
Namensraum** ausschließlich innerhalb dieses Programmlaufs P01, P02, …
in der Reihenfolge ihres erstmaligen Auftretens. Das Programm zählt
pro unbekannter Aktionskennung Axx die zugehörigen Feldalias-Vorkommen;
die globale Übersicht zeigt pro Pxx nur Häufigkeit, Anzahl betroffener
KMZ-Dateien und zugeordnete Axx-Aliase. Andersnamige XML-Namensräume
werden nur als Zahl foreign_namespace_field_count erfasst, **nicht**
als feldübergreifend vergleichbar behandelt.

Keine Originalfeldnamen, XML-Werte, Dateipfade, GPS-Werte, Aktionsnamen,
Hashes, UUIDs oder Zugangsdaten verlassen den Prozess. Beide
Alias-Mappings sind nur im RAM vorhanden und werden nicht gespeichert.
Die Aliasnummern sind weder stabil noch Teil des DJI-Standards.

Die zusätzlichen Zähler liefern ausschließlich Strukturkorrelation;
sie identifizieren nicht die Funktion eines unbekannten Befehls,
beweisen keine WPML-1.0.6-Semantik und erlauben ausdrücklich keine
Missionsexport-, Upload- oder Flugfreigabe.

Ohne --field-aliases bleibt das vorherige Ergebnisformat erhalten.

### Feldhäufigkeit je Aktionsinstanz

Die Feld-Alias-Diagnose zeigt jetzt zusätzlich pro Pxx-Feldkennung:

- actions_with_field: Anzahl der Aktionsinstanzen, in denen Pxx mindestens
  einmal vorkommt.
- multiplicity_per_action: Häufigkeitsverteilung je Aktionsinstanz,
  beispielsweise {"1": 187, "2": 182}. Die Schlüssel sind ausschließlich
  die Anzahl der gleichen XML-Feldelemente in genau einer Aktionsinstanz;
  keinerlei Werte oder Originalfeldnamen werden ausgegeben.

Hintergrund: In einer echten Pilot-2-Ausgabe kamen 551 P03-Feldinstanzen
auf 369 A02-Aktionen. Aus der Gesamtzahl alleine ließ sich noch nicht
ablesen, ob P03 mehrfach in einzelnen XML-Parametercontainern vorkommt
oder nur manche Aktionen das Feld enthalten. Die neue Verteilung löst
genau diese Mehrdeutigkeit, ohne Werte zu lesen oder zu veröffentlichen.

Die Ausgabe bleibt eine rein strukturelle Metadatenanalyse.
Insbesondere gilt weder ein mehrfaches Feld noch die Kopplung an
betweenAdjacentPoints als Bestätigung einer ausführbaren oder
übertragbaren DJI-Funktion. Nur GET-Zugriffe; kein O4, kein Upload,
keine Flugsteuerung.

### Wiederholte Feldnamen je ausführbare Route

Die echten WPML-1.0.6-Missionen ergaben 551 P03-Feldvorkommen
innerhalb 369 A02-Aktionen: 217 Aktionen mit 1, 122 mit 2 und
30 mit 3 identischen P03-XML-Elementen.

Mit --parameter-hints --field-aliases gibt das CLI jetzt zusätzlich
results[].unknown_field_multiplicity_by_route aus. Pro KMZ-Datei und
ausführbarem Folder wird je temporärem Feldalias Pxx eine Verteilung
angezeigt, wie häufig genau 1, 2, 3 usw. Felder innerhalb derselben
Aktionsinstanz vorkommen. So kann eine Häufung etwa auf einzelne
Waylines oder Teilrouten eingegrenzt werden.

Die Summe über alle Routen muss mit unknown_field_aliases[].occurrences
übereinstimmen. Ohne --field-aliases entfällt das Feld vollständig.
Es enthält ausschließlich Aliasbezeichner und ganzzahlige Zähler,
keine XML-Inhalte, Aktionsnamen, Rohfeldnamen, Koordinaten oder
Parameterwerte. Mehrfache Felder werden niemals als gültige
WPML-1.0.6-Semantik zertifiziert.

Ausgabe auf das interessante Feld eingrenzen, ohne weitere Rohdaten:

~~~bash
PYTHONPATH=src "$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" \
  -m aeronexus.pilot2_wayline_action_vocabulary \
  --limit 8 --parameter-hints --field-aliases |
"$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" -c '
import json,sys
d=json.load(sys.stdin)
print(json.dumps([
 {"index":i["index"],"routes":[r.get("P03",{}) for r in
 i.get("unknown_field_multiplicity_by_route",[])]}
 for i in d.get("results",[])
],indent=2))
'
~~~

### Grobe Lage wiederholter Felder innerhalb der XML-Teilroute

Nach einer Liveprüfung traten alle 30 dreifachen P03-Felder in den
jeweils ersten Foldern der vier Bibliotheksmissionen 1, 2, 4 und 7
auf. Das neue optionale Flag --position-buckets erlaubt die
weitere Zuordnung nach groben Dritteln der *XML-Placemark-Liste*.

~~~bash
cd ~/Projekte/AeroNexusAdvanced-pr46
PYTHONPATH="$PWD/src" \
  "$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" \
  -m aeronexus.pilot2_wayline_action_vocabulary \
  --limit 8 --parameter-hints --field-aliases --position-buckets
~~~

Das neue Feld results[].unknown_field_xml_placement_by_route enthält
pro Folder und anonymem Feldalias Pxx nur die Zählung der Aktions-
instanzen nach erstem, mittlerem bzw. letztem Drittel und Feldanzahl
innerhalb einer Aktion. Die Ausgabe enthält keine exakten Wegpunkt-
indizes, Datenpunkte, Entfernungen, GPS-Koordinaten, Feld-/Aktionsnamen,
UUIDs, Inhalte oder Parameterwerte. Ohne Flag bleibt die Ausgabe
unverändert.

**Wichtig:** Das ist ausschließlich die Stelle des actionGroup-
XML-Knotens in der Placemark-Reihenfolge. Gemäß DJI kann actionGroup
über actionGroupStartIndex und actionGroupEndIndex einen anderen
Ausführungsbereich festlegen. Die Statistik beschreibt deshalb NICHT
die reale Ausführungsposition oder Flugrichtung und darf nicht zu
Steuerungs- oder Sicherheitsentscheidungen verwendet werden.

DJI-Spezifikation:
https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html

### Sicherheitsgerichtete ActionGroup-Span-Prüfung

Bei Bedarf kann eine zusätzliche, rein lesende und standardmäßig
deaktivierte Diagnose die XML-Felder actionGroupStartIndex und
actionGroupEndIndex mit dem wpml:index der Placemark vergleichen.

~~~bash
cd ~/Projekte/AeroNexusAdvanced-pr46
PYTHONPATH="$PWD/src" \
  "$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" \
  -m aeronexus.pilot2_wayline_action_vocabulary \
  --limit 8 --parameter-hints --field-aliases --span-audit
~~~

Nur das neue Feld results[].unknown_field_xml_span_by_route erscheint
zusätzlich. Es gruppiert pro Folder und anonymem Parameteralias Pxx
die *Anzahl von Aktionen* mit diesem Feld nach:
single_at_anchor, range_starts_at_anchor, single_elsewhere,
range_starts_elsewhere, reversed_span, missing_or_invalid_span,
unresolved_placemark_index oder start_group_not_applicable.

Dabei werden ausschließlich Ganzzahlen intern verarbeitet, auf den
DJI-Indexbereich von 0 bis 65535 begrenzt und nur Statuskategorien
ausgegeben. Die Ausgabe enthält keine Start-/End- oder Wegpunktnummern,
Original-Aktionsnamen, Feldnamen, Nutzlastparameter, Koordinaten oder
Roh-XML. Bei fehlenden/mehrdeutigen Feldern wird kein Index geraten.

Insbesondere ist das **keine** Simulation der tatsächlichen zeitlichen
Flug- oder Kameraausführung. Ein DJI-ActionGroup-Geltungsbereich kann
vom Ort des XML-Placemark-Eintrags abweichen; auch eine formal
konsistente Spanne belegt keine ausführbare WPML-1.0.6-Mission.
Keine Flugkommandos, keine Uploads, kein O4.

Quelle zu den ActionGroup-Indizes:
https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html

### Optionale, grobe Index-Differenz der ActionGroup-Spannen

Alle 369 A02/P03-Aktionen der Pilot-2-Bibliothek haben eine
actionGroupStartIndex/EndIndex-Spanne, die am XML-Anker beginnt und
über diesen Index hinausgeht. Das sagt nichts über die genaue Länge,
Entfernung oder sichere Ausführung aus.

Eine weitere explizit aktivierte Diagnose zählt nur die Klassen der
**WPML-Indexdifferenz** und die gleichzeitig vorkommende Pxx-Feldanzahl:

~~~bash
cd ~/Projekte/AeroNexusAdvanced-pr46
PYTHONPATH="$PWD/src" \
 "$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" \
 -m aeronexus.pilot2_wayline_action_vocabulary \
 --limit 8 --parameter-hints --field-aliases \
 --span-audit --span-length-buckets
~~~

results[].unknown_field_xml_index_delta_by_route enthält pro Folder
und unbekanntem Feldalias Pxx einen Kreuzvergleich der groben
Indexdifferenz und Feldanzahl je Aktionsinstanz. Kategorien sind:
same_index, one_index_step, two_to_four_index_steps,
five_to_sixteen_index_steps, over_sixteen_index_steps,
starts_elsewhere, endpoint_outside_folder, reversed_span,
missing_or_invalid_index, unreliable_folder_indices und
start_group_not_applicable.

Die Indexklassen werden **nur dann** ermittelt, wenn die wpml:index-
Werte innerhalb desselben Folder vollständig, eindeutig und lückenlos
sind und die beiden Endpunkte auf deklarierte Indizes verweisen.
Anderenfalls liefert das Programm ausschließlich eine Statusklasse.

Die Ausgabe enthält keine absoluten Indizes, Koordinaten, Flugstrecken,
Aktions-/Feldnamen oder Parameterwerte. Eine Indexdifferenz ist keine
geografische Flugdistanz, keine Flugdauer und keine Flugfreigabe.
Unbekannte WPML-1.0.6-Aktionen werden weder ausgeführt noch nach
WPML 1.0.2 umgedeutet. Kein Missionsupload, keine Befehle, kein O4.

Referenz: https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html

## Im AeroNexus-Studio: anonyme Pilot-2-Aktionsdiagnose (opt-in)

Die Wayline-Bibliothek besitzt einen neuen Button **Aktionsdiagnose laden**.
Er ist ausdrücklich manuell auszulösen: Beim Laden der Studio-Seite
werden dadurch **keine** KMZ-Dateien abgerufen. Das bestehende
Viewer-Authentifizierungsmodell (Dashboard-Bearer oder explizit
freigegebener HTTPS-LAN-Modus) gilt auch für die neue GET-Route:

\`GET /api/v1/studio/pilot2/action-summary\`

Die API nutzt die bereits bekannte, vollständig inventarisierte Pilot-2-
Cloud-Sitzung und liest maximal acht lokale KMZ-Dateien über den
festen Loopback-/MinIO-Pfad. Sie gibt ausschließlich eine strikt
allowlist-basierte, anonyme Zusammenfassung mit Aktionszahlen,
temporären Axx-Aliasnamen, zulässigen Triggernamen, Schema-Versionen
und Routenanzahl zurück. Sie liefert keine Originalaktionsnamen,
unbekannten XML-Feldnamen, Feldwerte, Koordinaten, Datei-/Missionsnamen,
UUIDs, Tokens, Download-URLs oder KMZ-Inhalte.

Eine pro Sitzung getrennte, nur im RAM gehaltene 90-Sekunden-Zwischenspeicherung
und ein asynchrones Lock verhindern unnötige parallele Abfragen. Beim
Wechsel der Pilot-2-Credentials wird der Cache nicht weiterverwendet.
Der HTTP-Response trägt No-Store-Header; die Oberfläche erzeugt
Textknoten statt HTML aus den empfangenen Werten. Erfolgreiche
Authentifizierung muss vor jedem Lesevorgang erfolgen.

Die Ansicht zeigt ausdrücklich, dass WPML-1.0.6-Semantik und
Flugkompatibilität **nicht** verifiziert wurden. Insbesondere
werden keine Aktionssemantiken geraten und keine unbekannten Aktionen
im Studio-Editor oder WPML-Exporter freigeschaltet. Kein Upload,
keine Änderung an Missionen, kein MQTT-Publish, keine Flugbefehle
und keine O4-Integration.

Für den Pi-Smoketest im getrennten Test-Worktree:

~~~bash
WT="$HOME/Projekte/AeroNexusAdvanced-pr46"
PY="$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python"
cd "$WT"
PYTHONPATH="$WT/src" "$PY" -m pytest -q tests/test_pilot2_action_summary.py
~~~

Die Live-UI benötigt den Deployment-Stand dieses Branches;
das Wechseln des Test-Worktrees allein verändert den laufenden
AeroNexusAdvanced-Server **nicht**.

### Härtung der Studio-Diagnoseansicht (Sitzung, Fehlerzustand)

Beim Wechsel aus der Wayline-Bibliothek wird ein laufender
Aktionsdiagnose-GET mit AbortController abgebrochen, die Anfragegeneration
ungültig gemacht und die vorherigen anonymen Diagnosekarten entfernt.
Eine bereits empfangene HTTP-Antwort kann somit nach einem späteren
Tabwechsel keine veralteten Karten nachzeichnen. Das gilt auch, falls die
Antwort erst während des JSON-Parsens eintrifft.

Der Backend-Summarizer akzeptiert ausschließlich vollständige
Bibliotheksstände mit plausibler gemeldeter Gesamtzahl, eindeutigen
temporären Axx-Aliassen, konsistenten Gesamtzählern und explizit
false gesetztem full_content_verified sowie
flight_compatibility_verified. Fehlerhafte Summen und untypisierte
oder doppelte Aliaswerte führen zu einer anonymisierten Fehlermeldung,
nicht zur Ausgabe von Originaldaten.

Die Oberfläche beschriftet den bekannten Anteil deshalb ausdrücklich
als **Aktionen in der bekannten Typenliste** – eine Klassifizierung der
Textkennung und ausdrücklich *kein* Nachweis von WPML-1.0.6-Semantik.
Keine automatische Freigabe, kein Schreiben, keine Flugsteuerung.

Getestet mit pytest und gezielten negativen Fixtures:
parallel ausgelöste Abrufe (ein Scan), Cache-Ablauf, Credentials-Wechsel,
abgewiesene Viewer-Anfragen, doppelte Aliasse, inkonsistente
Metadaten und verschwundene Browseransichten.

### Isolierter HTTP-End-to-End-Smoketest ohne laufenden Server anzufassen

Der erfolgreiche Pi-Livetest prüfte das Python-Reader-Objekt direkt
(8/8 Waylines, 70 bekannte Texttypen, 579 unbekannte Aktionsvorkommen).
Die folgende separate Abnahme prüft die echte FastAPI-HTTP-Route
über einen rein prozessinternen ASGI-Transport:

~~~bash
(
 set -euo pipefail
 WT="$HOME/Projekte/AeroNexusAdvanced-pr46"
 PY="$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python"
 cd "$WT"
 PYTHONPATH="$WT/src" "$PY" -m pytest -q \
   tests/test_pilot2_action_http_smoke.py \
   tests/test_pilot2_action_summary.py
 PYTHONPATH="$WT/src" "$PY" \
   scripts/pi/pilot2_studio_action_http_smoke.py
)
~~~

Das Skript ruft /api/v1/studio/pilot2/action-summary zuerst ohne
Token und mit ungültigem Token auf und erwartet zweimal HTTP 401,
anschließend mit einem ausschließlich im Prozess erzeugten
temporären Bearer-Token HTTP 200. Geprüft werden außerdem No-Store,
explizit unverifizierte WPML-Semantik/Flugkompatibilität und
konsistente Antworten bei erneutem Abruf aus dem Sitzungs-Cache.

Die echte Pilot-2-Inventur und KMZ-Analyse werden dabei weiterhin
ausschließlich über die bestehenden lokalen GET-Pfade ausgeführt.
Der Test importiert die vorhandene App und verwendet httpx.ASGITransport,
ohne uvicorn/HTTP-Socket, MQTT-/Polling-Lifespan, systemd-Neustart,
Produktionsdeploy, Dateischreiben, Drohnenbefehle oder Missionsupload.
Es wird weder ein vorhandenes Dashboard-Token angezeigt noch geändert:
die temporäre Tokenumgebung existiert ausschließlich innerhalb des
Python-Prozesses.

**Abgrenzung:** Dieser Test bestätigt das Authentifizierungs- und
Routingverhalten des Entwicklungsbranchs im Prozess, nicht die
HTTPS-/Reverse-Proxy-Konfiguration des produktiv laufenden Servers
oder einen tatsächlichen Browser-Smoke. Ein späteres Live-Deployment
bedarf eines gesonderten, bewussten Schritts.
