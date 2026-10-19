# AeroNexusAdvanced – kompakter Operations-Arbeitsbereich

## Ziel

Die bestehende deutschsprachige Arbeitsoberfläche auf dem Raspberry Pi erhält
mehr nutzbare Arbeitsfläche. Flug- und Quelldaten werden nicht umgedeutet.
Die Änderung ist **präsentationsbezogen**; sie ist keine Base44-Backend-Migration.

## Umgesetzt

- Gemeinsame, schmale Navigation und reduzierte Header-Höhen für alle sieben
  fachlichen HTTPS-Seiten: Live-Status, Mission Studio, Operations, Medien,
  Thermal, Multispektral und Ergebnisraster.
- Live-Cockpit: kompaktere Flottenkennzahlen, OSD-Gauges, Karten-/
  Diagrammflächen, Gerätekarten, HMS- und Diagnoseelemente.
- Operations: engere Listen, KPI- und Cockpitkarten ohne andere Datenabfragen.
- Mission Studio: dichtere Formulare, Routen- und Werkzeugbereiche; die
  eigenständige 3-Spalten-Architektur (Bestand, Karte, Inspektor) bleibt erhalten.
- Medien, Thermal, Multispektral, Ergebnisraster: engere Panels, Filter und Listen.
- Separates Control-Portal unter Port 8085: schmalere Seitenleiste,
  kompaktere Funktionskarten und geringere Abstände.

## Unverändert

Keine neuen Flugbefehle, keine DJI-Sitzungsänderung, kein schreibender MQTT-Zugriff,
keine neuen Tokens, kein automatischer Mission-Upload. Die vorhandenen FastAPI-
Endpunkte, Status-Freshness, Gerätewerte, MinIO-Daten und Datenbanken bleiben
unverändert. Mangelnde oder veraltete Telemetrie muss weiter klar erkennbar sein.

Base44 ist eine **separate Designvorschau**. Diese GitHub-Änderungen betreffen
die vorhandenen Python-/HTML-Renderfunktionen und die optionale Port-8085-Seite,
nicht die Cloud-App.

## Abnahme vor einem Pi-Rollout

1. GitHub-Tests prüfen, insbesondere `tests/test_ui_navigation.py`,
   `tests/test_compact_ui.py`, `tests/test_status_live_cockpit.py` und
   `tests/test_control_portal.py`.
2. Browserprüfungen bei 390, 760, 1024 und 1440 Pixel Breite:
   kein horizontaler Seitenscroll, Navigation vollständig, Karte nutzbar,
   Inspector sichtbar, Statuswarnungen lesbar, Modal- und Keyboard-Fokus erhalten.
3. Livebetrieb: ausschließlich GET-basierte Zustandsprüfung, Fresh/Last-Known/
   Stale getrennt ausweisen; nicht aus UI-Elementen auf realen Flugstatus schließen.
4. Pi-Version, lokalen Git-Status und systemd-Service vor jeder Installation
   dokumentieren. Keine produktiven Volumes, TLS-Keys, MinIO-Buckets oder
   Cloud-Server-Betriebsverzeichnisse ersetzen.

Die Abnahme auf dem Raspberry Pi und Android ist in diesem Pull Request
**nicht durchgeführt**. Das Zusammenführen des PR ist nicht gleichbedeutend
mit einem produktiven Rollout.
