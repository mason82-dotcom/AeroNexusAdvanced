# AeroNexusAdvanced – Projektstatus / Wiederaufnahmepunkt

**Stand:** 16. Oktober 2026  
**Phase:** 8.7 erfolgreich getestet; Phase 8.8 noch nicht umgesetzt.  
**Repository:** `mason82-dotcom/AeroNexusAdvanced`  
**Letzter auf Raspberry Pi 5 bestätigter Entwicklungs-Commit:** `82cc168`

## Bestätigt auf Raspberry Pi 5

- Arbeitsverzeichnis: `/home/mason/Projekte/AeroNexusAdvanced`
- Virtuelle Python-Umgebung: `.venv/bin/python` (Python 3.13.5)
- Installation: `aeronexusadvanced` 0.1.0, editierbar
- `python -m pip check`: **No broken requirements found**
- `python -m pytest -q`: **298 passed, 1 warning in 0.87s**
- Bekannte, derzeit nicht blockierende Warnung:
  `StarletteDeprecationWarning` in `fastapi/testclient.py`
  zu `httpx` / `httpx2`.
- Stand der Tests: Mock-/Fixture-Tests der DJI-Adapter; kein nachgewiesener erfolgreicher DJI-Produktivabruf.

## Web-Dashboard – bestätigter Betriebsstand

- Raspberry-Pi-LAN-IP: **192.168.178.63**
- Vom Benutzer erfolgreich manuell gestartet:
  ```bash
  cd ~/Projekte/AeroNexusAdvanced
  .venv/bin/python -m uvicorn aeronexus.app:app \
    --host 192.168.178.63 --port 8000
  ```
- Oberfläche: `http://192.168.178.63:8000/status`
- Benutzer-Screenshot bestätigt erfolgreiche Darstellung über LAN.
- Anzeigeintervall: **30 Sekunden** (Browser-Abfrage des lokalen Status).
- Im Screenshot: **0 registrierte Geräte**, 0 Drohnen, 0 Fernsteuerungen;
  `Polling: disabled`; keine authentifizierten Gerätedetails.
- Der gestartete Prozess war ein **manueller Vordergrundprozess**;
  es ist **nicht bestätigt**, dass er noch läuft oder nach einem
  Neustart automatisch startet.
- Zugriff aktuell über **HTTP ohne TLS**, daher Dashboard-Token und
  sensible Geräte-/Positionsdaten **nicht über diese LAN-Verbindung eingeben**.
- Keine übernommene Live-Telemetrie aus einem DJI-Konto nachgewiesen.

## Implementierte Funktionen (Phasen 8.3–8.7)

- Strict read-only DJI FlightHub 2 Public Cloud OpenAPI V2 und
  FlightHub 2 On-Premises OpenAPI V2 Adapter; ausschließlich geprüfte
  HTTPS-GET-Pfade.
- Projekt- und Drohnenlisten, normalisierte Detail-Telemetrie sowie
  validierte lokale Projekt-/Geräteverwaltung.
- GPS-Position, Batterie, Flughöhe, horizontale/vertikale Geschwindigkeit,
  Flugzeit, Satellitenzahlen und uninterpretierten RTK-Rohzustand.
- UTC-Zeitstempel für den Empfang von lokal verarbeiteten Messwerten.
- Klassifikation `fresh`, `stale`, `missing`, `unknown_age`,
  `clock_skew`; veraltete Werte sind nicht als aktuell online markiert.
- FastAPI `/api/v1/status/summary` (anonyme aggregierte Kennzahlen),
  `/api/v1/status/devices` (separater Dashboard-Bearer-Token),
  `/status` (responsive Weboberfläche).
- Opt-in Polling-Baustein, aber **kein automatisch aktivierter DJI-Live-Sync**.
- **Sicherheitsanforderungen:** keine Flugbefehle; DJI-Dock-Integration
  ausdrücklich ausgeschlossen; nur Drohnen und Fernsteuerungen im
  kanonischen Bestand. Echte Controller-Erkennung noch nicht verifiziert.

## Nächste Schritte

1. **HTTPS im LAN** für `192.168.178.63` einrichten (inklusive
   vertrauenswürdiger Zertifikatskette auf den zugreifenden Geräten).
2. **systemd-Betrieb** für AeroNexusAdvanced mit Restart-Verhalten und
   kontrollierter Konfiguration einrichten; nicht mehrere Uvicorn-Instanzen
   unkoordiniert betreiben.
3. **Phase 8.8:** Explizit konfigurierbare, read-only DJI-Public-Cloud-
   Synchronisierung mit dem **selben** StatusRuntime/Inventory des Servers
   verbinden. Nur autorisierte GET-Endpunkte, kein Fernzugriff auf
   Flugsteuerung; Fehlerbehandlung, Backoff und Statusanzeige.
4. Erst nach Prüfung einer zuverlässigen On-Premises-Projekt-UUID-Zuordnung
   automatischen On-Premises-Import erlauben.
5. Anschließend DJI-Live-Antworten mit korrekt autorisiertem Testkonto
   prüfen, ohne Zugangsdaten oder Seriennummern in Chat/Logs zu posten.

## Wiederaufnahme

```bash
cd ~/Projekte/AeroNexusAdvanced
git pull --ff-only
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
```

**Wichtige Abgrenzung:** Dieses Dokument speichert den *Projekt- und
Betriebsstatus*, nicht fortlaufende Telemetriedaten oder den Arbeitsspeicher
des laufenden Webservers.
