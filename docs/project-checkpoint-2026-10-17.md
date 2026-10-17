# AeroNexusAdvanced – Projekt-Checkpoint vom 17.10.2026

> **Status:** Phase 21 (DJI-Medien aus MinIO) ist auf dem Raspberry Pi 5 praktisch getestet und funktionsfähig. **Der Code ist noch nicht in `main` gemergt.** Dieser Checkpoint dokumentiert den bestätigten Stand; er ist weder eine automatische Sicherung der MinIO-Medien noch ein Ersatz für ein Pi-Backup.

## Repository und Deployment

- Repository: `mason82-dotcom/AeroNexusAdvanced`
- Pi-Projektverzeichnis: `/home/mason/Projekte/AeroNexusAdvanced`
- Implementierungsbranch: `feature/dji-minio-media-index-20261017`
- GitHub Draft-PR: [#18 – Phase 21: DJI-MinIO-Medien schreibgeschützt indizieren und im Studio einlesen](https://github.com/mason82-dotcom/AeroNexusAdvanced/pull/18) (**offen, Draft, nicht gemergt**).
- Referenz-HEAD vor diesem Checkpoint: `c9ab38f5bf82f371c783af39cc4dd6f69eb5c2d3` (GitHub Actions: erfolgreich; **650 Tests bestanden, 1 Starlette/httpx2-Warnung**).
- Pi-Laufzeit: Python 3.13 in `.venv`, MinIO-SDK `7.2.20`, Webdienst `aeronexusadvanced` via `systemctl --user`.
- Mission Studio: `https://192.168.178.63:8000/studio` (direkter lokaler HTTPS-LAN-Zugriff).
- Laufender MinIO-Container: `aeronexusadvanced-cloud-minio-1`, API an `127.0.0.1:9000`, Bucket `dji-cloud`. Alte Edge-MinIO-Container waren gestoppt; nicht automatisch starten.

## Bestätigte Live-Abnahme – 17. Oktober 2026

1. `git fetch` / Branchwechsel / Installation `pip install -e '.[test,mqtt,minio]'` auf dem Pi erfolgreich.
2. `tests/test_minio_media_index.py`: **5 bestanden**.
3. `tests/test_minio_readonly_setup.py`: **3 bestanden**.
4. MinIO-Health: HTTP **200**.
5. Vollständiger erster, read-only MinIO-Scan:
   - **6.095** indizierte Medien, **6.095** neu, **0** aktualisiert, **0** aus Index entfernt, **32** ignorierte sonstige Objekte.
   - Scanzeit `2026-10-17T00:56:36.100920Z` (02:56:36 MESZ).
   - Formate: **6.076 JPEG (26,41 GiB)**, **16 TIFF (0,15 GiB)**, **3 MP4 (1,21 GiB)**; insgesamt rund **27,77 GiB**.
6. Der separate MinIO-Lesezugang wurde mit `scripts/pi/configure_minio_readonly.py` erstellt. `AERONEXUS_MINIO_*` steht in der privaten Projekt-`.env`. Der Dry-run mit dem neuen Konto meldete `{"bucket":"dji-cloud","read_access":"ok","first_object_exists":true}`.
7. Der Webdienst wurde neu gestartet und zeigte `active`.
8. Die authentisierte/LAN-freigegebene Katalog-API `GET /api/v1/studio/dji-media?limit=1` lieferte **6.095** Einträge und den korrekten Scanzeitstempel.
9. Der originale JPEG-Abruf `GET /api/v1/studio/dji-media/{id}/file` lieferte **HTTP 200**, `image/jpeg` und **2.670.592 Bytes**.
10. Im Android-Browser wurde der DJI-MinIO-Katalog mit Medienkarten und Metadaten sichtbar; die Bildvorschau über **„Ansehen“** funktionierte nach ausdrücklicher Bestätigung des Anwenders.

**Fazit:** Phase 21 ist funktional auf der realen Pi-/MinIO-Installation abgenommen. Originaldateien werden nur gelesen, nicht kopiert oder geändert. Dies belegt die reale Bildvorschau, **nicht** die Funktion jedes Downloads oder eine automatische Indexaktualisierung.

## Softwareumfang und Sicherheitsgrenzen

- Modul `src/aeronexus/minio_media_index.py`: expliziter idempotenter Scan; privater SQLite-Index `dji_minio_media.sqlite3`, Dateimodus 0600.
- GET-Katalog und GET-Streaming-Route in `src/aeronexus/app.py`; opaque Medien-IDs, Dateiabgleich über Größe und ETag, keine MinIO-Schreibbefehle.
- Studio-Integration in `src/aeronexus/studio_page.py`: Suche, Pagination, JPEG-Vorschau und Downloads, von lokaler editierbarer Medienbibliothek getrennt.
- MinIO-Reader-Setup `scripts/pi/configure_minio_readonly.py`: eigener Bucket-gebundener Benutzer und Policy mit `s3:ListBucket`, `s3:GetBucketLocation`, `s3:GetObject`; keine `PutObject`-/`DeleteObject`-Rechte. Zugangsdaten nie in Git oder in Chat-Ausgaben übernehmen.
- MinIO-Client `mc` wurde nach Stilllegung des ursprünglichen `dl.min.io`-Downloads vom offiziellen GitHub-Release `RELEASE.2025-08-13T08-35-41Z` mit SHA256-Prüfung bezogen.
- Bestehende lokale Datei `requirements-lock.txt` war **untracked**; nicht automatisch löschen, überschreiben oder committen.
- Dienst-/Konfigurationsänderungen auf dem Pi ausschließlich gezielt und mit Prüfung, keine Wiederaktivierung des Legacy-AeroNexus-Stacks.

## Offen / nächster Entwicklungsabschnitt

**Phase 22 – Medienbibliothek 2.0 (noch nicht umgesetzt oder beauftragt):**
- Echte Miniaturbilder/Thumbnails unmittelbar in der Galerie statt „DJI · Foto“-Platzhaltern; bandbreitenschonend, optional serverseitig gecacht.
- Responsive mobile Darstellung der Weboberfläche (im Android-Screenshot seitlich abgeschnitten).
- Regelmäßiger, nicht überlappender, read-only MinIO-Indexscan per `systemd --user` Timer (vorgeschlagen etwa alle 15 Minuten); Status, Fehlerprotokoll und klare Trennung vom Legacy-Stack.
- Optional danach: DJI EXIF/XMP-/GPS-Metadaten für geo-referenzierte Fotos und Zuordnung von Medien zur Mission; bisher **nicht** indiziert.
- Optional gezielte Validierung großer MP4-Downloads; bisher nur JPEG erfolgreich end-to-end abgenommen.
- PR #18 erst nach Freigabe/Review in `main` mergen; Stand heute Draft.

## Wiederaufnahme in einer späteren Sitzung

1. Diesen Checkpoint lesen, dann PR #18 und GitHub-Actions-Status prüfen.
2. Auf dem Pi vor jeder Änderung `cd ~/Projekte/AeroNexusAdvanced && git status --short && git branch --show-current`.
3. Dienste nur bei Bedarf prüfen: `systemctl --user is-active aeronexusadvanced`; MinIO via `curl --max-time 5 -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9000/minio/health/live`.
4. Aktuelle Medieninventur ohne Änderung: `.venv/bin/python -m aeronexus.minio_media_index --dry-run`; kompletter Scan nur ausdrücklich bei Bedarf: `.venv/bin/python -m aeronexus.minio_media_index`.
5. Keine Zugangsdaten, Token, kompletten `.env`-Dateien oder sensible DJI-Objektschlüssel in öffentliche GitHub-Dateien schreiben.

**Merksatz:** AeroNexusAdvanced Phase 21 auf Pi 5: 6.095 DJI-Medien aus `dji-cloud` erfolgreich read-only indiziert; REST-API, JPEG-Streaming und Smartphone-Vorschau laufen. Branch/PR #18 offen, `main` unverändert; nächster Vorschlag Phase 22 Thumbnails + Mobil-UI + Auto-Sync.
