# Produktive, schreibgeschützte UI-/API-Abnahme

**Voraussetzung:** bereits laufende Pi-Installation mit \`AERONEXUS_LAN_HOST\`
oder \`AERONEXUS_BIND\`, \`AERONEXUS_PORT\`, \`config/pki/ca.crt\` und
bestehender \`.env\`. Der Test kann aus einem **anderen Git-Worktree** laufen
und liest die Konfiguration ausschließlich aus der bestehenden Installation.
Die \`.env\` wird mit \`dotenv_values\` gelesen, nicht als Shell-Skript ausgeführt.

~~~bash
cd ~/Projekte/AeroNexusAdvanced-all-ui-acceptance
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  "$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python" \
  scripts/pi/production_ui_readonly_audit.py \
  --instance-dir "$HOME/Projekte/AeroNexusAdvanced" \
  --sample-media
~~~

**Eigenschaften:**
- Strikte TLS-/CA-Zertifikatsprüfung; kein \`verify=False\` oder \`curl -k\`.
- Keine Weiterleitungen, keine Proxy-Nutzung; ausschließlich vordefinierte
  \`GET\`-Pfade. Derselbe verifizierte Pi-Host wird für alle Anfragen verwendet.
- Bereits bestehender LAN-No-Token- oder Viewer-Bearer-Modus, ohne Token-Ausgabe.
- Acht HTML- und Health-Prüfungen; strukturierte Lesezugriffe auf reale lokale
  Status-, Missions-, Medien-, Flotten-, Cloud-, DJI-, Thermal-, Multispektral-
  und Raster-APIs.
- Fehlende optionale Komponenten werden **SKIP** (HTTP 404, 501, 503) statt
  einer fälschlichen Erfolgsbehauptung. Authentifizierungs- und
  Strukturfehler sind **FAIL**.
- Obergrenzen für HTTP-Response-Größen und -Zeit; keine Response-Bodies,
  Geräte-SNs, GPS-Koordinaten, Dateinamen oder Token im Terminal.
- \`--sample-media\` liest höchstens 24 Bytes einer kleinen, im Index
  als Browser-Vorschau ausgewiesenen JPEG/PNG/WebP-Datei; die Signatur wird
  geprüft. Ohne geeignetes Bild wird \`SKIP\` gemeldet. **Kein** Download,
  kein vollständiges Dekodieren und keine echte Browser-Medienanzeige.

**Nicht abgedeckt:** tatsächliche Map-Tile-Provider, privates DJI-Pilot-2-
Flugverhalten, WHEP/WebRTC-Livevideo, positive Thermal-Analyse, Map-Rendering,
Raster-Tile-Berechnung, Medienanzeige im Nutzerbrowser und vollständige
visuelle Mobil-Usability-Abnahme über das echte HTTPS-Frontend.

Kein Systemd-Neustart, kein Git-Update an der Installation und keine
Schreiboperation. Tests sind bewusst rein informativ und diagnostisch.

## Verbesserung der zwei SKIPs aus der Pi-Abnahme

`photo_map` prüft `GET /api/v1/photos/map?limit=10` statt einer
potenziell über 1 MiB großen Gesamtkartenantwort. Voraussetzung ist
ein AeroNexus-Server mit dem neuen optionalen `limit`-Parameter; bis
zur kontrollierten Installation dieses Backend-Updates kann der alte
Server weiter die vollständige Karte liefern und die Prüfung bleibt
`SKIP`.

`--sample-media` akzeptiert indexierte Browser-Vorschauen bis zur
serverseitigen 32-MiB-Grenze, liest aber weiterhin **höchstens 24 Bytes**
des HTTP-Responses. Wenn unter den neuesten zehn Objekten kein Kandidat
liegt, erfolgen bis zu vier zusätzliche begrenzte Suchabfragen nach
JPEG/PNG/WebP-Endungen (je 100 Metadatensätze). Sind keine geeigneten
Bilder im Index, bleibt die Prüfung korrekt `SKIP`.

Kein Download auf Festplatte. Ein positiver Header-Test ist keine
vollständige Bilddekodierung im Browser.
