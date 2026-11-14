import re
from io import BytesIO
from pathlib import Path

import rasterio
from PIL import Image
from rasterio.warp import transform_bounds

from cultivos.clip_scene import render_rgb
from cultivos.compute_ndvi import render_ndvi
from cultivos.config import load_imagery_config

LAYERS = ("rgb", "ndvi")
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def _paths(date: str, imagery: dict) -> tuple[Path, Path]:
    if not DATE_PATTERN.fullmatch(date):
        raise FileNotFoundError(date)
    stem = f"{date}_{imagery['tile']}"
    return Path(imagery["raw_dir"]) / f"{stem}.tif", Path(imagery["processed_dir"]) / f"{stem}_ndvi.tif"


def list_dates() -> list[dict]:
    imagery = load_imagery_config()
    suffix = f"_{imagery['tile']}.tif"
    dates = []
    for path in sorted(Path(imagery["raw_dir"]).glob(f"*{suffix}")):
        date = path.name[: -len(suffix)]
        dates.append({"date": date, "has_ndvi": _paths(date, imagery)[1].exists()})
    return dates


def image_bounds(date: str) -> list[list[float]]:
    raw_path, _ = _paths(date, load_imagery_config())
    with rasterio.open(raw_path) as src:
        west, south, east, north = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
    return [[south, west], [north, east]]


def render_png(date: str, layer: str) -> bytes:
    imagery = load_imagery_config()
    raw_path, ndvi_path = _paths(date, imagery)
    if layer not in LAYERS:
        raise FileNotFoundError(layer)
    source = raw_path if layer == "rgb" else ndvi_path
    if not source.exists():
        raise FileNotFoundError(source)

    with rasterio.open(source) as src:
        if layer == "rgb":
            image = Image.fromarray(render_rgb(dict(zip(src.descriptions, src.read())), imagery))
        else:
            image = Image.fromarray(render_ndvi(src.read(1), imagery["ndvi"]["preview"]))

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
