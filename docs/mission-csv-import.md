# CSV-Wegpunkte im Mission Studio

Im Missionseditor **Wegpunkte aus CSV importieren** öffnen, Datei auswählen,
Trennzeichen und Zahlenformat einstellen und **Vorschau prüfen** anklicken.
Die Tabelle zeigt die Dateireihenfolge; die Karte dient zur Lagekontrolle.
**Wegpunkte ersetzen** übernimmt die gesamte geprüfte Route in den aktuellen
Entwurf. Höhe, Geschwindigkeit, Fluggerät, Rückkehr- und übrige Missionswerte
bleiben erhalten. Rückgängig/Wiederherstellen funktioniert; erst **Speichern**
ändert eine gespeicherte Mission. Es erfolgt kein Upload an DJI.

## Dateivertrag

UTF-8 (BOM erlaubt), maximal 512 KiB, mindestens zwei und höchstens 500
ausführbare Wegpunkte. Trennzeichen Semikolon, Komma oder Tabulator explizit
wählen. Bei Dezimalkomma Semikolon oder Tab verwenden. Keine automatische
Erkennung und keine Tausendertrennzeichen.

```csv
latitude;longitude;take_photo
49.1533000;8.5841700;true
49.1535000;8.5844000;false
```

- Pflichtspalten `latitude` und `longitude`, optionale Spalte `take_photo`.
  Die Spaltenreihenfolge darf abweichen, die Bezeichner bestimmen die Bedeutung.
  Leerzeichen am Rand und Groß-/Kleinschreibung der Bezeichner werden normalisiert.
- Ausschließlich WGS84 in Grad. Koordinaten werden auf sieben Dezimalstellen
  gerundet; 0/0 ist auch nach Rundung unzulässig.
- Foto: `true/false`, `1/0`, `ja/nein` oder `yes/no` (ohne Bedeutung der
  Groß-/Kleinschreibung). Leere Fotoangabe oder fehlende Fotospalte: kein Foto.
- Leerzeilen werden ignoriert. Fehlermeldungen beziehen sich auf physische
  Dateizeilen, bei mehrzeiligen CSV-Feldern auf die abschließende Zeile.
- Unbekannte, leere oder doppelte Spalten werden zurückgewiesen. Insbesondere
  werden individuelle Höhen, Geschwindigkeiten, Namen und Aktionsfolgen nicht
  stillschweigend verworfen. Diese erste Version importiert nur die genannten Felder.
- Bei geschlossener Route zählt ein erforderlicher Rückkehrpunkt zum Limit.
  Mindestens drei unterschiedliche Koordinaten sind dann erforderlich.
- Jeder Fehler sperrt die gesamte Übernahme. Es werden höchstens 50 Fehler
  einzeln angezeigt. Über 500 Datenzeilen wird die Prüfung abgebrochen.

Plausible vertauschte Werte können nicht zuverlässig erkannt werden. Lage und
Spalten vor Übernahme prüfen. Die CSV-Beispieldatei im Dialog ist eine reine
Formatvorlage, keine freigegebene Flugroute.

## Technischer Ablauf und Prüfung

`POST /api/v1/studio/missions/preview.csv` nimmt den CSV-Inhalt entgegen.
Optionen: `delimiter=semicolon|comma|tab`, `decimal=dot|comma`,
`close_route=true|false`. Gleicher Zugriffsschutz wie die vorhandenen Studio-APIs.
Die Vorschau erstellt keinen Workspace und speichert weder Datei noch Mission.
Zeilenfehler liefern HTTP 200 mit `valid: false` und leerer `waypoints`-Liste;
Datei-/Formatfehler HTTP 422, Größenüberschreitung HTTP 413.

Automatisierte Prüfung: `python -m pytest -q`. Parser-/API-Grenzen und
KMZ-Roundtrip: `tests/test_mission_csv.py`; UI-Rennen und Undo:
`tests/test_mission_csv_js.py`.

Vor Pi-Abnahme in Chrome und Android prüfen:

1. Bestehende Mission öffnen, eigene ungespeicherte Änderung setzen.
2. CSV-Vorschau öffnen, beide Zahlenformate und Trennzeichen testen;
   Lage und Zeilen kontrollieren, bei >50 Zeilen weitere Zeilen anzeigen.
3. Falsche Spalten/Koordinaten prüfen: keine Übernahme möglich.
4. Datei-/Formatwechsel während des Ladens und Schließen per Escape prüfen;
   langsame/fehlende Verbindung muss wiederholbar bleiben.
5. Übernehmen, rückgängig, wiederherstellen: Missionswerte und ID bleiben erhalten.
6. Speichern, KMZ exportieren, erneut öffnen und Punkte/Fotos vergleichen.
7. Schmale Ansicht: Modalinhalt und Tabelle scrollen, Aktionen erreichbar;
   Tab-Reihenfolge, native Auswahl und Fokus nach Schließen prüfen.

Keine reale Flug- oder Firmwareabnahme durch automatisierte Tests.
