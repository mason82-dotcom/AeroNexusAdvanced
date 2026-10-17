# Automatischer Medien-Sync nach Pilot-2-Uploads

Stand: 17.10.2026 · Dienst `aeronexusadvanced-media-sync` (systemd `--user`)

Manuelle Medienuploads aus DJI Pilot 2 landen über den lokalen DJI-Cloud-API-
Server im MinIO-Bucket `dji-cloud`. Der Dienst hält danach alle
AeroNexusAdvanced-Kataloge aktuell – **nur lesend**, ohne Schreibzugriff auf
MinIO oder DJI:

1. Medienindex (`minio_media_index`) – vollständiger Abgleich mit dem Bucket
2. Fotokatalog (`photo_catalog`) – Modell/Kamera/Position aller JPEGs (Range-Read),
   erkennt auch FlightHub-Infrarotbilder `org_*.jpg` ([photo-catalog.md](photo-catalog.md))
3. Thermal-Geo-Index (`thermal_geo`) – Kopfdaten neuer Wärmebilder (Range-Read)
4. Multispektral-Katalog (`multispectral`) und fehlende NDVI-Übersichten
5. Thermal-Messungen (DJI Thermal SDK) aller noch nicht gemessenen Wärmebilder
   (abschaltbar: `AERONEXUS_MEDIA_SYNC_THERMAL=0` in `.env` oder `--no-thermal`)

Jeder Schritt ist isoliert: ein Fehler stoppt die anderen nicht; im Status
erscheinen nur Fehlertypen, keine Objektschlüssel oder Zugangsdaten.
Auch zurückgegebene Fehlerzähler (Thermal-Geo, Multispektral, NDVI und
Thermal-Messungen) setzen den Schritt und den Gesamtdurchgang auf `ok=false`.
`--once` endet dann mit Exitcode 1. NDVI-Fehler werden nur gezählt; Aufnahme-IDs
werden nicht in den Sync-Status übernommen. Ein nicht konfiguriertes Thermal SDK
bleibt ein ausdrücklich übersprungener Schritt.

## Ablauf

- **Start = vollständiger Scan:** Beim Dienststart läuft ein kompletter
  Durchgang. Im Abfrage-Modus wird der Vergleichs-Fingerabdruck **vor** diesem
  Scan erfasst, damit Uploads während des Scans anschließend auffallen.
- **Danach bei jedem Upload:**
  - *Abfrage-Modus* (Standard, keine zusätzlichen MinIO-Rechte): alle
    120 s wird ein Fingerabdruck des Bucket-Inhalts (Schlüssel, ETag, Größe)
    gebildet. Hat sich der Bucket geändert, läuft der Durchgang, sobald zwei
    Abfragen hintereinander gleich sind (Upload-Serie abgeschlossen),
    spätestens 10 min nach der ersten Änderung.
  - *Ereignis-Modus* (automatisch, wenn erlaubt): Abonnement der MinIO-
    Bucket-Benachrichtigungen; Durchgang 45 s nach dem letzten Upload-
    Ereignis, spätestens nach 10 min. Bei verweigertem Recht, Verbindungsfehler
    oder beendetem Ereignisstrom erfolgt ein vollständiger Abgleich und der
    Wechsel auf den Abfrage-Modus. Ein erneuter Dienststart versucht den
    Ereignis-Modus wieder; ein separater, möglicherweise hängenbleibender
    Test-Listener wird nicht mehr gestartet.
- **Fehlerwiederholung:** Fehlgeschlagene Durchgänge werden nach 120 s erneut
  versucht (im Abfrage-Modus bei der nächsten fälligen Abfrage), auch ohne
  neuen Upload. Der letzte fehlgeschlagene Bericht bleibt bis dahin sichtbar.
- **Sicherheitslauf** alle 6 h, falls Änderungen verpasst wurden.

## Ereignis-Modus freischalten (optional)

Der vorhandene Lesezugang darf Bucket-Ereignisse standardmäßig nicht
abonnieren. Freigabe (einmalig, bewusst durch den Betreiber):

```bash
.venv/bin/python scripts/pi/grant_minio_listen.py
systemctl --user restart aeronexusadvanced-media-sync
```

Das Skript legt eine **zusätzliche** Policy an, die nur
`s3:ListenBucketNotification` auf `dji-cloud` erlaubt, und hängt sie an den
Lesezugang aus `.env`. Die bestehende Lese-Policy bleibt unverändert; es
werden keine Schreib-, Lösch- oder Admin-Rechte vergeben. Die lokalen
MinIO-Root-Daten aus `cloud-server/edge/.env` werden nur für diesen Aufruf
gegen 127.0.0.1 genutzt und nie ausgegeben.

## Betrieb

```bash
bash deploy/pi/install-service.sh            # installiert/aktualisiert beide Dienste
systemctl --user status aeronexusadvanced-media-sync
journalctl --user -u aeronexusadvanced-media-sync -f
.venv/bin/python -m aeronexus.media_sync --once   # manueller Durchgang
```

- Status: `GET /api/v1/media/sync` und Kachel „Auto-Sync (Pilot 2 Uploads)“
  auf `/media` (Zustand, Modus, letzter Durchgang). Statusdatei
  `media_sync_status.json` (0600) im privaten Workspace.
- Der Dienst läuft mit niedrigerer CPU-/IO-Priorität (`Nice=10`,
  `IOSchedulingClass=idle`) und `MemoryMax=1500M`.
- Multispektral-Bandverarbeitung, M3M-Stacking und Thermal-SDK-Aufrufe teilen
  sich eine prozessübergreifende `flock`-Sperre im privaten Workspace
  (`image-processing.lock`, 0600). Webdienst, Sync und unterstützte CLI-
  Einstiegspunkte müssen unter demselben Benutzer mit demselben
  `AERONEXUS_WORKSPACE_DIR` laufen. Das gilt auch bei systemd `PrivateTmp`;
  die Sperrdatei liegt deshalb nicht unter `/tmp` und darf nicht gelöscht oder
  ersetzt werden. Nach einem Absturz gibt der Kernel die Sperre frei.
  Cache-Lesezugriffe bleiben möglich; die Sperre begrenzt aktive Berechnungen,
  nicht den insgesamt von Caches belegten Speicher. POSIX/Linux erforderlich.
