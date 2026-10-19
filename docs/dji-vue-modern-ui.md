# DJI Cloud-Control: optionales UI-Theme für Pilot 2 und Vue-Desktop

## Ziel und Grenzen

Das zusätzliche AeroNexus-CSS modernisiert **die bestehende DJI-Cloud-API-Vue-Anwendung** auf Port 8085, nicht nur das unabhängige Portal unter /aeronexus/.

Designumfang:
- DJI-Pilot-2-Anmeldung und Desktop-Login: dunkler, kontrastreicher Hintergrund, klarer Formularbereich, Fokusrahmen, mobile Breiten, lesbare Eingabefelder.
- Desktop-Cloud-Control: dunkle Kopfzeile, erkennbare Navigation und aktive Seitenleiste, harmonisierte Radien/Fokus, kompakte Zahlentabellen.
- DJI-Pilot-2-Statusseiten: Buttons und Eingabefelder werden behutsam modernisiert. Die gerätespezifischen Bedienansichten behalten ihre Layouts, damit Steuerungsfunktionen und Warnungen nicht verdeckt werden.

**Keine** Änderungen an Authentifizierung, DJI-Lizenz, Vue-Komponenten, DJI-JSBridge, Flugbefehlen, MQTT, Datenbank, Tokens, Gerätestatus, API-Requests oder bestehenden Missionen. Das Stylesheet erfindet keine Livewerte und ergänzt keine Gerätebefehle. Es liegt unter deploy/cloud-server/control-portal/pilot-ui.css und wird über das vorhandene compose.portal.yaml als statische Datei bereitgestellt. Das private Vue-HTML bekommt einen einzigen Link auf die CSS-Datei; für die Aktivierung ist ein manueller Neubau des branded Web-Images erforderlich.

Das [offizielle DJI Cloud API Demo Web](https://github.com/dji-sdk/Cloud-API-Demo-Web) wurde als strukturelle Referenz für die Login- und Ant-Design-Klassen genutzt. DJI hat die Wartung der Cloud-API-Demo-Repositories im April 2025 eingestellt und weist auf potenzielle Sicherheitsrisiken hin. Die eigene Cloud-API-Demo nicht ohne separate Sicherheitsprüfung öffentlich ins Internet stellen.

## Sicheres Staging auf dem Raspberry Pi

Lokale Dateien dürfen nicht durch git reset --hard oder git clean -fdx überschrieben werden.

~~~bash
cd ~/Projekte/AeroNexusAdvanced
git status --short --branch
python3 scripts/pi/stage_dji_vue_theme.py
~~~

Die Vorprüfung verlangt einen bekannten Vite-Einstieg, den Vue-Mountpoint, das neue CSS und ein gültiges schreibgeschütztes Portal-Overlay. Bei Abweichungen abbrechen und lokale Quellstruktur prüfen.

~~~bash
python3 scripts/pi/stage_dji_vue_theme.py --apply
.venv/bin/python -m pytest -q tests/test_dji_vue_theme.py tests/test_control_portal.py
~~~

Die Option --apply sichert das bisherige HTML einmalig unter cloud-server/edge/pilot-ui-backup/index.html (Dateimodus 0600) und ergänzt ausschließlich einen CSS-Link in der privaten Vue-index.html. Ein abweichendes Backup oder eine unbekannte HTML-Version führt zum Abbruch. Es erfolgt **kein** Docker-Build, Neustart, Upload, Datenbankzugriff oder Git-Commit der privaten Vue-Quellen.

## Build und kontrollierte Aktivierung (separat)

Der Web-Build benötigt Pi-Speicher und kann zeitintensiv sein. Freien Platz und RAM vorher prüfen. Bei lokaler Compose-Konfiguration niemals ungekürztes docker compose config oder Docker-Environment ausgeben, da Schlüssel oder Lizenzen darin stehen können.

~~~bash
cd ~/Projekte/AeroNexusAdvanced/cloud-server/edge
docker inspect aeronexusadvanced-cloud-control-1 --format '{{.Config.Image}}'
# Bestehendes branded-Image vor dem Build explizit als Rückfall erhalten:
docker image tag aeronexusadvanced/control:branded aeronexusadvanced/control:pre-theme-20261019
docker compose -f compose.core.yaml -f compose.brand.yaml -f compose.portal.yaml config --quiet

# Das bisherige Web-Image bleibt während des Builds online:
docker compose -f compose.core.yaml -f compose.brand.yaml -f compose.portal.yaml build control

# Nur nach erfolgreichem Build den Web-Container erneuern:
docker compose -f compose.core.yaml -f compose.brand.yaml -f compose.portal.yaml \
  up -d --no-deps --no-build --pull never --force-recreate control
~~~

Danach separat im Browser und an der Fernsteuerung prüfen:

1. HTTP 200 für /pilot-login, /project, /aeronexus/ und /aeronexus/pilot-ui.css auf Port 8085.
2. Pilot-2-WebView: Lizenzprüfung, bestehende Anmeldung, Rückkehr/Exit und Cloud-Verbindung.
3. Desktop-Web: Login, Seitenleiste, Workspace-, Medien- und Missionsansichten, schmaler Viewport, Tastaturfokus und Dialoge.
4. Die schreibgeschützte Produktivprüfung muss weiterhin 31 GET-Endpunkte bestätigen.

HTTP 200 beweist nicht, dass die DJI-Lizenz oder die Gestaltung in einer realen Pilot-2-WebView funktioniert.

## Rückfall

Vor dem Build das Image unter einem eigenen Tag sichern. Bei rein visuellen Problemen das zuvor gesicherte Image wieder unter dem erwarteten branded-Tag aktivieren:

~~~bash
cd ~/Projekte/AeroNexusAdvanced/cloud-server/edge
docker image tag aeronexusadvanced/control:pre-theme-20261019 aeronexusadvanced/control:branded
docker compose -f compose.core.yaml -f compose.brand.yaml -f compose.portal.yaml up -d --no-deps --no-build --pull never --force-recreate control
~~~

Alternativ kann der CSS-Link aus dem privaten Vue-HTML entfernt und die Oberfläche erneut gebaut werden. Das Originalindex-Backup liegt unter cloud-server/edge/pilot-ui-backup/index.html. Vor einer Wiederherstellung kontrollieren, ob seit der Sicherung andere legitime Anpassungen entstanden sind; das Backup keinesfalls blind über neuere Änderungen kopieren. Keine Datenbank-, MQTT-, MinIO- oder Zertifikatsdateien verändern.
