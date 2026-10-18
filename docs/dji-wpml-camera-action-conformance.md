# DJI WPML Kameraaktionen: dokumentierte Objektivauswahl (offline)

Stand: 19.10.2026. Diese Änderung betrifft **ausschließlich lokale** KMZ/WPML-
Erzeugung und den Reimport eigener AeroNexusAdvanced-Missionen. Es gibt keine
DJI-Flugbefehle, keinen Missionsupload, keine Aktivierung von PR #44 und keine
Änderung an MQTT, Live-Status, Survey-Vorschau oder dem produktiven Pi-Dienst.

## Referenzstand

- [DJI aktuelle WPML Common Elements](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html),
  Abschnitte `actionActuatorFuncParam / takePhoto` und `startRecord`.
  Diese aktuelle Tabelle nennt M4E/M4T explizit.
- [DJI Cloud-API-Doc englisch](https://github.com/dji-sdk/Cloud-API-Doc/blob/master/docs/en/60.api-reference/00.dji-wpml/40.common-element.md):
  Die ältere englische GitHub-Version führt in den Kameraaktionszeilen nur
  ältere Fluggeräte auf. Dies ist **keine** ausreichende Negativ-Aussage
  zur M4-Kompatibilität.

## Eng begrenzte Änderung

Die bestehenden `takePhoto`- und `startRecord`-Aktionen bekommen
bei den dokumentierten DJI-Fluggeräten zusätzlich:

| Modell | payloadLensIndex | useGlobalPayloadLensIndex |
| --- | --- | --- |
| Matrice 4E | `wide` | `0` |
| Matrice 4T | `wide` | `0` |
| Mavic 3E / 3T / 3M | *nicht gesetzt* | `0` |
| Mavic 3TA | *unverändert* | *unverändert* |

`wide` ist **ausschließlich die Weitwinkelkamera**, keine Wärmebild-
oder Multispektralaufnahme. Weitere Kameralinsen, Kombinationen und
Payload-Kanäle sind nicht neu freigegeben. `0` bedeutet, dass die
Aktionsparameter die globale Objektivwahl nicht verwenden. Andere
Kameraaktionen, einschließlich `stopRecord`, bleiben unverändert.

## Rückwärtskompatibilität und Import-Sicherheitsregel

`import_kmz` erlaubt weiterhin ausschließlich vollständig repräsentierbare
**AeroNexus-eigene** WPML-Dateien mit zwei unterstützten XML-Dokumenten.
Neue Exporte enthalten die dokumentierten Parameter. Beim Reimport
wird exakt **eines** von zwei vollständigen internen Formaten geprüft:
das neue Format oder die bisherige ältere AeroNexus-Kameraaktionsstruktur.
Für einen Import müssen **beide** XML-Dokumente demselben Format entsprechen.
Ein gemischtes Dokumentenpaar, einzelne nachgetragene Kameraelemente,
unbekannte Attribute/Aktionen, abweichende Linsenwerte oder veränderte
Flugparameter bleiben ausgeschlossen. Legacy wird nur intern für diese
Prüfung reproduziert, **nicht** für neue KMZ-Downloads.

## Isolierter Test (kein Drohnenzugriff)

```bash
cd ~/Projekte/AeroNexusAdvanced-wpml-action-review
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_wpml_export.py
```

Die automatisierten Tests decken die Objektivparameter in beiden
XML-Dokumenten, alte KMZ-Dateien, das Re-Export-Upgrade sowie strikten
Ausschluss gemischter Versionen und manipulierter Parameter ab.

**Nicht nachgewiesen** sind DJI-Pilot-2-Import, Modell-/Firmwareakzeptanz,
Linsensteuerung unter realen Bedingungen oder Flugtauglichkeit. Nach
positiver Testausführung muss die erzeugte KMZ zunächst offline in Pilot 2
begutachtet werden. Es darf daraus keine automatische Flugfreigabe entstehen.
