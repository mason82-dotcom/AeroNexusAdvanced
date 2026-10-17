# Lokaler DJI-Pilot-2-Wayline-Upload (separater CLI-Prototyp)

## Ausgangslage

Der DJI-Cloud-Server liefert Wayline-GETs und erlaubt das Lesen der
vorhandenen Bibliothek. Bei read-only Proben auf den drei POST-Endpunkten
wurden HTTP 200, JSON `code:-1` gemeldet. Das ist **kein erfolgreicher
Upload**. Die DJI-Demo-Implementierung enthält zusätzlich zu STS/Upload-Callback
den direkten Multipart-Endpunkt:

`POST /wayline/api/v1/workspaces/{workspace_id}/waylines/file/upload`

Dieser verarbeitet ein Feld `file`, prüft DJI-KMZ-Metadaten, speichert
die KMZ in Objektspeicher und registriert eine Wayline. Ob **genau dieses**
Verhalten in der lokal gebauten Variante `aeronexus/api:local`
funktioniert, bleibt zunächst unbestätigt. Keine produktive Mission oder
vorhandene Cloud-Route wird automatisch verändert.

Referenz:
https://github.com/dji-sdk/DJI-Cloud-API-Demo/blob/main/sample/src/main/java/com/dji/sample/wayline/controller/WaylineFileController.java

## Sicherheitsmodell

- Neues, separat gehaltenes Modul: `aeronexus.pilot_wayline_upload`
- **Standard ist Offline-Vorschau:** Mission anhand einer UUID lokal aus dem
  vorhandenen Workspace lesen; KMZ exportieren und roundtrip-validieren.
- Keine Web-API-Route, keine automatische Cloud-Synchronisierung, kein
  Aufruf aus dem Mission Studio, keine MQTT-Publish- oder Flugbefehle.
- Realer Upload erfordert **alle** Bedingungen:
  `--apply`, `--expect-model` (Bestätigung des Fluggerätetyps),
  `AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED=1`, ein
  interaktives Terminal und die zweite Bestätigung `UPLOAD`.
- Der Upload nutzt ausschließlich den lokal gespeicherten, privat
  berechtigten Pilot-2-Sitzungstoken; keine neuen MinIO-Root-Credentials.
- Vorher prüfen: Session per authentifiziertem GET validieren, vollständige
  Wayline-Liste auslesen, Namenskonflikt verweigern.
- Eindeutiger Dateiname wird intern aus Missions-UUID und zufälliger
  Kennung erzeugt. Keine Pfad- oder Storage-Key-Eingabe durch Nutzer.
- Genau ein POST, Weiterleitungen deaktiviert, 25-Sekunden-Timeout.
  Fehlerantworten werden nur als feste Statuscodes behandelt; keine
  Geheimnisse aus dem Servertext übernehmen oder loggen.
- Nach erfolgreichem POST wird die vollständige Cloud-Bibliothek erneut gelesen.
  Als registriert zählt nur eine Route mit **neu aufgetauchter Wayline-ID,
  passendem Fluggerät und eindeutigem Dateinamen**. Andernfalls **kein
  automatischer Retry**. Der Server kann die Datei bereits gespeichert haben.

## Probelauf (kein Upload)

Ausschließlich im separaten Feature-Worktree, nicht im aktuell
produktiven Quellbaum. Hierzu zuerst eine vorhandene Mission-UUID aus dem
privaten Mission Studio verwenden, **keine** unbekannte Cloud-Wayline-ID.

```bash
cd ~/Projekte/AeroNexusAdvanced-pilot-upload-test
PYTHONPATH="$PWD/src" \
  ~/Projekte/AeroNexusAdvanced/.venv/bin/python \
  -m aeronexus.pilot_wayline_upload --mission '<STUDIO-MISSIONS-UUID>'
```

Diese Vorschau zeigt nur Missionsname, Geräteprofil, Punktanzahl,
KMZ-Größe und den generierten Zielnamen. Sie öffnet keine Cloud-Verbindung.

### Lesende Cloud-Vorabprüfung (kein Upload)

Zunächst eine neue **Mavic-3M-Testmission** im Mission Studio speichern.
Die derzeitige Matrice-4T-Mission darf nicht unbemerkt als M3M gelten.
Danach mit der UUID dieser neu gespeicherten Mission:

```bash
cd ~/Projekte/AeroNexusAdvanced-pilot-upload-test
PYTHONPATH="$PWD/src" \
  ~/Projekte/AeroNexusAdvanced/.venv/bin/python \
  -m aeronexus.pilot_wayline_upload \
  --mission '<M3M-STUDIO-MISSIONS-UUID>' \
  --expect-model mavic3m --check-cloud
```

Der Befehl prüft ausschließlich Benutzer-Sitzung und Wayline-Bibliothek
mit GET. `--expect-model mavic3m` erzwingt die Modellkontrolle bereits
vor dem ersten Netzwerkkontakt. Kein Upload und keine Flugausführung.

**`--apply` vorerst nicht ausführen.** Erst einen ausdrücklich
freigegebenen Testupload nach Backend-Verifikation durchführen.

**Einen echten Upload erst ausführen, wenn der zuvor geprüfte Backend-Build
und eine ungefährliche Testmission ausdrücklich freigegeben wurden.**
Die Bestätigung, Gerätetyp, Höhenbezüge, Sicherheitseinstellungen und
spezielle Multispektralparameter müssen vor dem Einsatz in DJI Pilot 2
manuell geprüft werden. WPML-Export ist keine Flugfreigabe.

## Noch offen

- Live-Abnahme eines einzelnen bewusst freigegebenen Testuploads am
  tatsächlich installierten Backend mit positivem Bibliotheks-GET.
- Klären, wie die Backend-Version gemeldete Namenskonflikte sowie einen
  bereits gespeicherten MinIO-Gegenstand bei nachträglichem SQL-Fehler behandelt.
- Erst nach bestandener Abnahme eine explizite **Upload-Schaltfläche**
  im Mission Studio entwerfen; wegen der bestehenden passwortlosen
  LAN-Betriebsart muss diese schreibende DJI-Funktion einen separaten,
  starken Zugriffsschutz erhalten.
