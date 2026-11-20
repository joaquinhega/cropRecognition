"""Small synthetic Sentinel-2 scenes on disk: 10 m and 20 m bands sharing one origin, like a real tile."""

import math
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

CRS = "EPSG:32719"
MARGIN_M = 100
COARSE_M = 20
BAND_RES = {"blue": 10, "red": 10, "nir": 10, "rededge1": 20, "swir16": 20, "scl": 20}
CLEAR_VALUES = {"blue": 300, "red": 500, "nir": 3500, "rededge1": 1500, "swir16": 2000}
CLEAR, CLOUD = 4, 9

AGRELO_PARCEL = {
    "type": "Polygon",
    "coordinates": [[[-68.8975, -33.136], [-68.8932, -33.136], [-68.8932, -33.1333], [-68.8975, -33.1333], [-68.8975, -33.136]]],
}


class SceneArea:
    """A UTM rectangle around a lon/lat bbox, snapped to the 20 m grid."""

    def __init__(self, bbox: list[float]):
        to_utm = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
        west, south = to_utm.transform(bbox[0], bbox[1])
        east, north = to_utm.transform(bbox[2], bbox[3])
        xs, ys = [west, east], [south, north]
        self.left = math.floor((min(xs) - MARGIN_M) / COARSE_M) * COARSE_M
        self.top = math.ceil((max(ys) + MARGIN_M) / COARSE_M) * COARSE_M
        self.width_m = math.ceil((max(xs) + MARGIN_M - self.left) / COARSE_M) * COARSE_M
        self.height_m = math.ceil((self.top - min(ys) + MARGIN_M) / COARSE_M) * COARSE_M
        to_lonlat = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
        lon0, lat0 = to_lonlat.transform(self.left, self.top - self.height_m)
        lon1, lat1 = to_lonlat.transform(self.left + self.width_m, self.top)
        self.lonlat_bbox = [lon0, lat0, lon1, lat1]

    def shape(self, res: int) -> tuple[int, int]:
        return self.height_m // res, self.width_m // res


def write_band(path: Path, data: np.ndarray, area: SceneArea, res: int, shift_m: float = 0) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs=CRS,
        transform=from_origin(area.left + shift_m, area.top, res, res),
    ) as dst:
        dst.write(data, 1)


def make_scene(
    folder: Path,
    scene_id: str,
    day: str,
    area: SceneArea,
    *,
    cloud_cover: float,
    scl: np.ndarray | int = CLEAR,
    values: dict[str, np.ndarray | int] | None = None,
    shift_red_m: float = 0,
) -> dict:
    """Write the bands of one scene and return its raw Earth Search item (collection `sentinel-2-l2a`)."""
    folder.mkdir(parents=True, exist_ok=True)
    values = {**CLEAR_VALUES, **(values or {}), "scl": scl}
    assets = {}
    for name, res in BAND_RES.items():
        value = values[name]
        dtype = "uint8" if name == "scl" else "uint16"
        data = value.astype(dtype) if isinstance(value, np.ndarray) else np.full(area.shape(res), value, dtype=dtype)
        path = folder / f"{scene_id}_{name}.tif"
        write_band(path, data, area, res, shift_red_m if name == "red" else 0)
        assets[name] = {"href": str(path), "type": "image/tiff; application=geotiff", "roles": ["data"]}
    west, south, east, north = area.lonlat_bbox
    return {
        "type": "Feature",
        "stac_version": "1.0.0",
        "id": scene_id,
        "collection": "sentinel-2-l2a",
        "geometry": {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]},
        "bbox": area.lonlat_bbox,
        "properties": {"datetime": f"{day}T14:40:00Z", "eo:cloud_cover": cloud_cover, "grid:code": "MGRS-19HED"},
        "assets": assets,
        "links": [],
    }


def half_cloudy_scl(area: SceneArea) -> np.ndarray:
    """Clouds over the western half of the scene."""
    scl = np.full(area.shape(COARSE_M), CLEAR, dtype="uint8")
    scl[:, : scl.shape[1] // 2] = CLOUD
    return scl
