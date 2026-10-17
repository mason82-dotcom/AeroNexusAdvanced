# Missionen und Waylines abgleichen

Stand 17.10.2026. Es gibt drei getrennte Bestände: lokale Studio-Entwürfe,
FlightHub-Public-Cloud-Waylines/Flugaufträge und die Wayline-Bibliothek des
lokalen Pilot-2-Cloud-Servers. Der Bericht vergleicht Studio-Missionen mit
FlightHub-Cache und optional der lokalen Serverbibliothek. Eine nur auf der
Fernsteuerung gespeicherte, nicht hochgeladene Route bleibt unbekannt.

## Missionsprofile

| Studio-Profil | Fluggerät-Typ | Untertyp | Kamera-Typ |
|---|---:|---:|---:|
| Mavic 3E | 77 | 0 | 66 |
| Mavic 3T | 77 | 1 | 67 |
| Mavic 3M | 77 | 2 | 68 |
| Mavic 3TA | 77 | 3 | 129 |
| Matrice 4E | 99 | 0 | 88 |
| Matrice 4T | 99 | 1 | 89 |

Kamera-Untertyp und Nutzlastposition sind jeweils 0. Geräteauswahl und Export
verwenden dieselbe Profiltabelle. Speichern, Laden, CSV-Punktübernahme, KMZ-Export
und Re-Import behalten das gewählte Profil. CSV-Dateien enthalten weiterhin nur
Punkte, keine automatische Gerätemodell-Erkennung.

Dies erweitert den bestehenden Wegpunktmodus. Es erzeugt keine Mapping-Flächen,
Multispektral-Bandwahl, Thermal-Linsenauswahl oder neuen Kameraaktionen. Ein
M3M-Profil bedeutet nicht, dass der Export eine kalibrierte MS-Aufnahme erzeugt.
Firmware-/Pilot-2-Akzeptanz und reale Flugprüfung bleiben separat erforderlich,
insbesondere für M3TA. Keine Mission wird an ein Fluggerät gesendet.

## Konsistenzprüfung beim KMZ-Import

Nur eigene AeroNexus-Wegpunktdateien werden importiert. Aus der eingelesenen
Mission werden beide unterstützten XML-Dokumente erneut aufgebaut und mit den
vollständigen eingelesenen Dokumenten verglichen. RTH, Start-/Flughöhe, globale
und individuelle Geschwindigkeit, Modell/Nutzlast, Koordinaten, RC-Verlustregel,
Richtungs-/Kurvenparameter, Aktionsgruppen und Fotoaktionsparameter dürfen nicht
widersprechen oder beim erneuten Export verloren gehen. Zusätzliche Attribute,
Elemente oder Duplikate werden ebenfalls abgelehnt. Ein Autor-Text allein reicht
nicht als Nachweis eines unterstützten Dateiformats.

XML-Präfixe, Einrückung und die beiden numerischen Erstellungs-/Änderungszeiten
sind nicht Teil der Flugsemantik. Sonst ist der Vergleich bewusst streng,
einschließlich der von AeroNexus erzeugten Zahlenformatierung und Reihenfolge.
Extern umformatierte oder erweiterte DJI-Dateien können daher abgelehnt werden.
Eine abgelehnte Datei wird nicht als neue Mission gespeichert.

## Lesender Metadatenbericht

`GET /api/v1/studio/missions/reconciliation`

Gleicher LAN-/Bearer-Schutz wie die Studio- und FlightHub-Daten-APIs;
`Cache-Control: no-store`. Kein neuer öffentlicher Zugriff und keine automatische
Verknüpfung. Der Aufruf liest den FlightHub-Cache und lokale Missionsmetadaten.
Bei eingerichteter lokaler Anbindung werden zusätzlich die Server-Waylines
per GET geladen, höchstens einmal in 30 Sekunden. Siehe Einrichtung unten.

- `missions`: lokale ID, Name, Profil und Anzahl editierbarer Punkte; bis zu zehn
  Namenskandidaten je Mission mit Anbieter, Projekt, Cloud-Wayline-ID, Modell,
  Cloud-Änderungszeit und Dateigröße. `candidate_count` zählt auch weitere Treffer.
- `waylines`: alle im Cache vorhandenen Cloud-Routen einschließlich Template-Typ.
  Mapping-Routen werden dadurch nicht in bearbeitbare Wegpunktmissionen verwandelt.
- `flight_tasks`: getrennte Aufträge mit Status und `wayline_link=unavailable`.
  Der vorhandene normalisierte Task-Katalog enthält keine belastbare Wayline-ID;
  selbst gleiche Namen werden nicht als Verbindung ausgegeben.
- `projects`: unterscheidet nicht lesbare von erfolgreich leeren Sammlungen und
  markiert Sammlungen am derzeitigen 200-Einträge-Limit.
- `catalog_updated_at`: vorhandener globaler Cache-Zeitnachweis, keine Garantie,
  dass jede einzelne Sammlung erfolgreich oder vollständig aktualisiert wurde.
- `local_pilot`: eigener Verbindungszustand, Workspace, Abrufzeit, gemeldete
  Gesamtzahl, `pagination_complete`, `max_pages` und `requested_page_size`.
  Das bisherige Coverage-Feld `max_items_per_project_collection=200` gilt nur
  für den FlightHub-Katalog, nicht für die hier separat begrenzte lokale Quelle.
  Lokale Routen tragen den Anbieter
  `pilot2-local-cloud`; Workspace- und FlightHub-Projekt-IDs werden nicht vermischt.
  `updated_at_ms` ist die lokale Server-Änderungszeit in Millisekunden, während
  FlightHub `updated_at` weiterhin in Sekunden verwendet.

Namen werden nach NFC-Normalisierung, Groß-/Kleinschreibung und Leerzeichen
verglichen. Das ist ausschließlich ein Suchhinweis. `model_match` ist
true/false/null; auch gleicher Name und gleiches Modell liefern immer
`verification=name_only` und `content_match=null`. Routeninhalt, Prüfsumme und
Dateiversion sind nicht verifiziert. Doppelte Namen bleiben mehrdeutig.

Ohne Treffer lautet der Zustand `no_candidate_in_cache`, niemals „gelöscht“ oder
„fehlt sicher in der Cloud“. Der Cache kann leer, deaktiviert, veraltet,
unvollständig oder teilweise nicht lesbar sein. Tasks umfassen derzeit nur die
letzten 30 Tage, Sammlungen höchstens 200 Einträge je Projekt. Der Bericht
beansprucht keine vollständige Inventur. Private Dateien und Cloud-Daten bleiben
unverändert; URLs, Zugangsdaten und Missionskoordinaten werden nicht ausgegeben.

Auf dem konfigurierten Pi im direkten HTTPS-LAN nach Installation dieses Standes:

```bash
cd ~/Projekte/AeroNexusAdvanced
curl --fail --show-error --max-time 15 \
  --cacert config/pki/ca.crt \
  https://192.168.178.63:8000/api/v1/studio/missions/reconciliation \
  | .venv/bin/python -m json.tool
```

Im Token-Modus denselben geschützten Zugang wie beim bestehenden Studio verwenden;
keine Token in Chat-Ausgaben kopieren.

## Cloud-Routen im Studio

Im Studio auf Port 8000 gibt es einen eigenen Bereich **Cloud-Routen**.
Er lädt beim ersten Öffnen denselben geschützten Abgleich. Suche nach Namen,
Quellenfilter und zwölf Karten pro Seite helfen bei größeren Beständen.
„Routen aktualisieren“ liest den Bericht erneut; keine automatische Pollschleife.

Jede Karte zeigt Namen, Modell, Routentyp, Quelle/Scope, Änderungszeit und
Prüfstatus. Lokaler Abrufzeitpunkt und Quellenzustände stehen über der Liste.
Modellkonflikte und begrenzte Namenskandidaten werden sichtbar benannt; ein
gleicher Name wird niemals als verifizierter Inhalt dargestellt. Lokale
Millisekunden- und FlightHub-Sekunden-Zeitstempel werden korrekt in Berliner
Zeit angezeigt. Unbekannte geometrische Template-Codes bleiben sichtbar.

Die Bibliothek liest zunächst nur Metadaten. Auf expliziten Klick kann für
inventarisierte lokale Pilot-2-Waylines eine streng begrenzte, rein lesende
KMZ-Geometrievorschau auf einer separaten Kartenebene geladen werden.
Keine Routenänderung, Übernahme in den Editor, KMZ-Übertragung zur Drohne oder
Flugausführung. Ein offener Entwurf bleibt unverändert. Daten aus nicht lesbaren Quellen werden nicht als erfolgreich
leer ausgegeben. Fehler/Timeouts entfernen den alten Anzeigestand und erlauben
erneutes Laden. Suchbegriffe und Filter werden nicht in URLs oder persistenten
Browser-Speicher geschrieben.

## Lokale Pilot-2-Cloud anbinden

Voraussetzung: Der bereits migrierte Cloud-API-Server läuft auf dem Pi an
`127.0.0.1:6789`. Kein FlightHub-EU-Konto und kein DJI-App-Key ersetzen dessen
lokales Benutzerkonto. Die Anbindung startet oder verändert keine Container,
Datenbank, Brokerrechte oder Legacy-Dienste.

Nach Installation des neuen Codes als Dienstbenutzer `mason` aktiviert dieser
Befehl die Übernahme einer bestehenden Anmeldung **ohne Kontoabfrage**:

```bash
cd ~/Projekte/AeroNexusAdvanced
.venv/bin/python -m aeronexus.local_waylines --configure
```

Eine bereits vorhandene private Sitzungsdatei wird weiterverwendet. Andernfalls
wartet der Adapter als `awaiting_browser_session` auf die angemeldete lokale
Cloud-Oberfläche. Dafür das mitgelieferte Hilfsskript in die bereits migrierte
Weboberfläche übernehmen und ausschließlich deren Container neu bauen:

```bash
cd ~/Projekte/AeroNexusAdvanced
python3 scripts/enable_wayline_session_handoff.py --apply
cd cloud-server/edge
docker compose -f compose.core.yaml -f compose.brand.yaml build control
docker compose -f compose.core.yaml -f compose.brand.yaml \
  up -d --no-deps --no-build --pull never control
```

Build und Start nur nacheinander bei erfolgreichem vorherigem Befehl ausführen.
Das Vorbereitungswerkzeug verändert nur `index.html` und eine öffentliche
JavaScript-Datei im migrierten Web-Quellbaum, mit Sicherung der bisherigen
HTML-Datei. Es baut oder startet selbst nichts und ändert keinen Backendcode.
Danach die bereits angemeldete Cloud-Webseite auf
`http://192.168.178.63:8085` neu laden. Sie übernimmt ihre vorhandenen Werte
`x-auth-token` und `workspace_id` aus ihrem eigenen Browser-Speicher. Keine
Browserprofile werden durchsucht, keine Passwörter ausgelesen oder abgefragt.
Das gilt auch für eine bereits angemeldete Pilot-2-WebView nach Neuladen.
Ohne vorhandene Anmeldung kann kein gültiges Token erfunden werden; dann
bleibt der Zustand wartend. Die normale Cloud-Anmeldung wird nicht entfernt.

Der Helfer übergibt die bestehende Sitzung alle 30 Sekunden im sichtbaren
Browserfenster an einen dedizierten HTTPS-Endpunkt des Advanced-Dienstes.
Dieser ist separat opt-in (private `session-handoff.json`, Modus 0600) und
akzeptiert ausschließlich direkte LAN-/Loopback-Anfragen per HTTPS an
`192.168.178.63:8000` mit exakter Origin `http://192.168.178.63:8085`.
Es gibt kein globales CORS und keine Lockerung vorhandener Studio-APIs.
Vor dem Speichern validiert GET `/manage/api/v1/users/current` das Token
am bestehenden Server und bestätigt Workspace sowie Kontotyp 1 oder 2.
JWT-Inhalte werden nicht bloß decodiert und es werden keine Tokens signiert.
Andere Workspaces ersetzen eine bereits eingerichtete Sitzung nicht.

Die HTTPS-CA muss im verwendeten Browser/WebView vertraut sein. Ein TLS-/CORS-
oder Serverfehler unterbricht nicht die Cloud-Oberfläche; der Helfer versucht
es später erneut. Bestehende gleiche Tokens werden höchstens einmal pro Minute
erneut geprüft. Tokenwechsel wird erneut validiert und atomar gespeichert.
Browserabmeldung allein löscht nicht die separate private Pi-Sitzungsdatei;
deren Gültigkeit bleibt Sache des lokalen Cloud-Servers. Zum Abschalten die
private `session-handoff.json` entfernen, gegebenenfalls auch die Sitzungsdatei.

Nur als ausdrücklich gewählte Alternative bleibt die manuelle Anmeldung:
`.venv/bin/python -m aeronexus.local_waylines --login` bzw.
`--login --account pilot`. Nur sie fragt Benutzername/Passwort ab und sendet
POST `/manage/api/v1/login`; das Passwort bleibt ungespeichert. Sie prüft den
Wayline-GET vor dem Ersetzen einer bestehenden Datei. Es werden keine Benutzer
angelegt, Standardpasswörter ausprobiert oder Rechte erhöht.

Die Datei `~/.config/aeronexusadvanced/pilot-waylines.json` enthält ausschließlich
Workspace-ID und Sitzungstoken, Modus 0600 im Verzeichnis 0700. Dieses Token hat
die Kontoberechtigungen; **es ist kein vom Server eingeschränktes Lesetoken**.
Nur der Adapter beschränkt seine Verwendung auf GET. Symlinks, FIFOs, fremde
Dateibesitzer und unsichere Dateirechte werden verweigert. Die Datei gehört
nicht ins Repository oder in Chat-Ausgaben. Optionaler privater Pfad:
`AERONEXUS_LOCAL_WAYLINES_FILE`; CLI und Dienst müssen denselben Pfad verwenden.

Die eingerichtete Datei aktiviert den Adapter ausdrücklich. Ohne Datei und
ohne Übergabeaktivierung bleibt er `not_configured` und sendet keine Anfrage.
Ein Dienstneustart ist für eine
neue Sitzung nicht nötig; der nächste Bericht liest die Datei erneut. Zum
Deaktivieren die eigene Sitzungsdatei lokal entfernen; ein eventuell noch
serverseitig gültiges Token wird dadurch nicht widerrufen.

Probe ohne FastAPI-Neustart, Ausgabe enthält nur gefilterte Routenmetadaten:

```bash
cd ~/Projekte/AeroNexusAdvanced
.venv/bin/python -m aeronexus.local_waylines
```

Danach denselben HTTPS-Abgleichsbefehl oben ausführen. `connected` mit null
Waylines bedeutet erfolgreich leer; `not_configured`, `configuration_error`,
`awaiting_browser_session`, `authentication_required`, `business_error`, `upstream_error`, `unavailable`,
`invalid_response` und `inventory_changed` bedeuten keinen bestätigten Bestand.
Bei abgelaufener Sitzung eine noch angemeldete lokale Cloud-Webseite neu laden;
deren eigene erfolgreiche Sitzungsverlängerung kann das neue Token übergeben.
Advanced meldet sich dabei weder neu an noch verlängert es selbst Sitzungen.

Der Adapter verwendet ausschließlich die feste Loopback-Adresse und
`GET /wayline/api/v1/workspaces/{workspace_id}/waylines` mit `x-auth-token`.
Keine Weiterleitungen, System-Proxys, Datei-/Download-URLs, Uploads, Favoriten,
Flugaufträge oder MQTT-Kommandos. Nutzername, Storage-Key, signierte Links,
Signatur und Startkoordinaten werden verworfen. Unbekannte Template-Codes
bleiben numerisch unter `template_type_codes` erhalten; insbesondere die
lokalen Erweiterungen 4/5 werden nicht als Standard-Wegpunktmodus ausgegeben.

Es werden bis zu zehn Seiten mit je angefragten 50 Einträgen gelesen, insgesamt
höchstens 500 (bei kleinerer serverseitiger Seitengröße entsprechend weniger).
Antwortgröße pro Seite höchstens 1 MiB, HTTP-Timeout 5 Sekunden,
Gesamtbudget 15 Sekunden. Abweichende Seitenzahlen, wechselnde Gesamtzahl/
Seitengröße, doppelte Routen-IDs und unplausible Lücken verwerfen den Abruf.
Am Limit werden gefilterte Teilbestände mit `pagination_complete=false`
ausgegeben. Auch vollständig gelesene Seiten sind kein transaktionaler
Snapshot; `snapshot_consistency_verified=false` bleibt ausdrücklich bestehen.
Fehler ersetzen alte Cache-Werte durch eine leere Fehlerantwort; veraltete
Erfolge werden nicht als aktuelle Verbindung dargestellt. Cache maximal
30 Sekunden, nur im RAM; Löschen oder Wechsel der Sitzung wirkt sofort.

## Quellen und Prüfung

- [DJI Produkt-/Kameraindizes, einschließlich M3TA](https://developer.dji.com/doc/cloud-api-tutorial/en/overview/product-support.html)
- [DJI WPML-Indizes M3E/M3T/M3M](https://github.com/dji-sdk/Cloud-API-Doc/blob/master/docs/cn/60.api-reference/00.dji-wpml/40.common-element.md)
- [DJI WPML gemeinsame Elemente](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html)
- [DJI Pilot-2-Wayline-Verwaltung und lokale Kopien](https://developer.dji.com/doc/cloud-api-tutorial/en/feature-set/pilot-feature-set/pilot-wayline-management.html)
- [Offizielle Wayline-GET-Parameter und Antwort](https://github.com/dji-sdk/Cloud-API-Doc/blob/master/docs/en/60.api-reference/10.pilot-to-cloud/10.https/20.waypoint-management/10.obtain-waypointfile-list.md)
- [DJI Demo LoginController](https://github.com/dji-sdk/DJI-Cloud-API-Demo/blob/main/sample/src/main/java/com/dji/sample/manage/controller/LoginController.java)
- [DJI Demo Kontotypen](https://github.com/dji-sdk/DJI-Cloud-API-Demo/blob/main/sample/src/main/java/com/dji/sample/manage/model/enums/UserTypeEnum.java)

Regressionen: alle sechs Geräteprofile mit geschlossener Route/Fotoaktion,
veränderte RTH-/Geschwindigkeits-/Aktionsparameter, unbekannte/mehrfache XML-Felder,
Speichern/Laden/Export/Re-Import über die API, API-Zugriffsschutz, fehlende Quellen,
Namensmehrdeutigkeit und Modellkonflikte. Chromium war lokal nicht verfügbar;
der Installationsversuch lieferte defekte Downloadarchive. Echte Browserprüfung
der erweiterten Geräteauswahl und Pi-/Pilot-2-Abnahme stehen aus.
Lokaler Adapter zusätzlich mit HTTP-Mocks geprüft: GET-/Workspace-Begrenzung,
Pagination, Fehler, Limits, Cache, Tokenwechsel, Auth-Schutz und Dateirechte.
Die echte lokale Anmeldung und der Pi-Routenbestand sind noch nicht abgenommen.


## Schreibgeschützte Cloud-KMZ-Vorschau

Nur bereits gelistete Wayline-UUIDs aus einem vollständig geladenen
lokalen Pilot-2-Inventar sind auswählbar. Der GET-Endpunkt
/api/v1/local-cloud/waylines/{wayline_id}/preview prüft den bisherigen
Viewer-Zugriff, die Sitzung und den Workspace.

DJI GET /wayline/api/v1/workspaces/{workspace_id}/waylines/{id}/url
liefert einen signierten 302-Speicherlink. Der Server folgt der
Weiterleitung ausdrücklich nicht: Es werden ausschließlich HTTP-Links
für einen privaten/Loopback-Host auf Port 9000 und das konfigurierte
MinIO-Bucket akzeptiert. Das tatsächliche Ziel bleibt
127.0.0.1:9000; zur AWS-Signaturprüfung bleibt der ursprüngliche
Host-Header erhalten. Das DJI-Token wird nicht an MinIO gesendet.

Maximal 4 MiB komprimierte KMZ-Daten, 20 ZIP-Mitglieder, 2 MiB pro
Mitglied, 1000 Koordinaten und 32 GeoJSON-Geometrien. Die Vorschau
extrahiert nur WGS84-Koordinaten aus wpmz/waylines.wpml, alternativ
aus wpmz/template.kml. Keine XML-Metadaten, DJI-Kommandos,
Flugaktionen, signierten URLs oder KMZ-Rohdaten im Browser.

Die separate Leaflet-Kartenebene bleibt nicht-interaktiv. Solange
sie sichtbar ist, führen Kartenklicks nicht zu neuen Missions- oder
Geo-Punkten. "Cloud-Vorschau schließen" leert die Ebene. Es gibt
keine automatische Bearbeitung, Speicherung oder Flugfreigabe.

Wichtig: Das lokale Backend muss MinIO signierte Links zur
gewünschten Wayline liefern. Andere Storage-Origins werden bewusst
verweigert, nicht automatisch freigeschaltet. Der Pi-Liveabruf
muss separat bestätigt werden.


## Datenschutzschonender Live-Test auf dem Raspberry Pi

Das zusätzliche Kommando ist ausschließlich lesend und verwendet die bereits
privat gespeicherte Session. Es prüft zunächst die vollständige paginierte
Wayline-Liste und anschließend **standardmäßig nur die erste** gefundene Route.
Die Ausgabe nennt ausschließlich den laufenden Index, einen abstrakten
Fehlerzustand sowie bei erfolgreichem Abruf Geometrie-/Punktanzahl und Dateiquelle.
Route-Namen, -UUIDs, Token, S3-URLs und Roh-KMZ werden weder ausgegeben noch
auf die Festplatte geschrieben.

```bash
cd ~/Projekte/AeroNexusAdvanced
set -a
source .env
set +a
# Alte systemd-/Shell-Importpfade aus Fremd-Checkouts ausdrücklich überschreiben:
PYTHONPATH="$PWD/src" .venv/bin/python -m aeronexus.pilot2_wayline_preview --limit 1
```

Nach erfolgreichem Einzeltest können mit `--limit 8` bis zu acht inventarisierte
Routen geprüft werden. Bei nicht vollständigem Inventar oder fehlender Sitzung
wird kein KMZ-Dateiabruf ausgelöst. Mögliche Statuswerte sind etwa
`connected`, `storage_origin_rejected`, `storage_unavailable`,
`invalid_archive`, `unsupported_geometry` und `unavailable`.
`storage_origin_rejected` wird nicht durch Abschalten der URL-Prüfung
umgangen. Der echte Pi-Abruf und die Speicherlinkkompatibilität stehen
noch zur Abnahme aus.

## Gemeinsame Kartenübersicht von bis zu acht Pilot-2-Waylines

Im Mission Studio unter **Cloud-Routen** bietet die explizite Schaltfläche
„Alle lokalen Routen auf Karte (max. 8)“ eine gemeinsame GeoJSON-Vorschau.
Der Button wird erst nach vollständigem lokalem Pilot-2-Inventar aktiviert.
Es werden ausschließlich Einträge mit Quelle `pilot2-local-cloud` ausgewählt,
höchstens acht unterschiedliche Wayline-IDs aus der aktuellen Bibliothek.
FlightHub-Routen werden nicht für lokale DJI-KMZ-Downloads ausgegeben.

Jede Route wird erst nach Klick über den bestehenden, autorisierten und
streng begrenzten `GET /api/v1/local-cloud/waylines/{wayline_id}/preview`
angefordert. Ein neues Cloud- oder MinIO-Downloadverfahren gibt es nicht.
Die Abfragen erfolgen sequenziell, mit Abbruchmöglichkeit und begrenztem
Zeitbudget pro Anfrage. Fehler einer Route hindern nicht die Darstellung
der bereits erfolgreichen Routen; die Oberfläche kennzeichnet Teilerfolge.

Für jede erfolgreich gelesene Route zeigt das Kartenpanel Name, eigene
Farbe, Punktzahl und Geometrieanzahl. Checkboxen blenden nur den jeweiligen
schreibgeschützten Leaflet-Layer ein oder aus, „Zoom“ zentriert eine Route,
und „Alle sichtbaren Routen zentrieren“ passt den Kartenausschnitt an.
„Schließen“ bricht offene Requests ab, entfernt alle Vorschau-Layer und
ermöglicht anschließend wieder Kartenbearbeitung. Einzel- und
Mehrfachvorschau sind gegenseitig exklusiv.

Routennamen werden ausschließlich über DOM-Textknoten eingefügt,
GeoJSON-Elemente bleiben `interactive:false`; keine Routendaten
werden in editierbare Missionen oder den WPML-Export übernommen.
Die KMZ-Vorschau gibt ausdrücklich keine Flugfreigabe und liest keine
DJI-Flugaktionen aus. Die Funktion wurde automatisiert getestet;
eine reale Browserprüfung auf dem Pi ist zusätzlich erforderlich.
