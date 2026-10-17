# Automatischer Medien-Sync nach Pilot-2-Uploads

Stand: 17.10.2026 · Dienst `aeronexusadvanced-media-sync` (systemd `--user`)

Manuelle Medienuploads aus DJI Pilot 2 landen über den lokalen DJI-Cloud-API-
Server im MinIO-Bucket `dji-cloud`. Der Dienst hält danach alle
AeroNexusAdvanced-Kataloge aktuell – **nur lesend**, ohne Schreibzugriff auf
MinIO oder DJI:

1. Medienindex (`minio_media_index`) – vollständiger Abgleich mit dem Bucket
2. Thermal-Geo-Index (`thermal_geo`) – Kopfdaten neuer Wärmebilder (Range-Read)
3. Multispektral-Katalog (`multispectral`) und fehlende NDVI-Übersichten
4. Thermal-Messungen (DJI Thermal SDK) aller noch nicht gemessenen Wärmebilder
   (abschaltbar: `AERONEXUS_MEDIA_SYNC_THERMAL=0` in `.env` oder `--no-thermal`)

Jeder Schritt ist isoliert: ein Fehler stoppt die anderen nicht; im Status
erscheinen nur Fehlertypen, keine Objektschlüssel oder Zugangsdaten.

## Ablauf

- **Start = vollständiger Scan:** Beim Dienststart läuft ein kompletter
  Durchgang (eingerichtet am 17.10.2026 als einmaliger Erstscan).
- **Danach bei jedem Upload:**
  - *Abfrage-Modus* (Standard, keine zusätzlichen MinIO-Rechte): alle
    120 s wird ein Fingerabdruck des Bucket-Inhalts (Schlüssel, ETag, Größe)
    gebildet. Hat sich der Bucket geändert, läuft der Durchgang, sobald zwei
    Abfragen hintereinander gleich sind (Upload-Serie abgeschlossen),
    spätestens 10 min nach der ersten Änderung.
  - *Ereignis-Modus* (automatisch, wenn erlaubt): Abonnement der MinIO-
    Bucket-Benachrichtigungen; Durchgang 45 s nach dem letzten Upload-
    Ereignis, spätestens nach 10 min. Fällt bei verweigertem Recht
    automatisch auf den Abfrage-Modus zurück.
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
