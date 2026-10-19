# Refactoring-Bestandsaufnahme – 19. Oktober 2026

## Geltungsbereich

Ausgangspunkt ist GitHub-`main` bei Commit `cf1c4eb61d789f4e80f00d7cbf7edbc90ac869f8`
(Merge PR #75). Die GitHub-Git-Tree-API lieferte den vollständigen, nicht
abgeschnittenen Dateibaum (`truncated=false`). **Diese Prüfung ist keine
Messung auf dem Raspberry Pi und keine vollständige Ausführung aller Codepfade.**
Private Betriebsdateien, MinIO-Daten und die Pi-Laufzeit wurden nicht geöffnet
oder verändert.

| Git-Bestand | Umfang |
| --- | ---: |
| Dateien gesamt | 302 |
| Python-Quelldateien in `src/aeronexus` | 77 / 1.196.621 Bytes |
| Python-Testdateien in `tests` | 125 / 832.633 Bytes |
| Dokumentationsdateien in `docs` | 55 / 408.823 Bytes |
| `src/aeronexus/studio_page.py` | 177.057 Bytes |
| `src/aeronexus/app.py` | 80.988 Bytes |
| `src/aeronexus/operations_page.py` | 56.747 Bytes |
| `src/aeronexus/thermal_page.py` | 55.378 Bytes |
| `src/aeronexus/multispectral_page.py` | 54.659 Bytes |

Die Größen stammen aus Git-Dateimetadaten. Sie sind **keine** Messwerte für
RAM, CPU oder Netzwerknutzung. Die optionale Abhängigkeitsaufteilung in
`pyproject.toml` wird beibehalten.

## Erste überprüfbare Änderungen im Refactoring-Branch

1. `HmsHistory.list_events`: Gefilterte Gesamtsumme weiterhin korrekt,
   jedoch werden beim Paginieren nur die angeforderten Elemente als Liste
   gespeichert. Eine API-Anfrage benötigt daher keinen zusätzlichen Speicher
   proportional zur Zahl aller Treffer. Reihenfolge und Filter bleiben erhalten.
2. `StatusRuntime.summary`: Geräte- und Frischezähler einschließlich
   Health-Warnungen in einem Durchlauf über die projizierten Geräteansichten.
   Die Anonymität des Summary-Endpunkts bleibt unverändert.
3. `DjiMediaIndex.scan`: Bei unveränderten MinIO-Objekten nur den
   `scan_marker` aktualisieren; Änderungen behalten den bisherigen UPSERT.
   Die atomare Transaktion und das Entfernen nicht mehr vorhandener
   Katalogeinträge bleiben erhalten. **DJI-Bucketobjekte werden nie verändert.**
4. `render_studio`: Die statische HTML-Ausgabe wird einmalig berechnet und
   im Prozess gecacht. Die Seite enthält keine sitzungsbezogenen Werte oder
   vertraulichen Tokens.

Für diese Änderungen wurden gezielte Regressionstests ergänzt. Messbare
Beschleunigungen sind erst nach Vorher-/Nachher-Benchmarks nachgewiesen;
insbesondere sind noch **keine Prozentwerte** zu behaupten.

## Strukturelle nächste Kandidaten (noch nicht umgesetzt)

- `studio_page.py` und weitere große `*_page.py`-Module:
  eingebettetes HTML/CSS/JS in versionierte, überprüfte statische Assets
  zerlegen. Vorher Inhalts-Sicherheitsrichtlinien, Offline-Fähigkeit,
  Browser-Smoke-Tests und mögliche HTTP-Routenänderungen abgleichen.
- `app.py`: große Zahl von FastAPI-Routen nach fachlichen Routern
  gliedern. Erst nach Inventarisierung aller Endpunkte,
  Authentifizierungsregeln, HTTP-Statuscodes und Lifespan-Abhängigkeiten.
- `cloud_api_freshness.py` / `status_runtime.py`: Datenkopien und
  per-device HMS-Suchen unter reproduzierbarer, synthetischer DJI-
  Telemetrielast profilieren. Keine Änderung der Quellzeit-/Frischelogik
  ohne M3/M4- und OSD/State-Regressionsprüfungen.
- `minio_media_index.py`: bei großen Katalogen SQL-Ausführungspläne und
  Indizes für Filter, Sortierung und Paging prüfen. Nur auf einer Kopie
  eines privaten Testindex, nicht auf produktiven Mediendaten.
- `docs`, `scripts` und `tests`: archivierte Dokumentation und optionale
  Chromium-Werkzeuge separat halten. Nicht pauschal löschen, da sie die
  Offline-, Sicherheits- und DJI-WPML-Abnahme absichern.

## CI und Betriebsfreigabe

Auf dem untersuchten `main` lief Python 3.13 erfolgreich; Python 3.12
scheiterte bei einem Chromium-Studio-Browsertest mit Prozess-Exit `-6`,
während 1.633 andere Tests bestanden. Dieser Ausgang liegt **vor** dem
Refactoring und darf nicht unbesehen diesem Branch zugeschrieben werden.
Die Branch-CI muss je Commit/PR gesondert geprüft werden.

Flugkommandos, DJI-Missionsupload, EMQX/MQTT-Berechtigungen, WPML-Export,
TLS, lokale Session-Übergabe sowie private MinIO-/SQLite-Daten dürfen
durch die Optimierung weder freigegeben noch umgangen werden.
`main`, die lokale Pi-Arbeitskopie und der systemd-Produktivdienst bleiben
ohne expliziten Rollout unverändert. Vor einem späteren Deployment sind
echte DJI-Status-, Pilot-2-, HTTPS- und Browsertests notwendig.
