# Standalone Web-UIs: isolierte Chromium-Prüfung

Ergänzend zum vollständigen Studio-Desktop-/Mobil-Smoke werden die
Originaloberflächen von Operations, Thermal, Multispektral, Ergebnisraster,
DJI-Medienkatalog und Live-Status in echtem Chromium gestartet.

Der Test prüft initialen JavaScript-Start, lesende API-Anfragen,
Klick-Handler an statischen Schaltflächen, die sichtbare Reaktion auf
nicht verfügbare Daten sowie exemplarische Navigation, Suchen, Filtern,
Tab-Wechsel und Werkzeugauswahl.

**Wichtige Einschränkung:** Synthetische GET-API-Antworten simulieren
absichtlich die Nichterreichbarkeit der realen Datenquelle. Damit werden
der Start und die Fehlerfälle geprüft, **nicht** reale Wärmebildmessungen,
Karten, Raster-Rendering, Medienvorschauen, SDK-Anbindung oder
tatsächliche End-to-End-Workflows mit Daten. Die originale HTML-Seite und
ihre Handler bleiben unverändert, die externe Leaflet-Bibliothek wird
für den vollständig offline laufenden Test entfernt.

Start auf Raspberry Pi mit Chromium:

~~~bash
cd ~/Projekte/AeroNexusAdvanced
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python scripts/pi/standalone_ui_chromium_smoke.py
~~~

Alle sechs Module müssen PASS melden. Der Test greift auf keinen
produktiven Dienst zu und führt keinerlei Schreiboperation aus.

Getestete Viewports: Desktop 1440×900 und Mobil 420×860 für jedes Modul.
