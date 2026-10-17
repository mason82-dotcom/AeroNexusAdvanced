# Phase 18 – DJI Cloud API 2: überprüfte Integrationsgrenzen (17.10.2026)

## Entscheidung

AeroNexusAdvanced bleibt der lokale Python/FastAPI-Server auf dem
Raspberry Pi 5 (ARM64). Die produktive FlightHub-2-EU-OpenAPI-V2-Verbindung
bleibt der primäre, ausschließlich lesende Datenpfad. Keine Änderung an
DJI Pilot 2, an der Flugsteuerung oder am systemd-Dienst durch diesen Branch.

Die offizielle DJI Cloud API 2 ist eine eigenständige Plattform mit
Lizenz/Aktivierung, eigener Plattforminstallation und nativer Java/JNI-SDK-
Anbindung. Sie ist **keine** Versionsumschaltung des vorhandenen FlightHub
OpenAPI V2 oder des DJI Cloud-API-MQTT-Feeds. Bereits bestehende FlightHub-
Organisationsschlüssel ersetzen die Cloud-API-2-Plattformzugangsdaten nicht.

## Offizielle Quellen (Stand 17.10.2026)

- Produkt: https://developer.dji.com/cloud-api-2/
- Lizenz: https://developer.dji.com/resources/cloud-api-2/apply/
- Nutzungsbedingungen: https://developer.dji.com/cloud-api2-clause/terms/
- SDK/Demo: https://developer.dji.com/doc/cloud-api-2-tutorial/cn/
- Veröffentlichtes SDK im Downloadcenter **v3.3.6**:
  https://developer.dji.com/doc/cloud-api-2-tutorial/cn/downloads.html
- Offizielles GitHub-Repo (Devkit enthält auch
  `devkit/libs/flight-hub-sdk-3.3.7.jar`):
  https://github.com/dji-sdk/Cloud-API-2
- Deploymentbeschreibung:
  https://developer.dji.com/doc/cloud-api-2-tutorial/cn/deployment/installation.html

**Versionsabweichung:** DJI listet im öffentlichen Downloadcenter v3.3.6,
während das Devkit-Repository v3.3.7 enthält. Daraus allein folgt **nicht**,
dass eine konkrete SDK-/Plattformkombination freigegeben ist. Vor einem
realen Einsatz müssen Plattformversion, SDK-Build, Release Notes und
Lizenz-/Deployment-Kompatibilität zusammen geprüft werden.

Die Cloud-API-2-Lizenz wird nach den DJI-Nutzungsbedingungen kostenlos
bereitgestellt. Einzelne Zusatzdienste können kostenpflichtig sein.
DJI nennt für die Prüfung des Lizenzantrags **bis zu 30 Arbeitstage**.
Für Deutschland ist auf dem Formular die Region `Non-Chinese Mainland`
auszuwählen, wenn die Plattform dort eingesetzt wird; die Region darf
nicht versehentlich falsch gebunden werden.

## ARM64- und Bereitstellungsentscheidung

Der originale Cloud-API-2-Demo-/SDK-BFF nutzt JNI-Bibliotheken ausschließlich
für **Linux x86_64/AMD64**. Ein nativer Produktivbetrieb dieses BFFs auf
dem Raspberry Pi 5 (ARM64) ist damit nicht unterstützt.

Architektur nach Bereitstellung einer separat kontrollierten,
authentifizierten x86_64-Instanz:

```text
DJI Pilot 2 / unterstützte Drohne
         |
     DJI Cloud API 2 (separate Plattform mit Lizenz)
         |
     Java SDK BFF (Linux x86_64 / amd64, nicht Pi)
         |
         |  privates HTTPS + separates BFF-Bearer-Token
         |  ausschließlich GET /api/v1/devices
         v
AeroNexusAdvanced (Raspberry Pi 5, ARM64)
         |
    /api/v1/cloudapi2/devices
         |
    /operations (nur lesen)
```

**Wichtig:** Die bestehende Bridge konsumiert den REST-Endpunkt des
offiziellen `devkit/skeleton`-Demos bzw. eines ausdrücklich
kompatiblen BFFs, **nicht** unmittelbar das native DJI-SDK oder die
öffentliche Cloud-API-2-Plattform. Ein BFF ist derzeit weder bestätigt
noch installiert. Die DJI-Demo ist laut DJI nicht produktionsreif;
deren Authentifizierung, Exposition und Datenmodell sind bei jeder
Übernahme zu prüfen.

## Phasenweise Einführung

1. **P0 – jetzt:** Read-only-Bridge auf aktuellem `main` härten,
   ausschließlich im Feature-Branch testen; Bridge deaktiviert lassen.
   HTTP-Upstream-Body beim Lesen auf 1 MB begrenzen, bevor er vollständig
   im Speicher liegt. `lastOsdAt` nach Cacheabruf neu bewerten, damit
   alte Werte nicht weiter als live dargestellt werden. Exakter
   Upstream-Pfad `GET /api/v1/devices`, keine weiteren HTTP-Methoden.
2. **P1 – Voraussetzungen:** Entwicklerlizenz für Entwicklungsumgebung
   beantragen, vollständige Plattform-/SDK-Kompatibilität prüfen,
   x86_64-Server und verifizierbares HTTPS mit gültigem Zertifikat
   bereitstellen. Dabei keinen produktiven Pi-Dienst ersetzen.
3. **P2 – Abnahme BFF:** JWT-/BFF-Auth, Netzisolation, nur lesende
   API-Routen, Telemetrie-Feldschema, Online-/Offline-Status und
   `lastOsdAt` auf dem echten BFF prüfen. Drohnensupport (Matrice 4T)
   separat im vorgesehenen Cloud-API-2-Modus bestätigen. Keine
   Befehlsendpunkte freischalten und kein Gerät ohne Rückfallstrategie
   von der bestehenden FlightHub-EU-Anbindung lösen.
4. **P3 – Pi-Lesetest:** Wenn BFF tatsächlich läuft, Pi-`.env` nur privat
   und mit Modus 0600 konfigurieren. Die Bridge bleibt bis zu diesem
   Zeitpunkt ausgeschaltet; `/operations` muss im Fehlerfall
   `unavailable` statt fiktiver Livewerte anzeigen.
5. **P4 – getrennte UI-Bewertung:** Offizielle DJI-Komponenten wie
   Cockpit/Routen-Editor erst nach kompatiblem Backend, sauberer
   Authentifizierung und Browser-Sicherheitsprüfung evaluieren.
   Keine Einbindung von SDK-Steuerungsmethoden, Missions-Upload,
   KI-Flugbefehlen oder Dock-Funktionen.

## Invarianten / Rückfall

- `AERONEXUS_CLOUDAPI2_ENABLED` standardmäßig aus.
- FlightHub 2 EU/Cloud-API 1 und die lokalen Mission-Studio-Daten
  bleiben unverändert.
- Keine DJI-Schreibzugriffe, keine Steuerungsübernahme, keine
  Dock-Integration oder ungeprüfte Mission-Ausführung.
- Kein Vorwärts-Routing von DJI-Organisationstokens an das BFF.
- Fehler, veraltete Daten und unbekannte Zeitstempel werden nicht
  als bestätigter Livezustand ausgegeben.
- Zur Rücknahme genügt die nicht gesetzte bzw. auf `0` belassene
  Aktivierungsvariable; dieser Branch allein ändert keine Pi-Konfiguration.
- Browser erhält keinen direkten BFF-Zugriff und keine BFF-Tokens.

## Prüfung vor dem Mergen

```bash
cd /home/mason/Projekte/AeroNexusAdvanced
git fetch origin
git diff --stat origin/main...origin/feat/cloudapi2-bridge-hardening-main-20261017
# Nur in isolierter Dev-Umgebung testen, produktive .env nicht überschreiben:
.venv/bin/python -m pytest -q tests/test_cloud_api2_bridge.py
.venv/bin/python -m pytest -q
```

Der Code wird zuerst über CI und die Diff-Prüfung freigegeben.
**Kein Pi-Deployment und kein Neustart im Rahmen dieses Branches.**
