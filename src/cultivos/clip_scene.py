import argparse
import math
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pystac import Item
from rasterio.crs import CRS
from rasterio.io import DatasetReader
from rasterio.transform import Affine
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

from cultivos.config import load_imagery_config, load_zone_config
from cultivos.search_scenes import search_items


def find_item(day: str, bbox: list[float], imagery: dict) -> Item:
    day_imagery = {
        **imagery,
        "date_range": f"{day}T00:00:00Z/{day}T23:59:59Z",
        "max_cloud_cover": 101,
    }
    items = [
        item
        for item in search_items(bbox, day_imagery)
        if item.properties.get("grid:code") == imagery["tile"]
    ]
    if not items:
        raise SystemExit(f"No scene for {day} in tile {imagery['tile']}")
    return min(items, key=lambda item: item.properties["eo:cloud_cover"])


def window_for(src: DatasetReader, bbox: list[float]) -> Window:
    left, bottom, right, top = transform_bounds("EPSG:4326", src.crs, *bbox)
    window = from_bounds(left, bottom, right, top, transform=src.transform)
    col_off = math.floor(window.col_off)
    row_off = math.floor(window.row_off)
    width = math.ceil(window.col_off + window.width) - col_off
    height = math.ceil(window.row_off + window.height) - row_off
    return Window(col_off, row_off, width, height)


def read_clip(href: str, bbox: list[float]) -> tuple[np.ndarray, Affine, CRS, tuple[int, int]]:
    with rasterio.open(href) as src:
        window = window_for(src, bbox)
        data = src.read(1, window=window)
        return data, src.window_transform(window), src.crs, (src.width, src.height)


def write_geotiff(path: Path, bands: dict[str, np.ndarray], transform: Affine, crs: CRS) -> None:
    first = next(iter(bands.values()))
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=first.shape[0],
        width=first.shape[1],
        count=len(bands),
        dtype=first.dtype,
        crs=crs,
        transform=transform,
        compress="deflate",
    ) as dst:
        for index, (name, data) in enumerate(bands.items(), start=1):
            dst.write(data, index)
            dst.set_band_description(index, name)


def render_rgb(bands: dict[str, np.ndarray], imagery: dict) -> np.ndarray:
    rgb = np.stack([bands["red"], bands["green"], bands["blue"]], axis=-1).astype("float32")
    reflectance = (rgb - imagery["dn_offset"]) / imagery["dn_scale"]
    scaled = np.clip(reflectance / imagery["preview"]["max_reflectance"], 0, 1)
    return (scaled * 255).astype("uint8")


def write_preview(path: Path, bands: dict[str, np.ndarray], imagery: dict) -> None:
    image = Image.fromarray(render_rgb(bands, imagery))
    factor = imagery["preview"]["scale"]
    image.resize((image.width * factor, image.height * factor), Image.Resampling.NEAREST).save(path)


def clip_item(item: Item, day: str, bbox: list[float], imagery: dict) -> dict:
    bands: dict[str, np.ndarray] = {}
    for name in imagery["bands"]:
        bands[name], transform, crs, grid = read_clip(item.assets[name].href, bbox)

    scl, scl_transform, scl_crs, _ = read_clip(item.assets[imagery["scl_band"]].href, bbox)

    raw_dir = Path(imagery["raw_dir"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{day}_{imagery['tile']}"

    bands_path = raw_dir / f"{stem}.tif"
    scl_path = raw_dir / f"{stem}_scl.tif"
    write_geotiff(bands_path, bands, transform, crs)
    write_geotiff(scl_path, {"scl": scl}, scl_transform, scl_crs)
    return {"bands": bands, "bands_path": bands_path, "scl_path": scl_path, "crs": crs, "grid": grid, "stem": stem}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Scene date, YYYY-MM-DD")
    parser.add_argument("--preview", action="store_true", help="Also save a true color PNG")
    args = parser.parse_args()

    zone = load_zone_config()
    imagery = load_imagery_config()
    bbox = zone["work_area"]["bbox"]

    item = find_item(args.date, bbox, imagery)
    print(f"Scene: {item.id}, cloud cover {item.properties['eo:cloud_cover']:.1f}%")

    clip = clip_item(item, args.date, bbox, imagery)
    bands, bands_path, scl_path, grid = clip["bands"], clip["bands_path"], clip["scl_path"], clip["grid"]

    height, width = next(iter(bands.values())).shape
    share = 100 * (width * height) / (grid[0] * grid[1])
    print(f"CRS: {clip['crs']}")
    print(f"Clip: {width} x {height} px of a {grid[0]} x {grid[1]} px scene ({share:.3f}%)")
    print(f"Saved: {bands_path} ({bands_path.stat().st_size / 1024:.0f} KB)")
    print(f"Saved: {scl_path} ({scl_path.stat().st_size / 1024:.0f} KB)")

    if args.preview:
        preview_path = Path(imagery["raw_dir"]) / f"{clip['stem']}_preview.png"
        write_preview(preview_path, bands, imagery)
        print(f"Saved: {preview_path} ({preview_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
