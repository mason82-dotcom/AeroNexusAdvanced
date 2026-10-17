# Optionale GeoSense-/Metashape-Anbindung

Die Multispektral-Seite kann ausgewählte Mavic-3M-Aufnahmen als Arbeitsauftrag
für einen separaten Metashape-Rechner exportieren. Der Pi braucht dafür weder
Metashape noch eine Metashape-Lizenz. Er liest ausschließlich Originale aus dem
vorhandenen MinIO-Index und erstellt lokale ZIP-Arbeitskopien.

## Voraussetzungen und Grenzen

- Ein geeigneter Arbeitsrechner mit dem separat installierten Metashape-Python-Modul
  und aktivierter **Metashape Professional**-Lizenz; eine reine Demo erlaubt
  keinen vollständigen Speicher-/Exportworkflow. Installation und Aktivierung:
  <https://agisoft.freshdesk.com/support/solutions/articles/31000148930-how-to-install-metashape-stand-alone-python-module>.
- Die Python-Version muss zum installierten Agisoft-Modul passen. Die
  Verarbeitung benötigt wesentlich mehr RAM/GPU-Leistung als die Pi-Weboberfläche:
  <https://www.agisoft.com/downloads/system-requirements/>.
- Zusätzlich braucht der Worker PyYAML für den externen GeoSense-Code.
  Auf dem Pi entstehen keine zusätzlichen Python-Abhängigkeiten.
- Mindestens drei **überlappende Aufnahmen derselben Flugserie**. Drei Bilder
  allein garantieren keine Ausrichtung, Georeferenz oder Rekonstruktion.
  Innenaufnahmen und voneinander unabhängige Bodenfotos bilden keine geeignete
  Luftbildserie. Der Worker verwirft einen Kanal mit weniger als drei
  ausgerichteten oder ohne georeferenzierten Kameras.
- RGB erstellt ein Orthomosaik aus den zugeordneten `_D.JPG`-Originalen.
  Der Modus „MS-Rohbandmosaike“ erstellt vier unabhängige Mosaike aus Original-DN.
  Er enthält **keine Reflexionskalibrierung** und garantiert keine pixelgleiche
  Registrierung der vier Mosaike. Daraus wird keine NDVI-Karte berechnet.
- Geometrie und Radiometrie benötigen eine fachliche Abnahme an echten Daten.
  R-JPEG-Temperaturen werden in diesem Workflow nicht verarbeitet.
- Der Upstream exportiert gekachelte GeoTIFFs mit Übersichten. Das ist ohne
  zusätzliche Prüfung **keine bestätigte COG-Konformität**. Eine automatische
  Übernahme in einen Rasterkatalog oder Kartenviewer erfolgt hier nicht.

## Bedienung auf dem Pi

1. `/multispectral` öffnen und mit den Kontrollkästchen links 3–100 Aufnahmen
   derselben Flugserie markieren.
2. „Orthomosaik mit Metashape“ aufklappen und „RGB-Orthomosaik“ oder „MS-Rohbandmosaike“ wählen.
3. „Paket vorbereiten“ klicken. Download erfolgt anschließend über einen
   normalen, authentifizierten Dateilink; ein großes ZIP wird nicht als Browser-Blob
   in den Arbeitsspeicher des Smartphones geladen.
4. ZIP herunterladen, vollständig auf dem Arbeitsrechner entpacken und dessen
   `README.txt` befolgen. „Pakete aktualisieren“ stellt fertige Downloads nach
   einer unterbrochenen Anfrage oder einem Neuladen wieder her.
5. Nicht mehr benötigte lokale ZIP-Pakete über „Paket löschen“ entfernen.
   Das betrifft ausschließlich die erzeugte Arbeitskopie.

Begrenzungen: höchstens 100 Aufnahmen, 64 MiB pro Original und 4 GiB Originaldaten
pro Paket; 256 MiB freier Speicher müssen darüber hinaus verbleiben. Es werden
höchstens drei Pakete gleichzeitig aufbewahrt. Pakete sind eine Stunde abrufbar;
abgelaufene Pakete werden beim nächsten Vorbereiten entfernt. Diese Bereinigung
ist kein separat laufender Timer. Gleichzeitige Vorbereitung wird innerhalb eines
Serverprozesses verhindert. Die normale Pi-Installation verwendet einen Prozess.

Paketordner liegen unter `AERONEXUS_WORKSPACE_DIR/metashape_exports` (bzw. dem
standardmäßigen privaten Workspace). Verzeichnisse sind 0700, Archive 0600.
Manifest und API enthalten weder MinIO-Schlüssel noch MinIO-Zugangsdaten.
Die Originaldateien im Archiv enthalten weiterhin ihre originalen EXIF/XMP-Daten
(einschließlich etwaiger Positionen/Seriennummern).

## Worker vorbereiten und ausführen

Das GeoSense-Projekt wird getrennt installiert und nicht ins AeroNexus-Repository
kopiert oder automatisch nachgeladen. Verwendeter Stand:

- <https://github.com/GeoSense-Freiburg/metashape_ortho>
- Commit `101bc4e235982b34b3607eb035d84cc2448491ea` vom 04.12.2025.

Auf dem Arbeitsrechner in der passenden Metashape-Python-Umgebung:

```bash
git -c core.autocrlf=false clone https://github.com/GeoSense-Freiburg/metashape_ortho.git
git -C metashape_ortho checkout 101bc4e235982b34b3607eb035d84cc2448491ea
python -m pip install PyYAML
```

Im entpackten AeroNexus-Auftrag zunächst nur prüfen:

```bash
python worker.py --upstream /absoluter/pfad/metashape_ortho --gpu cpu
```

Erst `--run` startet eine Rekonstruktion:

```bash
python worker.py --upstream /absoluter/pfad/metashape_ortho --gpu 0 --run
```

Windows akzeptiert entsprechend einen Windows-Pfad. GPU-Optionen sind `cpu`,
`0`, `1` und `all`; die tatsächlich vorhandenen Geräte werden geprüft. CPU bleibt
aktiviert. Der Worker verändert keine CUDA-Umgebungsvariablen.

Ergebnisse liegen im neu angelegten `results`-Unterordner: Metashape-Projekte,
GeoTIFFs, `worker.log` und `results.json` mit Status und Ausgabe-Prüfsummen.
Vorhandene Ergebnisordner werden nicht überschrieben. Für einen weiteren Versuch
einen neuen Namen verwenden, zum Beispiel `--output results-retry`.

`results.json` unterscheidet `completed` und `failed`. Ein unvollständiger Lauf
ist kein erfolgreicher Auftrag, auch wenn bereits einzelne TIFFs existieren.
Die Berichtsfelder `radiometry` und `cog_validated: false` bleiben explizit.

## Was aus dem Upstream verwendet wird

Der mitgelieferte, eigenständig geschriebene `worker.py` verifiziert vor der
Verwendung die Git-Blob-Prüfsummen von `pipeline/utils.py` und
`pipeline/metashape_processor.py`. Danach lädt er die verifizierten Quellen direkt,
ohne fremde `__init__.py` oder `.pyc`-Caches auszuführen. Für die Verarbeitung nutzt
er `MetashapeProject.add_chunk` und `MetashapeChunkProcessor`:
Ausrichtung, Depth Maps, Modell, Punktwolke, Glättung, Orthomosaik und Rasterexport.

`main.py`, `process_folders` und der Upstream-Speicherhelfer werden nicht aufgerufen:
Sie enthalten unter anderem eine feste Speicherprüfung auf `/mnt/data`, interaktive
Abfragen, Umbenennen/Verschieben von Eingaben, pauschale Fehlerunterdrückung und das
Löschen von Lockdateien. Dokumente werden stattdessen direkt in neue Ergebnisdateien
gespeichert. Der Adapter behauptet keine Kompatibilität mit beliebigen anderen
Upstream-Versionen; ein Quellwechsel benötigt neue Prüfung und Tests.

## Alternative CLI auf dem Pi

Aufnahmen auflisten:

```bash
.venv/bin/python -m aeronexus.metashape_bridge list
```

Ausgewählte UUIDs als neues ZIP exportieren (Platzhalter ersetzen):

```bash
.venv/bin/python -m aeronexus.metashape_bridge prepare \
  --capture UUID1 --capture UUID2 --capture UUID3 \
  --mode rgb --output /pfad/zu/neuem-aeronexus-metashape.zip
```

Die CLI überschreibt keine vorhandene Ausgabedatei. Nach erfolgreichem Kopieren
entfernt sie das temporäre Serverpaket. Medien werden weder hochgeladen noch
umbenannt, verschoben oder gelöscht.

## API und Validierung

Alle Endpunkte verwenden denselben Viewer-/LAN-Zugriff wie der Multispektralbereich.
Es gibt keinen HTTP-Endpunkt zum Starten von Programmen oder einer Rekonstruktion.

| Methode und Route | Funktion |
|---|---|
| `GET /api/v1/multispectral/metashape/packages` | Abrufbare Pakete |
| `POST /api/v1/multispectral/metashape/packages` | `{capture_uuids: [...], mode: "rgb"}` oder `multispectral` |
| `GET /api/v1/multispectral/metashape/packages/{id}/file` | ZIP herunterladen |
| `DELETE /api/v1/multispectral/metashape/packages/{id}` | Lokales ZIP-Paket löschen |

ETag/Größe und Capture-/Bandzuordnung werden vor der Aufnahme ins ZIP geprüft.
Dateinamen werden ausschließlich aus validierten UUIDs und festen Kanälen erzeugt.
Der Worker prüft danach Dateiliste, Symlinks, Größen und SHA-256 jedes Originals.

Die automatisierten Tests verwenden synthetische Bilder und Metashape-Testdoubles.
Sie prüfen Datenintegrität, API-Zugriff, Grenzen, Ablauf, Worker-Aufrufreihenfolge,
Lizenz-/GPU-Prüfung, Fehlerstatus und Erhalt der Eingaben. Eine echte lizenzierte
Metashape-Rekonstruktion gehört zur noch ausstehenden Abnahme auf dem Arbeitsrechner.
