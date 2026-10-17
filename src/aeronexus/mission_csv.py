"""Bounded CSV waypoint preview. Never saves missions or calls DJI services."""
import csv
from io import StringIO
from math import isfinite
import re

from pydantic import ValidationError

from .wpml_export import Waypoint, WaypointMission, waypoints_for_export


MAX_CSV_BYTES = 512 * 1024
MAX_ERRORS = 50
DELIMITERS = {"semicolon": ";", "comma": ",", "tab": "\t"}
DECIMALS = {"dot": ".", "comma": ","}
REQUIRED_COLUMNS = {"latitude", "longitude"}
OPTIONAL_COLUMNS = {"take_photo"}


class MissionCsvError(ValueError):
    """A file, format or row error safe to display to the operator."""


def _number(raw: str, decimal: str) -> float:
    text = raw.strip()
    separator = re.escape(decimal)
    if not re.fullmatch(
        rf"[+-]?(?:[0-9]+(?:{separator}[0-9]+)?|{separator}[0-9]+)(?:[eE][+-]?[0-9]+)?",
        text,
    ):
        raise MissionCsvError("Dezimalzahl im gewählten Zahlenformat erforderlich; keine Tausendertrennzeichen.")
    value = float(text.replace(decimal, "."))
    if not isfinite(value):
        raise MissionCsvError("Endliche Dezimalzahl erforderlich.")
    return value


def _photo(raw: str) -> bool:
    text = raw.strip().lower()
    if text in ("", "false", "0", "nein", "no"):
        return False
    if text in ("true", "1", "ja", "yes"):
        return True
    raise MissionCsvError("Foto: true/false, 1/0 oder ja/nein verwenden.")


def preview_csv(data: bytes, *, delimiter: str = "semicolon", decimal: str = "dot",
                close_route: bool = False) -> dict:
    """Validate the entire file atomically; invalid previews expose no importable route.

    Physical CSV line numbers are reported, including blank lines. No automatic
    separator, coordinate order, height-reference or action inference is allowed.
    """
    if delimiter not in DELIMITERS or decimal not in DECIMALS:
        raise MissionCsvError("Unbekanntes Trennzeichen oder Zahlenformat.")
    separator, decimal_char = DELIMITERS[delimiter], DECIMALS[decimal]
    if separator == decimal_char:
        raise MissionCsvError("Dezimalkomma benötigt Semikolon oder Tab als Trennzeichen.")
    if not data or len(data) > MAX_CSV_BYTES:
        raise MissionCsvError("CSV muss 1 Byte bis 512 KiB groß sein.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MissionCsvError("CSV als UTF-8 speichern (BOM erlaubt).") from exc
    if "\x00" in text:
        raise MissionCsvError("CSV enthält ungültige Nullzeichen.")
    reader = csv.reader(StringIO(text, newline=""), delimiter=separator, strict=True)
    errors, rows = [], []
    error_count = 0

    def error(line: int, column: str, message: str) -> None:
        nonlocal error_count
        error_count += 1
        if len(errors) < MAX_ERRORS:
            errors.append({"line": line, "column": column, "message": message})

    count = 0
    try:
        header = next(reader, None)
        if header is None:
            raise MissionCsvError("Kopfzeile mit latitude und longitude fehlt.")
        columns = [cell.strip().lower() for cell in header]
        if len(set(columns)) != len(columns) or any(not cell for cell in columns):
            raise MissionCsvError("Kopfzeile enthält leere oder doppelte Spalten.")
        if not REQUIRED_COLUMNS.issubset(columns):
            raise MissionCsvError("Kopfzeile benötigt latitude und longitude; Trennzeichen prüfen.")
        if set(columns) - REQUIRED_COLUMNS - OPTIONAL_COLUMNS:
            raise MissionCsvError("Nur latitude, longitude und optional take_photo sind erlaubt. "
                                  "Höhen, Geschwindigkeit und weitere Aktionen werden nicht übernommen.")
        for cells in reader:
            line = reader.line_num
            if not cells or all(not cell.strip() for cell in cells):
                continue
            count += 1
            if count > 500:
                error(line, "", "Maximal 500 Wegpunkte erlaubt.")
                break
            if len(cells) != len(columns):
                error(line, "", "Spaltenanzahl passt nicht zur Kopfzeile; Trennzeichen prüfen.")
                continue
            values = dict(zip(columns, cells))
            parsed = {}
            start_errors = error_count
            for column, limit in (("latitude", 90), ("longitude", 180)):
                try:
                    value = _number(values[column], decimal_char)
                    if not -limit <= value <= limit:
                        raise MissionCsvError(f"WGS84-Wert muss zwischen −{limit} und {limit} Grad liegen.")
                    parsed[column] = round(value, 7)
                except MissionCsvError as exc:
                    error(line, column, str(exc))
            try:
                parsed["take_photo"] = _photo(values.get("take_photo", ""))
            except MissionCsvError as exc:
                error(line, "take_photo", str(exc))
            if error_count == start_errors:
                try:
                    point = Waypoint.model_validate(parsed)
                    rows.append({"line": line, **point.model_dump()})
                except ValidationError:
                    error(line, "latitude/longitude", "0/0 ist kein gültiger GPS-Fix (nach Rundung auf 7 Dezimalstellen).")
    except csv.Error:
        error(max(1, reader.line_num), "", "Ungültige CSV-Syntax; Anführungszeichen und Feldlängen prüfen.")
    if not error_count:
        if len(rows) < 2:
            error(max(1, reader.line_num), "", "Mindestens zwei Wegpunkte erforderlich.")
        else:
            mission = WaypointMission(name="CSV-Vorschau", close_route=close_route,
                                      waypoints=[Waypoint(**{key: row[key] for key in
                                                  ("latitude", "longitude", "take_photo")}) for row in rows])
            if close_route and len({(r["latitude"], r["longitude"]) for r in rows}) < 3:
                error(0, "", "Route schließen benötigt mindestens drei unterschiedliche Wegpunkte.")
            if len(waypoints_for_export(mission)) > 500:
                error(0, "", "Rückkehrpunkt überschreitet das Limit von 500 ausführbaren Wegpunkten.")
    return {"valid": error_count == 0, "row_count": count, "rows": rows,
            "errors": errors, "error_count": error_count,
            "waypoints": [{key: row[key] for key in ("latitude", "longitude", "take_photo")}
                          for row in rows] if not error_count else []}
