# Phase 13: AeroNexus Mission Studio (Chrome/Desktop)

**Implementation status:** Source code committed; full test suite and
browser validation on the Raspberry Pi still pending.

## Access

- Desktop UI: **`https://192.168.178.63:8000/studio`**
- Existing read-only DJI monitor: `https://192.168.178.63:8000/status`
- Chrome or another recent standards-compliant desktop browser.
- The separate **AeroNexus status token** (`AERONEXUS_STATUS_TOKEN` in the
  private server `.env`). It is **not** the DJI organization key.
- Trusted local Pi CA certificate: `config/pki/ca.crt` (see
  `docs/deploy-pi.md`). Never disable TLS certificate checks.
- **Browser internet access** for the pinned Leaflet 1.9.4 library and base
  map tiles; the Raspberry Pi API remains local. Basemap services see
  requested map tile coordinates, not the bearer token.
  Leaflet JS/CSS are loaded from jsDelivr with subresource integrity (SRI).
  Maps: OpenStreetMap contributors / Esri World Imagery, attribution embedded.

## Functional scope

### Interactive mission map

- Dark desktop console with persistent left sidebar and full-size map.
- OpenStreetMap streets or Esri satellite imagery.
- Click-to-place WGS84 waypoints, draggable markers, connected route line.
- Edit coordinates, reorder/insert/remove waypoints, add optional
  **take-photo action** at each point, fit route to map.
- Selected aircraft: DJI Matrice 4T (default) or Matrice 4E.
- Editable mission metadata: name, description, uniform takeoff-relative
  height, horizontal airspeed, safe takeoff height, RTH height, finish action.
- New/save/open/edit/delete missions in the Pi's private workspace;
  **nothing is uploaded to DJI**.
- Export DJI waypoint **KMZ** locally using exactly
  `wpmz/template.kml` and `wpmz/waylines.wpml`. The exporter uses XML,
  not unsafe string interpolation. All coordinates serialize as
  `longitude,latitude`.

### WPML scope and constraints

Official DJI sources (as of 2026-10-16):

- [DJI WPML template.kml](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/template-kml.html)
- [DJI WPML waylines.wpml](https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/waylines-wpml.html)
- [DJI product enums](https://developer.dji.com/doc/cloud-api-tutorial/en/overview/product-support.html)

Implemented subset:

- `http://www.dji.com/wpmz/1.0.2` namespace, `waypoint` template.
- M4T `droneEnumValue=99`, `droneSubEnumValue=1`,
  `payloadEnumValue=89`, position 0.
- M4E `droneEnumValue=99`, `droneSubEnumValue=0`,
  `payloadEnumValue=88`, position 0.
- WGS84 lat/lon, **uniform `relativeToStartPoint` height**, speed,
  conservative RC-loss action (goBack), finish action goHome/noAction,
  default follow-course heading and stop-at-waypoint turning; optional
  waypoint takePhoto action group.
- Bounds: 2–500 points to export, speed >0–15 m/s, relative height
  2–500 m, security height 1.2–1500 m and named profiles only.
  Importantly, these software limits are **not** a DJI flight
  authorization or a validation of local aviation rules.
- Arbitrary external WPML KMZ **import/edit** is not supported in this
  initial version. The editor can edit missions saved in AeroNexus.
  Full mapping2d/mapping3d, polygon areas, gimbal actions, per-waypoint
  ellipsoid/terrain height and DJI-specific extended metadata are not
  generated. Those require separately verified device/payload support.
- **Flight safety:** WPML structural conformance does not prove that
  a file will be accepted by the exact DJI Pilot 2 / firmware version.
  Before *every* real flight import the KMZ **manually** into DJI Pilot 2,
  inspect the planned track and actions, and verify airspace,
  altitude reference, obstacles, takeoff point, RTH and battery.
  The app cannot perform terrain/obstacle/airspace clearance.

### Private on-Pi media library

- Upload JPEG, PNG, WebP images and MP4 videos from Chrome.
- Persistent private storage outside Git:
  `~/.local/share/aeronexusadvanced/media`.
- Browse/search the local library with previews and delete items.
  Thumbnail/full file previews are requested using the **same bearer
  token**, loaded as temporary in-memory browser object URLs and
  revoked when disconnecting.
- Each media file capped at **25 MiB** and its signature checked.
  Maximum 500 media items; do not use the Pi as an unlimited video NAS.
- No FlightHub media downloads, DJI media browser, Exif georeferencing
  or photo-to-waypoint assignment in this phase. Those are separate
  future read-only improvements.

### Live fleet panel

- Uses the existing authenticated `GET /api/v1/status/devices`.
- Displays current device cards and allows plotting valid **fresh**
  GPS positions on the map. The external tile provider sees the
  requested map viewport; mission/telemetry JSON and credentials are
  **not** transmitted to the map service.
- Current FlightHub 2 integration shows the Matrice 4T; the RC Plus 2
  does not yet appear independently in that live project.

## HTTP API (all private endpoints need status Bearer token)

| Method | Path | Result |
|---|---|---|
| GET | `/studio` | Static shell, no identifiers |
| GET/POST | `/api/v1/studio/missions` | List/create saved drafts |
| GET/PUT/DELETE | `/api/v1/studio/missions/{uuid}` | Read/update/remove local draft |
| GET | `/api/v1/studio/missions/{uuid}/export.kmz` | Download offline WPML ZIP |
| GET/POST | `/api/v1/studio/media` | List/add private files |
| GET | `/api/v1/studio/media/{uuid}/file` | Authenticated binary download |
| DELETE | `/api/v1/studio/media/{uuid}` | Delete local media |

The media upload uses a raw body, `Content-Type` of one of the four
allowed types and an URL-encoded `X-Filename` header. Requests are
stream-limited to 25 MiB. New files live under UUID-based filenames;
client filename never becomes a filesystem path.

The directory `AERONEXUS_WORKSPACE_DIR` (optional; defaults to
`~/.local/share/aeronexusadvanced`) and its missions/media
subdirectories must be mode **0700**; records and media are mode **0600**.
Do not put this directory inside a synced/public web root or the Git repo.
Back it up if the missions are important; no automatic backup is provided.

## Security boundaries

- DJI Public Cloud / On-Premises integrations remain **read-only**.
- No DJI upload, execution, task start, aircraft config changes or
  remote media deletion; all POST/PUT/DELETE methods affect only private
  files on this Pi.
- **No DJI Dock support.**
- Browser token lives only in memory of the tab. Re-enter after reload.
- All content from DJI and media filenames is inserted via
  `textContent`, not `innerHTML`.
- The `/status` dashboard and `/studio` are both served via HTTPS
  using the existing systemd user service.

## Update and validate on Pi

```bash
cd ~/Projekte/AeroNexusAdvanced
git pull --ff-only
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
systemctl --user restart aeronexusadvanced
systemctl --user is-active aeronexusadvanced
```

The automated Python tests cover WPML ZIP/XML, model enumeration,
mission CRUD, media validation/storage, API authentication,
read-only boundaries and Chrome UI. **No fresh full Pi test run has
been performed on this implementation yet.** The final firmware-level
WPML import check in DJI Pilot 2 also remains to be done.
