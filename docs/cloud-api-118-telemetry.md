# Cloud API 1.18: zusätzliche Telemetrie und Mavic-3-Enterprise-Serie

Diese Erweiterung verarbeitet bereits von DJI Pilot 2 gesendete MQTT-Daten
lesend. Keine DJI-Kommandos, neue Brokerrechte, DRC-Sitzung, Topologieabfrage
oder automatische Aktivierung von `state`. Der Produktname „Cloud API 1.18“
bezeichnet den geprüften Dokumentationsstand, keine neue Clientbibliothek.

## Gerätefamilien und Nachweis

| Modell | Bekannter Kameraindex | Datenweg |
|---|---|---|
| Mavic 3 Enterprise / M3E | `66-0-0` | Gemeinsame Flugtelemetrie und übermittelte Kamerazustände |
| Mavic 3 Thermal / M3T | `67-0-0` | Zusätzlich übermittelte IR-Messpunkt-/Bereichswerte |
| Mavic 3 Multispectral / M3M | `68-0-0` | Gemeinsame Flugtelemetrie und übermittelte Kamerazustände |
| Mavic 3 Thermal Advanced / M3TA | `129-0-0` | Gemeinsame Flugtelemetrie und übermittelte IR-Kamerazustände |
| Matrice 4E / M4E | `88-0-0` | Gemeinsame Flugtelemetrie und dynamischer Gimbal-/Zoom-Block |
| Matrice 4T / M4T | `89-0-0` | Gemeinsame Flugtelemetrie und dynamischer Gimbal-/Zoom-Block |

RC Pro Enterprise und RC Plus 2 verwenden denselben validierten RC-Decoder.
Das RC-Modell wird nicht aus dem verbundenen Fluggerät geraten. Die
Kameraindizes erzeugen einen `aircraft_model_hint`, keine verifizierte
Topologieidentität. Er ersetzt in der Geräteansicht nur den generischen Namen
`Aircraft`, keine benutzerdefinierten Namen. Unbekannte Nutzlastindizes können
validierte Gimbalwerte liefern, erhalten aber keinen erfundenen Modellnamen.

Die M3M-Bandkalibrierung und NDVI-Auswertung bleiben im vorhandenen
dateibasierten Multispektral-Modul. Es werden keine Live-NDVI-, Sonnenlichtsensor-
oder Reflexionswerte aus allgemeinen OSD-Nachrichten abgeleitet. M3TA-Unterstützung
hier betrifft MQTT-Eigenschaften; sie behauptet keine neue Thermal-SDK-/
R-JPEG-Abnahme oder geprüfte M3TA-Footprint-Optik.

## Zusätzliche Daten

Die Status-API liefert sie unter `devices[].telemetry.cloud_details`.
Die vorhandene technische Gerätetabelle auf `/status` zeigt diese Struktur
unter **Werte anzeigen** als JSON. Es wird keine neue Cockpit-Oberfläche eingeführt.

- Fluglage: `heading_deg`, `roll_deg`, `pitch_deg`.
- Wind: `wind_speed_mps`, `wind_direction_code`. DJI-Windgeschwindigkeit
  wird aus der Wire-Einheit 0,1 m/s genau einmal umgerechnet; es bleibt eine
  geschätzte Größe, kein Wetterstationsmesswert.
- Heimatpunkt, Gesamtflugstrecke, Höhenlimit, Grenzannäherung, Nachtlichter,
  Flugzustandsgrund, Gang, RTH-Moduscodes und Batteriewarnschwellen.
- `position.quality_code`, einschließlich dokumentiertem Wert 10. Er bleibt
  getrennt von `rtk_state`/`is_fixed`; Satellitenzahl allein ist keine Fixbestätigung.
- `battery`: Restflugzeit und Rückkehr-/Landeschwellen; `battery_packs`:
  Index, Kapazität, Spannung, Temperatur, Ladezyklen, Typcodes und Firmware.
- Speicherbelegung in KiB, Hindernissensorzustände, Firmware- und Wartungsdaten.
- `payloads`: Gimbalwinkel/Zoom nach dynamischem Schlüssel, z. B. `89-0-0`.
- `cameras`: Nutzlastindex, Aufnahmezustand, verbleibende Fotos/Videozeit,
  Zoom, Belichtungs-/Fokuscodes und übermittelte M3-IR-Messpunkt-/Bereichswerte.
  ISO und Verschlusszeit bleiben DJI-Enums, keine erfundenen physikalischen Werte.
- RC: Ellipsoidhöhe, SDR-/4G-Linkzustände und Qualitätscodes/Frequenzbänder,
  Livestreamstatus ohne Video-ID/Seriennummer und globale Streamfähigkeitszähler.

Unbekannte Felder werden verworfen. Zahlen müssen endlich sein; Listen und
Texte sind begrenzt. Ungültige erlaubte Werte verwerfen das gesamte Paket,
ohne Teiländerung. Arrays sind vollständige versionierte Eigenschaften;
Objekte werden nach Blattfeld zusammengeführt. Keine Zugangsdaten, IMEI,
EID, ICCID, Akku-Seriennummern oder ungefilterte Rohmeldungen werden übernommen.
Fehlende Eigenschaften bedeuten unbekannt, nicht Null oder eine Gerätefähigkeit.

## Zeit, Reihenfolge und Teilmeldungen

Für MQTT-Geräte liefert die geschützte Status-API zusätzlich:

- `field_status`: pro Eigenschaft Empfangszeit, DJI-Quellzeit in Millisekunden,
  Empfangs-/Quellalter, Kanal (`osd`/`state`) und Frischezustand.
- `last_known_telemetry`: letzte validierte Werte zur historischen Prüfung.
  Diese Struktur kann veraltet sein und ist ausdrücklich kein aktueller Messsatz.
- `telemetry`: Werte mit abgelaufener oder zeitlich unplausibler Feldzeit werden
  als `null` ausgegeben. Die übrigen Eigenschaften bleiben unabhängig nutzbar.

Das Feldalter verwendet konservativ das größere von Empfangs- und Quellalter.
Es gilt die bestehende `AERONEXUS_STATUS_STALE_AFTER_SECONDS`-Grenze. Ein
frisches RTK-`state`-Paket erneuert daher weder alten Akku/GPS noch OSD-Liveness.
Bei einem neuen partiellen OSD wird nur der enthaltene Messwert erneuert.
Auch selten geänderte State-Konfigurationen laufen konservativ aus; ihre
letzten Werte bleiben in `last_known_telemetry` mit separatem Feldalter prüfbar.

Reihenfolge wird pro Feld über beide Kanäle geprüft. Ältere Quellzeiten
überschreiben neuere Werte nicht. Bei gleicher Quellzeit dürfen getrennte
Teilpakete bisher unbekannte Felder ergänzen; bereits zeitgestempelte Felder
werden nicht überschrieben oder aufgefrischt (first wins). Ein vollständig
veraltetes/wiederholtes Paket erhöht `ignored` und `outdated`.

Für bestehende Sender ohne `timestamp` bleibt ein Empfangszeit-Fallback mit
`source_timestamp_ms: null` möglich. Solche Meldungen dürfen keine bereits
quellzeitgestempelten Felder überschreiben. Ein Reihenfolgenachweis für
ausschließlich undatierte Sender ist nicht möglich. Ungültige Quellzeiten
werden abgewiesen; mehr als 30 Sekunden Zukunft ebenfalls. Zeitabweichungen
über einer Sekunde erscheinen als `clock_skew`, nicht als frische Messung.

Zeit- und Messwertspeicher sind wie das bestehende Inventory flüchtig und
werden beim Neustart neu aufgebaut. Die Erweiterung ändert weder FlightHub-
Frische noch gespeicherte Missionen und Medien. Empfang ist kein Nachweis
einer flugsicheren Verbindung oder einer aktuellen Flugfreigabe.

## Verifikation und Grenzen

`tests/test_cloud_api_118.py` prüft alle sechs Modellhinweise, RC-Eigenschaften,
Einheiten, Grenzen, Datenschutz, API-Zugriff sowie alte/gleiche Quellzeiten,
Teilpakete, State/OSD-Reihenfolge, Zeitabweichungen und Atomizität bei Fehlern.
Es werden synthetische Protokolldaten verwendet; keine reale Fluggeräteabnahme
behauptet. Vor Pi-Rollout lokale Änderungen/Branch prüfen, Extras beibehalten,
Tests ausführen und reale Pilot-2-Pakete gegen die erwarteten Werte vergleichen.

HMS, DRC-Kamera-/Laser-/Thermal-Livedaten sowie vollständige Stream-Topologie
sind getrennte Integrationen. Ein reiner MQTT-Subscribe fügt fehlende DRC-
Sitzungen nicht hinzu. MQTT-Rechte bleiben OSD plus optional State, nie Publish.

## Offizielle Grundlagen (abgerufen 17.10.2026)

- [Cloud API Release Notes, v1.18 vom 13.10.2026](https://developer.dji.com/doc/cloud-api-tutorial/cn/)
- [M4-Eigenschaften](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/mqtt/m4-series/properties.html)
- [M3-Eigenschaften](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/mqtt/m3-series/properties.html)
- [RC Plus 2](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/mqtt/dji-rc-plus-2/properties.html)
- [RC Pro](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/mqtt/rc-pro/properties.html)
- [Produkt-/Nutzlastindizes einschließlich M3TA](https://developer.dji.com/doc/cloud-api-tutorial/en/overview/product-support.html)
- [Offizielle WPML-Modell-/Nutzlastindizes einschließlich M3M](https://github.com/dji-sdk/Cloud-API-Doc/blob/master/docs/cn/60.api-reference/00.dji-wpml/40.common-element.md)

Die Website wurde gegenüber dem älteren öffentlichen Markdown-Spiegel
bevorzugt. Gemeinsame Eigenschaften sind eine Decoderfähigkeit, keine Garantie,
dass jede Firmware jedes Feld oder jede Kameraoption sendet.
