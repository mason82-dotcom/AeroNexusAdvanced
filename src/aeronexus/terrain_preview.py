"""Preview-only DEM raster sampling and watertight binary terrain STL.

No elevation source is used for DJI waypoint or obstacle clearance.
GeoTIFF loading is optional and requires a working local osgeo/GDAL binding.
"""
from __future__ import annotations

from io import BytesIO
from secrets import token_hex
from math import cos, isfinite, radians, sqrt
import struct

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TerrainUnavailable(RuntimeError):
    pass


class TerrainGrid(BaseModel):
    model_config = ConfigDict(extra="forbid")
    heights_m: list[list[float]] = Field(min_length=2, max_length=64)
    x_step_m: float = Field(gt=0, le=10000, allow_inf_nan=False)
    y_step_m: float = Field(gt=0, le=10000, allow_inf_nan=False)
    base_m: float = Field(default=2, ge=0.1, le=1000, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_grid(self):
        width = len(self.heights_m[0])
        if not 2 <= width <= 64 or any(len(row) != width for row in self.heights_m):
            raise ValueError("Terrain grid must be rectangular, 2..64 columns")
        if any(not isfinite(z) or not -500 <= z <= 9000
               for row in self.heights_m for z in row):
            raise ValueError("Terrain contains invalid elevation")
        return self


def terrain_overview(grid: TerrainGrid) -> dict:
    heights = [z for row in grid.heights_m for z in row]
    return {"rows":len(grid.heights_m),"columns":len(grid.heights_m[0]),
            "min_elevation_m":round(min(heights),3),
            "max_elevation_m":round(max(heights),3),
            "x_step_m":grid.x_step_m,"y_step_m":grid.y_step_m,
            "source":"local-grid-preview",
            "warning":"Terrain preview is not verified obstacle or flight clearance."}


def terrain_stl(grid: TerrainGrid) -> bytes:
    """Create closed mesh with bottom and boundary walls (binary STL).

    Coordinates are local metres, Z uses min elevation as zero plus base.
    No aircraft data, CRS claim, or external file execution.
    """
    rows, cols = len(grid.heights_m), len(grid.heights_m[0])
    minz = min(min(row) for row in grid.heights_m)
    def point(row, col):
        return (col*grid.x_step_m, row*grid.y_step_m,
                grid.heights_m[row][col]-minz+grid.base_m)
    triangles = []
    def add(a,b,c):
        triangles.append((a,b,c))
    for r in range(rows-1):
        for c in range(cols-1):
            p00,p10 = point(r,c),point(r,c+1)
            p01,p11 = point(r+1,c),point(r+1,c+1)
            add(p00,p10,p11)
            add(p00,p11,p01)
            bot00=(p00[0],p00[1],0.)
            bot10=(p10[0],p10[1],0.)
            bot01=(p01[0],p01[1],0.)
            bot11=(p11[0],p11[1],0.)
            add(bot00,bot11,bot10)
            add(bot00,bot01,bot11)
    edges=[]
    for c in range(cols-1):
        edges.append((point(0,c+1),point(0,c)))
        edges.append((point(rows-1,c),point(rows-1,c+1)))
    for r in range(rows-1):
        edges.append((point(r,0),point(r+1,0)))
        edges.append((point(r+1,cols-1),point(r,cols-1)))
    for a,b in edges:
        aa=(a[0],a[1],0.)
        bb=(b[0],b[1],0.)
        add(a,b,bb)
        add(a,bb,aa)
    if len(triangles)>30000:
        raise ValueError("Too many terrain triangles")
    output=BytesIO()
    output.write(b"AeroNexusAdvanced offline terrain preview".ljust(80,b"\0"))
    output.write(struct.pack("<I",len(triangles)))
    for a,b,c in triangles:
        u=tuple(b[i]-a[i] for i in range(3))
        v=tuple(c[i]-a[i] for i in range(3))
        n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],
           u[0]*v[1]-u[1]*v[0])
        norm=sqrt(sum(x*x for x in n))
        normal=tuple(x/norm for x in n) if norm else (0.,0.,0.)
        output.write(struct.pack("<12fH",*(normal+a+b+c),0))
    return output.getvalue()


def geotiff_preview(content: bytes, *, max_bytes: int=8*1024*1024,
                    geo_info: dict | None = None) -> TerrainGrid:
    """Sample a GeoTIFF on the Pi with optional GDAL, no disk persistence.

    Reject unknown spatial reference and non-metre unit assumptions.
    """
    if not content or len(content)>max_bytes:
        raise ValueError("GeoTIFF must be 1 byte to 8 MiB")
    if content[:4] not in (b"II*\x00", b"MM\x00*"):
        raise ValueError("Only classic GeoTIFF files are accepted")
    try:
        from osgeo import gdal  # type: ignore
    except ImportError as exc:
        raise TerrainUnavailable("GDAL Python bindings are not installed") from exc
    # Concurrent requests must never share a GDAL /vsimem path.
    path="/vsimem/aeronexus-"+token_hex(16)+".tif"
    ds=None
    try:
        # GDAL may raise; never leave a shared in-memory file behind.
        gdal.FileFromMemBuffer(path,content)
        ds=gdal.OpenEx(path,gdal.OF_RASTER|gdal.OF_READONLY,allowed_drivers=["GTiff"])
        if (ds is None or ds.RasterCount!=1 or
                not 2<=ds.RasterXSize<=4096 or not 2<=ds.RasterYSize<=4096 or
                ds.RasterXSize*ds.RasterYSize>4_000_000):
            raise ValueError("Invalid or oversized single-band GeoTIFF (maximum 4 million pixels)")
        spatial=ds.GetSpatialRef()
        if spatial is None:
            raise ValueError("GeoTIFF requires a declared spatial reference")
        gt=ds.GetGeoTransform()
        # The UI/STL preview uses a north-up, axis-aligned sampling grid.
        # Rotated or skewed rasters cannot be represented faithfully.
        if (len(gt)!=6 or not all(isfinite(v) for v in gt) or
                abs(gt[2])>1e-12 or abs(gt[4])>1e-12 or
                gt[1]<=0 or gt[5]>=0):
            raise ValueError("Only north-up, non-rotated rasters are supported")
        xdist=gt[1]
        ydist=-gt[5]
        if spatial.IsGeographic():
            # Do not silently call a non-WGS84 angular datum WGS84 metres.
            if str(spatial.GetAuthorityCode(None))!="4326":
                raise ValueError("Geographic DEM must use EPSG:4326 WGS84")
            lat=gt[3]+(ds.RasterYSize/2)*gt[5]
            if abs(lat)>85:
                raise ValueError("Geographic DEM is too close to the poles")
            xdist*=111320*cos(radians(lat))
            ydist*=111132
        elif spatial.IsProjected():
            factor=float(spatial.GetLinearUnits())
            xdist*=factor; ydist*=factor
        else:
            raise ValueError("Unsupported GeoTIFF spatial reference")
        if not all(isfinite(v) and v>0 for v in (xdist,ydist)):
            raise ValueError("Invalid raster pixel resolution")
        width=min(48,ds.RasterXSize)
        height=min(48,ds.RasterYSize)
        band=ds.GetRasterBand(1)
        try:
            data=band.ReadAsArray(buf_xsize=width,buf_ysize=height)
        except ImportError as exc:
            raise TerrainUnavailable("GDAL needs NumPy in the same Python environment") from exc
        if data is None:
            raise ValueError("Could not sample DEM")
        nodata=band.GetNoDataValue()
        values=[[float(v) for v in row] for row in data]
        if nodata is not None and any(v==nodata for row in values for v in row):
            raise ValueError("DEM contains NoData; clip to a complete region first")
        grid=TerrainGrid(heights_m=values,
                         # GDAL resamples pixel-centre values; the sampled
                         # centres are W/width and H/height pixels apart.
                         x_step_m=xdist*ds.RasterXSize/width,
                         y_step_m=ydist*ds.RasterYSize/height)
        if geo_info is not None:
            geo_info.clear()
            # Only return literal WGS84 positions if the bounded local
            # tangent-plane model is meaningful and centres stay in range.
            # Projected CRS needs a separate verified coordinate transform.
            if spatial.IsGeographic():
                lon_step=gt[1]*ds.RasterXSize/width
                lat_step=gt[5]*ds.RasterYSize/height
                west=gt[0]+gt[1]*ds.RasterXSize/(2*width)
                north=gt[3]+gt[5]*ds.RasterYSize/(2*height)
                east=west+(width-1)*lon_step
                south=north+(height-1)*lat_step
                if (all(isfinite(v) for v in (west,north,east,south)) and
                        -180<=west<=east<=180 and -90<=south<=north<=90 and
                        east-west<=0.45 and north-south<=0.45):
                    geo_info.update({"crs":"EPSG:4326","reference":"sample-centres",
                                     "west_lon":west,"north_lat":north,
                                     "lon_step_deg":lon_step,"lat_step_deg":lat_step,
                                     "horizontal_units":"WGS84 degrees",
                                     "vertical_reference":"unspecified"})
        return grid
    finally:
        ds=None
        gdal.Unlink(path)
