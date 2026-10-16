# Phase 17 – sicherer Raspberry-Pi-5-Rollout und Chrome-Abnahme

Diese Anleitung ergänzt [Phase 17](phase-17-geo-photo-survey-terrain.md).
**Die bisherigen GitHub-Actions-Tests sind kein Ersatz für eine echte Pi-/Chrome-Prüfung.**
Der folgende lokale Test greift weder auf DJI-Flugsteuerung zu noch
überschreibt er Konfigurationsdateien.

## 1. Arbeitskopie prüfen

Auf dem **Raspberry Pi 5** ausführen:

```bash
cd ~/Projekte/AeroNexusAdvanced
git status --short
git log -1 --oneline
systemctl --user is-active aeronexusadvanced
```

Bei lokalen Änderungen nicht `reset --hard` oder `clean -fd` benutzen.
Erst verstehen/sichern, danach nur bei sauberer Arbeitskopie:

```bash
git pull --ff-only
.venv/bin/python -m pip check
bash scripts/pi/phase17-smoke.sh
```

Das Skript prüft Python-/venv-Abhängigkeiten, Phase-17-Regressionstests,
GDAL und NumPy, Status des User-Dienstes; es startet den Dienst **nicht** neu.
Falls `pytest` fehlt, ausschließlich in der vorhandenen venv ergänzen:

```bash
.venv/bin/python -m pip install -e '.[test,mqtt]'
```

## 2. GDAL und NumPy

`osgeo.gdal` und `numpy` müssen **in derselben venv wie AeroNexus** verfügbar
sein. Systempakete `python3-gdal` sind in normalen isolierten virtualenvs
nicht automatisch importierbar. Bitte vor Änderungen zunächst die Python-
und GDAL-Version auf dem Pi ermitteln. Ein ungeprüftes `pip install gdal`
in der Produktiv-venv vermeiden.

Ohne passendes GDAL funktioniert GeoObjekt/GeoPhoto/Survey weiterhin;
nur der GeoTIFF-Upload meldet `503`. Beim GeoTIFF-Import werden Dateien
mit mehr als 8 MiB, mehr als vier Millionen Rasterpixeln, schiefen
Rasterachsen, fehlendem/ungeeignetem CRS oder NoData-Lücken abgewiesen.

## 3. Dienst bewusst neu starten und TLS-Liveprüfung

**Erst nach erfolgreichen lokalen Tests:**

```bash
systemctl --user restart aeronexusadvanced
systemctl --user is-active aeronexusadvanced
PHASE17_CHECK_LIVE=1 bash scripts/pi/phase17-smoke.sh
```

Die Live-Prüfung verwendet ausschließlich die lokale Projekt-CA
`config/pki/ca.crt` mit vollständiger TLS-Verifikation.
Sie liest `/health` und die öffentliche, statische `/studio`-Shell,
aber keine privaten Telemetrie-/Missions-/DJI-Daten. Die Verwendung von
`curl -k` wird ausdrücklich vermieden. Bei nicht erreichten
Endpunkten gibt das Skript einen Fehler zurück.

## 4. Chrome-Abnahme auf https://192.168.178.63:8000/studio

1. **Geo & Gelände:** Polygon zeichnen, einen Punkt ziehen, einen Punkt
   einzeln löschen, speichern, bearbeiten, nach Neuladen vergleichen.
   Gespeicherte WPML-Wegpunkte dürfen dabei unverändert bleiben.
2. **Flugstreifen:** Polygon auswählen, 20 m Spurabstand und 0° Richtung.
   Gestrichelte Streifen müssen innerhalb der Fläche liegen. Es sind
   **keine verbundenen oder flugfähigen DJI-Routen**.
3. **GeoPhoto:** Vorhandenes Testbild auswählen, WGS84-Koordinaten und
   Kameraausrichtung manuell erfassen, speichern und „Fotos auf Karte“
   testen. Keine automatisch ermittelte Bodenabdeckung.
4. **Gelände:** Bekanntes GeoTIFF (EPSG:4326 oder projiziert, Nord oben,
   ein Band, keine NoData-Lücken, maximal 8 MiB und vier Millionen Pixel)
   auswählen, Drahtgitter-Vorschau und STL-Export prüfen.
5. **Flottenstatus:** Bestehenden „Aktualisieren“-Knopf prüfen.
   Ereignis-WebSocket bleibt ohne explizites Opt-in aus.

Für optionalen WebSocket im **bereits explizit aktivierten**
`AERONEXUS_LAN_NO_TOKEN=1`-Modus zusätzlich
`AERONEXUS_STUDIO_EVENTS=1` in der privaten `.env` konfigurieren,
danach den Dienst bewusst neu starten. Ohne direktes vertrautes WSS-LAN
und passende Browser-Origin ist die Verbindung nicht zulässig.

## Bekannte Grenzen

- Kein automatischer GeoPhoto-Bildfußabdruck.
- Keine Hindernisprüfung, Geländefreigabe oder DJI-Survey-Mission.
- Kein eigenständiger RTK-/ADS-B-Kollisionsschutz.
- Der echte Pi-5-/Chrome-/GDAL-Live-Test ist separat zu dokumentieren.
