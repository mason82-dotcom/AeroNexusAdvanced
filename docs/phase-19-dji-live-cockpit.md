# Phase 19: DJI Pilot 2 Live-Cockpit im Operations Center

## Ziel und verifizierter Eingang

Die auf dem Raspberry Pi 5 laufende AeroNexusAdvanced-Instanz erhält
schreibgeschützte DJI-Cloud-API-OSD-Telemetrie vom lokalen EMQX-Broker.
Beim Labortest mit RC Plus 2 und Matrice 4T wurden für das Fluggerät
u. a. Akku-Prozent, Spannung/Temperatur, `height`, `elevation`,
Geschwindigkeiten, Flugmodus-Code, GPS-/RTK-Satelliten und Flugstatistik
erfolgreich dekodiert. Die Fernsteuerung liefert ihren eigenen Akkustand.

Im Indoor-Test lagen zunächst keine gültigen GPS-Koordinaten vor.
`is_fixed:0` ist **keine** bestätigte RTK-Fix-Meldung.
Ein OSD-Abonnement ist auch bei ausgeschalteter Drohne noch
`subscribed`: Das beweist nur die Broker-Verbindung, nicht einen aktuellen
Telemetriefluss. Nach einem Prozessneustart beginnt das lokale, nur im
Arbeitsspeicher gehaltene Geräte-Inventar leer. Eine ausgeschaltete
Drohne erscheint dann erst nach erneuter OSD-Übertragung wieder.

## Änderungen am Operations Center

- Der separate Abschnitt **DJI Cloud API · MQTT** zeigt den
  Subscriber-Status, gültige und abgewiesene Nachrichten seit Dienststart
  sowie das Alter des letzten erfolgreichen Empfangs.
  Ein grüner Live-Indikator erfordert `subscribed`, mindestens eine
  verarbeitete Nachricht und einen Empfang innerhalb von 60 Sekunden.
  Ein bestehendes Abonnement **ohne** neue Daten wird nicht als aktueller
  Empfang ausgegeben.
- Die **Fernsteuerungs-Anzeige** gibt Quelle, Online-/Frische-Status
  und Akku des RC-Geräts aus; fehlende Werte bleiben „Nicht übermittelt“.
- Fluggeräte aus FlightHub EU und DJI Cloud API werden in Auswahl und
  Cockpit anhand von `provider`, `project_id` und `device_id` getrennt.
  Bei gemeinsamem `device_id` wird das Fluggerät in den KPI-Zählern
  nur einmal gezählt; unterschiedliche Kennungen können nicht sicher
  als dasselbe physische Gerät zusammengeführt werden.
  Die DJI-MQTT-Quelle wird in der Fluggeräteauswahl bevorzugt.
- Die **GNSS-/RTK-Diagnose** kennzeichnet fehlende GPS-Koordinaten
  explizit und zeichnet ohne gültige Position **keinen** Kartenmarker.
  Die numerische RTK-Meldung `is_fixed:0` wird konservativ als
  „Kein bestätigter RTK-Fix“ dargestellt.
- Die DJI-Felder `height_m` und `elevation_m` sind ausdrücklich
  Rohwerte mit **ungeprüftem Bezug**, keine garantierte Höhe über
  Grund oder Startpunkt.
- Ist FlightHub-Polling deaktiviert, weist die Oberfläche darauf hin,
  statt eine aktuelle FlightHub-Synchronisierung zu suggerieren.

## Sicherheit und Grenzen

Die Änderung betrifft ausschließlich die lokale HTML-/JavaScript-Ansicht
des bestehenden FastAPI-Servers, Tests und Dokumentation. Sie ergänzt
weder MQTT-Publishing noch Flugsteuerungs-, RTK-Konfigurations-
oder DJI-SDK-Schreibbefehle. Der vorhandene schreibgeschützte
OSD-Subscriber mit eingeschränkter ACL bleibt unverändert.
Die Oberfläche lädt wie bisher in einem 15-Sekunden-Intervall lokale
HTTPS-GET-Endpunkte. Keine DJI-Zugangsdaten gelangen ins HTML oder
Browser-Storage.

Live-Werte sind zuletzt empfangene Daten, **keine**
Flugsicherheitsinstrumentierung; bei stale/offline wird nicht
von einer bestätigten Live-Verbindung gesprochen. Die FlightHub-EU-
Polling-Einstellung bleibt unabhängig von DJI MQTT unverändert.

## Kontrolle nach einem späteren Pi-Rollout

```bash
cd ~/Projekte/AeroNexusAdvanced
git status --short
# Nur bei sauberem Arbeitsbaum:
git pull --ff-only
.venv/bin/python -m pytest -q tests/test_operations_page.py
systemctl --user restart aeronexusadvanced.service
systemctl --user is-active aeronexusadvanced.service
curl -ksSf https://192.168.178.63:8000/api/v1/status/summary
```

Die Cloud-Docker-Container werden dafür nicht angefasst.
Aufruf der Ansicht: `https://192.168.178.63:8000/operations`.
Bei ausgeschalteter Drohne zeigt das Cockpit korrekterweise keinen
frischen Fluggerätedatensatz; die MQTT-Verbindung kann trotzdem
weiterhin `subscribed` melden.
