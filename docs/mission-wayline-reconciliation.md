# Missionen und Waylines abgleichen

Stand 17.10.2026. Es gibt drei getrennte Bestände: lokale Studio-Entwürfe,
FlightHub-Public-Cloud-Waylines/Flugaufträge und die Wayline-Bibliothek des
lokalen Pilot-2-Cloud-Servers. Der neue Bericht vergleicht die ersten beiden
anhand bereits gelesener Metadaten. Er verbindet sich nicht mit dem lokalen
Pilot-2-Cloud-Server und kennt dessen Routenbestand nicht.

## Missionsprofile

| Studio-Profil | Fluggerät-Typ | Untertyp | Kamera-Typ |
|---|---:|---:|---:|
| Mavic 3E | 77 | 0 | 66 |
| Mavic 3T | 77 | 1 | 67 |
| Mavic 3M | 77 | 2 | 68 |
| Mavic 3TA | 77 | 3 | 129 |
| Matrice 4E | 99 | 0 | 88 |
| Matrice 4T | 99 | 1 | 89 |

Kamera-Untertyp und Nutzlastposition sind jeweils 0. Geräteauswahl und Export
verwenden dieselbe Profiltabelle. Speichern, Laden, CSV-Punktübernahme, KMZ-Export
und Re-Import behalten das gewählte Profil. CSV-Dateien enthalten weiterhin nur
Punkte, keine automatische Gerätemodell-Erkennung.

Dies erweitert den bestehenden Wegpunktmodus. Es erzeugt keine Mapping-Flächen,
Multispektral-Bandwahl, Thermal-Linsenauswahl oder neuen Kameraaktionen. Ein
M3M-Profil bedeutet nicht, dass der Export eine kalibrierte MS-Aufnahme erzeugt.
Firmware-/Pilot-2-Akzeptanz und reale Flugprüfung bleiben separat erforderlich,
insbesondere für M3TA. Keine Mission wird an ein Fluggerät gesendet.

## Konsistenzprüfung beim KMZ-Import

Nur eigene AeroNexus-Wegpunktdateien werden importiert. Aus der eingelesenen
Mission werden beide unterstützten XML-Dokumente erneut aufgebaut und mit den
vollständigen eingelesenen Dokumenten verglichen. RTH, Start-/Flughöhe, globale
und individuelle Geschwindigkeit, Modell/Nutzlast, Koordinaten, RC-Verlustregel,
Richtungs-/Kurvenparameter, Aktionsgruppen und Fotoaktionsparameter dürfen nicht
widersprechen oder beim erneuten Export verloren gehen. Zusätzliche Attribute,
Elemente oder Duplikate werden ebenfalls abgelehnt. Ein Autor-Text allein reicht
nicht als Nachweis eines unterstützten Dateiformats.

XML-Präfixe, Einrückung und die beiden numerischen Erstellungs-/Änderungszeiten
sind nicht Teil der Flugsemantik. Sonst ist der Vergleich bewusst streng,
einschließlich der von AeroNexus erzeugten Zahlenformatierung und Reihenfolge.
Extern umformatierte oder erweiterte DJI-Dateien können daher abgelehnt werden.
Eine abgelehnte Datei wird nicht als neue Mission gespeichert.

## Lesender Metadatenbericht

`GET /api/v1/studio/missions/reconciliation`

Gleicher LAN-/Bearer-Schutz wie die Studio- und FlightHub-Daten-APIs;
`Cache-Control: no-store`. Kein neuer öffentlicher Zugriff. Keine externe
Abfrage, Schreiboperation oder automatische Verknüpfung. Der Aufruf liest den
vorhandenen FlightHub-Cache und die gespeicherten lokalen Missionsmetadaten.

- `missions`: lokale ID, Name, Profil und Anzahl editierbarer Punkte; bis zu zehn
  Namenskandidaten je Mission mit Anbieter, Projekt, Cloud-Wayline-ID, Modell,
  Cloud-Änderungszeit und Dateigröße. `candidate_count` zählt auch weitere Treffer.
- `waylines`: alle im Cache vorhandenen Cloud-Routen einschließlich Template-Typ.
  Mapping-Routen werden dadurch nicht in bearbeitbare Wegpunktmissionen verwandelt.
- `flight_tasks`: getrennte Aufträge mit Status und `wayline_link=unavailable`.
  Der vorhandene normalisierte Task-Katalog enthält keine belastbare Wayline-ID;
  selbst gleiche Namen werden nicht als Verbindung ausgegeben.
- `projects`: unterscheidet nicht lesbare von erfolgreich leeren Sammlungen und
  markiert Sammlungen am derzeitigen 200-Einträge-Limit.
- `catalog_updated_at`: vorhandener globaler Cache-Zeitnachweis, keine Garantie,
  dass jede einzelne Sammlung erfolgreich oder vollständig aktualisiert wurde.

Namen werden nach NFC-Normalisierung, Groß-/Kleinschreibung und Leerzeichen
verglichen. Das ist ausschließlich ein Suchhinweis. `model_match` ist
true/false/null; auch gleicher Name und gleiches Modell liefern immer
`verification=name_only` und `content_match=null`. Routeninhalt, Prüfsumme und
Dateiversion sind nicht verifiziert. Doppelte Namen bleiben mehrdeutig.

Ohne Treffer lautet der Zustand `no_candidate_in_cache`, niemals „gelöscht“ oder
„fehlt sicher in der Cloud“. Der Cache kann leer, deaktiviert, veraltet,
unvollständig oder teilweise nicht lesbar sein. Tasks umfassen derzeit nur die
letzten 30 Tage, Sammlungen höchstens 200 Einträge je Projekt. Der Bericht
beansprucht keine vollständige Inventur. Private Dateien und Cloud-Daten bleiben
unverändert; URLs, Zugangsdaten und Missionskoordinaten werden nicht ausgegeben.

Auf dem konfigurierten Pi im direkten HTTPS-LAN nach Installation dieses Standes:

```bash
cd ~/Projekte/AeroNexusAdvanced
curl --fail --show-error --max-time 15 \
  --cacert config/pki/ca.crt \
  https://192.168.178.63:8000/api/v1/studio/missions/reconciliation \
  | .venv/bin/python -m json.tool
```

Im Token-Modus denselben geschützten Zugang wie beim bestehenden Studio verwenden;
keine Token in Chat-Ausgaben kopieren. Es gibt in diesem Änderungssatz keine neue
Vergleichsseite; der Bericht ist über die API zugänglich.

## Quellen und Prüfung

- [DJI Produkt-/Kameraindizes, einschließlich M3TA](https://developer.dji.com/doc/cloud-api-tutorial/en/overview/product-support.html)
- [DJI WPML-Indizes M3E/M3T/M3M](https://github.com/dji-sdk/Cloud-API-Doc/blob/master/docs/cn/60.api-reference/00.dji-wpml/40.common-element.md)
- [DJI WPML gemeinsame Elemente](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html)
- [DJI Pilot-2-Wayline-Verwaltung und lokale Kopien](https://developer.dji.com/doc/cloud-api-tutorial/en/feature-set/pilot-feature-set/pilot-wayline-management.html)

Regressionen: alle sechs Geräteprofile mit geschlossener Route/Fotoaktion,
veränderte RTH-/Geschwindigkeits-/Aktionsparameter, unbekannte/mehrfache XML-Felder,
Speichern/Laden/Export/Re-Import über die API, API-Zugriffsschutz, fehlende Quellen,
Namensmehrdeutigkeit und Modellkonflikte. Chromium war lokal nicht verfügbar;
der Installationsversuch lieferte defekte Downloadarchive. Echte Browserprüfung
der erweiterten Geräteauswahl und Pi-/Pilot-2-Abnahme stehen aus.
