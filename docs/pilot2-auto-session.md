# DJI RC Plus 2: automatische Cloud-Sitzung nach einmaliger Kopplung

**Status:** Umsetzung im Repository; bis zur Ausführung auf dem Pi nicht aktiv.

## Verhalten

Die lokale DJI-Pilot-2-Seite \`http://192.168.178.63:8085/pilot-login\`
zeigt nach einem bereits erfolgreichen Pilot-Login zunächst **keine
Anmeldemaske** mehr. Sie ruft den vorhandenen authentifizierten Endpunkt
\`POST /manage/api/v1/token/refresh\` mit dem vorher gespeicherten
\`x-auth-token\` auf. Nach erfolgreicher Antwort prüft sie:

- dass die DJI-JSBridge die Lizenz bestätigt;
- dass der Server eine gültige Antwort mit einem neuen Token zurückgibt;
- dass der Benutzer weiterhin den Typ **Pilot (2)** hat;
- dass Benutzername und Workspace mit der vorhandenen lokalen Kopplung
  übereinstimmen;
- dass das DJI-API-Modul geladen und der neue Token gesetzt werden kann.

Erst dann wird ohne Eingabe auf \`/pilot-home\` navigiert. Die
\`pilot-home\`-Seite erneuert die laufende Sitzung zusätzlich alle **2 Stunden**
für längere Einsätze. Kein Passwort, Benutzerkonto oder JWT-Secret wird
fest in den Browser-Code geschrieben oder im Browser gespeichert.

**Erste Kopplung:** Ist noch kein Pilot-Token vorhanden, erscheint
einmalig die normale Benutzername-/Passwortmaske (ohne
hinterlegtes Standardpasswort). Mit dem bestehenden
Pilot-Konto anmelden; für die RC Plus 2 kann das der
separate \`pilot2\`-Benutzer oder der konfigurierte Pilot-Benutzer sein.

**WLAN-Aussetzer:** Der Browser zeigt „Erneut verbinden“ statt ein
neues Passwort zu verlangen. Die lokal gespeicherte Sitzung bleibt erhalten.
**Neu koppeln** löscht die lokal gespeicherten Pilot-Sitzungsdaten erst
nach explizitem Klick und zeigt dann die Anmeldemaske.

**Abgemeldet / Browserdaten gelöscht:** Eine erneute einmalige Kopplung
ist notwendig. Eine Garantie „für immer ohne Anmeldung“ ist nicht möglich,
wenn der RC-WebView-Speicher gelöscht wird, die Lizenz ungültig wird oder
der Server eine Sitzung verweigert. Die Web-Admin-Anmeldung auf \`/\`
wird **nicht** verändert.

## Sichere Bereitstellung auf dem Pi

\`\`\`bash
cd ~/Projekte/AeroNexusAdvanced
git pull --ff-only
python3 scripts/enable_pilot_autologin.py
\`\`\`

Die erste Ausführung ist **nur lesend** und prüft, ob der bereits
migrierte gepatchte DJI-Vue-Quellcode die erwarteten Login-Anker enthält.

Danach:

\`\`\`bash
python3 scripts/enable_pilot_autologin.py --apply
\`\`\`

Das Skript ändert **nur** zwei Dateien in
\`cloud-server/edge/runtime/upstream/web/src/pages/page-pilot/\`:

- \`pilot-index.vue\` — bedingte erste Kopplung + auto-login nur
  mit signiertem bestehendem JWT;
- \`pilot-home.vue\` — zeitgesteuerte Sitzungsverlängerung.

Alte Dateien werden geschützt unter
\`cloud-server/edge/pilot-session-backup/\` aufbewahrt. Keine Backend-Änderung,
keine neuen Passwörter und keine automatischen Containerstarts.

Zum Bauen die **bestehende** isolierte Branding-Compose verwenden.
Die zuvor erstellte Vorlage \`compose.brand.yaml\` bleibt unverändert:

\`\`\`bash
cd ~/Projekte/AeroNexusAdvanced/cloud-server/edge

docker compose -f compose.core.yaml -f compose.brand.yaml build control

# Nur wenn der Build erfolgreich ist:
docker compose -f compose.core.yaml -f compose.brand.yaml \
  up -d --no-deps --no-build --pull never control

docker inspect aeronexusadvanced-cloud-control-1 \
  --format 'Image: {{.Config.Image}} | Status: {{.State.Status}}'

curl -sS -o /dev/null \
  -w 'Pilot-2-Webseite: HTTP %{http_code}\n' \
  http://127.0.0.1:8085/pilot-login
\`\`\`

Das neue Image heißt weiterhin \`aeronexusadvanced/control:branded\`.
Der schon laufende Frontend-Container wird erst nach dem erfolgreichen
Build ersetzt; MySQL, EMQX, Redis, MinIO und DJI-API werden nicht
neu gestartet. Das originale Image \`aeronexus/control:local\` bleibt
für den Rückfall erhalten:

\`\`\`bash
docker compose -f compose.core.yaml \
  up -d --no-deps --no-build --pull never control
\`\`\`

Danach **an der RC Plus 2** prüfen:

1. Cloud Services → Open Platform → AeroNexusAdvanced.
2. Wenn noch nie angemeldet, einmal den **Pilot**-Zugang eingeben.
   Kein Standardpasswort wird mehr vorausgefüllt.
3. Die DJI-Cloud-Seite schließen und erneut öffnen.
   Nach kurzer „Verbindet automatisch“-Anzeige erscheint direkt
   \`pilot-home\`; kein Login-Formular.
4. Bei getrenntem WLAN erscheint „Erneut verbinden“.
   Netzwerk wiederherstellen und klicken.
5. Auf dem Pi den MQTT-Clientstatus über
   \`docker exec aeronexusadvanced-cloud-emqx-1 emqx ctl clients list\`
   prüfen. Ein HTTP 200 auf dem Login-Pfad beweist noch **keine**
   erfolgreiche DJI-/MQTT-Kopplung.

## Sicherheit und Grenzen

Die DJI-Lizenzprüfung wird **nicht entfernt**. Cloud-API-Pilot-Token
bleiben notwendige Signaturen, MQTT bleibt authentifiziert; Flugbefehle
werden durch das Auto-Login nicht neu implementiert. Die Anzeige in
AeroNexusAdvanced auf Port 8000 bleibt schreibgeschützt und die
FlightHub-EU-Anbindung bleibt unberührt.

Der bestehende DJI-Beispielserver (seit 2025 ohne Wartung) besitzt ein
**Sicherheitsproblem**: Sein \`refreshToken\`-Code erneuert sogar abgelaufene
signierte JWTs, ohne eine maximale Sitzungsdauer oder Widerrufsliste.
Diese Änderung führt den Mangel **nicht erst ein**, nutzt aber den
vorhandenen Mechanismus. Daher eine verlorene RC **nicht allein durch
Ändern des Pilot-Passworts** als abgemeldet betrachten; in so einem Fall
Token-/JWT-Schlüssel oder echte serverseitige Sitzungswiderrufe einplanen.
JWT-Schlüsseländerungen invalidieren ebenfalls andere Cloud-Sitzungen
und müssen geplant werden.

**Keinen Port ins Internet weiterleiten.** Die Pilot-Seite auf Port
8085 und API auf 6789 nutzen zurzeit unverschlüsseltes HTTP innerhalb
des LAN. Dabei können Zugangsdaten und Tokens von Mitlesern im Netz
erfasst werden. Für dauerhaft sicheren Betrieb HTTPS mit für die RC
vertrauenswürdigem Zertifikat und einen vertrauenswürdigen LAN-/VLAN-
Zugang vorsehen. Keine DJI-Lizenz, Passwörter oder \`docker compose config\`
mit interpolierten Umgebungsvariablen im Chat oder in GitHub posten.
