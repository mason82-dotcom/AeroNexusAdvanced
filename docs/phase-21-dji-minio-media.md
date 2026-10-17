# Phase 21 – DJI-Medien aus lokalem MinIO katalogisieren

## Betriebsmodell

Originalmedien liegen im externen MinIO-Bucket **dji-cloud** auf dem Pi
(Datenträger: /mnt/hc4backup/aeronexus-data/minio; S3-Port 9000).
Die neue Funktion erstellt **nur einen lokalen Metadatenindex**,
keine Medienkopien. Die Originalobjekte bleiben unverändert.
Es werden keine S3-PUT/DELETE/POST-Operationen und keine DJI-Flugbefehle ausgeführt.

- Indexdatei: ~/.local/share/aeronexusadvanced/dji_minio_media.sqlite3,
  privat (Datei 0600, Verzeichnis 0700), außerhalb von Git.
- Paginierte MinIO-Objektauflistung: JPEG/JPG/THM, PNG, WebP, DNG,
  TIFF, MP4, MOV, LRF und SRT (Groß-/Kleinschreibung unerheblich).
- Indexfelder: stabile Hash-ID, Bucket/Objektschlüssel **nur intern**,
  Name, MIME, Größe, ETag und Änderungsdatum. Keine erfundenen EXIF/GPS-Daten.
- Idempotenz: neue Objekte hinzufügen, geänderte Versionen aktualisieren,
  entfernte Objekte **nur aus dem Index** entfernen. Bei Abbruch bleibt
  der vorherige vollständige Katalog erhalten.
- Studio: /studio → Medienbibliothek → DJI-Medien aus MinIO.
  Separate Suche/Pagination, niemals eine Löschfunktion.
- Authentifizierte HTTP-GET-Endpunkte:
  /api/v1/studio/dji-media?limit=100&offset=0&q=DJI_
  und /api/v1/studio/dji-media/{id}/file.
  Kleine JPEG/PNG/WebP (maximal 32 MiB) lassen sich ansehen.
  Sonstige Dateien nur auf bewussten Download mit ?download=true.
  Medien werden gestreamt; sie belegen nicht automatisch lokalen Pi-Speicher.
- Vor dem Dateizugriff werden ETag und Größe aus MinIO gegen den
  Index geprüft, um geänderte Dateien nicht unter alter Kennung auszugeben.
  Der Browser erhält keine S3-Objektpfade, Zugangsschlüssel oder signierte Links.

## Einrichtung auf Raspberry Pi 5

Keine Änderung an der vorhandenen Cloud-API-Compose-Installation,
an Backups oder an bestehenden deaktivierten Timern.

~~~bash
cd ~/Projekte/AeroNexusAdvanced
git status --short
git fetch origin
git switch feature/dji-minio-media-index-20261017
.venv/bin/python -m pip install -e '.[test,mqtt,minio]'
.venv/bin/python -m pytest -q tests/test_minio_media_index.py
~~~

Den Branch erst wechseln, wenn keine ungesicherten lokalen Änderungen
überschrieben werden. Die private .env bleibt unberührt.

In die **bestehende, private Projekt-.env** eintragen:

~~~ini
AERONEXUS_MINIO_ENDPOINT=http://127.0.0.1:9000
AERONEXUS_MINIO_BUCKET=dji-cloud
AERONEXUS_MINIO_ACCESS_KEY=<Lesezugang>
AERONEXUS_MINIO_SECRET_KEY=<zugehöriger Schlüssel>
~~~

Unbedingt einen **eigenen Lesezugang** verwenden: s3:ListBucket auf
dji-cloud, s3:GetObject auf dji-cloud/* (ggf. s3:GetBucketLocation).
Keine Root-Keys und keine Credentials in Git oder Chat posten.
Die .env muss weiterhin Dateimodus 0600 besitzen.

## Eigener MinIO-Lesezugang für die Studio-Vorschau

Nach erfolgreicher Erstindexierung kann ein separater, zufällig erzeugter
MinIO-Lesezugang mit **ausschließlich** `s3:ListBucket` /
`s3:GetBucketLocation` für `dji-cloud` und `s3:GetObject` für
`dji-cloud/*` angelegt werden. Weder Root-Passwort noch neuer
Zugangsschlüssel werden im Terminal ausgegeben.

Für den Raspberry Pi 5 (ARM64) den offiziellen MinIO-Client herunterladen
und anhand der nebenstehenden SHA256-Prüfsummendatei verifizieren:

~~~bash
mkdir -p "$HOME/minio-binaries"
cd "$HOME/minio-binaries"
curl -fL --retry 3 -o mc   https://dl.min.io/client/mc/release/linux-arm64/mc
curl -fL --retry 3 -o mc.sha256sum   https://dl.min.io/client/mc/release/linux-arm64/mc.sha256sum
echo "$(awk '{print $1}' mc.sha256sum)  mc" | sha256sum --check --status && echo 'SHA256 geprüft'
chmod 700 mc
./mc --version
~~~

Falls die Prüfsumme **nicht** übereinstimmt, die Binärdatei nicht ausführen.
Es werden keine Systempakete oder MinIO-Container installiert oder aktualisiert.
Nur die offizielle URL `dl.min.io` verwenden.

~~~bash
cd ~/Projekte/AeroNexusAdvanced
.venv/bin/python scripts/pi/configure_minio_readonly.py

# Danach konfigurierte Leser-Verbindung testen:
.venv/bin/python -m aeronexus.minio_media_index --dry-run
systemctl --user restart aeronexusadvanced
systemctl --user is-active aeronexusadvanced
~~~

Der Einrichtungshelfer verwendet das bereits vorhandene lokale
`cloud-server/edge/.env`-Administratorkonto nur einmalig und mit
temporärem `MC_CONFIG_DIR`. Er erzeugt eine eigene MinIO-Policy und einen
zufälligen Reader, prüft den neuen Zugriff per Listen/HEAD und schreibt
erst danach die vier Variablen `AERONEXUS_MINIO_*` in die bestehende
private Projekt-`.env` (Dateimodus 0600). Bereits vorhandene Einstellungen
werden **nicht** überschrieben; ein zweiter Aufruf beendet sich ohne
Änderungen.

Die Account-Erstellung verändert nur MinIO-IAM-Metadaten, keine
Mediendateien. Root-Zugangsdaten bleiben in der ursprünglichen
gitignorierten Konfiguration. Die Client-Prozesse müssen auf dem
lokalen Pi mit entsprechender Benutzer-/Prozessisolation ausgeführt werden,
da der Einrichtungshelfer das erzeugte Reader-Secret für
`mc admin user add` kurzfristig als Prozessargument übergibt.

## Import und Kontrolle

~~~bash
cd ~/Projekte/AeroNexusAdvanced

# Bucket-Zugang prüfen; Index unverändert
.venv/bin/python -m aeronexus.minio_media_index --dry-run

# Vollständiger, atomarer DJI-Objekt-Indexabgleich
.venv/bin/python -m aeronexus.minio_media_index

# Lokales Indexergebnis, ohne Geheimnisse oder DJI-Objektpfade
.venv/bin/python - <<'PY'
from aeronexus.minio_media_index import DjiMediaIndex
data = DjiMediaIndex().list(limit=5)
print("Indiziert:", data["total"])
print("Letzter Scan:", data["last_scanned_at"])
for obj in data["media"]:
    print(obj["name"], obj["mime"], obj["size_bytes"], "Bytes")
PY

# Danach Webdienst neu laden
systemctl --user restart aeronexusadvanced
~~~

CLI lädt die .env per python-dotenv; bereits exportierte Variablen haben
Vorrang. Der Indexscan ist absichtlich **manuell**, nicht zeitgesteuert.
Neue DJI-Uploads erscheinen erst nach erneutem Scan.

## Abnahme

1. Dry-run: read_access=ok.
2. Erster Scan: indexed/added/updated/removed_from_index prüfen.
3. Zweiter Scan ohne neue Uploads: added=0, updated=0, removed_from_index=0.
4. Studio: Dateien einschließlich großer DNG/MP4 als DJI-Katalog sichtbar.
5. JPEG-Vorschau und kontrollierter DNG-Download; keine Löschfunktion.
6. Neuer DJI-Upload: erneuter Scan; nur neue Objekte zählen als added.

Nicht durch CI nachweisbar: reale Objektzahl, Pi-Netzwerkzugriff,
SDK-Berechtigungen und Browser-Live-Abnahme. Diese lokal prüfen.
