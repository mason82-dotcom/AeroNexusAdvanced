# Dokumentation – AeroNexusAdvanced

**Stand der Gliederung: 18.10.2026.** Die meisten Phasenberichte dokumentieren den Entwicklungszustand zum Zeitpunkt ihrer Erstellung. Sie sind **keine laufend aktualisierte Betriebsfreigabe**. Beginne mit den Hauptdokumenten, nicht mit alten PR-/Checkpoint-Angaben.

## Einstieg und sichere Inbetriebnahme

| Thema | Maßgebliche Referenz |
| --- | --- |
| Überblick und Installation | [Projekt-README](../README.md) |
| Repository-Stand, offene PRs und belegte Betriebsgrenzen | [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| Pi-systemd, HTTPS und Zertifikate | [deploy-pi.md](deploy-pi.md) |
| LAN-Zugriffsrechte und Sicherheitswarnungen | [phase-14-token-free-lan.md](phase-14-token-free-lan.md) |
| Lokaler Cloud-Server: früherer Migrationsablauf | [local-cloud-server-migration.md](local-cloud-server-migration.md) |
| DJI Pilot 2: vorhandene Sitzung und Geräte | [pilot2-auto-session.md](pilot2-auto-session.md) |
| Produktive API-Prüfung (GET-only) | [production-ui-readonly-audit.md](production-ui-readonly-audit.md) |
| Realer Chromium-/HTTPS-Test | [production-ui-browser-audit.md](production-ui-browser-audit.md) |

## DJI, Telemetrie und Betrieb

- [Live-Telemetrie-Cockpit](live-telemetry-cockpit.md) – Oberfläche, Datenalter, GPS/RTK, Kamera, RC und Grenzen
- [Cloud API MQTT / OSD](phase-9-cloud-api-live-feed.md) und [Cloud-API-1.18-Feldabbildung](cloud-api-118-telemetry.md)
- [HMS-Codes und deutscher Meldungskatalog](dji-cloudapi-hms.md)
- [FlightHub-Flottenanbindung](phase-10-flighthub-fleet.md) und [Quellenvergleich / Operations](phase-15-dji-sources-operations.md)
- [DJI Cloud API 2: separate SDK-Bridge](phase-18-cloudapi2-rollout.md) (historischer Versionsvergleich, kein Live-Release-Feed)
- [Lokaler Pilot-2-Status](status-local-pilot2.md), [Live-Stream / MediaMTX](livestream.md)
- [Geräte- und Modellcodes](pilot2-device-model-codes.md), [Pilot-2-Aktionskatalog](dji-pilot2-action-support.md)

## Studio, Missionsplanung und Geodaten

- [Cockpit mit Kartenfläche und Missionsinspektor](cockpit-ui.md) – Bedienkonzept nach OpenDroneKit als visueller Referenz

- [Mission Studio](phase-13-desktop-mission-studio.md), [Mission-/Wayline-Abgleich und Grenzen](mission-wayline-reconciliation.md)
- [CSV-Wegpunktimport](mission-csv-import.md), [WPML Kamera/Gimbal](dji-wpml-camera-gimbal-export.md)
- [Pilot-2-Wayline-Parameter](pilot2-wayline-parameter-audit.md), [Geometrievergleich](pilot2-wayline-geometry-compare.md)
- [GeoPhoto-/Survey-/Geländefunktionen](phase-17-geo-photo-survey-terrain.md)
- [Interaktives Terrain](phase-18-interactive-terrain.md), [Georeferenziertes Terrain](phase-19-georeferenced-terrain.md), [DEM-Neigung](phase-20-terrain-slope.md)
- [Foto- und Kartenprüfung](photo-catalog.md), [Rasterergebnisse](raster-results.md)

## Medien, Verarbeitung und Zusatzmodule

- [DJI-MinIO-Medien: aktueller Katalog](phase-21-dji-minio-media.md)
- [Automatischer Medien-Sync](media-auto-sync.md)
- [Thermal und PV](thermal.md), [Multispektral / Mavic 3M](multispectral.md)
- [Metashape-Workflow](metashape-integration.md)
- [Webbranding für lokalen DJI-Cloud-Server](pilot2-web-branding.md)
- [DJI-Cloud-Control-Vue: professionelle UI-Gestaltung, sichere Vorbereitung und Rückfall](dji-vue-modern-ui.md)
- [Port 8085: neues Control Center und optionale native FlightHub-2-Komponenten](control-portal-fh2.md) – sicherer Compose-Overlay, Freigabegrenzen und Rückfall

## Validierung und historische Entwicklungsprotokolle

Die nachstehenden Dokumente sind für Regressionen und forensische Nachvollziehbarkeit nützlich, ersetzen aber **keine** aktuelle Live-Abnahme:

- [Studio-Chromium-Abnahme mit synthetischen GET-Antworten](studio-full-ui-acceptance.md), [Standalone-UIs](standalone-ui-acceptance.md)
- [Phase 17 – Pi-Validierung](phase-17-pi-validation.md)
- [Frühe Gerätediscovery](phase-8-5-device-discovery.md), [Gerätezustand](phase-8-6-aircraft-state.md), [Flottenstatus](phase-8-7-fleet-status.md), [Dashboard-Diagnostik](phase-11-dashboard-diagnostics.md)
- [Pilot-zu-Cloud-Vergleich](pilot-to-cloud-feature-audit.md)
- [Archivierte Projektstatus-Chronik](archive/PROJECT_STATUS-2026-10-17.md)
- [Checkpoint vom 17.10.2026](archive/project-checkpoint-2026-10-17.md)
- [Frühere Phase-19-Live-Cockpit-Notizen](archive/phase-19-dji-live-cockpit.md)
- [Alte Phase-20-MinIO-Indexmigration](archive/phase-20-dji-minio-media-index.md)

## Pflege der Dokumentation

Neue Funktionen bekommen **eine** primäre fachliche Anleitung; veraltete Checkpoints werden unter `archive/` mit Datumsvermerk abgelegt. `PROJECT_STATUS.md` enthält nur den aktuellen **Repository-Stand**, offene Risiken und den letzten getrennt belegten **Pi-Stand**. Veraltete Versionszahlen und PR-Status nicht als aktuellen Fakt wiederholen. Die lokale `.env`, Zertifikate, Tokens und Gerätekennungen dürfen niemals Bestandteil öffentlicher Dokumente oder Logs sein.

- [FlightHub-orientierter Premium-Arbeitsbereich auf Port 8085](flighthub2-premium-workspace.md) – Schnittstellen, UI-Vertrag und sichere Rückkehr zum Original-DJI-Webcontainer.
