"""CSV format boundaries, atomic validation and existing WPML interoperability."""
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from aeronexus.app import app
from aeronexus.mission_csv import MAX_CSV_BYTES, MissionCsvError, preview_csv
from aeronexus.wpml_export import import_kmz


CSV = b"latitude;longitude;take_photo\n49.1533;8.58417;true\n49.1535;8.5844;false\n"
TOKEN = "csv-test-independent-dashboard-token-0123456789"
HEADERS = {"Authorization": "Bearer " + TOKEN}


@pytest.mark.parametrize("delimiter,decimal,data", [
    ("semicolon", "dot", CSV),
    ("comma", "dot", CSV.replace(b";", b",")),
    ("tab", "comma", CSV.replace(b";", b"\t").replace(b".", b",")),
    ("semicolon", "comma", CSV.replace(b".", b",")),
    ("semicolon", "dot", b"\xef\xbb\xbf" + CSV.replace(b"\n", b"\r\n")),
])
def test_formats_preserve_coordinate_order_and_photo(delimiter, decimal, data):
    result = preview_csv(data, delimiter=delimiter, decimal=decimal)
    assert result["valid"] and result["row_count"] == 2
    assert result["waypoints"] == [
        {"latitude": 49.1533, "longitude": 8.58417, "take_photo": True},
        {"latitude": 49.1535, "longitude": 8.5844, "take_photo": False},
    ]


def test_header_order_is_explicit_not_positional():
    result = preview_csv(b"longitude;latitude\n8.58;49.15\n8.59;49.16\n")
    assert result["valid"]
    assert result["waypoints"][0] == {"latitude": 49.15, "longitude": 8.58, "take_photo": False}


@pytest.mark.parametrize("data,options", [
    (b"", {}),
    (b"x" * (MAX_CSV_BYTES + 1), {}),
    (b"latitude;longitude\n\xff", {}),
    (b"latitude;longitude\n\x00", {}),
    (CSV, {"delimiter": "auto"}),
    (CSV, {"decimal": "auto"}),
    (CSV, {"delimiter": "comma", "decimal": "comma"}),
    (b"lat;lon\n49;8\n50;9\n", {}),
    (b"latitude;latitude;longitude\n49;49;8\n", {}),
    (b"latitude;longitude;altitude_m\n49;8;50\n50;9;70\n", {}),
    (b"latitude;longitude;heading\n49;8;0\n50;9;90\n", {}),
])
def test_ambiguous_or_lossy_files_are_rejected(data, options):
    with pytest.raises(MissionCsvError):
        preview_csv(data, **options)


@pytest.mark.parametrize("bad_row,column", [
    ("91;8;true", "latitude"),
    ("49;181;true", "longitude"),
    ("49;;true", "longitude"),
    ("NaN;8;true", "latitude"),
    ("1e999;8;true", "latitude"),
    ("49,15;8;true", "latitude"),
    ("49;8;SHOOT", "take_photo"),
    ("0;0;false", "latitude/longitude"),
    ("0.000000001;0;false", "latitude/longitude"),
    ("49;8;true;extra", ""),
])
def test_invalid_rows_are_atomic_and_report_physical_line(bad_row, column):
    data = f"latitude;longitude;take_photo\n\n49;8;true\n{bad_row}\n50;9;false\n".encode()
    result = preview_csv(data)
    assert not result["valid"] and result["waypoints"] == []
    assert result["errors"][0]["line"] == 4
    assert result["errors"][0]["column"] == column


def test_malformed_quoting_and_error_count_are_bounded():
    broken = preview_csv(b'latitude;longitude\n49;8\n"50;9\n')
    assert not broken["valid"] and broken["waypoints"] == []
    errors = preview_csv(b"latitude;longitude\n" + b"bad;8\n" * 100)
    assert errors["error_count"] == 100 and len(errors["errors"]) == 50


def test_minimum_count_and_closed_route_limits():
    assert not preview_csv(b"latitude;longitude\n49;8\n")["valid"]
    assert not preview_csv(CSV, close_route=True)["valid"]
    header = "latitude;longitude\n"
    points = [f"49.{i:07d};8\n" for i in range(500)]
    data = (header + "".join(points)).encode()
    assert preview_csv(data)["valid"]
    assert not preview_csv(data, close_route=True)["valid"]
    # An already explicit return point must not be added a second time.
    closed = (header + "".join(points[:-1]) + points[0]).encode()
    assert preview_csv(closed, close_route=True)["valid"]
    assert not preview_csv(data + b"50;9\n")["valid"]


@pytest.fixture
def api(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", TOKEN)
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR", str(root))
    monkeypatch.delenv("AERONEXUS_LAN_NO_TOKEN", raising=False)
    with TestClient(app) as client:
        yield client, root


def test_preview_requires_auth_and_does_not_create_workspace(api):
    client, root = api
    assert client.post("/api/v1/studio/missions/preview.csv", content=CSV).status_code == 401
    result = client.post("/api/v1/studio/missions/preview.csv", content=CSV, headers=HEADERS)
    assert result.status_code == 200 and result.json()["valid"]
    assert result.headers["cache-control"] == "no-store"
    assert not root.exists()


def test_api_errors_and_streamed_size_limit_leave_workspace_untouched(api):
    client, root = api
    path = "/api/v1/studio/missions/preview.csv"
    assert client.post(path, content=b"unsupported", headers=HEADERS).status_code == 422
    assert client.post(path + "?delimiter=comma&decimal=comma", content=CSV,
                       headers=HEADERS).status_code == 422
    assert client.post(path, content=iter([b"x" * 1024] * 513),
                       headers=HEADERS).status_code == 413
    result = client.post(path, content=CSV.replace(b"49.1533", b"91"), headers=HEADERS)
    assert result.status_code == 200 and not result.json()["valid"]
    assert result.json()["waypoints"] == []
    assert not root.exists()


def test_csv_points_save_and_wpml_round_trip_with_existing_settings(api):
    client, root = api
    preview = client.post("/api/v1/studio/missions/preview.csv", content=CSV, headers=HEADERS).json()
    assert not root.exists()
    mission = {"name": "CSV-Prüfung", "altitude_m": 42.0, "speed_mps": 4.0,
               "drone_model": "matrice4e", "waypoints": preview["waypoints"]}
    record = client.post("/api/v1/studio/missions", json=mission, headers=HEADERS)
    assert record.status_code == 201
    result = client.get(f'/api/v1/studio/missions/{record.json()["id"]}/export.kmz', headers=HEADERS)
    assert result.status_code == 200
    with ZipFile(BytesIO(result.content)) as archive:
        assert b"8.58417,49.1533" in archive.read("wpmz/waylines.wpml")
    imported = import_kmz(result.content)
    assert imported.altitude_m == 42 and imported.speed_mps == 4
    assert imported.drone_model == "matrice4e"
    assert [p.model_dump() for p in imported.waypoints] == preview["waypoints"]
