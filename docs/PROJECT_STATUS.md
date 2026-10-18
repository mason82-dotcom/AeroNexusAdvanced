# AeroNexusAdvanced – Projektstatus

**Dokumentationsstand: 18. Oktober 2026.** Dies ist eine **GitHub-/Entwicklungsbestandsaufnahme**, keine automatisierte Abfrage des produktiven Raspberry Pi. Die letzte unveränderte `main`-Basis bei dieser Prüfung war `3125225e8774ffb6aec3b10652776ddf5df52498` (Merge von PR #63: DJI Matrice-4-Kameraspeicher-OSD). Der tatsächliche Dienststand auf dem Pi muss separat ermittelt werden.

Zur älteren detaillierten Entwicklungschronik: [Archiv 17.10.2026](archive/PROJECT_STATUS-2026-10-17.md). Frühere Testzahlen, damalige PR-Zustände und Behauptungen zu damals nicht durchgeführten Rollouts gelten ausschließlich für ihren jeweiligen Zeitpunkt.

## Implementierungsumfang auf main

| Bereich | Implementiert / belegbarer Codepfad | Grenzen |
| --- | --- | --- |
| DJI Cloud API / OSD | Lesender MQTT-Consumer für OSD, optional /state und HMS, normalisierte M3-/M4-/RC-Daten, zeitliche Frischebehandlung | MQTT-Abo ist keine Bestätigung neuer Gerätedaten; Event-/HMS-Zustand hängt von realen Nachrichten ab |
| Live-Cockpit | `/status` mit Fluggerät, RC, OSD, Akku, GPS/RTK, Kamera, Gimbal und HMS | Keine erfundenen Werte bei fehlenden Daten; keine Flugsteuerung |
| Operationen | `/operations`, FlightHub-Quellen, lokale Cloud und optional Cloud-API-2-Bridge | Cloud API 2 ist unabhängig und standardmäßig deaktiviert |
| Studio | `/studio`, lokale Missionen, KMZ/WPML, CSV, Survey-/Terrain-Vorschau, lokale Medien und lesende Cloud-Wayline-Metadaten | DJI-Pilot-2-Akzeptanz und reale Flugausführung sind dadurch nicht nachgewiesen |
| Medien | Gemeinsamer privater MinIO-Metadatenindex für `/studio` und `/media`, Foto-/Medien-Funktionen | Leseindex löscht keine DJI-Bucketobjekte; Scanner und Medien-Sync sind separate Prozesse |
| Spezialmodule | `/thermal`, `/multispectral`, `/results`, optionale SDK-/Raster-Integration | Reale radiometrische und georeferenzierte Genauigkeit nicht allein durch Tests belegt |
| Sicherheit | Geschützte APIs; optional tokenfreier direkter HTTPS-LAN-Modus | Dieser Modus erlaubt je nach Route **lokale Mission-/Medien-Schreibzugriffe**; nicht öffentlich exponieren |

Die fachlichen Anleitungen stehen im [Dokumentationsindex](README.md). Die Konfiguration und Installationsschritte ergeben sich aus `.env.example`, [Pi-Betrieb](deploy-pi.md), [Live-Telemetrie](live-telemetry-cockpit.md), [Cloud-API-HMS](dji-cloudapi-hms.md) und [Missions-/Wayline-Abgleich](mission-wayline-reconciliation.md).

## GitHub-Arbeit in Bearbeitung

Bei der letzten Prüfung am 18.10.2026 waren folgende Pull Requests offen; der Status kann sich jederzeit ändern:

- [PR #44 – Pilot-2-Direktupload als optionales CLI](https://github.com/mason82-dotcom/AeroNexusAdvanced/pull/44): **nicht in main**. Die Schreibaktion besitzt zusätzliche Aktivierungs- und Bestätigungsschranken; der echte Cloud-Server-Upload wurde laut PR-Beschreibung nicht produktiv validiert. **Nicht** als freigegebenen Studio-Upload dokumentieren.
- [PR #62 – Leaflet-Survey-Regressionsprüfungen](https://github.com/mason82-dotcom/AeroNexusAdvanced/pull/62): testbezogene Arbeit, damals noch nicht gemergt.
- [PR #64 – sicheres Repository-Housekeeping](https://github.com/mason82-dotcom/AeroNexusAdvanced/pull/64): Ignore-Regeln und optionale Branch-Bereinigung, damals noch nicht gemergt.

Diese Dokumentationspflege wurde bewusst auf einem eigenen Branch angelegt. Es wurden keine DJI-Server-, MQTT-, Systemd-, MinIO- oder Flugsteuerungsdateien angefasst.

## Reale Pi- und DJI-Abnahme – sauber getrennt

Frühere Live-Rückmeldungen vom Raspberry Pi 5 zeigten einen erreichbaren HTTPS-Dienst, empfangene DJI-OSD-Telemetrie einer eingeschalteten Drohne/RC und zwei aktive HMS-Erinnerungen. Das belegt den damaligen Eingang dieser Werte, **nicht** deren fortlaufende Aktualität, den Zustand sämtlicher optionaler Datenquellen oder das Bestehen aktueller Browser-/Missionstests.

Ein `subscribed`-Status des MQTT-Consumers bestätigt nur die Broker-Verbindung. `accepted`, `last_message_at`, OSD-/State-Quellzeiten und die Frische jedes Geräts sind getrennt zu prüfen. Nach Dienstneustart kann ein nur im Arbeitsspeicher aufgebautes Inventar zunächst leer sein.

Zum lesenden Check auf dem Pi:

~~~bash
cd ~/Projekte/AeroNexusAdvanced
git status --short --branch
git log -1 --oneline
systemctl --user is-active aeronexusadvanced
curl --cacert config/pki/ca.crt https://192.168.178.63:8000/health
~~~

Für einen neuen positiven Nachweis müssen die [produktiven GET-API-Prüfungen](production-ui-readonly-audit.md) und gegebenenfalls die [Chromium-HTTPS-Prüfung](production-ui-browser-audit.md) **separat** ausgeführt werden. Ein GitHub-CI-Pass allein bestätigt keine echte DJI-Sitzung oder korrekte Anzeige auf einem Zielgerät.

## Offene Prüfpunkte / Entwicklungsgrenzen

1. Pilot-2-Wayline-Direktupload (PR #44) bis zur kontrollierten Backend-End-to-End-Prüfung nicht aktivieren oder als sicher freigegeben darstellen.
2. KMZ/WPML-Export und gerätespezifische Kamera-/Gimbal-Aktionen müssen vor realem Flug in DJI Pilot 2 und am jeweiligen Modell geprüft werden.
3. Nach Code- oder UI-Änderungen produktiven HTTPS-/Chromium-Test mit echter CA erneut durchführen, ohne unbeabsichtigte POST-/DELETE-Aufrufe.
4. Der mit PR #65 ergänzte HMS-Verlauf in einer lokalen privaten SQLite-Datei (geschützte GET-API \`/api/v1/status/hms-history\`, maximal 3.000 Übergänge) ist auf GitHub gemergt, aber sein Rollout auf dem Pi muss separat geprüft werden. DJI-HMS-Katalog, OSD-/State-Frische, M4-Kamerawerte und optionaler Media-/MinIO-Abgleich hängen vom tatsächlich installierten Code und der echten Quelle ab.
5. Für den Raspberry Pi die Hauptarbeitskopie, `.env`, TLS-Schlüssel, lokale `cloud-server/`-Daten sowie MinIO-/Docker-Volumes nicht mit Git-Aufräumkommandos löschen.

## Wiederaufnahme ohne Datenverlust

Vor jeder Aktualisierung den Pi-Branch, den Git-Status und den aktiven Dienststand feststellen. Bei lokalen Änderungen, Worktrees oder ungesicherten Daten nicht `git reset --hard` oder `git clean -fdx` einsetzen. Neue Funktionen zuerst als PR isoliert prüfen. Reproduzierbare Vorgehensweisen: [Pi-Deployment](deploy-pi.md), [reale UI-Prüfung](production-ui-browser-audit.md), [Repository-Index](README.md).
