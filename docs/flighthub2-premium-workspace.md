# FlightHub-orientierter AeroNexus-Arbeitsbereich (Port 8085)

## Produkt und Schnittstellen

Das responsive Control Center unter /aeronexus/ ist ein **eigenständiger AeroNexus-Arbeitsbereich** für DJI-Pilot-2- und FlightHub-2-Daten; es ist **kein Duplikat der originalen FlightHub-2-On-Premises-Webapplikation**.

Die UI verwendet bewusst nur bestehende, echte Zielrouten:

| Bereich | Aufruf | Quelle |
| --- | --- | --- |
| Cloud Control | /project auf Port 8085 | Originales DJI Cloud API Demo Vue |
| Pilot 2 | /pilot-login auf Port 8085 | Originale DJI-Pilot-2-Anmeldung |
| Flottenansicht | /operations auf HTTPS 8000 | AeroNexus, bestehender serverseitiger FlightHub OpenAPI V2 Leseadapter |
| Telemetrie | /status auf HTTPS 8000 | AeroNexus, DJI MQTT/OSD und optional FlightHub |
| Missionen | /studio auf HTTPS 8000 | Lokaler Missions- und Routenmanager |
| Medien, Thermal, Multispektral, Ergebnisse | Bestehende HTTPS-Routen | AeroNexus-Auswertung |
| Native DJI-Komponenten | /fh2-components auf HTTPS 8000 | Externe kompatible FlightHub-2-Installation; nur Opt-in |

Der offizielle **FlightHub 2 Frontend Standalone Component**-Quellcode beschreibt die Komponenten für Cockpit und Projektkarte. Ihr Javascript wird **nicht** aus dem öffentlichen HTTP-Portal gestartet. Die HTTPS-eigene Route erlaubt nach expliziter Zustimmung die DJI-Calls FH2.initConfig/FH2.loadProject/FH2.loadCockpit mit einem **separaten** lizenzierten FlightHub-2-Server; Flugfunktionen des nativen SDK sind nicht grundsätzlich lesend.

Das offizielle **FlightHub 2 OpenAPI V2 Demo** ist die API-Referenz für Geräte-, HMS- und Flugauftragslisten. Wir übernehmen seine Browser-tokenhaltige Demo-Architektur **nicht**. Bestehende OpenAPI GET-Adapter in AeroNexus bleiben serverseitig und werden über die geschützte Flottenoberfläche genutzt. Für eine echte DJI-FlightHub-2-On-Premises-Oberfläche fehlen in diesen beiden Repositories der vollständige proprietäre FH2-Server, die Frontend-Assets paas.js und die zugehörige Autorisierung.

### UI-Vertrag

Die Gestaltung orientiert sich am produktiven DESIGN.md des Projekts. Leitmotiv ist eine **technische Flug-Einsatzzentrale**: feste Navigationsleiste, gut lesbare Gerätegruppen, zurückhaltende Instrumentenfarben und eine **klar als schematisch beschriftete Datenflussdarstellung**. Sie zeichnet bewusst keine erfundenen Drohnenpositionen, Flugkarten oder Auftragszahlen.

Die UI im öffentlichen Port-8085-Dokument hat **keine sensiblen Eingaben**. Ein HEAD auf /pilot-login überprüft ausschließlich die Antwort der Web-Oberfläche. Bei Fehlern meldet sie eine nicht bestätigte Erreichbarkeit; sie behauptet weder MQTT-Online-Zustand noch FlightHub-Erfolg. Keine DJi-Tokens, URLs mit Projekttoken, LocalStorage oder POST/PUT/DELETE-Requests.

Deutsche Fachsprache, HTML-Navigation mit klar benannten Zielen, Tastaturfokus, reduzierte Bewegung, Mobilnavigation unter 900px, flache Panels, 4px-Radien und global sichtbare Scrollbars. Die Runtime-Farben stammen aus DESIGN.md: Hintergrund #10151c, Oberfläche #171e28, Rahmen #344151, Vordergrund #eaf3ff, Sekundärtext #a6b4c5 und Mint #75e3bd. Der HTTPS-Fachbereich besitzt weiterhin seine vorhandene kanonische Navigation aus ui_navigation.py.

### Integration und sichere Bereitstellung ohne Vue-Rebuild

Die bestehende DJI Cloud API Demo Web kann über /project und /pilot-login auf Port 8085 unverändert weiterlaufen. **Kein yarn build, kein Vite-Import, keine Container-Ersetzung mit fremden DJI-Frontend-Paketen.**

~~~bash
cd ~/Projekte/AeroNexusAdvanced
git status --short --branch
git pull --ff-only
.venv/bin/python -m pytest -q tests/test_control_portal.py tests/test_flighthub_premium_portal.py
python3 scripts/pi/stage_control_portal.py
~~~

Wenn der Portal-Overlay noch nicht existiert:

~~~bash
python3 scripts/pi/stage_control_portal.py --apply
~~~

**Bei auf Original-DJI zurückgesetztem** Webcontainer bitte zuerst das lokale Image verifizieren:

~~~bash
cd ~/Projekte/AeroNexusAdvanced/cloud-server/edge
docker image inspect aeronexus/control:local --format '{{.Id}}'
docker compose -f compose.core.yaml -f compose.portal.yaml config --quiet
docker compose -f compose.core.yaml -f compose.portal.yaml up -d --no-deps --no-build --pull never control
~~~

Dies erstellt nur den DJI-**Webcontainer** mit dem Original-Image und dem **read-only**-Mount unter /usr/share/nginx/html/aeronexus. API, Datenbank, MQTT, MinIO, Credentials und Docker-Volumes bleiben unverändert. Falls der Nutzer zuvor einen anderen originalen FlightHub-2-Dienst auf 8085 betrieb, die tatsächliche Compose-Zuordnung *vorher* prüfen: Dieses Overlay ist ausschließlich für das bekannte AeroNexus-Control-Container-Setup vorgesehen.

Die Seiten sind dann erreichbar:
- http://PI-IP:8085/aeronexus/ (FlightHub-orientierter Arbeitsbereich)
- http://PI-IP:8085/pilot-login (Original-DJI-Pilot-2)
- http://PI-IP:8085/project (Original-DJI-Verwaltung)
- https://PI-IP:8000/operations (geschützte Flottenansicht)
- https://PI-IP:8000/fh2-components (optional originale DJI-Widgets, separates FH2-Deployment erforderlich)

Das Bild, die Funktionen und der Verbindungszustand der tatsächlichen DJI-Cockpit-Widgets sind erst mit einem kompatiblen FlightHub 2 On-Premises und gültiger Sitzung überprüfbar. HTML/CI-Smoketests allein können diese Abnahme nicht ersetzen.

### Rückfall zum unveränderten DJI-Webcontainer

~~~bash
cd ~/Projekte/AeroNexusAdvanced/cloud-server/edge
docker compose -f compose.core.yaml up -d --no-deps --no-build --pull never control
~~~

Das Original-DJI-Image wird hierbei weiterverwendet; der zusätzliche Portal-Mount entfällt. **Niemals** Docker-Volumes löschen oder an den DJI-Zugangsdaten arbeiten, um nur das Styling zurückzunehmen.
