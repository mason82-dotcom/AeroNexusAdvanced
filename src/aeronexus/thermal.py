"""Thermography: DJI R-JPEG metadata, temperature grids and statistics.

Thermal images are taken from the read-only MinIO media index
(``*_T.JPG``, DJI infrared camera). Temperatures come exclusively from the
DJI Thermal SDK (thermal_sdk); without it only image metadata is shown and
no temperature is guessed from raw sensor counts.

Privacy: XMP fields are whitelisted. Aircraft/camera serial numbers, NTRIP
hosts, mount points and any unknown vendor fields are never returned.
"""
from __future__ import annotations

from array import array
from collections import OrderedDict
from dataclasses import dataclass
import math
import re
import struct
import threading

from .minio_media_index import (DjiMediaChanged, DjiMediaError, DjiMediaIndex, media_id,
                                read_indexed_object)
from .thermal_sdk import MAX_IMAGE_BYTES, MeasureParams, ThermalSdk, ThermalSdkError


class ThermalError(ValueError):
    pass


class ThermalNotFound(ThermalError):
    pass


class ThermalChanged(ThermalError):
    pass


THERMAL_SUFFIX = "_T.JPG"
VISUAL_SUFFIXES = ("_V", "_W", "_Z")  # M3T visible / M4T wide / M4T zoom
_XMP_HEADER = b"http://ns.adobe.com/xap/1.0/\x00"


def is_thermal_name(name: str) -> bool:
    return isinstance(name, str) and name.upper().endswith(THERMAL_SUFFIX)


def visual_keys(object_key: str) -> list[str]:
    """Candidate keys of the visible image taken with the same shutter release."""
    if not is_thermal_name(object_key):
        return []
    stem, ext = object_key[:-6], object_key[-4:]
    return [stem + (s if object_key[-6:-4].isupper() else s.lower()) + ext for s in VISUAL_SUFFIXES]


# --------------------------------------------------------------- R-JPEG ----

def jpeg_segments(data: bytes, *, partial: bool = False) -> dict:
    """Walk JPEG header segments up to SOS, bounded and without decoding pixels.

    ``partial``: ``data`` is only the beginning of the file (range read for
    the geo index); stop quietly at the cut instead of failing.
    """
    if not isinstance(data, (bytes, bytearray)) or data[:2] != b"\xff\xd8":
        raise ThermalError("Not a JPEG image")
    pos, xmp, app3, size, dji, truncated = 2, None, 0, None, False, False
    for _ in range(4096):
        if partial and pos + 4 > len(data):
            truncated = True
            break
        if pos + 4 > len(data) or data[pos] != 0xFF:
            raise ThermalError("Malformed JPEG header")
        marker = data[pos + 1]
        if marker == 0xFF:  # fill byte
            pos += 1
            continue
        if marker in (0xD9, 0xDA):
            break
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        if partial and length >= 2 and pos + 2 + length > len(data):
            truncated = True
            break
        if length < 2 or pos + 2 + length > len(data):
            raise ThermalError("Malformed JPEG segment")
        body = data[pos + 4:pos + 2 + length]
        if marker == 0xE1 and body.startswith(_XMP_HEADER) and xmp is None:
            xmp = body[len(_XMP_HEADER):].decode("utf-8", "replace")
        elif marker == 0xE3:
            app3 += len(body)
        elif marker == 0xE4 and b"iirp" in body[:16]:
            dji = True
        elif marker in (0xC0, 0xC1, 0xC2) and len(body) >= 5 and size is None:
            height, width = struct.unpack(">HH", body[1:5])
            size = (width, height)
        pos += 2 + length
    else:
        raise ThermalError("Too many JPEG segments")
    return {"xmp": xmp, "raw_bytes": app3, "size": size, "dji_ir_header": dji,
            "truncated": truncated}


_ATTR_RE = re.compile(r'([A-Za-z][\w-]*):([A-Za-z]\w*)="([^"]{0,200})"')
_ELEM_RE = re.compile(r"<([A-Za-z][\w-]*):([A-Za-z]\w*)>([^<]{0,200})</\1:\2>")


def _xmp_fields(xmp: str | None) -> dict[str, str]:
    if not xmp:
        return {}
    xmp = xmp[:65536]
    fields = {}
    for regex in (_ATTR_RE, _ELEM_RE):
        for prefix, name, value in regex.findall(xmp):
            fields.setdefault(f"{prefix}:{name}", value.strip())
    return fields


def _num(value, low, high):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and low <= number <= high else None


def _text(value, limit=40):
    if not isinstance(value, str) or not value:
        return None
    clean = "".join(c for c in value if c.isprintable())[:limit]
    return clean or None


def thermal_metadata(data: bytes, *, partial: bool = False) -> dict:
    """Whitelisted, typed metadata of a DJI R-JPEG (``radiometric`` is None
    when only the file header was read)."""
    seg = jpeg_segments(data, partial=partial)
    x = _xmp_fields(seg["xmp"])
    d = lambda name: x.get("drone-dji:" + name)  # noqa: E731
    lat = _num(d("GpsLatitude"), -90, 90)
    lon = _num(d("GpsLongitude") or d("GpsLongtitude"), -180, 180)  # older DJI typo
    if lat is not None and lon is not None and abs(lat) < 1e-4 and abs(lon) < 1e-4:
        lat = lon = None  # DJI writes ~0/0 without a GNSS fix (e.g. indoors)
    lrf_lat = _num(d("LRFTargetLat"), -90, 90)
    lrf_lon = _num(d("LRFTargetLon"), -180, 180)
    if lrf_lat is not None and lrf_lon is not None and abs(lrf_lat) < 1e-4 and abs(lrf_lon) < 1e-4:
        lrf_lat = lrf_lon = None
    lrf_ok = d("LRFStatus") == "Normal" and (_num(d("LRFTargetDistance"), 0.1, 5000) is not None)
    width, height = seg["size"] or (None, None)
    source = _text(d("ImageSource"))
    # Raw 16-bit sensor data in APP3: native size, or half the JPEG size when the
    # camera stores a super-resolution preview (M4T: 1280x1024 JPEG, 640x512 raw).
    raw_size = None
    if seg["size"] and seg["dji_ir_header"]:
        for w, h in ((width, height), (width // 2, height // 2)):
            if w and seg["raw_bytes"] == w * h * 2:
                raw_size = (w, h)
                break
    radiometric = None if seg["truncated"] else raw_size is not None
    return {
        "make": _text(x.get("tiff:Make")),
        "model": _text(x.get("tiff:Model") or d("DroneModel")),
        "image_source": source,
        "captured_at": _text(x.get("xmp:CreateDate") or x.get("exif:DateTimeOriginal")),
        "utc_at_exposure": _text(d("UTCAtExposure")),
        "width": width, "height": height,
        "radiometric": radiometric,
        "raw_width": raw_size[0] if raw_size else None,
        "raw_height": raw_size[1] if raw_size else None,
        "position": None if lat is None or lon is None else {
            "latitude": lat, "longitude": lon,
            "absolute_altitude_m": _num(d("AbsoluteAltitude"), -1000, 10000),
            "relative_altitude_m": _num(d("RelativeAltitude"), -1000, 10000),
            "gps_status": _text(d("GpsStatus"), 16),
            "rtk_flag": _num(d("RtkFlag"), 0, 100),
        },
        "gimbal": {
            "yaw_deg": _num(d("GimbalYawDegree"), -360, 360),
            "pitch_deg": _num(d("GimbalPitchDegree"), -180, 180),
            "roll_deg": _num(d("GimbalRollDegree"), -180, 180),
        },
        "flight_yaw_deg": _num(d("FlightYawDegree"), -360, 360),
        "laser_range": None if not lrf_ok else {
            "distance_m": _num(d("LRFTargetDistance"), 0.1, 5000),
            "latitude": lrf_lat, "longitude": lrf_lon,
            "absolute_altitude_m": _num(d("LRFTargetAbsAlt"), -1000, 10000),
        },
    }


# ---------------------------------------------------------- statistics ----

def temperature_stats(width: int, height: int, grid) -> dict:
    count = width * height
    if count <= 0 or len(grid) != count:
        raise ThermalError("Temperature grid does not match its size")
    hot = max(range(count), key=grid.__getitem__)
    cold = min(range(count), key=grid.__getitem__)
    ordered = sorted(grid)
    pick = lambda q: round(ordered[min(count - 1, int(q * (count - 1) + 0.5))], 2)  # noqa: E731
    return {
        "min_c": round(grid[cold], 2), "max_c": round(grid[hot], 2),
        "mean_c": round(math.fsum(grid) / count, 2),
        "p05_c": pick(0.05), "median_c": pick(0.5), "p95_c": pick(0.95),
        "hotspot": {"x": hot % width, "y": hot // width},
        "coldspot": {"x": cold % width, "y": cold // width},
    }


# -------------------------------------------------------------- service ----

@dataclass(frozen=True)
class Measurement:
    width: int
    height: int
    grid: array
    stats: dict
    overrides: dict


def _read_object(record: dict, settings, client) -> bytes:
    try:
        return read_indexed_object(record, settings, client, max_bytes=MAX_IMAGE_BYTES)
    except DjiMediaChanged as exc:
        raise ThermalChanged(str(exc)) from exc
    except DjiMediaError as exc:
        raise ThermalError(str(exc)) from exc


class ThermalService:
    """Lists thermal media and caches SDK measurements (bounded, in memory)."""

    CACHE_ENTRIES = 6
    FILE_CACHE_ENTRIES = 6

    def __init__(self, index: DjiMediaIndex, *, sdk_factory=ThermalSdk.from_env,
                 settings_factory=None, client_factory=None):
        from .minio_media_index import MinioMediaSettings, minio_client
        self.index = index
        self._sdk_factory = sdk_factory
        self._settings_factory = settings_factory or MinioMediaSettings.from_env
        self._client_factory = client_factory or minio_client
        self._sdk: ThermalSdk | None = None
        self._lock = threading.Lock()
        self._files: OrderedDict = OrderedDict()
        self._measurements: OrderedDict = OrderedDict()

    def sdk(self) -> ThermalSdk:
        if self._sdk is None:
            self._sdk = self._sdk_factory()
        return self._sdk

    def sdk_status(self) -> dict:
        try:
            return {"available": True, **self.sdk().version()}
        except ThermalSdkError as exc:
            return {"available": False, "reason": str(exc)}

    def record(self, item_id: str) -> dict:
        record = self.index.get(item_id)
        if record is None or not is_thermal_name(record["filename"]):
            raise ThermalNotFound("Thermal image not indexed")
        return record

    def visual_id(self, record: dict) -> str | None:
        """Same folder first; SD-card imports put each file in its own folder,
        so fall back to a filename that is unique in the index."""
        keys = visual_keys(record["object_key"])
        for key in keys:
            candidate = media_id(record["bucket"], key)
            if self.index.get(candidate) is not None:
                return candidate
        for key in keys:
            matches = self.index.ids_by_filename(key.rsplit("/", 1)[-1], limit=2)
            if len(matches) == 1:
                return matches[0]
        return None

    def list(self, *, query="", limit=50, offset=0) -> dict:
        result = self.index.list_thermal(query=query, limit=limit, offset=offset)
        for item in result["media"]:
            item["visual_id"] = self.visual_id(self.index.get(item["id"]))
        return result

    def _bytes(self, record: dict) -> bytes:
        key = (record["id"], record["etag"], record["size_bytes"])
        with self._lock:
            if key in self._files:
                self._files.move_to_end(key)
                return self._files[key]
        try:
            settings = self._settings_factory()
            data = _read_object(record, settings, self._client_factory(settings))
        except (ThermalError, DjiMediaError):
            raise
        except Exception as exc:  # MinIO SDK errors may echo object keys
            raise DjiMediaError("MinIO object unavailable") from exc
        with self._lock:
            self._files[key] = data
            while len(self._files) > self.FILE_CACHE_ENTRIES:
                self._files.popitem(last=False)
        return data

    def metadata(self, item_id: str) -> dict:
        record = self.record(item_id)
        meta = thermal_metadata(self._bytes(record))
        return {"id": record["id"], "name": record["filename"],
                "size_bytes": record["size_bytes"], "uploaded_at": record["modified_at"],
                "visual_id": self.visual_id(record), **meta}

    def measure(self, item_id: str, params: MeasureParams | None = None) -> Measurement:
        record = self.record(item_id)
        params = params or MeasureParams()
        key = (record["id"], record["etag"], tuple(sorted(params.overrides().items())))
        with self._lock:
            if key in self._measurements:
                self._measurements.move_to_end(key)
                return self._measurements[key]
        data = self._bytes(record)
        if not thermal_metadata(data)["radiometric"]:
            raise ThermalError("Image has no radiometric DJI thermal data")
        width, height, grid = self.sdk().measure(data, params)
        result = Measurement(width, height, grid, temperature_stats(width, height, grid),
                             params.overrides())
        with self._lock:
            self._measurements[key] = result
            while len(self._measurements) > self.CACHE_ENTRIES:
                self._measurements.popitem(last=False)
        return result

    def analysis(self, item_id: str, params: MeasureParams | None = None) -> dict:
        meta = self.metadata(item_id)
        from .thermal_geo import geometry
        result = {**meta, "geometry": geometry(meta), "sdk": self.sdk_status(), "measurement": None}
        if not meta["radiometric"]:
            result["measurement_error"] = "Keine radiometrischen DJI-Wärmebilddaten"
            return result
        if not result["sdk"]["available"]:
            result["measurement_error"] = "DJI Thermal SDK nicht verfügbar"
            return result
        try:
            m = self.measure(item_id, params)
        except ThermalSdkError as exc:
            result["measurement_error"] = str(exc)
            return result
        result["measurement"] = {"width": m.width, "height": m.height, "unit": "degC",
                                 "source": "DJI Thermal SDK dji_irp measure",
                                 "parameter_overrides": m.overrides, **m.stats}
        return result

    def pv_inspection(self, item_id: str, params: MeasureParams | None, region, thresholds,
                      conditions) -> dict:
        """PV abnormality report for one image (see pv_inspection)."""
        from .pv_inspection import condition_checks, inspect
        from .thermal_geo import geometry, ground_sample_m
        meta = self.metadata(item_id)
        m = self.measure(item_id, params)
        gsd = ground_sample_m(meta)
        return {
            "id": meta["id"], "name": meta["name"], "model": meta["model"],
            "captured_at": meta["captured_at"], "geometry": geometry(meta),
            "parameter_overrides": m.overrides,
            "checks": condition_checks(meta, conditions, ground_sample_m=gsd,
                                       thresholds=thresholds,
                                       emissivity=m.overrides.get("emissivity")),
            "conditions": {k: v for k, v in vars(conditions).items() if v is not None},
            **inspect(m.width, m.height, m.grid, region, thresholds, ground_sample_m=gsd),
            "basis": "Orientierung an IEC TS 62446-3:2017; Schwellwerte konfigurierbare "
                     "Richtwerte, Einstufung durch qualifizierte Thermografen.",
        }
