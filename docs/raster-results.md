# GeoTIFF-/COG-Ergebniskatalog

Die Seite `/results` zeigt fertige, lokal vorhandene GeoTIFFs und Cloud Optimized
GeoTIFFs als Web-Mercator-Kacheln. Sie erzeugt weder Orthomosaike noch kalibrierte
Reflexionsdaten. NDVI, GNDVI, NDRE, LCI, DSM und DTM werden anhand einzelner Wörter
im Dateinamen als Produkttyp vorgeschlagen; das ist keine Inhaltsprüfung.

## Auf dem Pi einrichten

Im Projektverzeichnis mit der vorhandenen virtuellen Umgebung installieren:

```bash
cd ~/Projekte/AeroNexusAdvanced
.venv/bin/python -m pip install -e '.[test,mqtt,minio,multispectral,raster]'
.venv/bin/python -m pip check
mkdir -p ~/.local/share/aeronexusadvanced/results
```

Fertige `.tif`-/`.tiff`-Dateien direkt in diesen Ordner kopieren. Unterordner und
Datei-Symlinks werden nicht verfolgt. Bei anderem `AERONEXUS_WORKSPACE_DIR` liegt
auch der Standard-Ergebnisordner dort unter `results/`.

Alternativ in der bereits verwendeten privaten Dienst-Konfiguration
`AERONEXUS_RESULTS_DIR=/absoluter/pfad/zu/ergebnissen` setzen. Das Verzeichnis muss
für den Dienstbenutzer lesbar sein. Danach den bestehenden Dienst neu starten:

```bash
systemctl --user restart aeronexusadvanced
systemctl --user is-active aeronexusadvanced
```

`/results` im vorhandenen HTTPS-LAN-Auftritt öffnen und **Ordner einlesen** wählen.
**Aktualisieren** lädt nur den bestehenden Katalog. **Ordner einlesen** ersetzt
seinen Inhalt durch die aktuell gültigen Dateien; abgelehnte Dateien erscheinen
im Scanbericht und werden aus dem Katalog entfernt. Quelldateien bleiben erhalten.
Ein fehlender Ordner oder mehr als 500 Kandidaten lässt den bisherigen Katalog
unverändert. Ein Scan liest Metadaten; Stichproben und Kacheln entstehen erst bei
Auswahl. Die Katalogdatei `raster-results.sqlite3` liegt privat (0600) im Workspace.

Ein Scan ist auch per CLI möglich (dieselben Umgebungsvariablen exportieren):

```bash
.venv/bin/python -m aeronexus.raster_results
```

## Darstellung und Grenzen

- Bandwahl sowie RGB nur bei ausdrücklich markierten Rot-/Grün-/Blau-Farbbändern.
  RGB beginnt mit dem Anzeigebereich 0–255; bei 16-Bit-Daten Grenzen passend setzen.
- Gespeicherter Bandfaktor und Offset werden auf die Werte angewendet.
- Index-Dateinamen starten mit −1 bis 1. Andere Einzelbänder starten mit einem
  ungefähren P2–P98-Kontrast aus höchstens 256 × 256 Stichproben. Dieser Kontrast
  verändert keine Messwerte. Bei konstanten Stichproben wird nur der Anzeigebereich
  erweitert; die Perzentilwerte bleiben unverändert. Extremwerte können visuell abgeschnitten erscheinen.
- NoData, interne Masken, Alpha und nicht endliche Werte sind transparent.
  Gültige Nullwerte bleiben sichtbar. Externe `.msk`, `.ovr` und `.aux.xml`-Dateien
  werden absichtlich nicht eingelesen: Masken und Übersichten intern bereitstellen.
- Eine COG-Kennzeichnung stammt aus GDAL-Metadaten und ersetzt keinen vollständigen
  Konformitätstest. Gewöhnliche GeoTIFFs funktionieren ebenfalls. Große Dateien
  benötigen interne Kacheln und Übersichten für zügige kleine Zoomstufen.
- Erforderlich: deklarierter CRS und affine Georeferenzierung. GCP/RPC, komplexe
  Bänder, mehr als 16 Bänder, Dimensionen über 500.000 Pixel, Blöcke über 64 MiB,
  Dateien über 64 GiB sowie Raster über Antimeridian/Polargebiete werden abgelehnt.
- Kein Hintergrundkartenanbieter. Leaflet 1.9.4 wird wie in den bestehenden
  Kartenansichten per CDN mit Integritätsprüfung geladen; dafür ist Internet nötig.
  Ohne Leaflet bleibt der Katalog mit Metadaten nutzbar.
- Kein Remote-URL-Import, kein GeoTIFF-Upload und keine automatische COG-Konvertierung.
  Kartenhöhe und DSM-Werte werden nicht als Flugweg-Höhen übernommen.

## API und Betrieb

Alle Datenrouten verwenden denselben LAN-/Bearer-Zugriffsschutz wie die vorhandenen
Medienansichten; im LAN-Modus werden fremde Ursprünge abgewiesen.

| Methode | Route | Zweck |
|---|---|---|
| GET | `/api/v1/results?q=&limit=50&offset=0` | Katalog, bis 100 Einträge je Seite |
| POST | `/api/v1/results/scan` | Lokalen Ordner neu einlesen |
| GET | `/api/v1/results/{id}` | Metadaten |
| GET | `/api/v1/results/{id}/statistics?band=1&v=…` | Ungefähre Bandstatistik |
| GET | `/api/v1/results/{id}/tiles/{z}/{x}/{y}.png` | 256×256-PNG, Zoom 0–22 |

Tile-Parameter: `band`, `mode=scalar|rgb`, `palette=viridis|gray|rdylgn|terrain`,
`low`, `high`, `v` (Katalogversion). Unter- und Obergrenze müssen endlich sein,
Betrag höchstens 10¹⁵, Obergrenze größer als Untergrenze. Metadaten enthalten
keine absoluten Quellpfade. APIs akzeptieren keine vom Browser angegebenen Pfade.

Die Version prüft Dateisystemidentität, Größe und Änderungszeiten, keinen
kryptografischen Inhalts-Hash. Geänderte Dateien liefern HTTP 409, entfernte
HTTP 404. Dann Ordner neu einlesen und Datei erneut auswählen. Vor einem Treffer
im serverseitigen Cache wird die Quelldateiversion erneut geprüft. Browserantworten
werden nicht gespeichert. PNG-Cache: höchstens 128 Kacheln und 16 MiB je Prozess;
Statistikcache: 64 Einträge. Zwei parallele Rasterberechnungen, 32 MiB GDAL-Cache
und 32 MiB Warp-Arbeitsspeicher begrenzen die Arbeit; dies ist keine harte
Obergrenze des gesamten Prozessspeichers. Ohne Raster-Extra bleibt der übrige
Gateway verfügbar, der Katalog meldet die fehlende Rasterunterstützung.

## Prüfung

Tests erzeugen echte WGS84-/UTM-GeoTIFFs und COGs und prüfen unter anderem Masken,
Nullwerte, NaN, RGB, Bandskalierung, Grenzen, Quelländerungen, Katalogrechte,
API-Zugriffsschutz und verzögerte JavaScript-Antworten. Die CI installiert das
Raster-Extra für Python 3.12 und 3.13. Ein visueller Browser- und Performance-Test
mit den tatsächlichen Ergebnisdateien auf dem Pi steht separat an.
