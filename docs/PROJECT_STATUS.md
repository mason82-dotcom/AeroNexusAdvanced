# AeroNexusAdvanced – Projektstatus / Wiederaufnahmepunkt

**Stand:** 16. Oktober 2026  
**Phase:** 17 (Mission Studio: P1 GeoObjekte/GeoPhoto, P2 lokale
Flächenflugstreifen und WSS-Cache-Ereignisse, P4 GeoTIFF-/STL-Vorschau)
nach PR #4 in main integriert und in GitHub Actions getestet.
Phase 15/16 FlightHub Operations Center auf Raspberry Pi 5/Chrome live
bestätigt; Phase 17 auf Pi/Chrome noch **nicht** live geprüft.
Phase 9 Cloud-MQTT und optionaler Cloud API 2 BFF bleiben deaktiviert.  
**Repository:** `mason82-dotcom/AeroNexusAdvanced`  
**Letzter dokumentierter Pi-Teststand:** **541 Tests, 1 Warnung**
(Phase 16, vor RTK-Scroll-Korrektur), systemd-Dienst `active`.
DJI Matrice 4T im Operations Center live bestätigt.
**Aktueller GitHub-Actions-Teststand:** **579 Tests, 1 Warnung**
(Python 3.12; PR #4 einschließlich Phase 17). Ein Pi-/Chrome-Test
der neu integrierten Funktionen sowie der RTK-Scroll-Korrektur steht aus.

## Bestätigt auf Raspberry Pi 5

- Arbeitsverzeichnis: `/home/mason/Projekte/AeroNexusAdvanced`
- Virtuelle Python-Umgebung: `.venv/bin/python` (Python 3.13.5)
- Installation: `aeronexusadvanced` 0.1.0, editierbar, zusätzlich
  `paho-mqtt` 2.1.0 (Extra `mqtt`)
- `python -m pip check`: **No broken requirements found**
- **537 passed, 1 warning** auf dem Pi (Phase 15) und
  `systemctl --user is-active aeronexusadvanced` → `active`.
  Die Testisolierung in `tests/conftest.py` verhindert den Zugriff
  automatisierter Tests auf produktive DJI- und Token-Umgebungsvariablen;
  produktive Konfiguration bleibt unverändert.
- Phase 13/14 Mission Studio und LAN-Zugriff sind auf dem Pi getestet.
  Phase 15 Operations Center mit der Matrice 4T im Chrome live gezeigt:
  aktueller FlightHub-Status, 5 Routen, 5 Modelle, HMS und OSD.
  Phase 16 hat **541 Tests auf dem Pi** bestanden, der Chrome-Live-Test
  bestätigt Online-Status, 86-%-Akku, Standby, RTK und HMS. Die nachträgliche
  RTK-Scroll-Korrektur ist mit **543 GitHub-Actions-Tests** geprüft;
  deren Pi-/Chrome-Nachtest steht noch aus.
- Bekannte, derzeit nicht blockierende Warnung:
  `StarletteDeprecationWarning` in `fastapi/testclient.py`
  zu `httpx` / `httpx2`.

## Live-Test FlightHub 2 (Phase 10) – bestätigt

- Gateway: **EU** `https://es-flight-api-eu.djigate.com`, OpenAPI **v2.0**
  (v0.1 antwortet ebenfalls).
- Organisationsschlüssel gültig, gehört zur Organisation mit dem
  Kurzcode aus `AERONEXUS_DJI_ORGANIZATION_ID` (Prüfung beim Start).
- 1 Projekt; **Matrice 4T** (`0-99-1`) online erkannt, Zustand
  (`DeviceState_wa345`) korrekt normalisiert: Akku, Spannung,
  Temperatur, Flugmodus, Satelliten, Höhe, Geschwindigkeit; HMS-Hinweise.
- Ohne GPS-Fix (drinnen) meldet DJI Position 0/0 → keine Position.
- **RC Plus 2 erscheint in FlightHub nicht als eigenes Gerät**; über
  FlightHub liefert das Dashboard derzeit nur die Drohne.
- Abweichungen der Live-API von der Dokumentation (alle in
  `docs/phase-10-flighthub-fleet.md` und durch Tests abgesichert):
  - Gerätelisten liefern `{"list": null}`, solange nicht
    `device_model_class=drone` mitgegeben wird; `rc` wird mit Code
    `210070` abgelehnt.
  - Per Pilot 2 verbundene Drohne steht im `gateway`-Feld, `drone` ist `null`.
  - Fehlender/ungültiger Schlüssel: HTTP 200 mit Code `200401`.
  - `height` = absolute Höhe, `elevation` = Höhe über Startpunkt.

## Web-Dashboard – aktueller Betriebsstand

- Oberfläche: **`https://192.168.178.63:8000/status`** (HTTP wird nicht
  mehr bedient).
- Betrieb als **systemd-User-Dienst** `aeronexusadvanced` (aktiviert,
  Linger an → Start beim Booten ohne Login; `Restart=always`, nach
  Absturz in ~10 s neu gestartet, getestet). Details: `docs/deploy-pi.md`.
  ```bash
  systemctl --user status aeronexusadvanced
  systemctl --user restart aeronexusadvanced   # nach .env-/Code-Änderungen
  journalctl --user -u aeronexusadvanced -f
  ```
- TLS: projekteigene lokale CA in `config/pki/` (gitignoriert, private
  Schlüssel 0600), Serverzertifikat für IP `192.168.178.63`, gültig bis
  **16.10.2027** (`deploy/pi/tls-renew-server.sh` verlängert mit derselben
  CA). Auf den Anzeigegeräten nur `config/pki/ca.crt` installieren.
- Konfiguration ausschließlich in `.env` (gitignoriert, `chmod 600`;
  Vorlage `.env.example`): Dashboard-Token, FlightHub-Schlüssel,
  Organisations-Kurzcode, MQTT-Zugangsdaten.
- FlightHub-Polling **aktiv**: alle 15 s, Telemetrie gilt nach 45 s
  als veraltet; Browser-Aktualisierung alle 5 s.
- Ein Polling-Zyklus kostet je Projekt 2 + 2 × Geräte GET-Aufrufe.
- MQTT-Feed (Phase 9) **deaktiviert** (`AERONEXUS_CLOUD_MQTT_ENABLED=0`);
  aktive Datenquelle ist FlightHub 2.
- FlightHub-Bibliothek (Routen, Karten-Modelle, Flugaufträge) wird alle
  10 min gelesen (`AERONEXUS_FH_CATALOG_SECONDS`); live bestätigt:
  5 Routen, 5 3D-Modelle, 0 Flugaufträge, Systemstatus OK.
- Der Launcher verweigert HTTP auf einer LAN-Adresse ohne TLS und eine
  `.env`, die nicht `chmod 600` ist.

## Implementierte Funktionen

- **Phasen 8.3–8.7:** strikt lesende FlightHub-2-Adapter (Public Cloud und
  On-Premises, nur geprüfte HTTPS-GET-Pfade), validierte lokale
  Projekt-/Geräteverwaltung, Frische-Klassifikation (`fresh`, `stale`,
  `missing`, `unknown_age`, `clock_skew`), Status-API mit separatem
  Dashboard-Token, responsive Weboberfläche.
- **Phase 9 – DJI Cloud API Live-Feed (opt-in):** abonniert ausschließlich
  `thing/product/+/osd` mit einem ACL-beschränkten Konto, sendet nie
  (Publish gesperrt); Drohne/Fernsteuerung aus OSD-Eigenschaften,
  strenge Validierung, anonyme Feed-Zähler. Doku:
  `docs/phase-9-cloud-api-live-feed.md`.
- **Phase 10 – FlightHub-2-Flotte (opt-in):** nach offizieller
  OpenAPI-V2.0-Spezifikation; Public `project/device` +
  `device/{sn}/state`, On-Premises `projects/{uuid}/topologies`
  (Drohnen + Fernsteuerungen mit Projektzuordnung); FlightHub-Text-Enums;
  automatisches Polling im selben StatusRuntime/Inventory des Servers
  (damit ist der frühere Punkt „Phase 8.8“ umgesetzt); HMS-Meldungen;
  `python -m aeronexus.probe_fleet` (nur Zähler). Doku:
  `docs/phase-10-flighthub-fleet.md`.
- **Übernommen aus `alecad/dji-flighthub2-cli`** (Apache-2.0, `NOTICE`):
  EU-Gateway/Regionen, OpenAPI v0.1, `{"list": null}`-Toleranz,
  typisierte Fehler mit Request-ID, Retry/Backoff für GET, HMS,
  Projektbibliothek (Routen, Modelle, Flugaufträge) und Flugspur als
  GeoJSON (`/api/v1/flighthub/catalog`, `.../tasks/{uuid}/track`).
- **Sicherheitsanforderungen unverändert:** keine Flugbefehle, keine
  Steuerungsübernahme, keine Schreiboperationen; DJI-Dock-Integration
  ausgeschlossen; nur Drohnen und Fernsteuerungen im Bestand.

## Phase 11 – mobile Dashboard-Diagnose (auf dem Pi getestet)

- Smartphone-taugliche Gerätekarten mit Akkubalken, Telemetrie-, GPS-/RTK- und
  HMS-Status, getrennten Höhendaten, Empfangsalter und Frischekennzeichnung.
- Anzeige des letzten erfolgreichen DJI-Synchronisierungszeitpunkts;
  zusätzliche FlightHub-Abfragen oder neue DJI-Berechtigungen sind nicht nötig.
- Geschützte Inhalte und verspätete asynchrone Antworten werden beim
  Trennen der Dashboard-Sitzung verworfen; die vollständige technische
  Gerätetabelle bleibt aufklappbar.
- Phase 11: **400 Tests auf dem Pi bestanden**; anschließend ein
  zusätzlicher Root-Weiterleitungstest: **401 Tests auf dem Pi bestanden**.
  Android-Screenshots bestätigen FlightHub-Live-Anzeige nach Anmeldung:
  Matrice 4T online, Akku/RTK/Flugmodus/HMS, 5 Routen, 5 3D-Modelle.
  Dokumentation: `docs/phase-11-dashboard-diagnostics.md`.

## Phase 12 – mobile FlightHub-Bibliothek und HMS

- Responsive Karten für Routen, 3D-Modelle und Flugaufträge,
  klassische Tabellen aufklappbar. Bibliothek vor erfolgreicher
  Authentifizierung ausgeblendet; HMS-Meldungen mit originalem DJI-Code
  und nur verifiziertem Klartext. Separate Akkufarbheuristik.
- 7 zusätzliche Regressionstests; GitHub-Actions-Test erfolgreich,
  neuer Pi-/Android-Smoke-Test steht aus.

## Phase 13 – Chrome Desktop Mission Studio

- **`https://192.168.178.63:8000/studio`**: interaktive Leaflet-Karte
  (OSM/Esri), eigene WPML-Wegpunktmissionen erstellen, bearbeiten,
  speichern, löschen und als KMZ exportieren. M4T (99/1, Kamera 89)
  und M4E (99/0, Kamera 88), DJI-WPML-Ordnerstruktur mit
  `template.kml` und `waylines.wpml`; nur ein konservativer
  `waypoint`-Teilumfang.
- Zusätzlich sicherer Re-Import **eigener AeroNexus-WPML-KMZ** zur
  Nachbearbeitung. Komplexe Fremdmissionen bewusst nicht unterstützt.
- Private Medienbibliothek für lokale JPEG/PNG/WebP/MP4-Dateien auf dem Pi,
  max. 25 MiB pro Datei, authentifizierte Vorschau und Löschung.
- Read-only Flottenansicht und optional GPS-Marker auf Karte.
- Alle Missions- und Medienänderungen bleiben lokal auf dem Pi,
  unter `~/.local/share/aeronexusadvanced` (0700, Dateien 0600).
- **Keine** DJI-Missionsübertragung oder -ausführung, keine
  automatisierte DJI Flugsteuerung oder Dock-Integration.
- GitHub CI/Python 3.12: **468 passed, 1 warning**. Raspberry Pi/
  Chrome-Test und anschließender manueller DJI-Pilot-2-Importcheck
  sind noch erforderlich. Details:
  `docs/phase-13-desktop-mission-studio.md`.

## Phase 14 – ohne Token in Status & Chrome Studio (CI bestätigt)

- **`/status` und `/studio` ohne Login-/Token-Eingabefelder**;
  lokale Flottendaten, FlightHub-Bibliothek, Missionen und Medien
  werden nach Seitenaufruf automatisch geladen.
- **Opt-in Pflicht:** `AERONEXUS_LAN_NO_TOKEN=1` und
  `AERONEXUS_LAN_HOST=192.168.178.63` in der privaten Pi-`.env`.
  LAN-Modus ist ausschließlich für direkte HTTPS-Verbindungen aus
  `192.168.178.0/24` (und Loopback) vorgesehen; Host, Origin,
  Fetch-Metadata und Peer-IP werden geprüft.
- Damit können **alle Geräte im Heimnetz** GPS-/Seriennummern sehen
  und lokale Studio-Missionen und Medien ändern/löschen. Niemals über
  öffentliche Ports, Reverse Proxies oder Gastnetz veröffentlichen.
- Zusätzlich den ursprünglich fatalen JavaScript-Klammerfehler im
  Leaflet-Kartencode behoben, der das komplette Chrome-Skript blockierte.
  Neue `node --check`-Regressionstests.
- **GitHub Actions: 486 Tests bestanden, 1 Warnung** (Python 3.12);
  Raspberry-Pi- und Chrome-Live-Test der Phase 14 noch ausstehend.
  Siehe `docs/phase-14-token-free-lan.md`.
- Flugsteuerung und DJI-Dock-Integration bleiben gesperrt.

## Phase 15 – FlightHub Operations Center und DJI-Quellenvergleich

- Neues **`/operations`** (Chrome): Projektkarte über 76694 Forst,
  Matrice-4T-Cockpit, Live-OSD/HMS, Status-basierte Flugauftrag-Filter,
  lokale Missionsvorschau und GeoJSON-Flugspuren. Ohne DJI-Steuerbefehle.
- Die technischen Beispiele
  `dji-sdk/FlightHub-2-Frontend-Standalone-Component`,
  `dji-sdk/FlightHub-2-OpenAPI-V2-Demo`,
  `dji-sdk/Cloud-API-2` und
  `alecad/dji-flighthub2-cli` verglichen.
- **CLI-Erweiterung:** Abruf von Medienmetadaten für bereits bekannte
  FlightHub-Flugaufträge. Original-URLs, Previews, signierte Links,
  DJI-Seriennummern und Zugangsdaten werden nicht weitergegeben.
- Optionaler **DJI Cloud API 2**-Quellenadapter: ausschließlich
  `GET /api/v1/devices` eines separat laufenden und authentifizierten
  offiziellen SDK-BFF (x86_64-Host). DRONE-only, keine DOCKs; OSD/HMS
  auf gültige Werte und Zeitstempel begrenzt. Ohne BFF bleibt der
  Adapter abgeschaltet, FlightHub 2 weiterhin betriebsbereit.
- **GitHub Actions/main: 537 Tests bestanden, 1 Warnung** auf dem
  Phase-15-Stand; Raspberry Pi 5 mit Python 3.13 ebenfalls
  **537 passed, 1 warning**, Operations Center in Chrome bestätigt.
  Der beim Live-Test beobachtete Fluggerätstatus der Matrice 4T:
  online, frisch, Spannung 16,365 V, Akku 87 %, Temperatur 32,2 °C,
  Flugmodus 0 (Standby), RTK `is_fixed:not_started`,
  HMS `0x16070042` ohne verifizierte Beschreibung.
- Dokumentation: `docs/phase-15-dji-sources-operations.md`.

## Phase 16 – kompaktes DJI-Cockpit, geprüft

- Anzeige der Gerätekonnektivität (Online/Offline/Unbekannt) **getrennt**
  von der Aktualität der empfangenen Daten (fresh/stale/missing/unknown_age/
  clock_skew): frischer Offline-Status wird nicht als Live-Telemetrie
  fehlinterpretiert.
- Oben fixierte Kurzübersicht von Akku, Modus, Start-relativer Höhe,
  horizontaler Geschwindigkeit und RTK; bei veralteten oder Offline-Daten
  eindeutiger Hinweis „nur letzte Messwerte“.
- Die im Status-Dashboard bereits verwendete, begrenzte RTK-Texttabelle
  wird übernommen (`is_fixed:not_started` → „RTK nicht gestartet“).
  Rohwerte verbleiben im aufklappbaren Technik-Bereich.
- Flugzeit/Flugstarts explizit **API-Werte**, insbesondere bedeuten
  jeweils 0 nicht gesichert eine nie geflogene Drohne.
  GPS-/RTK-Satellitenzahlen bleiben „laut DJI“, nicht GPS-Fix-Nachweis.
- HMS nur mit authentischem DJI-Code und übermitteltem Klartext.
  Aufgeklappte Details und Scrollposition bleiben bei 15-s-Updates.
- Zusätzliche Node.js-DOM-Regressionstests testen echte Rendererreaktionen
  bei Online-, Offline-, Stale- und unbekannten Statusangaben.
  **Auf dem Pi: 541 Tests bestanden, 1 Warnung.**
  Neue Chrome-Screenshots bestätigen das Haupt-Cockpit mit 86-%-Akku,
  Standby und korrekt lesbarem RTK sowie den aufklappbaren Technikbereich.
  Bei längerem RTK-Rohwert wurde ein abgeschnittener Textrest beobachtet;
  dessen Korrektur (Paint-Containment, Monospace-Volllängenzeile, kein
  unnötiges DOM-Rebuild beim 15-Sekunden-Refresh) ist mit
  **GitHub Actions/main: 543 Tests bestanden, 1 Warnung** geprüft.
  Pi-/Chrome-Nachtest dieser Scrollkorrektur ist noch ausstehend.

## Phase 17 – GeoPhoto, lokale Geo-Objekte, Flächenstreifen, Gelände

- PR **#4** am 16.10.2026 in `main` übernommen (Merge `7fabe6836030`).
  **GitHub Actions: 579 passed, 1 warning** (Python 3.12, inkl.
  Node-JavaScript-Syntax, API-/LAN-Zugriff, Geo-/STL-/WSS-Regressionen).
- Neuer eigenständiger, streng validierter Geo-Objekt-Speicher mit Punkt,
  Linie, Polygon, Kreis sowie CRUD im Mission Studio.
- GeoPhoto-Metadaten für lokal gespeicherte Bilder (manuelle GPS-
  Position, Höhe, Heading/Pitch/Roll, Aufnahmezeit und Notiz),
  eigene Kartenmarker. Keine automatische EXIF- oder Bildabdeckungsrechnung.
- Parallele Flugstreifen innerhalb von Polygonen als **Vorschau**,
  **keine** zusammenhängende flugfertige DJI-WPML-Route.
- Optionaler WSS-Statusereigniskanal `AERONEXUS_STUDIO_EVENTS=1` nur
  bei explizitem HTTPS-LAN-Zugriff. Standardmäßig deaktiviert.
- Begrenzter GeoTIFF-Import mit optionalen Python-GDAL-Bindings,
  schematische isometrische Höhenvorschau und lokaler binärer STL-Export.
  Ohne GDAL: GeoTIFF-API meldet Fehler statt falsche Geländedaten.
- DJI-Flugbefehle weiter 403; vorhandene WPML-Missionen unverändert.
- **Nicht auf Pi/Chrome installiert oder mit realem GDAL, GeoTIFF,
  WSS und DJI Pilot 2 importgetestet**. Siehe
  `docs/phase-17-geo-photo-survey-terrain.md`.

## Phase 18 – DJI Cloud API v1.18-Protokollabgleich (optional, read-only)

- DJI-Veröffentlichungsstand vom **13.10.2026 (v1.18)** mit offiziellen
  Release Notes verglichen: O4 Ground Station und Dock-2/3-Funktionen sind
  nicht automatisch für die Matrice 4T/Pilot 2 relevant.
- Vorhandenen Pi-MQTT-Empfänger erweitert: optional
  `AERONEXUS_OSD_STATE_ENABLED=1` für `thing/product/+/state`.
  Standard bleibt **OSD-only, aus**, solange der Pi-Broker nicht geprüft ist.
- Bei State-Nachrichten werden ausschließlich bereits bekannte Geräte und
  kanonisch freigegebene Telemetriefelder übernommen. Keine Speicherung von
  `device_secret`, Nonces oder unbekannten DJI-Meldungsstrukturen.
- RTK `is_fixed` akzeptiert jetzt auch begrenzte String-Enums neben
  Integer-Codes. Vollständige MQTT-Subscribe-Autorisierung für OSD und State
  erforderlich. Client bleibt gegen Publish gesperrt.
- FlightHub-EU-Polling, Mission Studio (inkl. Phase 17) und DJI-Flugkommando-
  Sperren unverändert. Kein automatischer Providerwechsel und **keine**
  FlightHub-2-On-Premises- oder Pilot-2-Serverinstallation.
- Tests mit Fake-MQTT/Fixture, noch **kein echter Pi-EMQX-/Pilot-2-End-to-End-Test**.
  Vor der Aktivierung muss ein separater DJI-Cloud-API-Broker samt
  Pilot-2-Workspace/Lizenz eingerichtet und die eigene Read-only-ACL
  verifiziert werden. Die per-Gerät-Frischemarkierung enthält noch keine
  getrennten Empfangsalter je `osd` und `state`-Eigenschaft.
  Details: `docs/phase-9-cloud-api-live-feed.md`.

## Nicht live verifiziert

- On-Premises-Topologie (`projects/{uuid}/topologies`): nur mit
  spezifikationsgetreuen Fixtures getestet.
- Phase-9-MQTT-Feed mit M4T/RC Plus 2 (braucht laufenden Broker).
- Drohne im Flug (Position, Flugmodi, Geschwindigkeiten unter GPS-Fix).

## Nächste Schritte

1. `config/pki/ca.crt` auf den Anzeigegeräten als vertrauenswürdige CA
   installieren (Anleitung `docs/deploy-pi.md`).
2. Feste IP bzw. DHCP-Reservierung für `192.168.178.63` im Router, sonst
   Zertifikat und `AERONEXUS_BIND` bei IP-Wechsel erneuern.
3. Testflug draußen mit GPS-Fix: Position, Flugmodus-Wechsel, Höhe und
   Geschwindigkeit im Dashboard prüfen.
4. Fernsteuerung (RC Plus 2) über FlightHub: prüfen, ob
   `topologies/history` oder ein anderer lesender Endpunkt die RC
   liefert; sonst über den Phase-9-MQTT-Feed abbilden.
5. Flugspur-GeoJSON mit einem echten FlightHub-Flugauftrag prüfen
   (bisher keine Aufträge im Projekt).

## Wiederaufnahme

```bash
cd ~/Projekte/AeroNexusAdvanced
git pull --ff-only
.venv/bin/python -m pip install -e '.[test,mqtt]'
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
set -a; . ./.env; set +a; .venv/bin/python -m aeronexus.probe_fleet
```

**Wichtige Abgrenzung:** Dieses Dokument speichert den *Projekt- und
Betriebsstatus*, nicht fortlaufende Telemetriedaten oder den Arbeitsspeicher
des laufenden Webservers. Seriennummern, Schlüssel und Positionen gehören
nicht in dieses Dokument.
