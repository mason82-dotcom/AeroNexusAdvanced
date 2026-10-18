# DJI Cloud API 1.18 – Matrice 4T / RC Plus 2: State-Protokollabnahme

Stand: 18.10.2026. **Code-Review und synthetische Regression sind keine reale Geräteabnahme.**
Dieses Protokoll beschreibt den bisher prüfbaren Datenpfad Pilot 2 → lokaler
DJI-Cloud-Server → EMQX → AeroNexusAdvanced → geschützte HTTPS-Status-API.
Die produktiven Pi-Prozesse, EMQX-ACLs und DJI-Konfiguration werden durch diesen
Branch **nicht** verändert.

## Herstellervertrag und beobachtbare Eigenschaften

DJI verwendet:

- `thing/product/{device_sn}/osd` für Eigenschaften mit `pushMode=0`,
  periodisch (in der Dokumentation 0,5 Hz);
- `thing/product/{device_sn}/state` für `pushMode=1`,
  **nur bei Zustandsänderung**;
- `thing/product/{gateway_sn}/property/set` ist ein **Schreibkanal** und bleibt
  für AeroNexusAdvanced gesperrt.

Für die Matrice 4T ist der Kamera-/Nutzlastindex `89-0-0` ein dokumentierter
**Modellhinweis**, kein durch die MQTT-Nachricht bewiesener Geräteidentitätsnachweis.
Die RC Plus 2 wird anhand ihrer eigenen, unter dem RC-SN publizierten OSD-Nachrichten
klassifiziert, nicht anhand des angeschlossenen Fluggeräts.

| Gruppe | DJI OSD (Beispiele) | DJI State (Beispiele) |
|---|---|---|
| M4T Fluggerät | Flugmodus, GPS/RTK, Höhe, Geschwindigkeit, Fluglage, Wind, Batterie, Entfernungsgrenze | Firmware, Steuerquelle, Homepoint, Batteriewarnschwellen, Payload-Zustände |
| RC Plus 2 | RC-Akku, Position/Ellipsoidhöhe, SDR-/4G-Link, DRC-Linkstatus | Firmware, Cloud-Autorisierungsstatus (nur Anzahl), Livestreamstatus/-kapazität |

Ein fehlender `state`-Wert ist kein Protokollfehler: Er kann seit dem Start
unverändert geblieben sein, von der Firmware nicht geliefert werden, vorher
eingetroffen sein oder wegen der ACL nicht ankommen. Er darf nicht aus OSD
erraten und nicht als 0 interpretiert werden. DRC-Verbindungsstatus ist **keine**
Freigabe für Flugsteuerung.

## Änderungen in diesem Branch

- DJI-OSD-Feld `distance_limit_status.state` (0/1) und
  `distance_limit_status.distance_limit` (15–8000 m) werden validiert und
  als `cloud_details.distance_limit.state_code` und
  `cloud_details.distance_limit.distance_limit_m` rein lesend ausgegeben.
- Die anonymisierte `live_feed.channels.osd/state`-Diagnose zählt je Kanal
  `accepted`, `rejected`, `ignored`, `outdated` und gibt den Zeitpunkt
  des zuletzt akzeptierten Pakets aus. Bestehende Zähler bleiben erhalten.
  `state` kann aktiviert oder deaktiviert sein – der Branch aktiviert es nicht.
- `scripts/pi/dji_state_conformance.py` liest ausschließlich vorhandene
  HTTPS-GET-Endpunkte, beobachtet bekannte Feldnamen und ihre Kanalzuordnung.
  Er verwirft sämtliche Geräte-IDs, Koordinaten, tatsächliche Messwerte,
  DJI-Envelope-/Rohdaten und Zugangsdaten. **Kein MQTT-Subscribe im Prüftool.**
- Unit-Tests prüfen Feldgrenzen, atomare Fehlerbehandlung,
  Kanaltrennung, fehlende State-Abdeckung und Redaktionsregeln.

## Konfigurations- und ACL-Abnahme

Zuerst am laufenden Pi mit der alten API feststellen, ob
`live_feed.state_topic_enabled` bisher `false` ist. In diesem Fall ist
eine vollständige `state`-Abnahme noch nicht möglich.

**Nur nach bewusstem administrativem Opt-in:**

```dotenv
AERONEXUS_CLOUD_MQTT_ENABLED=1
AERONEXUS_OSD_STATE_ENABLED=1
```

Das vorhandene **dedizierte, nicht veröffentlichende** MQTT-Konto benötigt:

- `SUBSCRIBE thing/product/+/osd`
- `SUBSCRIBE thing/product/+/state`
- optional separat `SUBSCRIBE thing/product/+/events` für HMS
- **kein** `PUBLISH` auf irgendwelche Topics, insbesondere niemals
  `property/set`, `services`, `drc/down`, `commands`.

Die bestehende Authentisierung darf nicht durch die Verwendung eines DJI-
Backend-, Administrations- oder Pilot-Kontos umgangen werden. Wenn ein
Subscription-Recht verweigert wird, meldet die Integration
`subscription_denied`, statt irreführend `subscribed`. Zugangsdaten und
EMQX-ACL-Auszüge mit Secrets nicht in Chat oder Tickets kopieren.

## Sicherer Test ohne Veränderung der produktiven Dienste

Nach Review den Branch separat auschecken:

```bash
cd ~/Projekte/AeroNexusAdvanced
git fetch origin
git worktree add ../AeroNexusAdvanced-dji-state \
  origin/feat/dji-state-conformance-20261018
cd ../AeroNexusAdvanced-dji-state
PYTHONPATH=src ../AeroNexusAdvanced/.venv/bin/python -m pytest -q \
  tests/test_dji_state_conformance.py tests/test_cloud_api_118.py \
  tests/test_cloud_api_mqtt.py
```

Der HTTP-Check benötigt bereits einen Server mit diesem Branch und dessen
anonymen `channels`-Zählern. Der Code wird **nicht** automatisch deployed.

Für die existierende, bewusst aktivierte tokenfreie HTTPS-LAN-Authentisierung:

```bash
cd ~/Projekte/AeroNexusAdvanced-dji-state
python3 scripts/pi/dji_state_conformance.py \
  --base-url https://192.168.178.63:8000 \
  --ca ../AeroNexusAdvanced/config/pki/ca.crt \
  --lan-without-token --seconds 120
```

Bei Bearer-geschütztem Zugriff den Token in der **lokalen Umgebung** als
`AERONEXUS_STATUS_TOKEN` bereitstellen und
`--lan-without-token` weglassen. Keine Tokens als CLI-Parameter eingeben.
Das Zertifikat wird geprüft, HTTP und Redirects werden zurückgewiesen.

Die Ausgabe enthält `outcome` und getrennte Zähler/Feldnamen – keine
konkreten Fluggeräte-IDs oder Livewerte. `not_observed` heißt lediglich,
dass das Feld im Beobachtungsfenster nicht gesehen wurde.

## Verbindliche Hardwareabnahme (noch offen)

1. **RC Plus 2 allein eingeschaltet:** tatsächlicher RC-OSD-Eingang,
   Akku/SDR, eigene Geräteidentität, keine vorgetäuschte Flugzeugfrische.
2. **Matrice 4T verbunden und am Boden:** Fluggerät und RC als getrennte
   Geräte, M4T-Payload-Hinweis `89-0-0`, GPS/RTK/Batterie.
3. **State-Subscription ausdrücklich freigegeben:** vollständige
   MQTT-SubAck-Gewährung sowie ein **tatsächlich akzeptiertes** State-Ereignis
   anhand `channels.state.accepted > 0`. Unveränderte Werte dürfen ausbleiben.
4. **Feldabgleich:** Dokumentationsfeldnamen, Einheiten, Code-Enge, Kamera-
   Indizes und echte `field_status[].channel` prüfen; `position.quality=10`
   nicht mit RTK-`is_fixed` verwechseln.
5. **Frische und Datenschutz:** nach OSD-Unterbrechung alte Navigation/
   Batterie nicht durch frisches State erneut freigeben. Kein Log/Report mit
   Seriennummern, Standort, Controller-/Browser-UUID oder Geheimnissen.
6. **Negativpfade:** fehlende State-ACL, Wiederholungen, Zeitstempelversatz
   und syntaktisch ungültige Pakete müssen ohne Teiländerung und ohne
   Schreibzugriff behandelt werden.

**Abschlusskriterium:** Nur die lokale Prüfung mit der echten RC Plus 2 und
Matrice 4T samt akzeptierten `state`-Events und Feld-zu-Feld-Abgleich erlaubt
die Kennzeichnung **„hardwareverifiziert“**. Bis dahin:
**„Code vorbereitet; reale State-/Protokollabnahme ausstehend“**.

## DJI-Primärquellen

- [DJI Pilot-to-Cloud MQTT Topic Definition](https://github.com/dji-sdk/Cloud-API-Doc/blob/master/docs/en/60.api-reference/10.pilot-to-cloud/00.mqtt/00.topic-definition.md)
- [DJI M4-Serie Properties](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/mqtt/m4-series/properties.html)
- [DJI RC Plus 2 Properties](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/mqtt/dji-rc-plus-2/properties.html)
- [DJI Aircraft Properties (gemeinsame Eigenschaften)](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/mqtt/aircraft/properties.html)
