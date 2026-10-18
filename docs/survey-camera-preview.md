# Kamerabasierte Flugstreifenvorschau (DJI, optisch geschätzt)

## Status und Sicherheitsgrenzen

Die Geo-Studio-Vorschau errechnet unabhängige, an ein Polygon geclippte
Flugstreifen. Sie ist **keine ausführbare Mission**.
Kein DJI-Flugbefehl, kein WPML/KMZ-Export, keine Flug-/Fotoauslösung und keine
Änderung des vorhandenen Mission-Workspace erfolgen über diesen Endpunkt.

Eine Höhe über Gelände wird nicht gegen ein Geländemodell geprüft.
Verbindungswege, Wendemanöver, Hindernisse, Gimbal-Neigung, Luftraum,
Verschlussart, Aufnahmeintervall, Geschwindigkeit, Wind und Akkureserven
werden nicht bewertet.

## Profile

Die Profile stammen aus DJI-Angaben zu maximaler Fotoauflösung und FOV.
Das FOV wird hier als **diagonales** FOV interpretiert, woraus die
Querbreite geschätzt wird. Bei DJI-48-MP-Kameras gilt die GSD nur
für den 48-MP-Fotomodus. Mavic 3M RGB und Multispektral sind getrennt.

| Profil | Auflösung | FOV |
|---|---|---|
| matrice-4e-wide (20 MP) | 5280 × 3956 | 84° |
| matrice-4t-wide (48 MP) | 8064 × 6048 | 82° |
| mavic-3e-wide (20 MP) | 5280 × 3956 | 84° |
| mavic-3t-wide (48 MP) | 8000 × 6000 | 84° |
| mavic-3m-rgb (20 MP) | 5280 × 3956 | 84° |
| mavic-3m-ms (5 MP) | 2592 × 1944 | 73,91° |

Herstellerangaben:
- https://www.dji.com/support/product/matrice-4-series
- https://www.dji.com/support/product/mavic-3-enterprise
- https://enterprise.dji.com/mavic-3-m/specs

## Berechnung

Für Nadir-Aufnahmen im Querformat bei ebenem Gelände:

- D = 2 × Höhe_AGL × tan(FOV_diagonal / 2)
- Querbreite B = D × Pixelbreite / hypot(Pixelbreite, Pixelhöhe)
- Bildlänge L = D × Pixelhöhe / hypot(Pixelbreite, Pixelhöhe)
- GSD_cm/px = 100 × B / Pixelbreite
- Spurabstand S = B × (1 − Seitenüberlappung / 100)
- Auslöseabstand T = L × (1 − Frontüberlappung / 100)
- Fotoanzahl grob = sum(ceil(Streifenlänge / T) + 1) für alle Streifen.

Die Schätzung enthält keine Wende- und Verbindungsfotos. Eine tatsächlich
erreichbare Überlappung hängt von Aufnahmeintervall, Geschwindigkeit,
Kameramodus und Geländehöhe ab.

## Bedienung

1. Mission Studio → **Geo & Gelände**: gespeichertes Polygon auswählen.
2. Im Bereich **Parallele Flugstreifen · Vorschau** optional das DJI-Profil
   wählen. Standard bleibt **Manuell · Spurabstand eingeben**.
3. Höhe, seitliche Überlappung und Frontüberlappung eingeben. Im
   Kameramodus ist das manuelle Spurabstandfeld gesperrt.
4. **Flugstreifen berechnen** klicken; die Karte zeigt unabhängig
   geplante Linien, GSD, Bildmaße, Auslöseabstand und Fotoanzahl.

Die API weist ungültige Kamerawerte und automatisch errechnete
Spurabstände außerhalb von 2–200 Metern mit HTTP 422 ab,
statt sie stillschweigend zu begrenzen.

## Pi-Prüfung ohne produktives Deployment

Feature-PR #66 basiert auf Test-PR #62. Der Produktivdienst bleibt
unverändert. Die Tests laufen mit synthetischen Geo-Objekten.
Testdateien: tests/test_survey_camera.py und
tests/test_survey_camera_chromium.py.

Für den echten Leaflet-Chromium-Test muss
AERONEXUS_LEAFLET_TEST_ASSETS auf SHA256-verifizierte
Leaflet-1.9.4-Dateien zeigen.

Nach einer späteren eigenständigen Bereitstellung muss der optionale
Kameramodus erneut gegen die produktive HTTPS-API geprüft werden.
