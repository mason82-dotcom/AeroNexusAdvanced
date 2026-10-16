# AeroNexusAdvanced – Projektstatus / Wiederaufnahmepunkt

**Stand:** 16. Oktober 2026  
**Phase:** 10 (FlightHub-2-Flotte, live) erfolgreich getestet; Phase 9
(DJI Cloud API MQTT-Feed) implementiert, noch nicht live getestet.  
**Repository:** `mason82-dotcom/AeroNexusAdvanced`  
**Letzter auf Raspberry Pi 5 bestätigter Entwicklungs-Commit:** `6322869`

## Bestätigt auf Raspberry Pi 5

- Arbeitsverzeichnis: `/home/mason/Projekte/AeroNexusAdvanced`
- Virtuelle Python-Umgebung: `.venv/bin/python` (Python 3.13.5)
- Installation: `aeronexusadvanced` 0.1.0, editierbar, zusätzlich
  `paho-mqtt` 2.1.0 (Extra `mqtt`)
- `python -m pip check`: **No broken requirements found**
- `env -u AERONEXUS_DJI_ORGANIZATION_ID .venv/bin/python -m pytest -q`:
  **393 passed, 1 warning** (auf dem Pi für Commit `6322869` bestätigt).
- Danach wurde `tests/conftest.py` ergänzt: Eine automatische Test-Fixture
  blendet ausschließlich **während der Testläufe** die produktiven Variablen
  `AERONEXUS_DJI_*`, `AERONEXUS_FH_*`, `AERONEXUS_CLOUD_MQTT_*` und
  `AERONEXUS_STATUS_TOKEN` aus. Tests setzen bei Bedarf explizit künstliche
  Werte. `tests/test_env_isolation.py` enthält zwei Regressionstests.
  **Neuer Teststand (erwartet 395 Tests) muss noch auf dem Pi bestätigt werden.**
  Die produktive Organisationsprüfung wurde nicht geändert.
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

## Phase 11 – mobile Dashboard-Diagnose (noch nicht auf dem Pi getestet)

- Smartphone-taugliche Gerätekarten mit Akkubalken, Telemetrie-, GPS-/RTK- und
  HMS-Status, getrennten Höhendaten, Empfangsalter und Frischekennzeichnung.
- Anzeige des letzten erfolgreichen DJI-Synchronisierungszeitpunkts;
  zusätzliche FlightHub-Abfragen oder neue DJI-Berechtigungen sind nicht nötig.
- Geschützte Inhalte und verspätete asynchrone Antworten werden beim
  Trennen der Dashboard-Sitzung verworfen; die vollständige technische
  Gerätetabelle bleibt aufklappbar.
- Code und fünf Regressionstests in GitHub ergänzt; **400 Tests erwartet,
  vollständiger Pi-Test noch ausstehend**. Dokumentation:
  `docs/phase-11-dashboard-diagnostics.md`.

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
