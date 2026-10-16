# DJI Pilot 2: Web-Anmeldung auf AeroNexusAdvanced umbenennen

Stand: vorbereitet im Repository. **Auf dem Raspberry Pi noch nicht angewendet.**

## Bereits verifiziert

- DJI Cloud API: `aeronexusadvanced-cloud-api-1` läuft, HTTP 401 auf `/`
  bestätigt einen antwortenden Backend-Listener.
- EMQX, MySQL und Redis: `healthy`. MinIO: HTTP 200; fünf Buckets
  einschließlich `dji-cloud`, STS-Benutzer mit Lesezugriff vorhanden.
- Vue-Control-Webserver: `http://192.168.178.63:8085/pilot-login` liefert
  HTTP 200; die RC Plus 2 zeigt die Login-Seite mit **„AeroNexus Pilot“**.
- Workspace und Plattform in der *neuen* Datenbank `cloud_sample` wurden
  bereits beide zu **AeroNexusAdvanced** umbenannt.
- Der gut sichtbare „AeroNexus Pilot“-Text stammt dagegen aus
  `src/locales/de.ts` (Übersetzung des Schlüssels `Pilot Cloud API Demo`),
  und der HTML-Titel aus `index.html`. **Nicht** aus MySQL.
- Die obere Leiste „Cloud Api Platform“ gehört zu DJI Pilot 2 selbst
  und wird durch diese Webseite nicht umbenannt.

## Sichere Vorprüfung auf dem Pi

```bash
cd ~/Projekte/AeroNexusAdvanced
git pull --ff-only
python3 scripts/brand_cloud_server.py
```

Der Check liest lediglich die ungefährlichen Werte `SERVER_HOST`,
`WORKSPACE_NAME`, `PLATFORM_NAME`, und aus der laufenden API
`SERVER_HOST`, `BROKER_HOST`, `BROKER_PORT`.

Erwartet werden `SERVER_HOST=192.168.178.63` und `BROKER_HOST=192.168.178.63`,
`BROKER_PORT=1884`. Abweichungen **zuerst korrigieren**, nicht einfach
den Login-Button auf der Fernsteuerung drücken. Die Prüfung liest niemals
`DJI_APP_KEY`, `DJI_APP_LICENSE`, MQTT- oder Login-Passwörter aus.

## Branding lokal vorbereiten – ohne Ausfall

```bash
cd ~/Projekte/AeroNexusAdvanced
python3 scripts/brand_cloud_server.py --apply
```

Ändert nur:

- `cloud-server/edge/runtime/upstream/web/src/locales/de.ts`:
  `"Pilot Cloud API Demo": "AeroNexusAdvanced"`
- `cloud-server/edge/runtime/upstream/web/index.html`:
  `<title>AeroNexusAdvanced</title>`
- legt `cloud-server/edge/compose.brand.yaml` als **explizites**
  Build-Overlay an.

Originaldateien werden unter `cloud-server/edge/branding-backup/`
gesichert. Änderungen sind idempotent; unbekannte Quellversionen und
abweichende lokale Overlay-Dateien werden abgewiesen.

**Es werden weder Flug- oder MQTT-Berechtigungen geändert noch die
Anmeldung oder die DJI-Lizenzprüfung entfernt.** Der ursprüngliche
Web-Container und das alte Image bleiben unverändert.

## Nur das Web-Frontend neu bauen

```bash
cd ~/Projekte/AeroNexusAdvanced/cloud-server/edge

# Baut nur die Vue-Control-Webseite in ein NEUES Image:
docker compose -f compose.core.yaml -f compose.brand.yaml build control

# Erst nach erfolgreichem Build den einen Web-Container ersetzen:
docker compose -f compose.core.yaml -f compose.brand.yaml \
  up -d --no-deps --no-build --pull never control

# API und alle anderen Container bleiben unberührt:
docker compose -f compose.core.yaml ps

# Prüfen, welche Web-Image-Version läuft:
docker inspect aeronexusadvanced-cloud-control-1 \
  --format '{{.Config.Image}}'

# Nur Serverantwort und Dateinamen, keine DJI-Secrets anzeigen:
curl -sS -o /dev/null -w 'Pilot-2-Webseite: HTTP %{http_code}\n' \
  http://127.0.0.1:8085/pilot-login
docker exec aeronexusadvanced-cloud-control-1 \
  sh -c 'grep -Rl -m1 AeroNexusAdvanced /usr/share/nginx/html/assets | head -3'
```

**Achtung Build:** Original-DJI-Demo-Web verwendet für die Lizenzfreigabe
Build-Argumente `VITE_DJI_APP_ID`, `VITE_DJI_APP_KEY`,
`VITE_DJI_APP_LICENSE`. Diese Werte waren bereits in der älteren
Vue-Auslieferung vorhanden, sind in einem Browser-Bundle grundsätzlich
einsehbar und dürfen **niemals** in Chat, Build-Protokollen, CI-Artefakten
oder einem öffentlichen Image veröffentlicht werden. Nicht
`docker compose config` ungekürzt posten.

Der Raspberry Pi hat etwa 2 GiB verfügbaren RAM und viel Swap. Ein
vollständiger Vue-Build kann mehrere Minuten dauern. Bei fehlgeschlagenem
Build bleibt der bisherige Webserver aktiv; bitte dann nur die
**Fehlerzeilen ohne Schlüsselwerte** mitteilen.

## Rückfall

Wenn das neue Frontend nicht funktioniert, ohne Datenverlust das alte
`aeronexus/control:local` wieder einsetzen:

```bash
cd ~/Projekte/AeroNexusAdvanced/cloud-server/edge
docker compose -f compose.core.yaml \
  up -d --no-deps --no-build --pull never control
```

Damit bleibt die gesamte API/MQTT-Konfiguration identisch. Die
Quellcodeänderungen in der kopierten `runtime/upstream/web`-Arbeitskopie
werden dadurch **nicht** zurückgesetzt und das GitHub-Repo nicht verändert.

## Weiterer Betrieb

Auf der DJI RC Plus 2 die Cloud-Services-Seite aktualisieren und kontrollieren,
dass unter dem DJI-Logo **AeroNexusAdvanced** steht. Wenn WebView-Caching
weiter die alte Seite zeigt, die Cloud-Seite in Pilot 2 schließen und neu
öffnen; nicht die DJI-App oder Zugangsdaten löschen.

Danach mit dem bestehenden Pilot-Benutzer anmelden und **zuerst am Boden**
prüfen, ob MQTT-Telemetrie den Broker auf Port 1884 erreicht. Keine
automatischen Flugbefehle; die AeroNexusAdvanced-Live-Anzeige kann separat
schreibgeschützt aktiviert werden. Die FlightHub-EU-Anbindung am
HTTPS-Dashboard auf Port 8000 bleibt erhalten.
