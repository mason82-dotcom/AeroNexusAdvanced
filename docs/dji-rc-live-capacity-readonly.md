# DJI RC Plus 2 / RC Pro – lesender Livestream-Fähigkeitsabgleich

Stand: 2026-10-19. DJI Cloud API 1.18; Quellen:
- https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/pilot-to-cloud/mqtt/dji-rc-plus-2/properties.html
- https://github.com/dji-sdk/Cloud-API-Doc/blob/master/docs/en/60.api-reference/10.pilot-to-cloud/00.mqtt/20.rc-pro/00.properties.md

## Umfang

Der RC-Gateway sendet `live_capacity` ereignisgesteuert über `thing/product/{sn}/state`.
Der Decoder stellt aus der DJI-Hierarchie `device_list → camera_list → video_list`
ausschließlich folgende ergänzende Daten unter
`telemetry.cloud_details.live_capacity` bereit:

- `source_devices_count`: Anzahl der vollständig gelieferten Device-List-Einträge
- `source_cameras_count`: Summe der gelieferten Camera-List-Einträge; `null`, wenn eine Liste fehlt
- `source_streams_count`: Summe der Video-List-Einträge; `null`, wenn eine Liste fehlt
- `video_types`: validierte, sortierte Typkategorien oder `null` bei unvollständigen Video-Einträgen
- `switchable_video_types`: validierte, sortierte Kategorien oder `null` bei fehlenden Umschaltlisten

`available_videos` und `simultaneous_videos` bleiben wie bisher vorhanden.
Nur dokumentierte und getestete Meldungen sind eine Datenquelle. Fehlende Listen
bedeuten unbekannt, nicht null Quellen; **explizite leere Listen** dürfen null Quellen belegen.
Wenn eine neue `device_list` nur Teilstrukturen enthält, werden davon abhängige
Aggregationsergebnisse als `null` markiert, um alte und neue Teilinformationen nicht
zu scheinbar vollständigen Verfügbarkeitsdaten zu kombinieren.

## Sicherheit und Datenschutz

Die DJI-Felder `sn`, `camera_index`, `video_index` und sonstige freie Texte
werden nach Form-/Grenzprüfung **nicht gespeichert**. Video-Typen bleiben strikt
auf die festen Kategorien `normal`, `wide`, `zoom`, `ir`,
`thermal`, `infrared` und `other` begrenzt; unbekannte,
syntaktisch gültige Werte werden nur als `other` gezählt.

Die Eingangsstrukturen sind begrenzt auf 16 Geräte, je 16 Kameras, je 32
Streams und je 16 umschaltbare Typen. Ungültige Arrays oder Typen werden
atomar abgewiesen; keine Feldänderung erfolgt bei einem ungültigen MQTT-Paket.
Die kanonische Validierung erlaubt nur bekannte Aggregationsfelder.

Jeder einzelne Summenwert besitzt weiterhin die Quellzeit- und Empfangszeit-
Frischeprüfung des bestehenden MQTT-Inventars. Ist der State-Wert veraltet,
zeigt die Live-Telemetrie `null`, während die interne `last_known_telemetry`
weiterhin den alten, ausdrücklich nicht als live bestätigten Wert enthält.

Es gibt weder neue MQTT-Abonnements noch Publish-Rechte, keine Remote-
Kameraumschaltung und keine Flugsteuerung. Das Cockpit zeigt lediglich
die vorhandenen validierten Werte an.

## Tests und Einschränkungen

Die synthetischen Regressionen in `tests/test_cloud_api_118.py` prüfen
M4T/RC-typische Kameralisten, fehlende Unterlisten, Teil-Updates,
Verfallszeiten, unbekannte Enumtexte, Atomizität und Redaktionen.
Es bleibt zu prüfen, welche `device_list`-Form die konkrete DJI RC Plus 2
mit der eingesetzten Firmware tatsächlich liefert. Die Implementierung ist
**kein** Hardware-, Streamstart- oder Flugfreigabenachweis.

Vor produktivem Rollout mit PR #68 und #71 auf einem temporären Integrations-
Worktree zusammenführen und die vollständige Testsuite laufen lassen.
