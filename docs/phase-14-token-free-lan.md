# Phase 14 — Browserzugriff ohne Token (nur Heimnetz)

## Ergebnis

Das FlightHub-Status-Dashboard `/status` und das Chrome Mission Studio
`/studio` besitzen **keine Token-Eingabefelder oder Login-Knöpfe** mehr.
Gerätestatus, Routen-/Modellbibliothek und lokal gespeicherte Missionen und
Medien werden beim Laden der Seite automatisch abgerufen.

Zuvor war ein JavaScript-Syntaxfehler in der Umrechnung eines Leaflet-
Längengrads vorhanden, der das gesamte Chrome-Studio-Skript blockierte;
dieser ist behoben. Ein neuer Node.js-`--check`-Test parst die wirklichen
Browser-Skripte.

## Sicherheitsmodell

Der neue Modus muss in der **privaten** Datei
`~/Projekte/AeroNexusAdvanced/.env` ausdrücklich aktiviert werden:

```dotenv
AERONEXUS_LAN_NO_TOKEN=1
AERONEXUS_LAN_HOST=192.168.178.63
```

Damit werden **alle** Status- und Studio-API-Routen ausschließlich für
**direkte** Zugriffe aus `192.168.178.0/24` und vom Pi selbst (Loopback)
freigegeben. Es ist keine Benutzeranmeldung mehr erforderlich.

Schutzmaßnahmen (serverseitig in `src/aeronexus/lan_access.py`):

1. Exakte feste Zieladresse `192.168.178.63` in der Konfiguration und
   genau dieser HTTPS-Host im Request (oder `localhost/127.0.0.1` für
   lokale Pi-Werkzeuge): Schutz vor DNS-Rebinding und fremden Host-Namen.
2. Peer-IP direkt aus der TCP-Verbindung, keine Vertrauensannahme über
   `X-Forwarded-For`, `Forwarded` oder `X-Real-IP`.
3. **HTTPS** für alle nichtlokalen Verbindungen; zusätzlich verweigert
   `deploy/pi/run-server.sh` einen LAN-Bind ohne TLS, sofern die
   unsichere explizite Ausnahme nicht gesetzt ist.
4. Cross-Site-Fetches werden über `Sec-Fetch-Site` abgelehnt;
   `Origin` muss bei Vorhandensein exakt dem Seitenursprung entsprechen.
   Bei schreibenden Aufrufen ist ein gültiger Origin oder ein
   `Sec-Fetch-Site: same-origin` notwendig.
5. Bei deaktiviertem LAN-Modus bleibt die bisherige Backend-Tokenprüfung
   als Fallback erhalten; die neue Weboberfläche besitzt aber **kein
   Eingabefeld** mehr. Daher den LAN-Modus für diese UI explizit einschalten.
6. Die gesperrte DJI-Flugsteuerungs-API bleibt **403**.
   Missionen und Medien werden nur lokal auf dem Pi erstellt, bearbeitet
   oder gelöscht; **keine DJI-Cloud-Uploads, kein Dock**.

**Wichtige Konsequenz:** Jedes Gerät/Programm im freigegebenen Heimnetz
kann Geräteseriennummern, GPS-Positionen und Missionen lesen sowie
lokale Missionen und Medien erstellen, ändern oder löschen. Ein
gemeinsames WLAN ist deshalb **keine** Benutzer-Authentifizierung.
Diesen Modus nicht in Gast-/öffentlichen WLANs, über einen öffentlichen
Reverse Proxy oder eine Router-Portweiterleitung bereitstellen.
Als Alternativen eignen sich ein vertrauenswürdiges VLAN, eine
Pi-Firewall mit Geräte-IP-Allowlist oder eine gesonderte Benutzerauthentifizierung.

## Installation auf dem Pi

```bash
cd ~/Projekte/AeroNexusAdvanced
git pull --ff-only
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
```

Anschließend die beiden Konfigurationseinträge in `.env` ergänzen,
Berechtigung `chmod 600 .env` kontrollieren und neu starten:

```bash
systemctl --user restart aeronexusadvanced
systemctl --user is-active aeronexusadvanced
```

Im Chrome-PC-Browser jeweils über die HTTPS-Adresse mit vertrauenswürdiger
lokaler CA öffnen:

- `https://192.168.178.63:8000/studio`
- `https://192.168.178.63:8000/status`

Keine Token-Abfrage und kein Klick auf „Verbinden“ notwendig.

## Tests

- Neue API-Sicherheitstests simulieren echte Client-IP-Adressen in
  `192.168.178.0/24` bzw. außerhalb, korrekte und fremde Hosts,
  echte HTTPS-Origins, CSRF-Versuche sowie lokale Missions- und
  Medien-CRUD-Aufrufe ohne Token.
- Die bisherigen Tests für den alten Bearer-Modus bleiben erhalten.
- Echte JavaScript-Syntaxprüfung für beide Weboberflächen mittels
  `node --check` (optional bei fehlendem Node.js).
- GitHub Actions testet Python 3.12; den kompletten Testlauf zusätzlich
  auf dem Raspberry Pi 5 unter Python 3.13 durchführen.
