# AeroNexusAdvanced Control Portal – Port 8085

## Architektur und Funktionsumfang

Der bestehende Container **aeronexusadvanced-cloud-control-1** veröffentlicht TCP 8085 (Nginx TCP 80) und führt die originale DJI Cloud API / Pilot 2 Vue-Anwendung aus. Die Anmeldung unter **/pilot-login** sowie Lizenz-, Autorisierungs-, API- und MQTT-Pfade bleiben unangetastet.

Ein zusätzliches **schreibgeschütztes Docker-Bind-Mount** stellt zwei neue Seiten bereit:

- **http://PI-IP:8085/aeronexus/**: responsives AeroNexus Control Center als Portal zu den vorhandenen geschützten HTTPS-Modulen auf TCP 8000 (Status, Operations, Studio, Medien, Thermal, Multispektral, Ergebnisse). Die einzige eingebaute Onlineprüfung ist ein HTTP HEAD auf **/pilot-login**. Daraus kann man nur die Antwort des Webservers ableiten, **nicht** den Zustand von Drohne, MQTT, API oder FlightHub.
- **http://PI-IP:8085/aeronexus/fh2.html**: optionaler Einbettungsmodus für die **echten DJI FlightHub 2 Frontend-Komponenten**. Erst nach manueller Eingabe eines **separaten, kompatiblen FlightHub-2-Hosts**, einer gültigen Projekt-UUID und eines Projekttokens sowie ausdrücklicher Zustimmung wird das offizielle Skript **paas.js** des vertrauenswürdigen Hosts geladen. Unterstützte Calls: **FH2.initConfig**, **FH2.loadProject** oder **FH2.loadCockpit**. Für den Cockpit-Modus sind Geräte-SNs erforderlich. Ohne kompatible FlightHub-2-Umgebung wird **kein** nativer DJI-Baustein angezeigt.

**Wichtig:** Die DJI Cloud API auf 8085/6789 ist **kein** FlightHub-2-On-Premises-Frontend. Native DJI-Widgets können selbst Flugsteuerungs- oder Schreibaktionen anbieten. Die optionale Einbettung ist **nicht** technisch schreibgeschützt. Daher nur nach bewusster Freigabe mit vertrauenswürdigem Host verwenden. Der Server lädt keine zusätzlichen Bibliotheken von Drittanbietern für die Standard-Portalseite.

Das [DJI FlightHub 2 OpenAPI V2 Demo](https://github.com/dji-sdk/FlightHub-2-OpenAPI-V2-Demo) wird bewusst nicht unverändert in den Browser kopiert. Das Beispiel verwendet browserseitige Zugangsdaten und beinhaltet POST-Funktionen zur Erstellung von Flugaufträgen. AeroNexus besitzt bereits serverseitige, lesende OpenAPI-V2-Adapter für Geräte, HMS, Projekte und Aufträge, die über das geschützte **/operations** genutzt werden. Kein OpenAPI-Organisationstoken wird ins öffentliche Web-Bundle eingebaut.

Offizielle Quellen:
- [FlightHub 2 Frontend Standalone Component](https://github.com/dji-sdk/FlightHub-2-Frontend-Standalone-Component)
- [DJI Komponentendokumentation](https://fh.dji.com/user-manual/en/custom-development/frontend-components/component-introduction.html)
- [FlightHub 2 OpenAPI V2 Demo](https://github.com/dji-sdk/FlightHub-2-OpenAPI-V2-Demo)
- AeroNexus: [FlightHub-Flottenintegration](phase-10-flighthub-fleet.md), [Cloud-API und Projektstatus](PROJECT_STATUS.md)

## Sicher auf dem Raspberry Pi vorbereiten

Vor jeder Änderung den tatsächlichen Git-Stand und lokale Änderungen kontrollieren. Niemals .env, Cloud-Daten, Datenbank, Zertifikate oder Docker-Volumes überschreiben.

~~~bash
cd ~/Projekte/AeroNexusAdvanced
git status --short --branch
python3 scripts/pi/stage_control_portal.py
python3 scripts/pi/stage_control_portal.py --apply
~~~

Ohne Option **--apply** prüft das Skript nur die Voraussetzungen. Mit **--apply** schreibt es **ausschließlich** die lokale Datei cloud-server/edge/compose.portal.yaml mit Rechten 0600. Existiert eine inhaltlich abweichende Datei bereits, wird abgebrochen. Es führt keinerlei Docker-Befehle aus. Der Compose-Overlay bindet den versionierten Ordner deploy/cloud-server/control-portal **read-only** nach /usr/share/nginx/html/aeronexus ein, ohne die Original-Weboberfläche zu überschreiben. Es wird weder ein neues Image heruntergeladen noch eine API-Konfiguration geändert.

## Separat aktivieren

Nach dem Review der lokalen Compose-Umgebung **nur den Web-Container** neu erstellen – niemals die gesamte Cloud herunterfahren:

~~~bash
cd ~/Projekte/AeroNexusAdvanced/cloud-server/edge
docker inspect aeronexusadvanced-cloud-control-1 --format '{{.Config.Image}}'
docker compose -f compose.core.yaml -f compose.brand.yaml -f compose.portal.yaml config --quiet
docker compose -f compose.core.yaml -f compose.brand.yaml -f compose.portal.yaml up -d --no-deps --no-build --pull never control
curl -sS -o /dev/null -w 'Pilot-2-Login: HTTP %{http_code}\n' http://127.0.0.1:8085/pilot-login
curl -sS -o /dev/null -w 'AeroNexus-Portal: HTTP %{http_code}\n' http://127.0.0.1:8085/aeronexus/
curl -sS -o /dev/null -w 'DJI-Komponenten: HTTP %{http_code}\n' http://127.0.0.1:8085/aeronexus/fh2.html
~~~

HTTP 200 belegt nur die Web-Auslieferung. Zusätzlich muss die Browserfunktion auf Desktop/Mobil geprüft werden. Die geschützten Module auf Port 8000 müssen separat über korrektes TLS erreichbar sein.

## Sicherer Rückfall

Das Portal wieder aus dem Container herausnehmen, **ohne** die originalen Services, Daten oder Docker-Volumes zu verändern:

~~~bash
cd ~/Projekte/AeroNexusAdvanced/cloud-server/edge
docker compose -f compose.core.yaml -f compose.brand.yaml up -d --no-deps --no-build --pull never control
~~~

Das gespeicherte Overlay kann ungenutzt verbleiben. Keinesfalls docker compose down -v oder git clean -fdx verwenden.
