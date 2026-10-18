# DJI Pilot 2 Cloud: einmaliger Upload ausschließlich der synthetischen KMZ-Testdateien

**Stand 19.10.2026.** Dieser Schritt ist eine optionale **schreibende**
Operation an der lokalen DJI Cloud API Demo auf dem Raspberry Pi 5.
Der Pilot-2-Cloud-Server wird nicht von GitHub aus erreicht.
Ein erfolgreiches lokales CI-Ergebnis ersetzt **keine** Live-Upload-Abnahme.
Die Dateien bleiben ausdrücklich **DO NOT FLY**; es findet keine
Missionsplanung, Flugtask-Erstellung, DJI-Gerätesteuerung oder ein Upload
auf FlightHub statt.

Stacked Entwicklung: PR #75 -> PR #77 -> dieser Branch. Alle drei
müssen vor einem allgemeinen Produktionsrollout separat bewertet werden.

## Welche Dateien?

Nur die beiden zuvor erzeugten lokalen Dateien:

- `AeroNexus_WPML_OFFLINE_ONLY_DO_NOT_FLY_MATRICE4T.kmz`
- `AeroNexus_WPML_OFFLINE_ONLY_DO_NOT_FLY_MATRICE4E.kmz`

**Nicht hochladen:** `offline-verification.json`. Die JSON-Datei dient
ausschließlich der lokalen SHA-256-Validierung.

Die Matrice-4T-KMZ ist für den Importtest mit der M4T relevant; die
M4E-Version nicht als M4T-Wayline verwenden. Für jeden Fluggerättyp ist
eine **separate** Übertragung erforderlich.

## 1. Entwicklungsbranch isoliert verwenden

Die ausgegebenen Dateien unter
`/home/mason/wpml-pilot2-offline-20261019-014844` stammen bereits aus
einem lokal bestandenen 81-Test-Lauf. Keine Dateien neu erzeugen.

```bash
set -e
cd ~/Projekte/AeroNexusAdvanced
git fetch origin

git worktree add --detach \
  ~/Projekte/AeroNexusAdvanced-wpml-cloud \
  origin/test/wpml-pilot2-cloud-upload-20261019

cd ~/Projekte/AeroNexusAdvanced-wpml-cloud
PYTHON="$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python"
test -x "$PYTHON" || exit 1
test -z "$(git status --porcelain)" || exit 1

PYTHONPATH="$PWD/src" "$PYTHON" -m pytest -q \
  tests/test_pilot2_fixture_upload.py \
  tests/test_wpml_pilot2_offline_acceptance.py

SOURCE="$HOME/wpml-pilot2-offline-20261019-014844"

# Lokale Datei-/Manifestprüfung, KEIN Netzwerk:
PYTHONPATH="$PWD/src" "$PYTHON" -m aeronexus.pilot2_fixture_upload \
  --source-dir "$SOURCE" --model matrice4t
```

Wenn bereits eine identische Worktree-Kopie existiert, **nicht**
automatisch löschen, überschreiben oder umkonfigurieren. Git und
systemd-Dienst werden hier nicht aktualisiert.

## 2. DJI-Cloud-Verbindung schreibgeschützt prüfen

```bash
cd ~/Projekte/AeroNexusAdvanced-wpml-cloud
PYTHON="$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python"
SOURCE="$HOME/wpml-pilot2-offline-20261019-014844"

PYTHONPATH="$PWD/src" "$PYTHON" -m aeronexus.pilot2_fixture_upload \
  --source-dir "$SOURCE" --model matrice4t --check-cloud
```

Der Client kommuniziert nur mit der bestehenden lokalen Cloud auf
`http://127.0.0.1:6789`, fragt die private Sitzung und die vollständige
Wayline-Bibliothek ab und verweigert bereits vorhandene Dateinamen.

Die Sitzung muss in
`~/.config/aeronexusadvanced/pilot-waylines.json` bereits korrekt und
privat vorhanden sein. **Keine Tokens/Passwörter in Chat, URLs oder
Shell-Verlauf übergeben.** Wenn `cloud_session_missing`,
`cloud_preflight_unavailable` oder `cloud_inventory_incomplete`
erscheint, nicht weiter zum Upload gehen.

## 3. Erst nach erfolgreicher Prüfung EINEN Upload ausdrücklich freigeben

Das Kommando fordert für die M4T die separate Eingabe `UPLOAD MATRICE4T`
an; erst danach erfolgt höchstens **ein** Multipart-POST:

```bash
cd ~/Projekte/AeroNexusAdvanced-wpml-cloud
PYTHON="$HOME/Projekte/AeroNexusAdvanced/.venv/bin/python"
SOURCE="$HOME/wpml-pilot2-offline-20261019-014844"

AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED=1 \
PYTHONPATH="$PWD/src" "$PYTHON" -m aeronexus.pilot2_fixture_upload \
  --source-dir "$SOURCE" --model matrice4t --apply
```

Das Programm prüft noch einmal Sitzung, Bibliothek und Modell und
sendet ausschließlich an
`POST /wayline/api/v1/workspaces/{workspace_id}/waylines/file/upload`.
Der HTTP-Response darf keine automatische Wiederholung auslösen.

- `registered`: neue Route mit dem erwarteten Namen und Modell in der
  Cloud-Bibliothek gefunden. **Noch keine RC-Download- oder Flugfreigabe.**
- `cloud_name_already_exists`: Route schon vorhanden; keine Duplikate
  schreiben, erst in Pilot 2 prüfen.
- `submitted_unverified`, `upload_outcome_unknown` oder
  `upload_rejected_or_outcome_unknown`: Bibliothek manuell prüfen,
  **nicht erneut hochladen**. Der Remote-Endpunkt könnte den
  Schreibvorgang bereits ausgeführt haben.
- `upload_disabled`: absichtlich blockiert, solange der Gate-Parameter
  nicht gesetzt ist.

Optional, **nur wenn ein M4E-Importtest tatsächlich gewünscht ist**:

```bash
# Zuerst separat mit --check-cloud und --model matrice4e prüfen!
AERONEXUS_PILOT_WAYLINE_UPLOAD_ENABLED=1 \
PYTHONPATH="$PWD/src" "$PYTHON" -m aeronexus.pilot2_fixture_upload \
  --source-dir "$SOURCE" --model matrice4e --apply
```

Die zweite Eingabe lautet dann `UPLOAD MATRICE4E`.

## 4. Auf RC Plus 2 nachsehen

DJI Pilot 2 muss mit der **gleichen lokalen Cloud und demselben
Workspace** verbunden sein. Die schreibend registrierte Testwayline
sollte nach Aktualisieren der **Cloud-Wayline-/Routenbibliothek** sichtbar
werden. Zum **Bearbeiten** ist laut DJI ein Download auf die RC
erforderlich. Cloud-Speicherung ist daher nicht mit dem Vorhandensein
einer bearbeitbaren lokalen RC-Datei gleichzusetzen.

Die entsprechende M4T-Testmission ausschließlich **importieren,
anzeigen und prüfen**. **Nicht starten, nicht fliegen und nicht in einen
automatischen Flugauftrag aufnehmen.** Die Koordinaten und Flughöhen
sind synthetisch und nicht freigegeben.

Die lokale Upload-Funktion wurde anhand des optionalen [PR #44](https://github.com/mason82-dotcom/AeroNexusAdvanced/pull/44)
und der [DJI-Pilot-2-Wayline-Verwaltung](https://developer.dji.com/doc/cloud-api-tutorial/en/feature-set/pilot-feature-set/pilot-wayline-management.html)
abgeglichen. Eine Live-End-to-End-Prüfung dieses konkreten Servers ist
noch erforderlich.
