"""Authenticated local GeoObject, GeoPhoto, survey and STL APIs."""
from io import BytesIO
import struct
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from aeronexus.app import app


TOKEN="local-test-viewer-"+"x"*40
HEADERS={"Authorization":"Bearer "+TOKEN}
POLYGON={"name":"Field A","kind":"polygon","vertices":[
    {"latitude":49.1,"longitude":8.5},
    {"latitude":49.1,"longitude":8.502},
    {"latitude":49.102,"longitude":8.502},
    {"latitude":49.102,"longitude":8.5},
]}
MISSION={"name":"Separate WPML","waypoints":[
    {"latitude":49.11,"longitude":8.5},{"latitude":49.12,"longitude":8.6}]}


@pytest.fixture()
def api(tmp_path,monkeypatch):
    monkeypatch.delenv("AERONEXUS_LAN_NO_TOKEN",raising=False)
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN",TOKEN)
    monkeypatch.setenv("AERONEXUS_WORKSPACE_DIR",str(tmp_path/"workspace"))
    with TestClient(app) as client:
        yield client,tmp_path/"workspace"


def test_geo_objects_are_authenticated_local_only_and_persist(api):
    client,root=api
    assert client.get("/api/v1/studio/geo-objects").status_code==401
    assert not root.exists()
    created=client.post("/api/v1/studio/geo-objects",headers=HEADERS,json=POLYGON)
    assert created.status_code==201,created.text
    geo_id=created.json()["id"]
    listing=client.get("/api/v1/studio/geo-objects",headers=HEADERS)
    assert [obj["id"] for obj in listing.json()["objects"]]==[geo_id]
    assert (root/"geo_objects").stat().st_mode & 0o077==0
    changed=client.put("/api/v1/studio/geo-objects/"+geo_id,headers=HEADERS,
                       json={**POLYGON,"name":"Renamed"})
    assert changed.status_code==200,changed.text
    assert changed.json()["object"]["name"]=="Renamed"
    assert client.delete("/api/v1/studio/geo-objects/"+geo_id,
                         headers=HEADERS).status_code==204
    assert client.get("/api/v1/studio/geo-objects",
                      headers=HEADERS).json()["objects"]==[]


def test_invalid_geometry_fails_with_no_workspace_write(api):
    client,root=api
    invalid={**POLYGON,"flight_command":"start"}
    assert client.post("/api/v1/studio/geo-objects",headers=HEADERS,json=invalid).status_code==422
    assert client.get("/api/v1/studio/geo-objects",headers=HEADERS).json()["objects"]==[]
    assert list((root/"geo_objects").glob("*.json"))==[]


def test_survey_is_preview_only_and_never_changes_wpml(api):
    client,_=api
    mission=client.post("/api/v1/studio/missions",json=MISSION,headers=HEADERS)
    assert mission.status_code==201
    mission_id=mission.json()["id"]
    before=client.get("/api/v1/studio/missions/"+mission_id+"/export.kmz",headers=HEADERS).content
    response=client.post("/api/v1/studio/survey/preview",headers=HEADERS,json={
        "polygon":POLYGON,"spacing_m":20,"bearing_deg":10})
    assert response.status_code==200,response.text
    result=response.json()
    assert result["kind"]=="survey-preview"
    assert result["leg_count"]>2
    assert result["distance_m"]>0
    after=client.get("/api/v1/studio/missions/"+mission_id+"/export.kmz",headers=HEADERS).content
    with ZipFile(BytesIO(before)) as left, ZipFile(BytesIO(after)) as right:
        assert left.read("wpmz/template.kml")==right.read("wpmz/template.kml")
    assert client.post("/api/v1/flight/command",headers=HEADERS).status_code==403
    assert client.post("/api/v1/studio/survey/preview",json={
        "polygon":POLYGON,"spacing_m":20}).status_code==401


def test_geophoto_updates_persist_on_pi_and_reject_unsupported_metadata(api):
    client,root=api
    uploaded=client.post("/api/v1/studio/media",
        headers={**HEADERS,"Content-Type":"image/jpeg","X-Filename":"test.jpg"},
        content=b"\xff\xd8\xffvalid-ish-test-content")
    assert uploaded.status_code==201
    media_id=uploaded.json()["id"]
    patch="/api/v1/studio/media/"+media_id+"/geo"
    valid={"latitude":49.12,"longitude":8.52,"altitude_m":102,
           "heading_deg":35,"pitch_deg":-60,"roll_deg":2,
           "captured_at":"2026-10-16T19:00:00+02:00","notes":"Camera west"}
    result=client.patch(patch,headers=HEADERS,json=valid)
    assert result.status_code==200,result.text
    assert result.json()["latitude"]==49.12
    assert result.json()["captured_at"].endswith("+02:00")
    assert client.get("/api/v1/studio/media",headers=HEADERS).json()["media"][0]["heading_deg"]==35
    assert client.patch(patch,headers=HEADERS,
        json={"latitude":49.1,"longitude":None}).status_code==422
    assert client.patch(patch,headers=HEADERS,
        json={**valid,"heading_deg":360}).status_code==422
    assert client.patch(patch,json=valid).status_code==401
    assert (root/"media"/(media_id+".json")).stat().st_mode & 0o077==0


def test_geophoto_disallows_video_geolocation(api):
    client,_=api
    uploaded=client.post("/api/v1/studio/media",
        headers={**HEADERS,"Content-Type":"video/mp4","X-Filename":"a.mp4"},
        content=b"\0\0\0\x14ftypisom")
    assert uploaded.status_code==201
    result=client.patch("/api/v1/studio/media/"+uploaded.json()["id"]+"/geo",
        headers=HEADERS,json={"latitude":49.1,"longitude":8.5})
    assert result.status_code==422


def test_terrain_stl_auth_and_binary_shape(api):
    client,_=api
    grid={"heights_m":[[100,101],[102,103]],
          "x_step_m":5,"y_step_m":8}
    assert client.post("/api/v1/studio/terrain/export.stl",json=grid).status_code==401
    result=client.post("/api/v1/studio/terrain/export.stl",json=grid,headers=HEADERS)
    assert result.status_code==200,result.text[:100]
    assert result.headers["content-type"].startswith("model/stl")
    assert struct.unpack("<I",result.content[80:84])[0]==12
    assert client.post("/api/v1/studio/terrain/export.stl",headers=HEADERS,
        json={**grid,"heights_m":[[1,2],[3,float("nan")]]}).status_code==422
    assert client.post("/api/v1/studio/terrain/geotiff",headers=HEADERS,
        content=b"not tiff").status_code==422
    assert client.post("/api/v1/studio/terrain/geotiff",headers=HEADERS,
        content=b"II*\x00"+b"\0"*(8*1024*1024)).status_code==413
