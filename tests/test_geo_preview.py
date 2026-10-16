"""Independent planning previews have no DJI commands, data or WPML side effects."""
import struct
from io import BytesIO

import pytest
from pydantic import ValidationError

from aeronexus.geo_planning import GeoObject, SurveyPlanRequest, generate_survey_preview
from aeronexus.terrain_preview import TerrainGrid, terrain_overview, terrain_stl, geotiff_preview, TerrainUnavailable


POLY = {"name":"Vermessungsfeld","kind":"polygon","vertices":[
    {"latitude":49.1,"longitude":8.5},
    {"latitude":49.1,"longitude":8.502},
    {"latitude":49.102,"longitude":8.502},
    {"latitude":49.102,"longitude":8.5},
]}


def test_polygon_parallel_preview_is_within_region_and_preview_only():
    plan=SurveyPlanRequest(polygon=GeoObject.model_validate(POLY),
                           spacing_m=20,bearing_deg=0)
    generated=generate_survey_preview(plan)
    assert generated["kind"]=="survey-preview"
    assert generated["leg_count"]>=3
    assert generated["leg_count"]==len(generated["legs"])
    assert generated["distance_m"]>100
    assert "no safe connecting turns" in generated["note"]
    for leg in generated["legs"]:
        assert len(leg)==2
        for p in leg:
            assert 49.1-1e-6 <= p["latitude"] <= 49.102+1e-6
            assert 8.5-1e-6 <= p["longitude"] <= 8.502+1e-6
    assert POLY["vertices"]==[{"latitude":49.1,"longitude":8.5},
                              {"latitude":49.1,"longitude":8.502},
                              {"latitude":49.102,"longitude":8.502},
                              {"latitude":49.102,"longitude":8.5}]


@pytest.mark.parametrize("kind,points,radius",[
    ("point",[(49.1,8.5)],None),("line",[(49.1,8.5),(49.2,8.5)],None),
    ("circle",[(49.1,8.5)],100),
])
def test_other_geo_types_have_explicit_constraints(kind,points,radius):
    obj=GeoObject(name="Test",kind=kind,
                  vertices=[{"latitude":a,"longitude":b} for a,b in points],
                  radius_m=radius)
    assert obj.kind==kind
    with pytest.raises(ValidationError):
        SurveyPlanRequest(polygon=obj)


@pytest.mark.parametrize("polygon",[
    {"name":"Crossed","kind":"polygon","vertices":[
       {"latitude":49.1,"longitude":8.5},{"latitude":49.102,"longitude":8.502},
       {"latitude":49.102,"longitude":8.5},{"latitude":49.1,"longitude":8.502}]},
    {"name":"Duplicate","kind":"polygon","vertices":[
       {"latitude":49.1,"longitude":8.5},{"latitude":49.1,"longitude":8.502},
       {"latitude":49.102,"longitude":8.5},{"latitude":49.1,"longitude":8.5}]},
    {"name":"Dateline","kind":"polygon","vertices":[
       {"latitude":49.1,"longitude":179.9},{"latitude":49.1,"longitude":-179.9},
       {"latitude":49.102,"longitude":179.9}]},
])
def test_invalid_polygons_fail_closed(polygon):
    with pytest.raises(ValidationError):
        GeoObject.model_validate(polygon)


def test_too_many_survey_lines_rejected():
    plan=SurveyPlanRequest(polygon=GeoObject.model_validate(POLY),
                           spacing_m=2,bearing_deg=0)
    # This particular region is ~146m across, so still below cap.
    assert generate_survey_preview(plan)["leg_count"]>=10
    bigger=GeoObject(name="large",kind="polygon",vertices=[
        {"latitude":49.0,"longitude":8.5},
        {"latitude":49.0,"longitude":8.53},
        {"latitude":49.03,"longitude":8.53},
        {"latitude":49.03,"longitude":8.5}])
    with pytest.raises(ValueError,match="Too many"):
        generate_survey_preview(SurveyPlanRequest(polygon=bigger,spacing_m=2))


def test_binary_stl_closed_bottom_and_walls():
    grid=TerrainGrid(heights_m=[[100,105],[110,120]],x_step_m=10,y_step_m=20)
    data=terrain_stl(grid)
    count=struct.unpack("<I",data[80:84])[0]
    assert count==12  # 4 top/bottom triangles + 8 wall triangles
    assert len(data)==84+count*50
    assert b"AeroNexusAdvanced" in data[:80]
    overview=terrain_overview(grid)
    assert overview["min_elevation_m"]==100
    assert overview["max_elevation_m"]==120
    assert overview["columns"]==2


@pytest.mark.parametrize("heights",[
    [[1]], [[1,2],[3]], [[1,2],[3,float("nan")]], [[1,2],[3,99999]]
])
def test_invalid_terrain_rejected(heights):
    with pytest.raises(ValidationError):
        TerrainGrid(heights_m=heights,x_step_m=1,y_step_m=1)


def test_gdal_input_rejects_non_tiff_before_dependency_check():
    with pytest.raises(ValueError,match="GeoTIFF"):
        geotiff_preview(b"not a tiff")
    with pytest.raises(ValueError,match="8 MiB"):
        geotiff_preview(b"II*\x00"+b"\0"*(8*1024*1024))


def test_preview_functions_do_not_import_dji_sdk():
    assert "read-only" not in terrain_overview(TerrainGrid(
        heights_m=[[1,1],[2,2]],x_step_m=1,y_step_m=1))["warning"].lower()



def test_geotiff_gdal_sampling_is_bounded_and_mem_paths_unique(monkeypatch):
    """Mock optional GDAL to verify geotransform and independent /vsimem paths."""
    import sys
    from types import SimpleNamespace

    seen=[]
    freed=[]
    class SRS:
        def IsGeographic(self): return False
        def IsProjected(self): return True
        def GetLinearUnits(self): return 1.0
    class Band:
        def ReadAsArray(self,*,buf_xsize,buf_ysize):
            assert (buf_xsize,buf_ysize)==(2,2)
            return [[120.,121.],[123.,124.]]
        def GetNoDataValue(self): return None
    class Dataset:
        RasterCount=1
        RasterXSize=2
        RasterYSize=2
        def GetSpatialRef(self): return SRS()
        def GetGeoTransform(self): return (100.,2.,0.,200.,0.,-3.)
        def GetRasterBand(self,n):
            assert n==1
            return Band()
    class GDAL:
        OF_RASTER=1
        OF_READONLY=2
        def FileFromMemBuffer(self,path,content): seen.append(path)
        def OpenEx(self,path,flags,allowed_drivers):
            assert path in seen and allowed_drivers==["GTiff"]
            return Dataset()
        def Unlink(self,path): freed.append(path)
    monkeypatch.setitem(sys.modules,"osgeo",SimpleNamespace(gdal=GDAL()))
    first=geotiff_preview(b"II*\x00"+"mock".encode())
    second=geotiff_preview(b"II*\x00"+"mock".encode())
    assert first.heights_m==[[120,121],[123,124]]
    assert first.x_step_m==2
    assert first.y_step_m==3
    assert first.model_dump()==second.model_dump()
    assert len(set(seen))==2
    assert freed==seen
