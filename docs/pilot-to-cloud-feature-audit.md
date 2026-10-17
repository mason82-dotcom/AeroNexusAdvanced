# Pilot-to-Cloud Audit und inkrementelle Ergänzungen (17.10.2026)

## Quellen und Abgrenzung

DJI Cloud API (Pilot 2, nicht Cloud API 2 SDK und nicht FlightHub OpenAPI):
- https://github.com/dji-sdk/Cloud-API-Doc/tree/master/docs/en/30.feature-set/10.pilot-feature-set
- https://github.com/dji-sdk/Cloud-API-Doc/tree/master/docs/en/60.api-reference/10.pilot-to-cloud
- https://developer.dji.com/cloud-api/

Die Matrix unterscheidet **AeroNexusAdvanced** (dieses Repository) vom
bestehenden separat bereitgestellten Cloud-Server unter `cloud-server/edge`.
Dessen produktive, gitignorierte Quell-/Containerstände sind NICHT Bestandteil
dieser Repositoryprüfung. Ein passender DJI-Endpunkt beweist nicht, dass die
lokal deployte Upstream-Version ihn fehlerfrei implementiert.

| Pilot-to-Cloud Funktionsgruppe | AeroNexusAdvanced vor Audit | Entscheidung / Status |
|---|---|---|
| Pilot-Anmeldung, Lizenz, Workspace, JSBridge | bestehende externe Pilot-2-Cloud + Session-Handoff | unverändert; kein unkontrolliertes Token-Sharing |
| MQTT OSD / State | vorhandene lesende Integration | behalten |
| Geräte-Topologie (GET `devices/topologies`) | keine direkte lokal-scoped Abfrage | **neu:** /api/v1/local-cloud/topology |
| Situational Awareness / WebSocket Push | Status über andere Quellen; kein aktiver WebSocket-Replay | vorerst keine neue Server-WS; Poll/Cache der Topologie lesend |
| Kartenobjekte (GET `element-groups`) | lokale Studio-Geometrien, keine Cloud-Mirror-Abfrage | **neu:** /api/v1/local-cloud/map-elements mit manuell zuschaltbarer, nicht-interaktiver Studio-Kartenebene |
| Kartenobjekte erstellen/ändern/löschen und WS-Verteilung | nicht implementiert | bewusst nicht automatisch: Cloud-Schreibzugriffe benötigen separates Berechtigungs-, Konflikt- und Versionierungsmodell |
| Wayline-Liste | lokaler, paginierter, rein lesender GET | vorhanden; nur Metadaten, kein Inhaltsgleichheitsnachweis |
| Wayline-Favoriten, Dubletten, Downloadlinks, STS, Upload-Callback | nicht Teil der schreibgeschützten Studio-Schnittstelle | Upstream muss geprüft werden; kein Blind-POST |
| Wayline-Direktupload | noch kein stabiler GUI-Upload | separates Draft-PR #44 für explizit bestätigten CLI-Prototyp, NICHT Teil dieses Branches |
| Medienimport/Upload/Quick-Upload, Fingerprints und Callback | externe Pilot-Cloud speichert Medien, MinIO-Index und Event-Sync lesen sie | kein zweiter Schreibpfad; vorhandene 6095er Stichprobe ist kein Beleg für alle Callback-Verträge |
| Livestream | lokale MediaMTX-Wiedergabe | Aktivierung/Steuerkommandos nicht implementieren, bestehende Anzeige behalten |
| Pilot-Logs per JSBridge | kein verschlüsselter Pilot-Log-Import | gesondertes Projekt: Schlüsselmanagement, Zugriff und Log-Datenschutz |
| Drittanbieter-App / H5-Integration | lokaler Pilot-Webview vorhanden | nicht erforderlich für lesende Pilot-2-Daten |
| DRC / Fernsteuerung, Flugmanöver | nicht vorhanden | **ausgeschlossen:** Sicherheitsgrenze, keine Flugbefehle |
| Dock-, Firmware- und OTA-Funktionen | nicht Teil von Pilot-to-Cloud; Cloud-API-2 separat | nicht vermischen |

## Neue API-Endpunkte

Alle neuen Endpunkte verwenden die existierende Dashboard-Bearer- oder
HTTPS-LAN-Berechtigungsprüfung. Beide senden ausschließlich **GET** an die
feste lokale Loopback-Adresse `http://127.0.0.1:6789`, mit dem validierten
Workspace der privat gespeicherten Sitzung und dem `x-auth-token` nur am
Upstream. Keine Redirects, kein Proxy, keine alternativen Hosts. Antworten
sind auf 1 MiB beschränkt und 20 Sekunden gecacht; Fehler verdrängen den
letzten Erfolg. `Cache-Control: no-store` schützt die Browser-Antwort.

- `GET /api/v1/local-cloud/map-elements`: `state`, `groups`, `features`,
  `crs=EPSG:4326`, `skipped_unsupported`, `complete`, `updated_at`.
  Es werden nur valide GeoJSON-Punkte, Linien und Polygone ausgegeben.
  Nutzername, Cloud-Rohdaten und freie GeoJSON-Properties werden verworfen.
  Keine automatische Übernahme in bearbeitbare Studio-Entwürfe.
- `GET /api/v1/local-cloud/topology`: `state`, `devices`, `links`,
  `complete`, `updated_at`. Enthält nur SN, Rolle, Modell, Rufname und
  Online-Flag; keine Nutzer-IDs, Icon-URLs oder Zugangsdaten.

Fehler sind als `state` sichtbar:
`not_configured`, `awaiting_browser_session`, `configuration_error`,
`authentication_required`, `business_error`, `invalid_response`,
`upstream_error`, `unavailable`. Insbesondere **HTTP 200 mit
`code=-1` ist ein fehlgeschlagener Upstream-Geschäftsvorgang**, kein
funktionierender Endpunkt. Die bislang beobachteten `code=-1`-Antworten
beweisen weder einen funktionierenden Direktupload noch dessen Ursache.
Ein gültiger Token/Workspace und die Server-Logs müssen lokal abgeglichen
werden; das Upstream-`message` wird absichtlich nicht an Browser weitergegeben.

## Sicherer Test auf dem Pi

```bash
cd ~/Projekte/AeroNexusAdvanced
git fetch origin
git switch feature/pilot2-map-topology-audit-20261017
.venv/bin/python -m pytest -q tests/test_pilot2_readonly.py tests/test_local_waylines.py

# Bei bereits aktivem HTTPS-LAN-Modus, nach bewusstem Update und Neustart:
curl --fail --show-error --cacert config/pki/ca.crt \
  https://192.168.178.63:8000/api/v1/local-cloud/map-elements \
  | .venv/bin/python -m json.tool
curl --fail --show-error --cacert config/pki/ca.crt \
  https://192.168.178.63:8000/api/v1/local-cloud/topology \
  | .venv/bin/python -m json.tool
```

Im reinen Bearer-Modus ist zusätzlich der **separate**
Dashboard-`Authorization: Bearer`-Header erforderlich; DJI-Zugangsdaten
nicht im Terminalverlauf oder Chat veröffentlichen.

Die neuen Endpunkte sind gegen Mock-Responses getestet; ein echter Pilot-2-
Livetest bleibt erforderlich. Kein Service wird von diesem Branch gestartet,
keine Datenbank verändert und kein Mission-Upload ausgelöst.

## Studio-Kartenanzeige

Im Mission Studio unter **Karte & Missionen** ist eine Schaltfläche
`Pilot-2-Layer einblenden` vorhanden. Sie lädt die Karte **nur nach Klick**,
zeichnet validierte GeoJSON-Geometrien nicht-interaktiv (kein versehentliches
Einfügen eines Flug-Wegpunkts) und entfernt die Ebene jederzeit wieder.
Die Ansicht bleibt getrennt von editierbaren Studio-Missionen, lokalen
Geo-Objekten und Telemetrie; keine Speicherung oder Rückübertragung.
