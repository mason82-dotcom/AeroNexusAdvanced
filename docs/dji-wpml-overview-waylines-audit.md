# DJI WPML overview and executable waylines reference: offline scope audit

Checked on **19 October 2026** against DJI's official reference:

- [Overview (2025-03-19)](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/overview.html)
- [Template.kml (2026-03-19)](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/template-kml.html)
- [Waylines.wpml (2026-03-19)](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/waylines-wpml.html)
- [Common Elements (2026-03-19)](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/common-element.html)
- [Common Elements, Chinese revision (2026-10-13)](https://developer.dji.com/doc/cloud-api-tutorial/cn/api-reference/dji-wpml/common-element.html)

## Additional rules from the DJI WPML overview

1. WPML is an XML/KML-derived format in a **ZIP container named `.kmz`**.
2. `wpmz/template.kml` is the **editable planning template**.
   `wpmz/waylines.wpml` is the **executable route**. Both serve different
   purposes: a well-formed template is not a complete executable route.
3. `wpmz/res/` holds **auxiliary assets** such as Spot-Check reference
   photographs or audio needed by resource-dependent actions.
   These resources are **not mandatory for the implemented basic waypoint
   profile**. They must *not* be silently dropped when importing foreign DJI
   files that do rely on them.
4. DJI defines the route's **name as the KMZ file name**. A friendly
   `Document/name` in XML alone does not satisfy every DJI naming/user
   interface expectation. The current AeroNexus KMZ download name and
   Pilot 2 library display should be verified separately.
5. `waylines.wpml` can contain **multiple `Folder` objects**, each
   representing an executable route. For example, a `mapping3d`
   operation can emit five routes. The AeroNexus waypoint editor
   intentionally accepts exactly one canonical Folder with one waylineId.
   Its explicit refusal of other DJIs' valid multi-Folder archives does
   **not** mean those archives are invalid DJI WPML.

## Cross-file constraints verified for the local waypoint subset

| Constraint | Offline verification |
| --- | --- |
| `templateId` links template and executable Folder | Same value in both XML documents |
| `waylineId` unique per route | Canonical AeroNexus subset contains one, index 0 |
| `executeHeightMode` defines `executeHeight`'s reference | Both present and set to relativeToStartPoint |
| `autoFlightSpeed` | Consistent between template and executable Folder |
| Executable waypoint `index` and `Point/coordinates` | Exactly ordered and matched with the template |
| `waypointHeadingParam` | Heading mode and `waypointHeadingPathMode` explicitly present in new exports |
| Continuous stop curve | `waypointTurnMode` and conditionally required `useStraightLine=1` present |
| `actionGroup` and `actionTrigger` | Verified by existing DJI-action conformance tests |
| Foreign file with `wpmz/res/` | Remains non-editable, not silently flattened to the local format |
| File with multiple executable Folders | Remains non-editable, not collapsed into one route |

The strict local importer additionally compares the two complete XML
document signatures against **known AeroNexus generations**, never
generic DJI file signatures. A missing element in one waypoint only, or
a mixture of old/new heading blocks in the two documents, is rejected.

### Compatibility migration and open points

- New `followWayline` exports include
  `waypointHeadingPathMode=followBadArc` in the template global block
  and each executable waypoint, as required in the current DJI reference.
  `smoothTransition` retains the selected per-point yaw path. Old
  unmodified AeroNexus archives remain importable, with an advisory.
- `stopRecord/payloadLensIndex` is **not required for Matrice 4E/4T**
  in DJI's English product-specific table. The Chinese reference revised
  2026-10-13 marks it optional; no guessed camera parameter is emitted.
- Matrice 4 **Dock** features such as megaphone/searchlight or resource-backed
  oriented capture are not thereby enabled for **Matrice 4T**. Model and
  payload capabilities are separate and must be checked per product.
- DJI Pilot 2's Wayline Library editing guidance requires a **new route
  name** after local editing for sharing. The AeroNexus local export
  does not on its own guarantee that a DJI Cloud/Pilot workflow will
  accept the name.
- For DJI WPML 1.0.6, resource-bearing actions, generic third-party KMZ,
  multi-Folder templates or native DJI Pilot 2 export/import, AeroNexus
  **does not claim full support or flight compatibility**.

### Reproducible tests

Run `tests/test_wpml_waylines_reference.py`,
`tests/test_wpml_heading_path_legacy.py` and the existing
WPML/studio regression tests in the isolated development worktree.

**Safety statement:** No Cloud upload, remote-controller interaction,
flight execution, Pilot 2 import acceptance or device compatibility
verification has occurred. This is an offline XML and ZIP contract check.
