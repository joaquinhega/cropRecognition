"""D1-T1: monthly Sentinel-2 observations for the sample pixels.

D-030 adapted to a zone that can span several tiles: each month the scenes are ranked by how many sample
pixels they see clean, and every pixel takes its value from the first scene of that ranking where it is clean.
A pixel with no clean scene in the month stays without data (no interpolation).
"""

from collections.abc import Callable
from functools import lru_cache

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.errors import RasterioError
from rasterio.transform import rowcol
from rasterio.windows import Window

from cultivos.modules.indices import compute, reflectance
from cultivos.modules.scenes import NODATA, SceneReadError, asset_href, cloud_cover

VALUE_DECIMALS = 4
Reader = Callable[[str, np.ndarray, np.ndarray], np.ndarray]


@lru_cache(maxsize=8)
def _to_crs(crs_wkt: str) -> Transformer:
    return Transformer.from_crs("EPSG:4326", crs_wkt, always_xy=True)


def read_points(href: str, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    """Values of band 1 at each point; NODATA for points outside the image. Reads one window around the points."""
    try:
        with rasterio.open(href) as src:
            xs, ys = _to_crs(src.crs.to_wkt()).transform(lons, lats)
            rows, cols = (np.asarray(values) for values in rowcol(src.transform, xs, ys))
            inside = (rows >= 0) & (rows < src.height) & (cols >= 0) & (cols < src.width)
            values = np.full(len(lons), NODATA, dtype="int64")
            if inside.any():
                row0, row1 = int(rows[inside].min()), int(rows[inside].max()) + 1
                col0, col1 = int(cols[inside].min()), int(cols[inside].max()) + 1
                block = src.read(1, window=Window(col0, row0, col1 - col0, row1 - row0))
                values[inside] = block[rows[inside] - row0, cols[inside] - col0]
    except RasterioError as error:
        raise SceneReadError(f"No se pudo leer {href}: {error}") from error
    return values


def _rounded(value: float) -> float | None:
    return round(float(value), VALUE_DECIMALS) if np.isfinite(value) else None


def month_observations(
    month: str,
    candidates: list[dict],
    lons: np.ndarray,
    lats: np.ndarray,
    imagery: dict,
    indices: dict,
    reader: Reader = read_points,
) -> tuple[list[dict], dict]:
    """Rows (one per pixel with data: position in the sample, scene, reflectances and indices) and the month summary."""
    errors, ranked = 0, []
    for item in candidates:
        try:
            scl = reader(asset_href(item, imagery, "scl"), lons, lats)
        except SceneReadError:
            errors += 1
            continue
        clean = ~np.isin(scl, imagery["invalid_scl_classes"])
        if clean.any():
            ranked.append((int(clean.sum()), item, clean))
    ranked.sort(key=lambda entry: (-entry[0], cloud_cover(entry[1]), entry[1]["id"]))

    remaining = np.ones(len(lons), dtype=bool)
    rows, used = [], []
    band_roles = [role for role in imagery["assets"] if role != "scl"]
    for _, item, clean in ranked:
        take = np.flatnonzero(remaining & clean)
        if not take.size:
            continue
        try:
            raw = {role: reader(asset_href(item, imagery, role), lons[take], lats[take]) for role in band_roles}
        except SceneReadError:
            errors += 1
            continue
        bands = {role: reflectance(values, imagery) for role, values in raw.items()}
        computed = compute(bands, indices)
        scene_date = item["properties"]["datetime"][:10]
        for position, pixel in enumerate(take):
            rows.append(
                {
                    "pixel": int(pixel),
                    "month": month,
                    "scene_id": item["id"],
                    "scene_date": scene_date,
                    **{role: _rounded(bands[role][position]) for role in band_roles},
                    **{name.lower(): _rounded(values[position]) for name, values in computed.items()},
                }
            )
        remaining[take] = False
        used.append({"id": item["id"], "date": scene_date, "pixels": int(take.size)})
        if not remaining.any():
            break

    with_data = int(len(lons) - remaining.sum())
    info = {
        "month": month,
        "candidates": len(candidates),
        "read_errors": errors,
        "scenes": used,
        "pixels_with_data": with_data,
        "share_with_data": round(with_data / len(lons), 4) if len(lons) else 0,
    }
    return rows, info
