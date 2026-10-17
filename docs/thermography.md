# Thermografie-Modul (`/thermal`)

Stand: 17.10.2026 · Branch `feature/thermography-tsdk-20261017`

Eigener Web-UI-Tab für radiometrische DJI-Wärmebilder (R-JPEG, `*_T.JPG`)
aus dem schreibgeschützten MinIO-Medienindex (Phase 21). Temperaturen
berechnet ausschließlich das **DJI Thermal SDK** (TSDK v1.8, `dji_irp
measure`, float32). Ohne SDK zeigt der Tab nur Vorschau und Metadaten; aus
Sensor-Rohwerten wird **keine** Temperatur geschätzt (eine einfache
Rohwert-Formel lag beim Test um etwa 4 K neben dem SDK).

## Funktionen

- Liste aller Wärmebilder im Index mit Suche (Dateiname/Datum), Paginierung
  und automatischer Zuordnung des Sichtbilds (`_V`/`_W`/`_Z`, gleicher
  Ordner oder eindeutiger Dateiname bei SD-Importen).
- Falschfarbendarstellung des SDK-Temperaturrasters im Browser: Paletten
  Iron, Rainbow, White/Black hot, Arctic, Lava; Bereich Min–Max, P5–P95
  oder manuell; Isotherme; Hot-/Coldspot-Marker; Farbskala.
- Messwerkzeuge: Punkt (Klick) und Bereich (Ziehen; Min/Max/Mittel),
  Temperaturanzeige unter dem Mauszeiger.
- Messparameter: Emissionsgrad (mit Material-Richtwerten), Distanz,
  Luftfeuchte, reflektierte Temperatur, Umgebungstemperatur. Leere Felder =
  in der Aufnahme gespeicherte Werte. Bereiche wie `dji_irp` v1.8.
- Metadaten (XMP-Whitelist): Modell, Aufnahmezeit, Position, Höhen,
  Gimbal, Laser-Distanz. **Nicht** ausgegeben: Drohnen-/Kamera-Seriennummern,
  NTRIP-Host/Mountpoint, unbekannte Herstellerfelder.
- Export: PNG (mit Markern), Messungen als CSV, komplettes Temperaturraster
  als CSV, JSON-Bericht.

## API (Viewer-Zugriff wie Mission Studio: LAN-Modus oder Dashboard-Token)

| Route | Inhalt |
|---|---|
| `GET /thermal` | Web-UI-Tab |
| `GET /api/v1/thermal/status` | SDK-Bereitschaft, Anzahl Wärmebilder |
| `GET /api/v1/thermal/images?q=&limit=&offset=` | Wärmebildliste mit `visual_id` |
| `GET /api/v1/thermal/images/{id}/analysis?emissivity=…` | Metadaten + Statistik |
| `GET /api/v1/thermal/images/{id}/temperatures?…` | float32-LE-Raster, `X-Thermal-Width/Height` |

Sicherheitsgrenzen: nur indizierte opaque IDs, Abgleich von Größe und ETag
vor jedem Lesen (409 bei Änderung), max. 16 MiB pro Bild, SDK als separater
Prozess mit minimaler Umgebung (keine `AERONEXUS_*`-Variablen), Zeitlimit
90 s, ein Lauf gleichzeitig, Ausgabegröße und Wertebereich geprüft. Kein
Schreibzugriff auf MinIO oder DJI. Bis zu 6 Messungen im Speicher-Cache.

## Installation des DJI Thermal SDK auf dem Pi 5

DJI liefert Linux nur für x86/x64. Auf dem Pi 5 (ARM64, 16-KiB-Seiten) kann
qemu-user die SDK-Bibliotheken nicht laden; **Box64** kann es. Debian-Box64
kapselt `libstdc++`/`libgcc_s`/`libgomp` nicht, daher werden deren
x86_64-Versionen privat mitgeliefert.

```bash
deploy/pi/install-thermal-sdk.sh ~/Downloads/dji_thermal_sdk_v1.8_20250829.zip
```

Das Skript arbeitet ohne root und außerhalb des Repositorys:

- SDK → `~/.local/opt/dji-tsdk/bin` (DJI-Lizenz, nie committen),
- `box64` per `apt-get download` aus den signierten APT-Quellen,
- x86_64 `libstdc++6`, `libgcc-s1`, `libgomp1` von deb.debian.org, geprüft
  gegen die `InRelease`-Signatur (gpgv + debian-archive-keyring) und SHA256,
  → `~/.local/opt/aeronexus-box64`,
- Rauchtest `dji_irp -V`, danach die `.env`-Zeilen (`AERONEXUS_DJI_TSDK_*`,
  `AERONEXUS_BOX64*`) setzen und den Dienst neu starten.

## Live-Abnahme auf dem Pi (17.10.2026)

- `GET /api/v1/thermal/status`: SDK `V1.7` (TSDK v1.8), Runner `box64`,
  **2.072** Wärmebilder im Index.
- M3T-R-JPEG 640×512: SDK-Messung 8,6–15,4 °C (Median 11,1 °C), ca. 0,8 s
  pro Bild (Box64), gecacht 2 ms; Emissionsgrad-Override wirkt.
- M4T-Aufnahme (1280×1024-Vorschau, Raster 640×512): 21,5–22,8 °C.
- Temperaturraster per HTTPS: 1.310.720 Byte, 640×512.
- Browser-UI: JavaScript per Node geprüft; manuelle Prüfung in Chrome/Android
  steht noch aus.

## Karte der Wärmebilder (Ansicht „Karte“)

- Privater Geo-Index `thermal_geo.sqlite3` (0600, Workspace) mit
  Whitelist-XMP je Wärmebild. Aufbau ausdrücklich auf dem Pi:
  `.venv/bin/python -m aeronexus.thermal_geo` – liest per HTTP-Range nur die
  ersten 256 KiB je Objekt, überspringt unveränderte ETags, entfernt Einträge,
  die nicht mehr im Medienindex sind. Erstscan: 2.072 Bilder in ca. 51 s.
- Karte (Leaflet, Satellit/OSM): Aufnahmepunkte, Tooltip mit Höhe, Pitch und
  Bodenauflösung; Klick öffnet das Bild. Ab Zoom 17 Bodenabdeckung
  (Footprint) aller Nadir-Aufnahmen (Pitch −75…−105°), das gewählte Bild
  hervorgehoben.
- Footprint/Bodenauflösung aus relativer Höhe, Gimbal-Yaw/-Pitch und
  diagonalem Sichtfeld laut DJI-Datenblatt (M3T/M30T IR 61°, M4T IR 45°;
  Weitwinkel 84° bzw. 82°). Annahme: ebenes Gelände auf Startpunkthöhe –
  Planungshilfe, keine Orthorektifizierung.
- `GET /api/v1/thermal/map`: Positionen, Footprints (ohne Objektschlüssel).

## Overlay Wärmebild/Sichtbild (Ansicht „Overlay“)

- Das zugehörige Sichtbild (`_V`/`_W`) wird auf den Ausschnitt des
  IR-Sichtfelds zugeschnitten (Verhältnis der Sichtfelder) und unter das
  Wärmebild gelegt; Regler für Deckkraft, Skalierung (±30 %) und Versatz
  gleichen die Parallaxe zwischen den Kameras aus.
- Geprüft mit einer echten M3T-Aufnahme (44 m, Nadir): Kanten des Sichtbilds
  liegen ohne Korrektur auf den Straßenrändern im Wärmebild.

## PV-Inspektion (Orientierung an IEC TS 62446-3)

- Werkzeug „PV-Bereich“: Rechteck um die Module. Referenz = Median des
  Bereichs; Anomalien = zusammenhängende Flächen (4er-Nachbarschaft) ≥
  Referenz + Erkennungsschwelle (Standard 3 K, min. 4 Pixel).
- ΔT-Klassen (einstellbar, Standard < 10 K / 10–20 K / ≥ 20 K): verbreitete
  Praxis-Auslegung; **nicht** aus dem Normtext verifiziert (kostenpflichtig).
  Vor Verwendung gegen IEC TS 62446-3:2017 und Prüfauftrag abgleichen. Die
  Einstufung (Fehlerbild, Klasse) trifft ein qualifizierter Thermograf;
  Musterangaben (Hotspot, Einzelzelle, Zellstreifen, großflächig) sind
  geometrische Hinweise aus Zellgröße und Bodenauflösung.
- Prüfliste Messbedingungen: Einstrahlung ≥ 600 W/m², Wind ≤ 28 km/h,
  Bewölkung ≤ 2/8, Blickwinkel zur Modulnormalen ≤ 30° (aus Gimbal und
  Modulneigung/-ausrichtung), ≥ 5 px je Zellkante, Emissionsgrad gesetzt
  (Modulglas ca. 0,85), radiometrische Daten. Eingaben, die nicht aus dem
  Bild ableitbar sind (Einstrahlung, Wind, Bewölkung), trägt der Prüfer ein.
- Plausibilitätswarnungen: gesamtes Bild statt PV-Bereich, > 15 % auffällige
  Fläche (Nicht-PV-Flächen im Bereich), < 3 px je Zellkante.
- Export: PV-Bericht (JSON) und Anomalienliste (CSV).
- `GET /api/v1/thermal/images/{id}/pv?x&y&w&h&detect_k&class2_k&class3_k&min_pixels&cell_size_m&irradiance&wind&cloud&tilt&azimuth&emissivity…`
- Hinweis zu den vorhandenen Daten: Die geprüften M3T-Aufnahmen zeigen
  Straße, Bahn und Felder, keine PV-Anlage. Eine fachliche Abnahme mit
  echten PV-Aufnahmen (Einstrahlung ≥ 600 W/m², ≤ ca. 17 m Flughöhe für
  5 px/Zelle mit M3T) steht aus.

## Offene Punkte / Vorschläge

- Batch-PV-Analyse ganzer Flüge mit Anomalienkarte und Persistenz der
  Ergebnisse im privaten Workspace.
- Automatische Modulerkennung statt manuellem PV-Bereich.
- Geo-Index regelmäßig per `systemd --user`-Timer aktualisieren.
- Gerenderte Wärmebilder als georeferenzierte Kacheln auf der Karte.
