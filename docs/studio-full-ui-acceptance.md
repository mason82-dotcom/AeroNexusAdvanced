# AeroNexusAdvanced UI / Chromium-Funktionsabnahme

## Prüfbereich

Der neue Browser-Smoke lädt die **vollständige, tatsächlich gerenderte**
Studio-HTML-Seite mit ihren Original-JavaScript-Handlern und CSS-Regeln.
Es wird nicht bloß eine reduzierte Komponenten-Nachbildung getestet.

Desktop (1440 × 900) und Mobil (420 × 860):

- Start der vollständigen Studio-Seite sowie initiale GET-Daten
- Navigation zwischen allen sechs Tabs und Sichtbarkeit der Seitenleisten
- Missionsplanung, Route, Zwischenpunkt, Undo/Redo, Verschieben und Löschen
- Kamera-/Gimbal-Aktionen bleiben bei Koordinatenänderungen erhalten
- Geo-Zeichenmodus, 3D-Steuerelemente/Reset und CSV-Dialog
- Medien- und DJI-Medienlisten, Suche und Aktualisieren
- Cloud-Routenliste, lesende WPML-Aktionsdiagnose, Tab-Wechsel-Cleanup
- Flottenliste und Pilot-2-Gerätetopologie
- Kartentools/Fokus sowie sichere Fehlermeldung bei fehlender Leaflet-Bibliothek
- Zugänglichkeit der fünf eigenständigen Seiten aus der Studio-Navigation

Die sieben HTML-Endpunkte werden zusätzlich über einen isolierten
FastAPI-TestClient geprüft (\`/studio\`, \`/status\`, \`/operations\`,
\`/media\`, \`/thermal\`, \`/multispectral\`, \`/results\`).

## Sicherheitsgrenze

Für den Chromium-Test werden Leaflet-CDN und externe Kartendienste
bewusst deaktiviert. Die tatsächlich gerenderte UI erhält ausschließlich
**synthetische GET-Antworten** über einen Browser-Fetch-Stub. Alle
Schreibzugriffe werden verweigert. Es gibt keine echte Authentifizierung,
keine DJI-Sitzung, kein MinIO, keine Flugdaten, keinen Upload, keinen
Backend-Dienst und keinen Zugriff auf den privaten Missionsspeicher.

Der Test ist **kein** produktiver HTTPS-End-to-End-Test und bestätigt weder
die tatsächliche Darstellung der Kartenkacheln, die Schnittstellen privater
Medien-Dateien, die reale DJI-Sitzung noch die Flugkompatibilität.

## Manuelle lokale Ausführung auf dem Pi

~~~bash
cd ~/Projekte/AeroNexusAdvanced
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python scripts/pi/studio_full_ui_chromium_smoke.py
~~~

Erwartet werden \`PASS\` auf Desktop und Mobil.
