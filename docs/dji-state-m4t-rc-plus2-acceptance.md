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
  Zusätzlich werden `is_near_distance_limit`, `rth_altitude` und
  `rc_lost_action` als validierte, rein lesende Sicherheitszustände übernommen.
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

Der passende Broker-ACL-Patch ist separat als
[AeroNexus PR #14](https://github.com/mason82-dotcom/AeroNexus/pull/14)
vorbereitet. Er ändert keine aktive EMQX-Konfiguration. Erst den tatsächlichen
Bind-Mount und den ACL-Status des laufenden Containers prüfen; **nicht**
`AERONEXUS_OSD_STATE_ENABLED=1` aktivieren, solange das Subscribe-Recht fehlt.

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

## Pi-Livenachweis: State-Verarbeitung auf beiden Geräten (18.10.2026)

Vom Betreiber auf dem aktiven Pi berichtet, nach ACL-Erweiterung und bewusstem
State-Opt-in:

| Nachweis | Live-Befund |
|---|---|
| `live_feed.state` | `subscribed` |
| `live_feed.state_topic_enabled` | `true` |
| Globale Zähler unmittelbar nach Neustart | `accepted=12, rejected=0, ignored=7, outdated=0` |
| DJI-Cloud-API-Inventar | 1 Fluggerät, 1 Controller |
| Fluggerät / `field_status` | 46 OSD-Felder, **1 State-Feld** |
| Controller / `field_status` | 16 OSD-Felder, **1 State-Feld** |
| Namentlich bestätigtes State-Feld am Controller | `cloud_details.cloud_control_authorization_count` |

Die `field_status[].channel=state`-Ursprungsmarkierung wird ausschließlich beim
MQTT-Ingest erzeugt; somit ist die **lokale Verarbeitung eines State-Felds
je Gerät** nachgewiesen, nicht nur ein erfolgreiches Broker-Subscribe. Diese
Zählung betrifft **gespeicherte Feldpfade**, nicht empfangene MQTT-Nachrichten.
Anschließende Bestandsprüfung über die geschützte HTTPS-Geräte-API:

| Gerät | Verarbeitetes State-Feld | Empfangsalter | DJI-Quellalter | Feldfrische |
|---|---|---:|---:|---|
| Fluggerät | `cloud_details.rth_mode_code` | 474,493 s | 496,183 s | `stale` |
| Controller | `cloud_details.cloud_control_authorization_count` | 474,492 s | 496,181 s | `stale` |

Beide Geräte waren gleichzeitig `fresh`: die OSD-Frische wird **nicht**
durch ältere State-Felder herabgesetzt oder unzulässig erneuert. Beide
State-Felder besitzen einen DJI-Quellzeitstempel. Aus den beiden unabhängigen
Altersangaben ergibt sich eine ungefähr **21,69 Sekunden ältere Quellzeit**
gegenüber dem Gateway-Empfang. Bei der bislang empfohlenen 15-s-Grenze
kann das State-Feld somit bereits beim Empfang als `stale` projiziert worden
sein. Ungeklärt sind DJI-/Pi-Uhrendifferenz, ursprüngliche Ereigniszeit und
Transport-/Pufferverzögerung. Vor einer Anpassung der Frischepolitik
**OSD-Quell-/Empfangsalter als Gegenprobe vergleichen**, keine Zeitstempel
automatisch korrigieren oder alte State-Eigenschaften als live ausgeben.
Die sieben ignorierten Pakete sind ohne kanalgetrennte Messung nicht erklärbar;
insbesondere sind sie nicht mit fehlerhaften State-Paketen gleichzusetzen.

**Noch nicht abgenommen:** Feldwerte/Einheiten gegenüber DJI, die tatsächliche
M4T-/RC-Plus-2-Modellidentität aus dem Protokoll, State-Paketdeltas während
eines definierten Zeitfensters, die Aktualitäts- und Liveness-Negativtests
sowie weitere reale State-Eigenschaften. Die vollständig hardwareverifizierte
Protokollabnahme bleibt offen. Für eine gefahrlose Feldprüfung ausschließlich
bekannte Feldpfade samt `channel` und `freshness` aus der bestehenden HTTPS-API
anzeigen; keine Seriennummern, Positionen oder Rohpayloads ausgeben.

## Zweiter Pi-Snapshot: OSD-Uhren plausibel, State-Felder fehlen

Eine spätere API-Stichprobe zeigt bei `stale_after_seconds=45` jeweils ein
`fresh`-Gerät und **46/46 frische OSD-Felder beim Fluggerät sowie 16/16 beim
Controller**. Die DJI-OSD-Quellzeit ist gegenüber der Empfangszeit um
ca. **0,41 s (Fluggerät) bzw. 0,45 s (RC) jünger** (gemessen als
`source_age_seconds - age_seconds` = −0,41/−0,45 s). Dies spricht
gegen einen durchgehend um ca. 22 Sekunden falsch laufenden Zeitgeber.
Zur Zeit dieses zweiten Snapshots meldet `field_status` **0 State-Felder
bei beiden Geräten**. Das belegt keine State-Störung: Inventar und
Feld-Zeitstempel sind flüchtig und werden beim Prozessneustart neu aufgebaut;
ohne neue zustandsgetriggerte Events bleiben entsprechende Felder aus.
Ein tatsächlicher Prozessneustart zwischen den Snapshots ist noch nicht
nachgewiesen. Die installierte Applikation stellt `live_feed.channels` noch
nicht bereit.

### Eigenständige read-only Topic-Beobachtung ohne Deployment

Der neue `scripts/pi/dji_state_topic_observer.py` eröffnet eine zweite,
temporäre MQTT-Sitzung ausschließlich mit dem schon vorhandenen dedizierten
`aeronexus_osd`-Konto. Die Subscriber-ACL bleibt unverändert.
Der Observer zählt nur **Nachrichten pro Topic-Kategorie** (`osd` und `state`),
greift auf keine MQTT-Payloads zu und schreibt weder Protokolle noch
Gerätekennungen. Der Publish-Aufruf ist zusätzlich lokal deaktiviert.
Er bestätigt die beiden MQTT-SUBACKs und liefert ausschließlich anonyme
Zahlen. Dafür muss der geänderte Server-Branch **nicht** deployed werden.

Auf dem laufenden Pi (Produktions-Checkout bleibt unberührt):

```bash
cd ~/Projekte/AeroNexusAdvanced
git fetch origin pull/68/head
git show FETCH_HEAD:scripts/pi/dji_state_topic_observer.py \
  | PYTHONPATH=src .venv/bin/python - --env-file .env --seconds 120
```

Voraussetzung: `AERONEXUS_OSD_STATE_ENABLED=1`, bestehende .env mit Mode 0600,
`paho-mqtt` und `python-dotenv` in der vorhandenen venv. Falls die
Kanalzähler in den 120 Sekunden `state_messages: 0` zeigen, ist das
**kein** Fehlernachweis (DJI sendet `state` nur bei Zustandsänderung).
`state_messages > 0` bestätigt eine tatsächlich zugestellte
MQTT-State-Nachricht am Broker unabhängig von deren Akzeptanz im Decoder.
Das Tool muss nur bei am Boden stehendem Fluggerät verwendet werden; keine
Flugeinstellungen zur künstlichen State-Erzeugung verändern.

## Reale topic-seitige Messung und unabhängige Decoderabnahme

Der temporäre MQTT-Observer wurde vom Betreiber erfolgreich am produktiven
Broker ausgeführt, ohne Änderungen am laufenden Dienst:

| Beobachtung | Ergebnis |
|---|---:|
| Subscriber-SUBACK für OSD und State | erfolgreich |
| Beobachtungsfenster | 120 s |
| OSD-Nachrichten im Fenster | **120** |
| State-Nachrichten im Fenster | **20** |
| Verbindungsunterbrechung | **nein** |

Damit ist die tatsächliche **Zustellung von State-MQTT-Nachrichten** auch
während des Beobachtungsfensters nachgewiesen. Diese Zahl sagt noch nichts
darüber aus, wie viele Nachrichten die produktive Decoder-Instanz
akzeptiert hat. Deren getrennte `live_feed.channels`-Zähler sind derzeit
nicht deployed. Der produktive Dienst lief zum Zeitpunkt der Probe seit
`2026-10-18 23:47:43 CEST` (MainPID 1131721); ob es ein tatsächlicher
Prozessneustart zwischen den früheren API-Snapshots war, ist noch nicht
lückenlos nachgewiesen.

### Decodergegenprobe ohne Deployment und ohne Rohdatenexport

Neu: `scripts/pi/dji_state_decoder_observer.py`. Diese Probe eröffnet
einen zweiten, temporären und **nur lesenden** MQTT-Subscriber und führt
die bereits lokal installierte kanonische `CloudOsdIngest`-Dekodierung in
einem **isolierten RAM-Inventar** aus. Der Listener verarbeitet MQTT-Payloads
nur im Speicher; er speichert und druckt **keine** Rohdaten, IDs, Positionen,
Eigenschaftswerte oder Token. Die Terminalausgabe enthält nur aggregierte
OSD-/State-Zähler für `accepted`, `ignored`, `rejected`, `outdated`,
übermittelte Nachrichten und akzeptierte Geräteklassen.

```bash
cd ~/Projekte/AeroNexusAdvanced
set -o pipefail
git fetch origin pull/68/head
git show FETCH_HEAD:scripts/pi/dji_state_decoder_observer.py \
  | PYTHONPATH=src .venv/bin/python - --env-file .env --seconds 120
```

Der Test verändert weder die produktive `.env` noch EMQX noch den Dienst.
**Wichtig:** Er führt den Decoder aus dem lokalen `src`-Checkout aus,
nicht automatisch den Code von PR #68. Die Beobachtung beschreibt deshalb
die **isolierte lokale Decoder-Reproduktion**, nicht die tatsächlichen
Paketentscheidungen des parallelen produktiven Prozesses. Ein positiver
State-Empfang bei `state_accepted=0` würde auf unbekannte Geräte,
nicht unterstützte State-Properties, Quellzeit-Reihenfolge oder
Validierungsfehler hinweisen. Keine DJI-Einstellungen verändern, um
ein Ereignis künstlich zu erzeugen.

## Verbindliche Hardwareabnahme (noch offen)

1. **RC Plus 2 allein eingeschaltet:** tatsächlicher RC-OSD-Eingang,
   Akku/SDR, eigene Geräteidentität, keine vorgetäuschte Flugzeugfrische.
2. **Matrice 4T verbunden und am Boden:** Fluggerät und RC als getrennte
   Geräte, M4T-Payload-Hinweis `89-0-0`, GPS/RTK/Batterie.
3. **State-Subscription ausdrücklich freigegeben:** vollständige
   MQTT-SubAck-Gewährung sowie ein **tatsächlich akzeptiertes** State-Ereignis
   anhand `accepted_during_observation.state > 0`. Der kumulierte Wert
   `channels.state.accepted` allein reicht hierfür nicht. Unveränderte Werte dürfen ausbleiben.
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
