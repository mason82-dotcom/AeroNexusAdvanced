# Lokalen DJI-Cloud-API-Server nach AeroNexusAdvanced umziehen

Status: **Migrationswerkzeug bereitgestellt; Pi-Migration noch nicht ausgeführt.**
Dies ist der vorher separat installierte, auf DJI Cloud API / DJI Pilot 2
basierende **AeroNexus-Edge-Server**, *nicht* FlightHub 2 On-Premises.

## Ausgangspunkt (Pi 5, geprüft am 17.10.2026)

- Alt: `/home/mason/Projekte/AeroNexus/edge` plus relative Abhängigkeiten
  `api/docker`, `telemetry/emqx`, `evidence`, `control/docker`.
- Neu: `/home/mason/Projekte/AeroNexusAdvanced/cloud-server/edge`.
- **Alle** `aeronexus-edge-*`-Container sind gestoppt. Mosquitto bleibt auf
  Host-Port **1883** aktiv. EMQX war auf **1884**, Web UI 8085, API 6789,
  MinIO 9000 und Dashboard auf 127.0.0.1:18083 konfiguriert.
- Auf Pi etwa 2,7 GiB RAM verfügbar und 5,1 GiB Swap belegt:
  **nur Kernkomponenten** verwenden.
- `aeronexusadvanced.service` auf 8000 und die EU-FlightHub-Anbindung
  **unverändert** lassen.

## Zielaufbau

```text
AeroNexusAdvanced/
├── .env                          # bestehende FastAPI/FlightHub-Konfiguration
├── deploy/cloud-server/
│   └── compose.core.yaml         # versionierte, überprüfbare Vorlage
├── scripts/migrate_cloud_server.py
└── cloud-server/                 # vollständig gitignoriert, enthält Geheimnisse
    ├── edge/
    │   ├── compose.core.yaml     # isolierter Docker-Projektname
    │   ├── docker-compose.legacy.yml  # bisheriger Vollstack, NICHT starten
    │   ├── .env                  # ALTE Cloud-API-App-ID/Key/License; 0600
    │   ├── runtime/              # ausgecheckter/gepatchter DJI-Demo-Backend-/Web-Code
    │   ├── data/{mysql,redis,emqx,minio,basemaps,...}
    │   └── logs/
    ├── api/docker/application.yml
    ├── telemetry/emqx/acl.conf
    ├── control/{docker,patches}
    ├── evidence/{docker/minio,scripts/minio-init.sh}
    └── fleet/sql
```

Nur **sieben** Container sind im neuen Compose enthalten:
`mysql`, `redis`, `emqx`, `minio`, `minio-init`, `api`, `control`.
Das Projekt heißt **`aeronexusadvanced-cloud`**. Anders als der
Alt-Stack werden **keine** Mapping-, Farming-, PV-, TSDK- oder Streamingdienste
gestartet; deren Webseitenbereiche im alten Vue-Control-Image funktionieren
ohne diese Backend-Dienste gegebenenfalls nicht.

Das Compose verwendet **bereits lokal installierte/pinnte Docker-Images**
und baut nichts selbst. Das kopierte alte `docker-compose.yml` wird im
Ziel bewusst in `docker-compose.legacy.yml` umbenannt: Ein versehentliches
`docker compose up` ohne `-f` soll **keinen** alten Vollstack starten.
Die Daten werden mit `sudo rsync -a`
einschließlich der Container-UIDs, ACL-Dateien und der Datenbanken bei
**gestoppten** Altcontainern kopiert. Es erfolgt kein SQL-Re-Init,
keine Änderung an Credentials und kein Upstream-Git-Reset.

Externe MinIO-Datenträger (`MINIO_DATA_DIR=/mnt/...`) bleiben ausdrücklich
extern; das Werkzeug benennt sie in der Vorprüfung und kopiert sie **nicht**
in das Projekt. Das ist für Daten auf separaten Laufwerken gewollt. Wenn
**alle** Mediendaten physisch im neuen Projektordner liegen sollen, muss der
Speicherumzug separat geplant werden.

## Schritt A: Read-only-Vorprüfung

```bash
cd ~/Projekte/AeroNexusAdvanced
git pull --ff-only
python3 scripts/migrate_cloud_server.py
```

Ausgabe enthält keine Zugangsschlüssel. Der Check sucht die alten Pfade,
gespeicherte Daten und benötigte Docker-Images, meldet externen MinIO-Speicher
und ob alte Container noch aktiv sind. Falls Images fehlen, erst die
Image-Situation prüfen. **Nicht** `setup.sh` erneut ausführen:
das Programm rendert Auth-CSV, SQL und Patches und könnte den bestehenden
Zustand verändern.

Das Migrationswerkzeug verweigert bewusst das Staging, wenn:
- alte Edge-Container laufen, das neue Compose-Projekt bereits existiert
  oder Ziel bzw. `.partial` vorhanden sind;
- notwendige Verzeichnisse oder Docker-Images fehlen;
- der alte Server ein `docker-compose.override.yml` besitzt (könnte
  TLS-, Port- oder Sicherheitsanpassungen enthalten);
- Quell-Datenbanken Symlinks sind, der MinIO-Mount fehlt,
  das Ziel nicht genügend freien Platz für eine zweite Kaltkopie bietet
  oder die Compose-Validierung noch auf den alten Quellpfad zeigt.

## Schritt B: Sichere Kaltkopie

```bash
cd ~/Projekte/AeroNexusAdvanced
python3 scripts/migrate_cloud_server.py --stage
```

Hier fragt `sudo` gegebenenfalls nach deinem lokalen Linux-Passwort. Es
wird weder im Chat noch in GitHub gespeichert. Der alte Quellordner und
**alle gestoppten Container** bleiben unberührt. Der Kopiervorgang kann je
nach MySQL- und Mediengröße länger dauern. Bei Fehler bleibt ein
`cloud-server.partial` zur Untersuchung; nichts wird automatisch gelöscht.

Der **neue** Compose-Stack startet nach der Kopie nicht automatisch und
hat `restart: "no"` (absichtlich). Die alte tägliche Sicherung wurde
früher explizit deaktiviert und wird nicht wieder aktiviert.

## Schritt C: Kontrollieren, noch nicht alles starten

```bash
cd ~/Projekte/AeroNexusAdvanced/cloud-server/edge

# Nur die sieben minimalen Dienste anzeigen:
docker compose -f compose.core.yaml config --services

# Aktuell noch keine neuen laufenden Container:
docker compose -f compose.core.yaml ps -a

# Neue Datenpfade kontrollieren (keine Secrets anzeigen):
stat -c '%a %U:%G %n' .env ../telemetry/emqx/acl.conf
```

Die `docker compose config`-Vollausgabe **nicht** ins Chatfenster
kopieren: sie enthält interpolierte Passwörter, DJI-App-Schlüssel und Lizenz.
Auch `edge/.env` und `runtime/emqx/auth-bootstrap.csv` **nie** posten.

Für den ersten Aktivierungsschritt nur nach Freigabe:

```bash
cd ~/Projekte/AeroNexusAdvanced/cloud-server/edge
docker compose -f compose.core.yaml up -d --no-build emqx
docker compose -f compose.core.yaml ps emqx
```

Im Gegensatz zum früheren alten Stack trägt der Container dann einen Namen
mit Präfix `aeronexusadvanced-cloud-` und lauscht auf 1884. Port 1883 und
Mosquitto werden nicht angetastet. EMQX-Benutzer und -Autorisierungsregeln
müssen **vor** DJI-Pilot-2-Anmeldung funktional geprüft werden. Die bestehende
ACL erlaubt dem Benutzer `aeronexus_osd` ausschließlich `/osd`.
`AERONEXUS_OSD_STATE_ENABLED=1` im Advanced-Backend **noch nicht setzen**,
sonst scheitert die zusätzliche `/state`-Subscription an der alten ACL.

Wenn EMQX verifiziert ist und die Ressourcen ausreichen, werden
`mysql redis minio minio-init api control` separat und schrittweise gestartet.
Die alte Control-Weboberfläche kann auf im Image fest einkompilierte
Hostname-/Portwerte verweisen: nach dem Start Browser + Pilot-2-WebView
explizit testen, **nicht** eine erfolgreiche Docker-Healthprüfung als
bestätigte DJI-Cloud-API-Verbindung interpretieren.

Die vorhandene `AERONEXUS_CLOUD_MQTT_ENABLED=0`-Einstellung des
AeroNexusAdvanced-Dienstes bleibt bis zur bestätigten MQTT-Authentifizierung
unangetastet. Erst danach den separaten read-only Empfang über
`127.0.0.1:1884` aktivieren und `live_feed.state=subscribed` sowie
steigende Empfangszähler prüfen. Pilot 2 muss selbst mit der privaten
Drittanbieter-Cloud angemeldet sein; FlightHub-EU-Zugangsdaten sind hierfür
keine Ersatz-Anmeldung.

## Rückfall und Abschluss

- Original `~/Projekte/AeroNexus` nicht löschen, solange Daten, Lizenz,
  Login und DJI-Geräte nicht über die neue Installation bestätigt wurden.
- Beide Compose-Projekte **nicht gleichzeitig** starten: die Hostports
  1884, 6789, 8085 und 9000 würden kollidieren. Kein `docker compose up`
  ohne die explizite Datei `-f compose.core.yaml` im neuen Projekt.
- Bei Problemen neuen minimalen Stack gezielt stoppen:
  `docker compose -f compose.core.yaml stop`. Keine Volumes löschen,
  kein `down -v`, kein `docker system prune`.
- Alte externe Sicherungen, Watchtower, Cronjobs und systemd-Starts sind
  nicht automatisch umgestellt. Erst nach der vollständigen Migration
  auf Wunsch neu konfigurieren.
- Der externe Datenträger, falls benutzt, bleibt ein gemeinsames
  Infrastruktur-Element und erfordert eigene Backup-/Rollback-Strategie.
