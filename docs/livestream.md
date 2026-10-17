# Livestream im Operations Center

Der Bereich **„Kamerabild“** in `/operations` zeigt Livestreams des Fluggeräts,
die DJI Pilot 2 an den MediaMTX des lokalen DJI-Cloud-Stacks sendet
(Dienst `mediamtx`, siehe [local-cloud-server-migration.md](local-cloud-server-migration.md)).

## Ablauf

1. Livestream in DJI Pilot 2 oder in der Cloud-Weboberfläche (`:8085`) starten.
   Das Backend vergibt die RTMP-Adresse `rtmp://<Pi>:1935/live/<SN>-<Nutzlast>`.
2. `/operations` fragt alle 10 s die aktiven Streams ab
   (`GET /api/v1/live/streams`). Ist das Fluggerät im Cockpit gewählt, wird
   sein Stream vorausgewählt.
3. **Ansehen** baut eine WebRTC-Verbindung auf:
   - Der Browser schickt sein Angebot (SDP) an
     `POST /api/v1/live/streams/{id}/whep`.
   - Das Gateway reicht es an MediaMTX (`127.0.0.1:8889`) weiter und gibt die
     Antwort samt Sitzungskennung (`X-Live-Session`) zurück.
   - Das Video läuft danach verschlüsselt (DTLS-SRTP) über UDP 8189 direkt von
     MediaMTX zum Browser.
4. **Stopp**, ein Seitenwechsel oder das Streamende schließen die Sitzung
   (`DELETE …/whep/{session}`).

## Warum über das Gateway?

`/operations` läuft über HTTPS, MediaMTX im LAN über HTTP. Direkte Aufrufe
würde der Browser als Mixed Content blockieren. Nur die kleine WebRTC-Anmeldung
läuft über das Gateway, das Video nicht.

## Sicherheit

- MediaMTX-Adressen müssen Loopback-HTTP sein:
  - `AERONEXUS_MEDIAMTX_API` (Standard `http://127.0.0.1:9997`)
  - `AERONEXUS_MEDIAMTX_WEBRTC` (Standard `http://127.0.0.1:8889`)
- **Undurchsichtige Stream-IDs:** Streampfade enthalten die Seriennummer. Der
  Browser erhält nur eine ID (Hash) und eine Bezeichnung aus dem Gerätenamen.
  Die ID wird bei jeder Anfrage gegen die aktuelle Pfadliste aufgelöst.
- **Grenzen:** SDP höchstens 64 KiB, 5 s Timeout, keine Weiterleitungen, keine
  Proxy-Variablen.
- **Fehlertexte:** MediaMTX-Fehlertexte werden in eigene Meldungen übersetzt,
  nicht weitergereicht.
- **Kein Cross-Site-POST:** Das Angebot verlangt `Content-Type: application/sdp`.
  Dieser Typ ist nicht CORS-safelisted, fremde Seiten können also nicht posten.
- **Zugriff:** wie bei den übrigen Lese-APIs (LAN-Modus oder Dashboard-Token).
- **Keine Steuerung:** Zuschauen sendet nichts an das Fluggerät.

## Hinweise

- **Codec:** Browser zeigen per WebRTC nur H.264 (sowie VP8/VP9/AV1)
  zuverlässig an. H.265 meldet die Seite als nicht abspielbar; in Pilot 2
  H.264 wählen. Der Pi 5 kodiert nicht um.
- **Browser:** Open-Source-Chromium ohne proprietäre Codecs kann kein H.264.
  Chrome, Edge und Android-Browser können es.
- **Netz:** UDP 8189 muss im LAN erreichbar sein; sonst steht die
  Signalisierung, aber kein Bild („Keine Medienverbindung“).
