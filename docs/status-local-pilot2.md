# Statusseite: lokale DJI Cloud API statt FlightHub

## Umfang

Die Statusseite (`/status`) verwendet den lokalen DJI-Cloud-Server als
primäre Quelle. Der Zugriff auf DJI Pilot 2 bleibt **lesend**:

- **Dienstzustand:** `GET /api/v1/cloud/stack` überwacht Backend, EMQX,
  MinIO, Webfrontend und optional MediaMTX auf Loopback.
- **Fluggeräte und Controller:** `GET /api/v1/status/devices` liest
  aktuelle MQTT-OSD-Werte, inklusive Empfangsalter, Einzel-Feld-Frische und
  zuletzt gültiger Quellzeit; unbekannt ist nicht automatisch offline.
- **Routen:** `GET /api/v1/local-cloud/waylines` verwendet exakt den
  bestehenden `LocalWaylineReader` (begrenzte, authentisierte GET-Abfrage
  an `127.0.0.1:6789`). Der Browser sieht ausschließlich die erlaubten
  Namen, Geräteprofile, Template-Typen und Änderungszeiten.
- FlightHub-Katalog und FlightHub-Polling werden auf der Statusseite
  **nicht** angefordert oder angezeigt. Bestehende FlightHub-APIs und
  andere Module bleiben unverändert.

Die lokale Wayline-Bibliothek unterstützt nur **Metadaten**. Noch nicht über
diesen Adapter verfügbar: KMZ-Dateiinhalte, Karten-Modelle, lokale
Flugaufträge und FlightHub-HMS-Events.

## Zustände und Schutz

`connected` mit leerer Liste bedeutet erfolgreich leer. Andere Zustände
(`not_configured`, `awaiting_browser_session`,
`authentication_required`, `unavailable`, `configuration_error`,
`upstream_error`, `invalid_response`, `inventory_changed`) zeigen
explizit an, warum keine aktuellen Routen vorliegen. Fehlgeschlagene
Abrufe zeigen **keine** zuvor gespeicherten Erfolgskarten als aktuell.
`pagination_complete: false` bedeutet, dass das Abruflimit erreicht
wurde; die UI behauptet dann keine vollständige Bibliothek.

Die API nutzt die bestehende Viewer-Authentifizierung beziehungsweise die
explizit aktivierte direkte HTTPS-LAN-Freigabe. Keine Zugangsdaten,
Browser-Sitzungstoken, DJI-Objektschlüssel oder signierten URLs werden
an den Browser zurückgegeben. Browser-Daten werden mit `textContent`
dargestellt.

## Rollout / read-only Prüfung auf Raspberry Pi 5

Vor jedem Checkout lokale Änderungen prüfen: `git status --short --branch`.
Auf dem bisherigen Feature-Branch können uncommittete Änderungen liegen,
die **nicht** überschrieben werden dürfen.

Bei sicherem Arbeitsbaum / getrenntem Worktree testen:

```bash
.venv/bin/python -m pytest -q tests/test_status_local_cloud.py \
  tests/test_status_mobile_library.py tests/test_status_dashboard_cards.py \
  tests/test_cloud_stack.py tests/test_frontend_javascript.py
```

Die bekannte lokale Cloud-Sitzung aus
`docs/mission-wayline-reconciliation.md` wird wiederverwendet; **kein
erneuter Login nötig**, sofern die vorhandene Session noch gültig ist.
Nach Deployment `/status` auf dem Handy kontrollieren und
`/api/v1/local-cloud/waylines` per authentisiertem GET vergleichen.

## DJI-Mission nach Pilot 2 hochladen: separater Entwicklungsabschnitt

DJI dokumentiert dafür eine Kette aus (1) validiertem WPML/KMZ-Export,
(2) temporären Cloud-Storage-Berechtigungen, (3) Upload des KMZ-Objekts
in den vorgesehenen Wayline-Speicher, (4) Registrierung per
`POST /wayline/api/v1/workspaces/{workspace_id}/upload-callback`
und (5) lesender Prüfung der neuen Wayline-ID in der Bibliothek.

Diese Schritte sind **nicht** Teil der Statusseitenänderung. Insbesondere
ist die bestehende read-only MinIO-Identität keine Berechtigung zum
Wayline-Upload. Vor einer Implementierung müssen Ziel-Bucket,
zugelassener Schreibpfad, STS-/Objektspeicher-Vertrag und Rückfallstrategie
am tatsächlich installierten lokalen Cloud-Server geprüft werden.
Die DJI-MQTT-Verbindung bleibt subscribe-only; automatische Flugstarts
bleiben ausgeschlossen.

Offizielle Referenz:
https://developer.dji.com/doc/cloud-api-tutorial/en/feature-set/pilot-feature-set/pilot-wayline-management.html
