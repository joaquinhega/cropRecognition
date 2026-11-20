"""Read Sentinel-2 assets over a parcel on one 10 m grid and choose the cleanest scene of a month (D-030, D-031)."""

from dataclasses import dataclass

import numpy as np
import rasterio
import shapely
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.errors import RasterioError
from rasterio.features import geometry_mask
from rasterio.io import DatasetReader
from rasterio.transform import Affine
from rasterio.windows import Window
from shapely.geometry import Polygon, mapping

from cultivos.clip_scene import window_for

ALIGN_TOLERANCE = 1e-6
NODATA = 0


class SceneReadError(RuntimeError):
    """An asset could not be read or does not line up with the parcel grid."""


@dataclass(frozen=True)
class Grid:
    crs: CRS
    transform: Affine
    width: int
    height: int

    @property
    def res(self) -> float:
        return self.transform.a


@dataclass(frozen=True)
class SceneChoice:
    item: dict
    grid: Grid
    valid: np.ndarray
    share: float
    valid_pixels: int
    parcel_pixels: int


@dataclass(frozen=True)
class MonthPick:
    choice: SceneChoice | None
    candidates: int
    read_errors: int


def _integer_factor(coarse: float, fine: float) -> int:
    factor = round(coarse / fine)
    if factor < 1 or abs(coarse - factor * fine) > ALIGN_TOLERANCE:
        raise SceneReadError(f"La resolución {coarse} m no es múltiplo de la grilla de {fine} m.")
    return factor


def _upsample(data: np.ndarray, factor: int) -> np.ndarray:
    if factor == 1:
        return data
    return np.repeat(np.repeat(data, factor, axis=0), factor, axis=1)


def _read(src: DatasetReader, window: Window) -> np.ndarray:
    """Read band 1; outside the image (parcel on the edge of a tile) the pixels are no data."""
    inside = (
        window.col_off >= 0
        and window.row_off >= 0
        and window.col_off + window.width <= src.width
        and window.row_off + window.height <= src.height
    )
    return src.read(1, window=window, boundless=not inside, fill_value=NODATA)


def read_mask_grid(href: str, bbox: list[float], grid_m: float) -> tuple[np.ndarray, Grid]:
    """Scene classification (SCL) over the bbox, and the fine grid it defines."""
    try:
        with rasterio.open(href) as src:
            window = window_for(src, bbox)
            data = _read(src, window)
            factor = _integer_factor(src.res[0], grid_m)
            grid = Grid(
                crs=src.crs,
                transform=src.window_transform(window) @ Affine.scale(1 / factor),
                width=int(window.width) * factor,
                height=int(window.height) * factor,
            )
    except RasterioError as error:
        raise SceneReadError(f"No se pudo leer {href}: {error}") from error
    return _upsample(data, factor), grid


def read_on_grid(href: str, grid: Grid) -> np.ndarray:
    """One asset (10 m or 20 m) resampled by repetition onto the fine grid."""
    try:
        with rasterio.open(href) as src:
            if src.crs != grid.crs:
                raise SceneReadError(f"{href} está en otra proyección que la máscara de nubes.")
            res = src.res[0]
            factor = _integer_factor(res, grid.res)
            offsets = (
                (grid.transform.c - src.transform.c) / res,
                (src.transform.f - grid.transform.f) / res,
                grid.width / factor,
                grid.height / factor,
            )
            if any(abs(value - round(value)) > ALIGN_TOLERANCE for value in offsets):
                raise SceneReadError(f"{href} no está alineado con la grilla de la máscara de nubes.")
            col, row, width, height = (round(value) for value in offsets)
            data = _read(src, Window(col, row, width, height))
    except RasterioError as error:
        raise SceneReadError(f"No se pudo leer {href}: {error}") from error
    return _upsample(data, factor)


def parcel_mask(polygon: Polygon, grid: Grid) -> np.ndarray:
    """True for the pixels whose center falls inside the parcel."""
    transformer = Transformer.from_crs("EPSG:4326", grid.crs.to_wkt(), always_xy=True)
    projected = shapely.transform(polygon, transformer.transform, interleaved=False)
    return geometry_mask([mapping(projected)], out_shape=(grid.height, grid.width), transform=grid.transform, invert=True)


def asset_href(item: dict, imagery: dict, role: str) -> str:
    try:
        return item["assets"][imagery["assets"][role]]["href"]
    except KeyError as error:
        raise SceneReadError(f"La escena {item['id']} no tiene la banda {imagery['assets'][role]}.") from error


def cloud_cover(item: dict) -> float:
    value = item["properties"].get("eo:cloud_cover")
    return 100.0 if value is None else float(value)


def choose_scene(candidates: list[dict], polygon: Polygon, imagery: dict) -> MonthPick:
    """The candidate with the largest share of clean parcel pixels. Tries the least cloudy first and stops at a fully clean one."""
    bbox = list(polygon.bounds)
    best, errors = None, 0
    for item in sorted(candidates, key=lambda candidate: (cloud_cover(candidate), candidate["id"])):
        try:
            scl, grid = read_mask_grid(asset_href(item, imagery, "scl"), bbox, imagery["grid_m"])
        except SceneReadError:
            errors += 1
            continue
        inside = parcel_mask(polygon, grid)
        parcel_pixels = int(inside.sum())
        if not parcel_pixels:
            continue
        valid = inside & ~np.isin(scl, imagery["invalid_scl_classes"])
        valid_pixels = int(valid.sum())
        share = valid_pixels / parcel_pixels
        if best is None or share > best.share:
            best = SceneChoice(item, grid, valid, share, valid_pixels, parcel_pixels)
        if share >= 1:
            break
    return MonthPick(best, len(candidates), errors)


def read_bands(item: dict, grid: Grid, imagery: dict) -> dict[str, np.ndarray]:
    """Every band role except the cloud mask, on the fine grid."""
    return {role: read_on_grid(asset_href(item, imagery, role), grid) for role in imagery["assets"] if role != "scl"}
