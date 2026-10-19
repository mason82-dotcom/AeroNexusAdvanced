# AeroNexus-Cockpit

Die Bedienoberfläche orientiert sich am Arbeitsbereichskonzept von
[OpenDroneKit](https://github.com/00PrabalK00/OpenDroneKit). Die Umsetzung ist
eigenständig: es werden weder Quellcode noch Logos oder Desktop-Abhängigkeiten
übernommen. Referenzstand: `1ef6351ba387aaace7e6907d10babc6feb2351d3`.

## Bedienung

Direkter Einstieg: **https://PI-IP:8000/studio**. Im Control-Portal auf Port 8085
führt „Missionen planen“ zu derselben Oberfläche. Die Pilot-2-Anmeldung ist ein
eigener Zugang und wird für den Mission Manager nicht verwendet.

- Links: lokalen Entwurf oder Cloud-Route auswählen und laden; Wegpunkte,
  Speichern, Rückgängig, Import und Export.
- Mitte: Karte und Routenvorschau; Kartenfokus erweitert die Arbeitsfläche.
- Rechts: Fluggerät, Höhe, Geschwindigkeit, Start/Rückkehr, Routenanalyse und
  die Bearbeitung des ausgewählten Wegpunkts.
- Unten: tatsächlicher Lade-/Fehlerstatus des Missionsspeichers. Das ist keine
  Bestätigung einer Drohnenverbindung.

Eine Cloud-Vorschau zeigt ihren schreibgeschützten Kontext und blendet die
Felder des zurückgehaltenen lokalen Entwurfs aus. Nach Rückkehr zum lokalen
Entwurf sind die bisherigen Eingaben wieder verfügbar. Quellenprobleme bleiben
im Mission Manager sichtbar. Die theoretische Flugzeit ist keine Flugfreigabe.

Ab 1001px stehen drei Spalten nebeneinander. Auf Tablets teilen sich Bestand
und Einstellungen die linke Spalte mit eigenen Scrollbereichen. Auf Smartphones
stehen die Bereiche untereinander; der Kartenfokus bleibt erreichbar.

## Umfang und Prüfung

Gemeinsame Navigation und Gestaltung gelten auch für Live-Status, Übersicht,
Medien, Thermal, Multispektral und Ergebnisraster. Es werden ausschließlich
vorhandene AeroNexus-Funktionen angeboten. Es gibt keine OpenDroneKit-Demodaten,
zusätzliche Flugbefehle oder Lizenz-/Bridge-Abhängigkeit von OpenDroneKit.

Regression: `tests/test_ui_navigation.py` prüft mit verfügbarem Playwright-
Chromium die Panelanordnung, Werterhalt, Werkzeugwechsel, Cloud-Kontext,
Tastaturbedienung und Fehleranzeige bei 390/760/1440px. Der vollständige
[Studio-Smoke](studio-full-ui-acceptance.md) verwendet synthetische GET-Antworten.
Dies ersetzt keine Bedienprüfung mit produktiven Pi-Routen.
