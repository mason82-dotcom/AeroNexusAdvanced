# DJI Live-Telemetrie-Cockpit (/status)

## Ziel und Geltungsbereich

Die bisherige Flotten-Statusseite ist als responsives Live-Cockpit für
Fluggeräte und Fernsteuerungen neu aufgebaut. Das Cockpit verwendet
**ausschließlich** `GET /api/v1/status/devices?limit=200` für geschützte
Telemetrie, `GET /api/v1/status/summary` für anonymisierte Zähler und
die bisherigen getrennten Lesedatenwege für lokale Cloud-Dienste und Waylines.
Es steuert keine Drohne, fragt keine fremden Dienste ab und benötigt keinen
neuen DJI-Account, kein Browser-Tokenfeld und keine weiteren MQTT-ACL-Rechte.

Die Oberfläche funktioniert ohne GIS-Kartenkacheln, Drittanbieter-CDNs,
Video-Livestream und angeschlossene Fluggeräte. Fehlende oder ungültige
Daten werden als fehlend angezeigt, **nie als null, 0 oder RTK-Fix erfunden**.

## Live-Cockpit

- Geräteselektor für Fluggeräte und RCs; Identität aus Provider, Projekt,
  Device-ID; Auswahl bleibt bei Aktualisierungen erhalten.
- Primärwerte für Akku, Flug-/RC-Modus, Startbezugshöhe,
  Horizontalgeschwindigkeit, RTK und OSD-Eingangsalter.
- Navigation: GPS (WGS84), Höhen, horizontale/vertikale Geschwindigkeiten,
  Satelliten, Positionsqualität, Kurs-/Roll-/Nickwinkel, Homepoint,
  Flugzeit/-strecke, Flugzustand.
- Energie: Akkusatz, Spannung und Temperatur, Ladezyklen, Firmware,
  Warnschwellen, Restflugzeit und Rückkehr-/Landereserve.
- RC: DRC-Status, getrennte SDR-/4G-Status und Qualitätscodes,
  Frequenzbänder, Cloud-Berechtigungsanzahl, Stream-/Linkkapazität.
- Kamera: dynamische Nutzlasten aus `cloud_details.cameras`, Aufnahmestatus,
  verbleibende Bilder/Videozeit, Zoom, Fokus-/Belichtungscodes, IR-Punkt-
  und IR-Bereichstemperaturen. Kein erfundener Live-Bild-/DRC-Kanal.
- Nutzlast/Gimbal: individuelle Index-Blöcke, Gimbalwinkel, Zoom,
  Firmware und datensparsame Steuerquelle.
- Sicherheit: Wind als DJI-Schätzwert, Höhen-/Gebietsgrenzzustand,
  Hindernissensoren, Nachtlichter, RTH-/Gang-/Firmwarestatus.
- HMS: sofern eine getrennte Quelle Meldungen lieferte; explizit als
  letzte abgerufene HMS-Daten ohne garantierte Ereigniszeit gekennzeichnet.
- Vollständige Einzel-Feld-Frische- und Kanaldarstellung (`osd`/`state`),
  sowie die vorhandene technische JSON-Tabelle und Cloud-Wayline-Metadaten
  als aufklappbare erweiterte Diagnose.

## Aktualisierung und Datensicherheit

Browser `GET /api/v1/status/devices` wird maximal alle 5 Sekunden
ausgelöst (oder in der vorhandenen engeren Konfiguration). In
Hintergrund-Tabs werden automatische Geräteabrufe ausgelassen. Die übrigen
Cloud-/Summary-/Wayline-Intervalle bleiben unverändert. Die Server-Frische-
grenze bleibt **separat** konfiguriert, standardmäßig 90 s. Ein 5-s-Polling
macht 90 Sekunden alte Quellwerte deshalb **nicht** neu.

Ein Wert wird nur als Livewert angezeigt, wenn (1) die geschützte
Geräte-API erfolgreich antwortete, (2) der Onlinezustand explizit
`true` ist, (3) die Gerätefrische `fresh` meldet, (4) das
OSD-Eingangsalter höchstens 15 Sekunden beträgt und (5) eine ggf.
vorhandene Einzel-Feld-Uhr ebenfalls `fresh` meldet und weder ihr
Quell- noch Empfangsalter 15 Sekunden überschreitet. Bei HTTP-Fehler,
Offline, Stale, fehlender oder unplausibler Uhr wird die Live-Anzeige
zurückgesetzt. Historische Werte bleiben ausschließlich im vorhandenen
technischen `last_known_telemetry`, eindeutig beschriftet. Nur vorhandene
Messwerte werden visualisiert; unbekannte DJI-Enums bleiben Codes.

Die Browser-Trends (max. 60 pro Messreihe) und die relative GNSS-Spur
(max. 120 Punkte) bleiben **flüchtig im RAM**; sie sind kein Flugschreiber.
OSD-Zeitstempel deduplizieren neue Messpunkte, nicht Browser-Refreshs.
Anomale Positionssprünge über 50 km starten eine neue relative Spur. Offline-/Stale- oder API-Ausfälle verwerfen
lokale Browser-Verläufe, um über Empfangslücken keine durchgehende
Flugspur zu suggerieren.
Keine Positions-/Seriennummern-, Token- oder DJI-Rohdaten verlassen über
neue Verbindungen den lokalen Browser.

## Abnahme / Deployment

Feature-Branch und PR zunächst ohne Pi-Deployment prüfen:

```bash
.venv/bin/python -m pytest -q tests/test_status_live_cockpit.py \
    tests/test_status_local_cloud.py tests/test_status_dashboard_cards.py \
    tests/test_status_mobile_library.py tests/test_frontend_javascript.py
.venv/bin/python -m pytest -q
```

Dann live auf dem Raspberry Pi 5 über das existierende verifizierte
HTTPS-LAN mit echter DJI Cloud-API-OSD-Quelle und RC Plus 2 prüfen:
Drohne aus/RC an; beide verbunden; kein GPS-Fix; Akku-/Funk-/RTK-Messungen;
OSD-Unterbrechung; `state` optional/nicht automatisch; alte/schadhafte
Quellzeit; Kameras im Standby/bei Aufnahme. Kein automatisches Deployment,
keine Veränderung von Pilot 2 oder systemd.

**Abgrenzung:** Das Cockpit zeigt alle **vom existierenden Backend
normalisierten** Felder und behält die vollständige technische Tabelle.
Es fügt keine noch nicht vorhandenen DJI-DRC-/HMS-Topics oder neue
Telemetrie in die Hardware ein. Cloud API 2 und FlightHub bleiben eigene
Datenwege. Fehlende reale RC-/Fluggeräteabnahme ist nicht mit
synthetischer CI-Abnahme gleichzusetzen.


## Persistenter HMS-Ereignisverlauf (main seit PR #65)

Die HMS-Anzeige kann zusätzlich **normalisierte Zustandsübergänge** aus dem
lokalen, privaten SQLite-Speicher darstellen. Die Funktion wurde mit
[PR #65](https://github.com/mason82-dotcom/AeroNexusAdvanced/pull/65)
auf GitHub gemergt; ihre produktive Verfügbarkeit hängt vom ausgerollten
Pi-Code ab.

- Historie von maximal 3.000 Übergängen in
  `~/.config/aeronexusadvanced/hms-history.sqlite3` (private Dateirechte).
- Gezählt werden u. a. Erscheinen, aus einem vollständigen HMS-Snapshot
  Verschwinden, Wiederauftreten und relevante Prioritätsänderungen.
  Identische aufeinanderfolgende Snapshots erzeugen keine Ereignisflut.
- Geschützter, paginierter GET-Zugriff:
  `/api/v1/status/hms-history`. Die Anzeige markiert
  **Pi-Empfangszeiten**; das sind nicht automatisch DJI-Ereigniszeiten.
- „Nicht mehr gemeldet“ ist **kein Nachweis**, dass ein technischer
  Defekt sicher behoben wurde. Ein wieder erschienener Code ist ein
  eigener Zustandswechsel.
- Es entstehen keine zusätzlichen MQTT-Schreibrechte, Flugbefehle,
  Rohdaten-Dumps oder öffentlich zugänglichen Gerätekennungen.

Die separaten [HMS-Code- und Übersetzungsregeln](dji-cloudapi-hms.md)
gelten weiterhin. Die Chronik ist nicht identisch mit dem
Frischeindikator des OSD-Datenstroms.

