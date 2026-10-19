# AeroNexusAdvanced

Lokales DJI-Daten- und Auswertungsportal auf Basis von Python/FastAPI für einen Raspberry Pi 5. Die Anwendung verbindet **lesende** Quellen von DJI Cloud API (Pilot 2 / MQTT), FlightHub 2 OpenAPI und optional DJI Cloud API 2 mit einer geschützten Weboberfläche. Eigene Missionen und Medien können lokal bearbeitet werden; daraus folgt **keine Freigabe für Flugsteuerung oder automatischen DJI-Upload**.

**Dokumentation:** [Einstieg und thematischer Index](docs/README.md) · [aktueller Repository-Stand und offene Punkte](docs/PROJECT_STATUS.md) · [Pi-Betrieb](docs/deploy-pi.md) · [technisches Design](DESIGN.md) · [UX-Vertrag](UX-CONTRACT.md)

## Funktionsübersicht

| Oberfläche | Zweck | Wichtige Grenzen |
| --- | --- | --- |
| `/status` | DJI-Live-Cockpit: Fluggerät/RC, OSD, Akkus, GPS/RTK, Kameras, Link und HMS | Nur empfangene und zeitlich gültige Werte; MQTT-Abonnement allein bedeutet **nicht** Live-Daten |
| `/operations` | Betriebsübersicht, DJI-/FlightHub-Quellenvergleich, optionale Videowiedergabe | Kein Flugkommando; Cloud API 2 benötigt einen separaten authentifizierten x86_64-Backend-Dienst |
| `/studio` | Lokale Wegpunktplanung, CSV, Geometrie/Survey, KMZ-Export/-Import, lokale Medien, Cloud-Wayline-Metadaten | Kein automatischer DJI-Missionsupload oder Flugstart über die produktive Weboberfläche |
| `/media` | DJI-MinIO-Medienkatalog, Fotokatalog, Metadaten und Medien-Sync-Status | DJI-Originalmedien und Bucket bleiben bei Katalogabfragen unverändert |
| `/thermal` | DJI-R-JPEG, Thermal-Messungen, optionale PV-Analyse | Radiometrische Messungen benötigen ein passend installiertes Thermal SDK |
| `/multispectral` | Mavic-3M-Bänder, Indizes, Verarbeitung und Export | Ergebnisse hängen von Eingangsqualität, Kalibrierung und installierten Abhängigkeiten ab |
| `/results` | Raster-/GeoTIFF-/COG-Katalog und Kartenkacheln | Abhängigkeit von optionalen Raster-/GDAL-Komponenten |

Der auf GitHub integrierte HMS-Verlauf aus PR #65 speichert normalisierte HMS-Zustandswechsel in einer privaten, begrenzten SQLite-Chronik und stellt dafür eine geschützte Lese-API bereit. Ein produktiver Pi-Rollout ist damit noch nicht bestätigt.

Details: [Live-Cockpit](docs/live-telemetry-cockpit.md), [Missions- und Wayline-Abgleich](docs/mission-wayline-reconciliation.md), [DJI-HMS](docs/dji-cloudapi-hms.md), [MinIO-Medien](docs/phase-21-dji-minio-media.md).

## Datenquellen und Sicherheitsgrenzen

- **DJI Cloud API / Pilot 2:** Optionaler, standardmäßig deaktivierter MQTT-Leser am eigenen EMQX-Broker. Über `thing/product/+/osd` (optional `/state` und HMS-Events) kommen nur tatsächlich gesendete Werte an. MQTT-Lesezugang benötigt eigene ACLs; keine Publish-Berechtigung. [Konfiguration](docs/phase-9-cloud-api-live-feed.md).
- **FlightHub 2:** Unabhängige OpenAPI-V2-Lesezugriffe auf freigeschaltete Projekte und Geräte; keine Gleichsetzung mit lokalen Cloud-Routen. [Flottenanbindung](docs/phase-10-flighthub-fleet.md).
- **DJI Cloud API 2:** Getrennte, optional deaktivierte Bridge zu einem bereits betriebenen, authentifizierten SDK-Backend (x86_64); **nicht** die gleiche Schnittstelle wie MQTT oder FlightHub. [Integrationsgrenzen](docs/phase-18-cloudapi2-rollout.md).
- **Lokale Speicherung:** Studio-Missionen, Medien und Indexdaten liegen außerhalb von Git. Das private Verzeichnis `cloud-server/`, `.env`, Zertifikatsschlüssel und MinIO-Objekte sind nicht Teil des Repositorys.
- **Sicherheit:** Der optionale tokenfreie HTTPS-LAN-Modus kann lokalen Geräten **auch Schreibzugriff auf Studio-Missionen und lokale Medien** ermöglichen. Nicht ins Internet weiterleiten. [LAN-Zugriffsmodell](docs/phase-14-token-free-lan.md).
- Die technische Blockierung von Flugbefehlen ersetzt **nicht** die manuelle Sicherheitsprüfung exportierter DJI-KMZ/WPML-Dateien vor einem Flug.

## Optionales Control Center auf Port 8085

Ein eigenständiges, responsives [AeroNexus-Control-Portal](docs/control-portal-fh2.md) kann per ausschließlich lesendem Docker-Bind-Mount unter `/aeronexus/` neben der bestehenden DJI-Pilot-2-Anmeldung bereitgestellt werden. Es verlinkt die bestehenden geschützten Fachmodule, während die native FlightHub-2-Projektkarte bzw. das DJI-Cockpit eine **separate FlightHub-2-Installation**, eigene Projektberechtigungen und eine bewusste Aktivierung voraussetzen. Dieses optionale Portal enthält keine DJI-Secrets und startet keine Flüge. **Das Vorbereiten auf GitHub ist kein produktiver Pi-Rollout.**

## Installation und Entwicklung

Voraussetzung: Python 3.11 oder neuer. Die Grundinstallation ist nicht gleichbedeutend mit einer betriebsbereiten DJI-/MinIO-Anbindung.

~~~bash
git clone https://github.com/mason82-dotcom/AeroNexusAdvanced.git
cd AeroNexusAdvanced
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test,mqtt]'
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
~~~

Optionale Pakete: `minio`, `multispectral`, `raster`, `ui-browser` (siehe `pyproject.toml`). Die Konfigurationsvorlage ist `.env.example`; niemals echte Tokens oder DJI-Gerätekennungen in Git einchecken.

Für den Pi sind der systemd-User-Dienst, TLS-Zertifikate und das vorhandene lokale Netzwerk ausdrücklich separat einzurichten. **Nicht** blind in einer produktiven Pi-Arbeitskopie überschreiben oder `git clean -fdx` ausführen.

[Pi-Betrieb und TLS](docs/deploy-pi.md) · [Lokale Cloud-Migration (historischer Ablauf)](docs/local-cloud-server-migration.md) · [MinIO-Reader und Index](docs/phase-21-dji-minio-media.md).

## Betriebsdiagnose

Die folgenden Befehle lesen nur den Status der bestehenden Pi-Installation:

~~~bash
cd ~/Projekte/AeroNexusAdvanced
git status --short --branch
systemctl --user is-active aeronexusadvanced
systemctl --user status aeronexusadvanced --no-pager
curl --cacert config/pki/ca.crt https://192.168.178.63:8000/health
~~~

Die gezeigte IP ist der dokumentierte Beispiel-/Pi-LAN-Host und muss gegebenenfalls an die tatsächliche Konfiguration angepasst werden. Ein grüner Health-Check belegt nicht automatisch einen frischen MQTT-Datenstrom, eine angemeldete RC oder eine erfolgreiche Cloud-Wayline-Synchronisation.

Sichere Abnahmepfade: [Produktiv-API nur lesend](docs/production-ui-readonly-audit.md), [Produktiv-Browserprüfung](docs/production-ui-browser-audit.md), [isolierte Studio-Chromium-Tests](docs/studio-full-ui-acceptance.md).

## Entwicklungsstatus und Historie

Die maßgebliche GitHub-Implementierung ist der Stand von `main`; ein **Test-/Dokumentationsstand ist kein Nachweis, dass er bereits auf dem Pi ausgerollt wurde**. Aktuelle GitHub-Branches, noch offene Pilot-2-Upload-Arbeit und die Grenzen der letzten beobachteten Live-Daten: [PROJECT_STATUS](docs/PROJECT_STATUS.md).

Die ursprünglichen detaillierten Phasenprotokolle bleiben zur Nachvollziehbarkeit erhalten und sind im [Dokumentationsindex](docs/README.md) getrennt von Betriebs- und Funktionsanleitungen aufgelistet. Einzelne veraltete Zwischenstände liegen unter `docs/archive/`.

## Lizenz, Rechte und externe Dienste

Siehe [NOTICE](NOTICE) und die jeweils verlinkten Anleitungen. DJI-SDKs, DJI-Cloud-API-Dokumentation, Kartendienste und optionale externe Werkzeuge haben eigene Nutzungsbedingungen. Kartenaufrufe können den sichtbaren Kartenausschnitt an die jeweiligen Tile-Provider übertragen.
