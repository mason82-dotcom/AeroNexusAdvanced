# DJI Cloud API – HMS-Codes und deutschsprachige Meldungen

## Abdeckung

AeroNexusAdvanced löst HMS-Kennungen nach DJIs offiziellen Regeln auf:
- \`dock_tip_0xXXXXXXXX\` für DJI-Dock-Fehler,
- \`fpv_tip_0xXXXXXXXX\` am Boden bzw. ohne flugabhängigen Text,
- \`fpv_tip_0xXXXXXXXX_in_the_sky\` für den Flugzustand.

Die Meldung verwendet zuerst den offiziellen deutschen Text (\`de\`),
danach das englische Original (\`en\`). Platzhalter wie \`%alarmid\`,
\`%index\`, \`%component_index\`, \`%battery_index\`,
\`%dock_cover_index\` und \`%charging_rod_index\` werden aus den
übermittelten Argumenten ersetzt. Fehlen die Daten, bleibt der
Platzhalter als \`?\` sichtbar. **Unbekannte Codes werden nicht geraten.**

Die Cloud-API-Level sind 0 = Information, 1 = Erinnerung, 2 = Warnung.
Die Event-Module sind 0 = Flugmission, 1 = Geräteverwaltung,
2 = Medien, 3 = HMS. Diese Werte sind getrennt von den
**fünfstufigen Payload-SDK-HMS-Leveln**.

Die lokalen UI-Seiten \`/status\` und \`/operations\` verwenden die
normalisierte \`device.health\`-Projektion, samt Code, Modul,
deutschem bzw. englischem Beschreibungstext, Dringlichkeit und Flugstatus.

## Vollständigen DJI-HMS-Katalog installieren

Die veröffentlichten DJI-Texte werden **nicht** ins Projekt übernommen.
Der offizielle mehrsprachige Katalog enthält sehr viele Codes und wird
bei Bedarf einmalig per HTTPS heruntergeladen. Ein kleiner Satz an
bekannten RTK-/Signal-Meldungen funktioniert auch ohne Download.

~~~bash
cd ~/Projekte/AeroNexusAdvanced
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python scripts/pi/install_dji_hms_catalog.py
~~~

Das Skript prüft die HTTPS-Zertifikatskette, lehnt Redirects ab, prüft
Dateigröße und JSON-Struktur und schreibt atomar mit Rechten 0600 nach
\`~/.config/aeronexusadvanced/hms.json\`. Es wird **nicht** automatisch
vom Server aufgerufen. Optionaler Pfad:
\`AERONEXUS_HMS_CATALOG_PATH=/absoluter/pfad/hms.json\`.

Originalquelle:
- [DJI Cloud API HMS-Spezifikation](https://github.com/dji-sdk/Cloud-API-Doc/blob/master/docs/en/30.feature-set/20.dock-feature-set/60.hms.md)
- [Original DJI hms.json](https://terra-1-g.djicdn.com/fee90c2e03e04e8da67ea6f56365fc76/SDK%20%E6%96%87%E6%A1%A3/CloudAPI/hms.json)
- [DJI Dock 3 HMS-Event](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dock-to-cloud/mqtt/dock/dock3/hms.html)

## DJI-MQTT-HMS-Events: Opt-in, nur lesend

Die bestehende MQTT-Integration empfängt standardmäßig weiterhin nur OSD
und gegebenenfalls \`state\`. Für vollständige HMS-Events kann zusätzlich

~~~dotenv
AERONEXUS_OSD_HMS_ENABLED=1
~~~

in der produktiven \`.env\` gesetzt werden. Nur dann wird
\`thing/product/+/events\` mit QoS 0 **abonniert**. Dafür muss das
bestehende Broker-Konto *ausschließlich SUBSCRIBE*-Rechte auf diesen
Topic-Filter erhalten. **Keine MQTT-Publish-Berechtigung erteilen.**
Die Anwendung versendet keine MQTT-Kommandos.

Die Anwendung akzeptiert nur \`method="hms"\`, höchstens 20 Alarme
und bekannte Gerätedaten aus dem bestehenden Inventar. Ein HMS-Event
mit leerer Liste gilt als Auflösung aller bisherigen Alarme dieses
Geräts; veraltete Zeitstempel dürfen neuere Warnungen nicht löschen.
Ein HMS-Event allein erzeugt kein Gerät und erneuert keine OSD-Frische.
Gerätezuordnungen werden nicht anhand eines geratenen Gateway-Kontexts
vorgenommen.

**Hinweis:** Das Cloud-API-Event enthält einen Gateway-Topic-Schlüssel.
Bei gemischten Dock-/Aircraft-Events ist ohne eindeutige Gerätezuordnung
keine sichere Zuschreibung an andere Geräte möglich. In diesem Fall
wird lediglich die beim Topic bekannte Identität verwendet, andernfalls
die Meldung ignoriert. Zuordnung und Dock-Alarmtext sollten gegen eine
echte DJI-Dock-Sitzung validiert werden.

## Grenzen

- Der lokale Code kann *alle im installierten DJI-Katalog enthaltenen,
  dokumentierten HMS-Copy-Keys* auflösen. Proprietäre oder später
  eingeführte Schlüssel erscheinen weiterhin als unbekannter Code.
- Die sechsstelligen **Cloud-API-Befehlsergebnis-Codes** sind ein
  anderer Namensraum und werden hier nicht mit HMS-Codes verwechselt.
- Kein automatisches Herunterladen von Übersetzungen, kein Zurücksenden
  von Fehlern an DJI und keine automatischen Reparatur- oder Flugaktionen.
- Das Deployment auf dem Pi bleibt bis zur ausdrücklichen Integration
  und einer kontrollierten Konfigurationsprüfung unverändert.

## Verifizierte Katalog-Abdeckung (DJI-Cloud-API-Demo)

Der von DJI veröffentlichte Beispielkatalog `sample/src/main/resources/hms.json`
enthält derzeit **2.451 HMS-Schlüssel** (2.205 Fluggerät- und 246 Dock-Schlüssel).
Deutsch (`de`) ist für **1.830** Einträge mit nichtleerem Text vorhanden,
Englisch (`en`) für **2.409**. Die Sprachabdeckung unterscheidet sich je
Katalogversion. Fehlende deutsche Einträge werden mit englischem Originaltext
angezeigt, und vollständig unbekannte Schlüssel nur mit Code.

Im HMS-Event steht die Alarmherkunft explizit in `device_type`
(Domäne 0 = Fluggerät, 3 = Dock). Diese Angabe hat Vorrang gegenüber
dem Typ des MQTT-Gateways. Das Gateway kann Meldungen für verschiedene
Geräte übertragen; die Anzeige darf solche Meldungen nicht einem anderen
Gerät nur aufgrund des Topic-Namens zuordnen.
