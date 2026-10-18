# Positive Chromium-Browserabnahme gegen den produktiven Pi

**Ziel:** Reale Browserausführung der sieben Fach- und Studio-HTML-Seiten
über die vorhandene HTTPS-LAN-Adresse, mit echten JSON-GET-Antworten,
technisch blockierten Schreibzugriffen und überprüfbaren Mobil-Layouts.

## Einrichtung im isolierten Prüf-Worktree

Das Produktivsystem und der vorhandene \`.env\`-Speicher bleiben unberührt.

~~~bash
cd ~/Projekte/AeroNexusAdvanced
git fetch origin main
git worktree add --detach ~/Projekte/AeroNexusAdvanced-live-browser-audit origin/main
"$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" -m pip install \
  "playwright>=1.56,<2"
# Browser-Paket nicht herunterladen: der vorhandene System-Chromium wird genutzt.
cd ~/Projekte/AeroNexusAdvanced-live-browser-audit
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  "$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" \
  scripts/pi/production_ui_browser_audit.py \
  --instance-dir "$HOME/Projekte/AeroNexusAdvanced"
~~~

Voraussetzungen: \`chromium\` und \`certutil\`
(Debian/Raspberry Pi OS: Paket \`libnss3-tools\`). Der Test meldet die
fehlende Voraussetzung, statt unsicher auf \`--ignore-certificate-errors\`
auszuweichen. Die lokal signierende CA wird **nur** in eine temporäre
NSS-Datenbank importiert. Die Python-HTTPS-Vorprüfung verwendet dieselbe
lokale CA und prüft den \`/health\`-Endpunkt, bevor Chromium startet.

## Was wird tatsächlich geprüft?

- Original-DOM, Scripts und echte HTTPS-API-GETs: Studio, Live-Status,
  Operations, DJI-Medien, Thermal, Multispektral und Ergebnisse.
- Beide Viewports: Desktop 1440×900 und Mobil 420×860,
  mobile Chrome-Emulation mit Touch.
- Vorhandensein des relevanten Oberflächenelements und horizontaler
  Überlauf relativ zum Viewport (mehr als 8px => FAIL).
- Mindestens eine echte erfolgreiche API-GET-Antwort je Seite.
- Keine unbehandelten JavaScript-Ausnahmen.
- Physische Browserklicks auf explizit geprüfte, sichere Schaltflächen:
  Karten-Werkzeuge, Aufgabenfilter, Medien-Refresh, Thermal-Tabs,
  Multispektral-Ansicht und Ergebnis-Suche; der Status wird nur gelesen.
- Keine Textausgaben, GPS-Koordinaten, Gerätenummern, Projektnamen,
  Mediennamen, Screenshots, Netzwerkinhalte oder Bearer-Tokens im Terminal.

## Sicherheitsgrenzen

- \`BrowserContext.route("**/*", ...)\` blockiert sämtliche Methoden
  außer GET. Nur der exakte produktive HTTPS-Origin und die Leaflet-1.9.4-
  Assets von jsDelivr sind erlaubt. WHEP/POST/DELETE/Upload/Scan/
  Missionsänderungen sind ausgeschlossen.
- Token für Browser-GETs wird **nur** den API-Anfragen auf dem Pi-Origin
  angefügt, nie Drittanbieter-Ressourcen. Zusätzliche JS-Sperren verhindern
  Formularschreibzugriffe, XHR-Writes, WebSocket- und Beacon-Sendungen.
- Keine ungefragten Kartenkacheln von Drittanbietern. Bei
  \`--allow-tiles\` (ausdrückliche Nutzerentscheidung) werden je Seite
  höchstens 18 OSM/Esri-Kacheln geladen. Tile-Requests enthalten
  zwangsläufig die zugehörigen Kachelkoordinaten und kontaktieren den
  Drittanbieter; ohne Opt-in findet **keine** externe Kachelprüfung statt.
- Auch beim erfolgreichen Audit gelten Bilddekodierung, Thermal-/Raster-
  Berechnung, WebRTC, echte DJI-Kommandos und andere schreibende E2E-Aktionen
  weiterhin nicht als abgenommen. Visuelle Detailprüfung menschlicher Nutzer
  kann durch DOM-/Layoutchecks nicht vollständig ersetzt werden.

**Wichtig:** \`PASS\` bedeutet sichere positive Browserstart-/Layout-
und GET-Interaktion, nicht vollständige Funktionsfreigabe für Flugoperationen.
