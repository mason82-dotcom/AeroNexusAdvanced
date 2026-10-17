# DJI-Medienseite: gemeinsamer Phase-21-Katalog

Die eigenständige Metadatenansicht `/media` und ihre GET-Endpunkte
`/api/v1/dji/media` und `/api/v1/dji/media/summary` bleiben erreichbar.
Sie lesen jetzt denselben privaten SQLite-Katalog wie das Mission Studio.
Die Kategorien Bild, RAW, Video, Audio und Begleitdatei bleiben erhalten.
Die vorhandenen LAN-/Token-Zugriffsprüfungen gelten weiterhin.

## Einmaliger Umstieg von der früheren Phase-20-Implementierung

- Der Scanner benötigt den separaten MinIO-Lesezugang und das Extra `minio`.
  Einrichtung und Pi-Kommandos: [Phase 21](phase-21-dji-minio-media.md).
- Der aktive Index ist `dji_minio_media.sqlite3` im privaten Workspace,
  standardmäßig `~/.local/share/aeronexusadvanced`.
- `var/dji-media-index.sqlite3` wird nicht mehr verwendet, nicht automatisch
  migriert und nicht gelöscht. Bei bisherigen Phase-20-Installationen ist
  ein expliziter Scan des Buckets nötig. Originalmedien bleiben unverändert.
- Auf dem bereits für Phase 21 eingerichteten Pi wird derselbe vorhandene
  Katalog weiterverwendet. Kein erneutes Reader-Setup nötig.
- Der Scan liest mit dem SDK und dem Bucket-beschränkten Reader. Kein
  `docker exec`, kein MinIO-Root-Konto und kein `mc` im normalen Scanpfad.
- Beide UIs zeigen einen Scan erst nach erfolgreichem Abschluss. Bei einem
  Scanfehler oder Überschreiten von 250.000 Objekten bleibt der vorige
  Katalog erhalten. Aus MinIO verschwundene Dateien werden ausschließlich
  aus dem lokalen Index entfernt.

## Kommandos

```bash
# Zugang prüfen, keine Indexänderung:
.venv/bin/python -m aeronexus.minio_media_index --dry-run
# Gesamten Katalog explizit aktualisieren:
.venv/bin/python -m aeronexus.minio_media_index
```

Der alte Einstieg `python -m aeronexus.dji_media_index` bleibt eine reine
Zugangsprüfung. `--apply` leitet zum expliziten Indexscan weiter.
`--max-objects` begrenzt den Scan; die Zugangsprüfung prüft nur die erste
Listenantwort und bestätigt keine vollständige Inventur.

Es gibt weiterhin keinen automatischen Scan, Timer oder Medienimport.
