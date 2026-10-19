# DJI WPML: vollständiger Pflichtfeldabgleich nach Anwendungsfall

**Datum:** 19.10.2026 · **Prüfstand:** AeroNexusAdvanced Draft-PR #82
(`feat/wpml-heading-turn-offline-20261019`), DJI WPML Namespace 1.0.2.

**Dies ist kein Nachweis für eine erfolgreiche DJI-Pilot-2-Einfuhr, keine
Firmware-Kompatibilitätsbescheinigung und keine Flugfreigabe.**

## Maßgebliche DJI-Tabellen

1. [template.kml](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/template-kml.html): Datei-/Missionsdaten, waypoint-/mapping-/oblique-/strip-spezifische Daten
2. [waylines.wpml](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/waylines-wpml.html): ausführbarer Pfad und Wegpunktdaten
3. [Common Elements](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html): Geräte, Nutzlast, Heading, Kurven, Aktionen

Die englische DJI-Dokumentation listet auch Matrice 4E/4T; eine ältere
öffentliche GitHub-Synchronisierung der DJI-Dokumentation hat teilweise
abweichende Produktlisten. Bei produktspezifischen Feldern hat die
aktuelle DJI-Entwicklerseite Vorrang.

**Methodik:** Jede Dokumentationstabelle wurde nach *Yes*, *conditional*
und *optional/parent optional* getrennt. Nur die zum tatsächlich
exportierten Anwendungsfall passenden Regeln sind zwingend.
Die Testmatrix `tests/test_wpml_required_fields.py` kontrolliert
die emittierten XML-Elemente. Der bestehende strikte Reimport kontrolliert
außerdem, dass keine anderen XML-Parameter beim Roundtrip verloren gehen.

**Zusätzlicher Offline-Checker:** `src/aeronexus/wpml_required_fields.py`
prüft die Pflichtfeld-Präsenz unabhängig vom kanonischen KMZ-Reimport.
`wpml_conformance.audit_kmz` liefert bei wirklich fehlenden Feldern
strukturierte Befunde mit `document`, `field` und `code` statt eines
pauschalen Importfehlers; Missionsdaten und Koordinaten werden nicht
ausgegeben. Die Abdeckung für nicht unterstützte DJI-Vorlagentypen ist
bewusst ausschließlich dokumentarisch, da die Feldbedingungen dort
von weiteren Vorlagentyp-Parametern abhängen. Die DJI-Konformitäts-
und Flugfreigabe-Flags bleiben immer `false`.


## 1. Übergreifende Container- und Missionsfelder

| DJI-Element | Bedingung | Aktueller Stand |
| --- | --- | --- |
| ZIP `wpmz/template.kml` und `wpmz/waylines.wpml` | AeroNexus-Wegpunkt-KMZ | Beide vorhanden; fremde Dateien beim Edit-Import abgewiesen |
| KML-Namespace, `Document`, `Folder` | Beide Dokumente | Vorhanden |
| `missionConfig/flyToWaylineMode` | Beide | Vorhanden: safely |
| `missionConfig/finishAction` | Beide | Vorhanden: goHome oder noAction |
| `missionConfig/exitOnRCLost` | Beide | Vorhanden: executeLostAction |
| `missionConfig/executeRCLostAction` | Bei executeLostAction | Vorhanden: goBack |
| `missionConfig/takeOffSecurityHeight` | Beide | Vorhanden |
| `missionConfig/globalTransitionalSpeed` | Beide | Vorhanden |
| `missionConfig/globalRTHHeight` | waylines.wpml | Vorhanden |
| `droneInfo/droneEnumValue` | Geräteblock | Vorhanden |
| `droneInfo/droneSubEnumValue` | Modellspezifisch | Für alle sechs AeroNexus-Profile vorhanden |
| `payloadInfo/payloadEnumValue` | Nutzlastblock | Vorhanden |
| `payloadInfo/payloadPositionIndex` | Nutzlastblock | Vorhanden: 0 |
| `autoRerouteInfo/missionAutoRerouteMode` | Nur wenn autoRerouteInfo vorhanden | Parent wird nicht erzeugt; beide Unterfelder daher nicht fehlend |
| `autoRerouteInfo/transitionalAutoRerouteMode` | Nur wenn autoRerouteInfo vorhanden | Siehe vorherige Zeile |
| `payloadParam/payloadPositionIndex` | Nur wenn payloadParam vorhanden | Parent im Wegpunkt-Subset nicht vorhanden |
| `payloadParam/imageFormat` | Nur wenn payloadParam vorhanden | Parent im Wegpunkt-Subset nicht vorhanden |
| `author`, `createTime`, `updateTime` | Nicht zwingend | Im template.kml dennoch vorhanden |
| `takeOffRefPoint`, `takeOffRefPointAGLHeight` | Nicht zwingend | Nicht erzeugt; kein Pflichtfelddefizit |

`payloadInfo` und `payloadParam` sind unterschiedliche XML-Blöcke.
Die verpflichtenden Kinder eines **optionalen** Elternblocks bedeuten
nicht, dass der Elternblock auf jeder Mission erzeugt werden muss.

## 2. template.kml – Wegpunktvorlage

| Pflichtfeld | Voraussetzung | Aktueller Stand |
| --- | --- | --- |
| `Folder/templateType` | Wegpunktvorlage | waypoint |
| `Folder/templateId` | Wegpunktvorlage | 0 |
| `Folder/autoFlightSpeed` | Wegpunktvorlage | Vorhanden |
| `waylineCoordinateSysParam/coordinateMode` | Bei Koordinatenblock | WGS84 |
| `waylineCoordinateSysParam/heightMode` | Bei Koordinatenblock | relativeToStartPoint |
| `Folder/globalWaypointTurnMode` | Wegpunktvorlage | Vorhanden |
| `Folder/globalUseStraightLine` | **Genau bei kontinuierlichem Kurven-Stopp oder Kurven-Durchflug** | Für neuen Stopp-Kurvenmodus: 1; Altformat schreibt 1 auch bei geradem Stopp, siehe Abweichung A2 |
| `Folder/gimbalPitchMode` | Wegpunktvorlage | usePointSetting |
| `Folder/globalHeight` | Wegpunktvorlage | Vorhanden |
| `globalWaypointHeadingParam/waypointHeadingMode` | Wenn globalWaypointHeadingParam enthalten | followWayline |
| `globalWaypointHeadingParam/waypointHeadingPathMode` | Innerhalb des Heading-Blocks nach DJI-Referenztabelle | **Fehlt** im globalen Standardblock; Hinweis A1 |
| `Placemark/Point/coordinates` | Je Wegpunkt | Vorhanden: Longitude,Latitude |
| `Placemark/index` | Je Wegpunkt | Vorhanden, fortlaufend |
| `Placemark/useGlobalHeight` | Je Wegpunkt | 1 |
| `Placemark/ellipsoidHeight`, `height` | Nur wenn useGlobalHeight=0 | Nicht erforderlich |
| `Placemark/useGlobalSpeed` | Je Wegpunkt | 1 |
| `Placemark/waypointSpeed` | Nur wenn useGlobalSpeed=0 | Nicht erforderlich |
| `Placemark/useGlobalHeadingParam` | Je Wegpunkt | 1 oder 0 bei opt-in smoothTransition |
| `Placemark/waypointHeadingParam` | Bei useGlobalHeadingParam=0 | Im neuen Modus vorhanden inkl. angle/path |
| `Placemark/useGlobalTurnParam` | Je Wegpunkt | 1 |
| `Placemark/waypointTurnParam` | Bei useGlobalTurnParam=0 | Nicht erforderlich |
| `Placemark/useStraightLine` | Bei entsprechendem lokalen Kurvenmodus | Kein lokaler Turn-Override im Template |
| `Placemark/gimbalPitchAngle` | Bei gimbalPitchMode=usePointSetting | Vorhanden: 0 |

Das globale `waylineCoordinateSysParam/positioningType` ist laut
DJI ausdrücklich **optional** und beeinflusst den Flug nicht;
AeroNexus gibt trotzdem `GPS` aus.

## 3. waylines.wpml – ausführbare Wegpunkte

| Pflichtfeld | Voraussetzung | Aktueller Stand |
| --- | --- | --- |
| `Folder/templateId` | Jede ausgeführte Route | 0 |
| `Folder/waylineId` | Jede ausgeführte Route | 0 |
| `Folder/autoFlightSpeed` | Jede ausgeführte Route | Vorhanden |
| `Folder/executeHeightMode` | Jede ausgeführte Route | relativeToStartPoint |
| `Placemark/Point/coordinates` | Je Wegpunkt | Vorhanden |
| `Placemark/index` | Je Wegpunkt | 0…n-1 |
| `Placemark/executeHeight` | Je Wegpunkt | Vorhanden |
| `Placemark/waypointSpeed` | Bei lokaler Geschwindigkeitsvorgabe; konservativ ausgegeben | Vorhanden |
| `Placemark/waypointHeadingParam` | Je ausführbarem Wegpunkt | Vorhanden |
| `waypointHeadingParam/waypointHeadingMode` | Bei Heading-Block | Vorhanden |
| `waypointHeadingParam/waypointHeadingAngle` | Bei smoothTransition | Vorhanden, -180°…180° |
| `waypointHeadingParam/waypointPoiPoint` | Bei towardPOI | Nicht anwendbar: towardPOI gesperrt |
| `waypointHeadingParam/waypointHeadingPathMode` | Bei Heading-Block laut DJI | Bei smoothTransition vorhanden; **fehlt beim Standardmodus** (A1) |
| `Placemark/waypointTurnParam` | Je Wegpunkt | Vorhanden |
| `waypointTurnParam/waypointTurnMode` | Bei Turn-Block | Vorhanden |
| `waypointTurnParam/waypointTurnDampingDist` | Nur bei mode=coordinateTurn oder Durchflugkurve und dokumentierter Bedingung | Beide Modi gesperrt; neuer Stopp-Kurvenmodus schreibt es nicht |
| `Placemark/useStraightLine` | Bei kontinuierlichem Kurven-Stopp/Durchflug | **In PR #82 ergänzt**: 1 bei kontinuierlichem Stopp |

## 4. Gemeinsame Aktionsstrukturen

Diese Felder sind obligatorisch, **wenn eine Aktion vorhanden ist**,
aber nicht bei einem Wegpunkt ohne Aktionen.

| Block | Pflichtfelder | Status |
| --- | --- | --- |
| `actionGroup` | `actionGroupId`, `actionGroupStartIndex`, `actionGroupEndIndex`, `actionGroupMode` | Vorhanden, Indizes begrenzt |
| `actionTrigger` | `actionTriggerType` | Vorhanden |
| `actionTrigger` für multipleTiming/multipleDistance | `actionTriggerParam` > 0 | Nicht anwendbar: Trigger gesperrt |
| `action` | `actionId`, `actionActuatorFunc` | Vorhanden |
| `actionActuatorFuncParam` | Aktionsabhängige Pflichtfelder | Im Folgenden einzeln geprüft |

### Aktionsspezifische Pflichtfelder

| Unterstützte Aktion | Belegte Pflichtfelder | Status |
| --- | --- | --- |
| `takePhoto` | payloadPositionIndex, fileSuffix, useGlobalPayloadLensIndex (M4: zusätzlich payloadLensIndex) | Vorhanden; M3TA nur konservativ und nicht gerätezertifiziert |
| `startRecord` | payloadPositionIndex, fileSuffix soweit für Produkt gelistet, useGlobalPayloadLensIndex (M4: payloadLensIndex) | Vorhanden, modellabhängig |
| `stopRecord` | payloadPositionIndex (LensIndex laut neuer DJI-Tabelle ausdrücklich nur für einzelne andere Modelle) | Vorhanden für AeroNexus-Profile |
| `focus` | payloadPositionIndex, isPointFocus, focusX, focusY, isInfiniteFocus | Vorhanden; Bereichsfokus gesperrt |
| `focus` bei Bereichsfokus | focusRegionWidth, focusRegionHeight | Nicht anwendbar |
| `zoom` | payloadPositionIndex, focalLength | Vorhanden |
| `gimbalRotate` | payloadPositionIndex, gimbalHeadingYawBase, gimbalRotateMode, Pitch-/Roll-/Yaw-Enable/-Winkel, Time-Enable/-Wert | Vorhanden |
| `gimbalEvenlyRotate` | gimbalPitchRotateAngle, payloadPositionIndex und trigger=betweenAdjacentPoints | Vorhanden |

Die restlichen DJI-Aktionen, darunter `customDirName`, `rotateYaw`,
`hover`, `accurateShoot`, `orientedShoot`, `panoShot`,
`recordPointCloud` und neuere Pilot-2-spezifische Aktionen, werden
nicht erzeugt. Deren eigene Pflichtfeldlisten sind daher nicht
pauschal als „fehlend“ zu bewerten. Für eine spätere Implementierung
müssen alle aktions- und modellspezifischen Pflichtfelder **neu**
abgeglichen werden.

## 5. Andere DJI-Vorlagen – nicht Teil dieses Exporters

Ein umfassender Spezifikationsabgleich umfasst auch die Pflichtfelder
der übrigen DJI-Template-Typen. Diese können nicht als allgemeine
Pflichtfelder des Typs `waypoint` gelten:

| Vorlagentyp | Typische verpflichtende spezifische Felder | AeroNexus WPML-Status |
| --- | --- | --- |
| `mapping2d` | elevationOptimizeEnable, shootType, direction, margin, ellipsoidHeight, height; globalShootHeight und surfaceFollowModeEnable im Koordinatenblock | Nicht als WPML-Mapping-Template exportiert |
| `mapping3d` | inclinedGimbalPitch, inclinedFlightSpeed, shootType, direction, margin, ellipsoidHeight, height; globalShootHeight/surfaceFollowModeEnable bei entsprechenden Koordinatenangaben | Nicht als WPML-Schrägbild-Template exportiert |
| `mappingStrip` | caliFlightEnable, shootType, direction, margin, singleLineEnable, cuttingDistance, boundaryOptimEnable, leftExtend, rightExtend, includeCenterEnable, ellipsoidHeight, height, stripUseTemplateAltitude; globalShootHeight/surfaceFollowModeEnable im Koordinatenblock | Nicht als WPML-Streifenflug-Template exportiert |
| Oberflächenfolge | surfaceRelativeHeight nur bei surfaceFollowModeEnable=1 | Nicht unterstützt |
| Fixed mapping heading | mappingHeadingAngle bei mappingHeadingMode=fixed | Nicht unterstützt |

Auch `overlap`-Felder sind in den DJI-Tabellen nicht allgemein
als Pflichtfeld für den Wegpunktflug gekennzeichnet.

## 6. Offene Abweichungen und Freigabestatus

| ID | Priorität | Befund | Bewertung |
| --- | --- | --- | --- |
| A1 | Hoch | `waypointHeadingPathMode` fehlt im globalen Heading-Block und bei normalen followWayline-Ausführungspunkten | DJI-Tabelle: Yes; mögliche Geräte-/Vorlagenabweichung; wird im Offline-Audit als Advisory gemeldet |
| A2 | Mittel | Das kanonische Altformat schreibt `globalUseStraightLine=1` auch bei diskontinuierlicher Geraden/Stopp | DJI formuliert „required iff“ für kontinuierliche Kurven; bestehende Route absichtlich noch nicht geändert |
| A3 | Mittel | Das Altformat schreibt `waypointTurnDampingDist=0` beim Modus ohne erforderliche Dämpfung | Alte AeroNexus-Missionen bleiben lesbar; für den neuen Stop-Curve-Modus wird das optionale Feld nicht geschrieben |
| A4 | Hoch | DJI Pilot 2 / Matrice-4-Import und reale Flugsemantik bleiben ungetestet | Kein Produktions- oder Flugfreigabenachweis |
| A5 | Mittel | WPML 1.0.6 und DJI-externe KMZ dürfen nicht als editierbares 1.0.2-Profil normalisiert werden | Import verweigert unbekannte Strukturen; keine stille Konvertierung |
| A6 | Hoch | Ein älterer Stand der offiziellen DJI-Common-Elements-Tabelle kennzeichnet `payloadLensIndex` auch für `stopRecord` als erforderlich. Der aktuelle konservative AeroNexus-Export schreibt es für diese Aktion nicht. | **Produktspezifische Pflichtfeldlage mit aktueller DJI-Tabelle/Pilot 2 weiter zu verifizieren**; ohne diesen Nachweis keine vollständige Zertifizierung |

**Schlussfolgerung:** Für das explizit implementierte Wegpunkt-Subset
sind die identifizierten *bedingten Pflichtfelder* in PR #82 abgedeckt,
mit der vorstehenden offenen Interoperabilitätsfrage bei Headings.
Der Standard-Export kann nicht als „vollständig DJI-konform“
gekennzeichnet werden. DJI-Firmware, Pilot-2-Import und reale
Flugsicherheit müssen unabhängig geprüft werden.

Automatische Regression:
`tests/test_wpml_required_fields.py` plus vorhandene
`tests/test_wpml_heading_turn.py`, `tests/test_wpml_export.py`,
`tests/test_wpml_conformance.py`, `tests/test_studio_api.py`.
