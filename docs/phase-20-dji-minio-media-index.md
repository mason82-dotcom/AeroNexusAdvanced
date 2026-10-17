# Phase 20 – DJI-Medien aus MinIO indizieren (schreibgeschützt)

## Ausgangslage

Der eigene DJI-Cloud-API-Server nutzt einen MinIO-S3-Bucket, dessen Name
in cloud-server/edge/.env unter MINIO_BUCKET steht. Das ist eine andere
Quelle als FlightHub EU oder die lokale Mission-Studio-Medienablage.

## Implementiert

- Scanner: python -m aeronexus.dji_media_index (Vorprüfung, keine lokale SQLite-Änderung).
- Übernahme: python -m aeronexus.dji_media_index --apply (nur SQLite-Index schreiben).
- Die Quelle wird mit Docker-Exec im bereits laufenden Container
  aeronexusadvanced-cloud-minio-1 über MinIO Client mc gelesen.
  Die Zugangsdaten bleiben im Container, die temporäre mc-Konfiguration
  wird dort unter /tmp nach Abschluss entfernt.
- Ausschließlich MinIO-Listenoperationen; keine S3-Downloads, PUTs,
  Löschungen, Objektänderungen oder Starts/Stops von Cloud-Diensten.
- Die private Datenbank liegt unter var/dji-media-index.sqlite3 (0600,
  Verzeichnis 0700, Git-ignoriert). Sie enthält Original-Key, Bucket,
  stabilen Objekt-Hash, Dateinamen, Größe, ETag und MinIO-Änderungszeit.
  Originalschlüssel erscheinen nicht in den öffentlichen API-Daten.
- Unterstützte Metadatentypen: JPEG/PNG/TIFF/HEIC/AVIF/WebP, DNG/RAW,
  MP4/MOV/INSV/LRF/AVI, Audio und SRT/XMP-Begleitdateien.
  TIFF wird nicht ohne EXIF/XMP als Thermal- oder Multispektralbild ausgegeben.
- Wiederholte Scans sind idempotent. Nur Dateien des letzten vollständig
  erfolgreichen Scans erscheinen in der API; veraltete Indexeinträge
  werden nicht destruktiv entfernt. Fehler führen zum Transaktions-Rollback.
- Geschützte lokale GETs: /api/v1/dji/media/summary und /api/v1/dji/media,
  Filter nach kind, q (Dateiname), limit, offset. Gleicher LAN-/Token-Schutz
  wie /api/v1/status/devices. Keine Objektschlüssel oder signierten URLs.
- Browser-Übersicht: https://192.168.178.63:8000/media. Sie zeigt
  Indexzustand, Gesamtvolumen, Kategorien, Upload-Zeit und Dateinamen.
  Eine Medienvorschau oder ein Download ist **noch nicht enthalten**.
  Ein Scan lässt sich nicht über den Browser auslösen.

## Raspberry Pi: erst nach Merge

    cd ~/Projekte/AeroNexusAdvanced
    git status --short
    git pull --ff-only
    .venv/bin/python -m pytest -q tests/test_dji_media_index.py

    # Nur lesen / zählen, noch kein Index-Write
    .venv/bin/python -m aeronexus.dji_media_index

    # Bei plausiblen Zahlen lokalen Index anlegen bzw. aktualisieren
    .venv/bin/python -m aeronexus.dji_media_index --apply

    # Neue HTTP-Seite und Lese-API aktivieren, Cloud-Container unverändert
    systemctl --user restart aeronexusadvanced.service
    systemctl --user is-active aeronexusadvanced.service
    curl -ksSf https://192.168.178.63:8000/api/v1/dji/media/summary

Danach im LAN https://192.168.178.63:8000/media öffnen.

Neue Medien können jederzeit mit demselben --apply-Befehl nachindiziert
werden. Der Webdienst muss bei Folgescans **nicht** neu gestartet werden.
Es wird kein Timer eingerichtet, da große Buckets ressourcenintensiv
sein können. Standardmäßig werden höchstens 250000 Objekt-Einträge
je Scan verarbeitet, --max-objects kann dies begrenzt anpassen.

## Interpretation und Grenzen

- state=not_indexed: noch kein erfolgreicher Scan.
- state=ready, total=0: erfolgreicher Scan, keine erkannten Medientypen.
- HTTP 401/503: bestehenden LAN-/Dashboard-Zugang bzw. Index prüfen;
  keinesfalls Zugangsdaten in Browser-Anfragen kopieren.
- MinIO-last_modified ist der Objektänderungszeitpunkt und beweist
  **nicht** die Aufnahmezeit.
- Der Index lädt **keine Mediendaten**. Aufnahme-EXIF, DJI-XMP,
  Kamera/Linse, Thermaldaten, GNSS und Flugzuordnung bedürfen eines
  späteren gesonderten Content-Importers.
- Die Datenbank enthält möglicherweise Seriennummern in internen
  Objekt-Keys. Daher lokal privat halten und nicht ins Repo committen.
- Durch Entfernen der lokalen Index-Datei verschwinden nur
  Indizierungsdaten; keine Originaldatei im DJI-MinIO wird angerührt.
