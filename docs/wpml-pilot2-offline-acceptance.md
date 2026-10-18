# DJI Pilot 2: kontrollierte WPML-Offline-Abnahme (Matrice 4E / 4T)

Stand: 19.10.2026. Diese Anleitung beschreibt eine **rein lokale** und
synthetische Abnahmevorbereitung. Das Skript **importiert nichts in DJI Pilot 2**,
startet keine Drohne, lädt keine Mission hoch und verändert weder den
AeroNexusAdvanced-Produktivdienst noch die lokalen Cloud-Dienste.

Die Entwicklung baut auf der Kameraaktionskorrektur aus [PR #75](https://github.com/mason82-dotcom/AeroNexusAdvanced/pull/75)
auf und bleibt bis zur manuellen Sichtprüfung getrennt von `main`.

## 1. Artefakte auf dem Pi erzeugen (offline)

Für die Prüfung eine **isolierte Arbeitskopie** des hier angegebenen
Entwicklungsbranches verwenden. Es ist keine Aktualisierung oder
Neustart des systemd-Dienstes nötig.

```bash
cd ~/Projekte/AeroNexusAdvanced-wpml-offline
test "$(git branch --show-current)" = "test/wpml-pilot2-offline-acceptance-20261019" || exit 1
test -z "$(git status --porcelain)" || exit 1
test -x .venv/bin/python || exit 1

PYTHONPATH="$PWD/src" .venv/bin/python -m pytest -q \
  tests/test_wpml_export.py \
  tests/test_wpml_pilot2_offline_acceptance.py

OUTPUT="$HOME/wpml-pilot2-offline-$(date +%Y%m%d-%H%M%S)"
PYTHONPATH="$PWD/src" .venv/bin/python \
  scripts/pi/wpml_pilot2_offline_acceptance.py \
  --output-dir "$OUTPUT"

ls -la "$OUTPUT"
PYTHONPATH="$PWD/src" .venv/bin/python -m json.tool \
  "$OUTPUT/offline-verification.json"
```

Voraussetzung: separate vorhandene Checkout-Umgebung mit Python und dem
installierten Projekt. Das Skript erstellt **nur** ein neues Verzeichnis
(Modus 0700), zwei KMZ-Dateien und einen JSON-Prüfbericht (Dateimodus 0600).
Vorhandene Ausgabeverzeichnisse werden verweigert, nicht überschrieben.
Die generierten Dateien werden niemals zu Git hinzugefügt.

Dateien:

- `AeroNexus_WPML_OFFLINE_ONLY_DO_NOT_FLY_MATRICE4E.kmz`
- `AeroNexus_WPML_OFFLINE_ONLY_DO_NOT_FLY_MATRICE4T.kmz`
- `offline-verification.json`

Beide KMZ enthalten ausschließlich `wpmz/template.kml` und
`wpmz/waylines.wpml` für einen **synthetischen**, ausdrücklich
nicht zur Flugausführung freigegebenen Wegpunkttest.
Die Testpunkte wurden nicht vor Ort vermessen. Ein Beispiel importiert
keine echten Auftragsdaten und sollte niemals als reale Flugroute
verwendet werden.

Die lokale Validierung prüft u. a. ZIP-CRC, Dateinamen, XML-
Namespaces, M4E/M4T-Aircraft-/Payload-Enums, Wegpunktnummerierung,
`takePhoto`, `startRecord`, `stopRecord` und bei Foto-/Videostart
`payloadLensIndex=wide` sowie `useGlobalPayloadLensIndex=0`.
Zusätzlich muss der strenge AeroNexus-eigene KMZ-Reimport dieselbe
Mission zurückliefern.

Der JSON-Bericht enthält SHA-256 je KMZ, **keine** Testkoordinaten und
keine Zugangsdaten. Zwei einzelne Läufe können unterschiedliche KMZ-
SHA-256 ergeben, weil die ZIP-Metadaten Zeitstempel enthalten können;
der Hash schützt nur das konkrete jeweils erzeugte Testartefakt.

## 2. Manuelle Abnahme in DJI Pilot 2

Die Datei wird **nur zur Prüfung der Import-Kompatibilität** auf die
Fernsteuerung kopiert. Kein automatischer Pilot-2-Upload, keine
Cloud-Wayline-Veröffentlichung und vor allem **kein Start einer Mission**.

1. Vorab Fluggerätmodell, Fernsteuerung, DJI Pilot-2-Version und
   Firmwareversion lokal dokumentieren, aber keine Seriennummern oder
   Zugangstokens in GitHub speichern.
2. Die passende KMZ für M4E beziehungsweise M4T auf die RC Plus 2
   kopieren und in der lokalen Routenverwaltung von DJI Pilot 2 den
   Importdialog verwenden, sofern die Version diese Funktion unterstützt.
3. Ohne Flugausführung dokumentieren, ob DJI Pilot 2 das Archiv annimmt.
   Ablehnungstext oder ungeklärte Einstellungen wörtlich erfassen.
4. Falls Import erfolgreich ist: Fluggerät-/Payload-Typ, drei Wegpunkte,
   Höhenreferenz (relativ zum Startpunkt), Fluggeschwindigkeit, RTH,
   Fotoaktion und Video-Start/Stopp im Editor überprüfen.
5. Bei fehlenden, abgewandelten oder widersprüchlichen Parametern
   **nicht fliegen und keine automatische Korrektur annehmen**.
6. Importierte Testmission nach Sichtprüfung nicht als einsatzbereit
   markieren; sie darf nicht auf die Drohne ausgeführt werden.

### Abnahmeprotokoll (ohne vertrauliche Kennungen)

| Prüfung | M4E | M4T |
| --- | --- | --- |
| KMZ in Pilot 2 lesbar | offen | offen |
| Aircraft-/Payload-Zuordnung korrekt | offen | offen |
| Wegpunkte 3 / WGS84 korrekt | offen | offen |
| Foto- und Videoaktionen sichtbar | offen | offen |
| Höhenreferenz und RTH korrekt | offen | offen |
| Fehlermeldungen / Firmware-Besonderheiten dokumentiert | offen | offen |
| Flugfreigabe erteilt | **NEIN** | **NEIN** |

## 3. Abgrenzung

- Strukturell valider XML-Export ist **kein** Nachweis der tatsächlichen
  Kompatibilität von Firmware, Pilot 2, Kameraaktionen oder
  Geländesicherheit.
- Exportmissionen können bei manueller Auswahl potenziell ausführbar sein.
  Daher ausschließlich für die beschriebene Import-/Sichtprüfung nutzen.
- Keine Verbindung zur schematischen Survey-Vorschau und keine
  Vereinheitlichung von AGL- und Startpunkt-Höhen.
- Ohne ausdrücklich dokumentiertes Ergebnis von Pilot 2 bleibt
  `dji_pilot2_import_verified=false`; es gibt **keinen** automatischen
  Umschalter in einen freigegebenen Zustand.

Quellen: [DJI WPML Common Elements](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html),
[DJI WPML Format](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/overview.html),
[DJI Pilot 2 Wayline-Verwaltung](https://developer.dji.com/doc/cloud-api-tutorial/en/feature-set/pilot-feature-set/pilot-wayline-management.html).
