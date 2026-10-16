"""Phase 17 DEM import safety: bounded decoding and geospatial honesty."""
import math
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from aeronexus.terrain_preview import TerrainUnavailable, geotiff_preview


def stub_gdal(monkeypatch, *, shape=(2, 2), transform=(8.5,.0001,0,49.2,0,-.0001),
              projected=False, epsg="4326", fail_numpy=False):
    made=[]
    removed=[]
    class SRS:
        def IsGeographic(self):
            return not projected
        def IsProjected(self):
            return projected
        def GetAuthorityCode(self, key):
            assert key is None
            return epsg
        def GetLinearUnits(self):
            return 1
    class Band:
        def GetNoDataValue(self):
            return None
        def ReadAsArray(self, *, buf_xsize, buf_ysize):
            if fail_numpy:
                raise ImportError("numpy unavailable")
            return [[200 for _ in range(buf_xsize)] for _ in range(buf_ysize)]
    class Dataset:
        RasterCount=1
        RasterXSize=shape[0]
        RasterYSize=shape[1]
        def GetSpatialRef(self):
            return SRS()
        def GetGeoTransform(self):
            return transform
        def GetRasterBand(self, i):
            assert i==1
            return Band()
    class GDAL:
        OF_RASTER=1
        OF_READONLY=2
        def FileFromMemBuffer(self, name, data):
            made.append(name)
        def OpenEx(self, name, mode, allowed_drivers):
            assert allowed_drivers==["GTiff"]
            return Dataset()
        def Unlink(self,name):
            removed.append(name)
    monkeypatch.setitem(sys.modules,"osgeo",SimpleNamespace(gdal=GDAL()))
    return made,removed


@pytest.mark.parametrize("shape",[(4097,2),(2,4097),(2001,2000),(4096,4096)])
def test_reject_oversized_geotiffs_before_sampling(monkeypatch,shape):
    made,removed=stub_gdal(monkeypatch,shape=shape)
    with pytest.raises(ValueError,match="oversized"):
        geotiff_preview(b"II*\x00compressed raster")
    assert made==removed


@pytest.mark.parametrize("transform",[
    (8.5, .0001, .00001, 49.2, 0, -.0001),
    (8.5, .0001, 0, 49.2, .00001, -.0001),
    (8.5, -.0001, 0, 49.2, 0, -.0001),
    (8.5, .0001, 0, 49.2, 0, .0001),
])
def test_reject_skewed_rotated_or_flipped_rasters(monkeypatch,transform):
    _,removed=stub_gdal(monkeypatch,transform=transform)
    with pytest.raises(ValueError,match="north-up"):
        geotiff_preview(b"II*\x00raster")
    assert len(removed)==1


def test_reject_unknown_geographic_datum(monkeypatch):
    stub_gdal(monkeypatch,epsg="4269")
    with pytest.raises(ValueError,match="EPSG:4326"):
        geotiff_preview(b"II*\x00raster")


def test_wgs84_sampling_reports_positive_metre_grid(monkeypatch):
    made,removed=stub_gdal(monkeypatch)
    grid=geotiff_preview(b"II*\x00raster")
    assert grid.heights_m==[[200,200],[200,200]]
    assert 6<grid.x_step_m<9
    assert 10<grid.y_step_m<12
    assert made==removed


def test_missing_numpy_fails_as_dependency_error(monkeypatch):
    made,removed=stub_gdal(monkeypatch,projected=True,fail_numpy=True)
    with pytest.raises(TerrainUnavailable,match="NumPy"):
        geotiff_preview(b"II*\x00raster")
    assert made==removed


def test_pi_readiness_script_is_syntax_valid_and_never_deploys():
    path=Path(__file__).parents[1]/"scripts/pi/phase17-smoke.sh"
    content=path.read_text()
    for forbidden in ("git pull", "systemctl --user restart", "curl -k", "curl --insecure",
                      "sudo ", ". .env", "source .env"):
        # All operations are non-mutating; only the comment documents git pull.
        if forbidden=="git pull":
            assert content.count(forbidden)==1
            continue
        assert forbidden not in content
    assert "curl --fail --silent --show-error" in content
    assert "--cacert" in content
    assert "PHASE17_CHECK_LIVE" in content
    if shutil.which("bash"):
        result=subprocess.run(["bash","-n",str(path)],capture_output=True,text=True)
        assert result.returncode==0,result.stderr
