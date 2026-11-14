import argparse
import math
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

from cultivos.compute_ndvi import MASKED_COLOR, render_ndvi
from cultivos.config import load_imagery_config

MIXED_COLOR = (200, 40, 40)
NEIGHBOR_OFFSETS = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0)]


def print_table(settings: dict) -> None:
    pixel_size = settings["pixel_size_m"]
    print("Parcel size | side (m) | pixels | clean pixels | clean share")
    for hectares in settings["areas_ha"]:
        side_px = math.sqrt(hectares * 10000) / pixel_size
        total = side_px**2
        clean = max(0.0, side_px - 2) ** 2
        marker = "  <- target minimum" if hectares == settings["target_min_ha"] else ""
        print(f"{hectares:>6} ha | {side_px * pixel_size:8.0f} | {total:6.0f} | {clean:12.0f} | {100 * clean / total:8.0f} %{marker}")


def mixed_pixels(ndvi: np.ndarray, threshold: float) -> np.ndarray:
    height, width = ndvi.shape
    padded = np.pad(ndvi, 1, constant_values=np.nan)
    largest = np.zeros_like(ndvi)
    for dy, dx in NEIGHBOR_OFFSETS:
        neighbor = padded[1 + dy : 1 + dy + height, 1 + dx : 1 + dx + width]
        difference = np.nan_to_num(np.abs(ndvi - neighbor), nan=0.0)
        largest = np.maximum(largest, difference)
    return largest > threshold


def write_map(path: Path, ndvi: np.ndarray, mixed: np.ndarray, preview: dict) -> None:
    rgb = render_ndvi(ndvi, preview)[..., :3].copy()
    rgb[mixed] = MIXED_COLOR
    rgb[np.isnan(ndvi)] = MASKED_COLOR
    image = Image.fromarray(rgb)
    factor = preview["scale"]
    image.resize((image.width * factor, image.height * factor), Image.Resampling.NEAREST).save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Scene date, YYYY-MM-DD. Also builds the mixed pixels map")
    args = parser.parse_args()

    imagery = load_imagery_config()
    settings = imagery["parcel_size"]
    print_table(settings)
    if not args.date:
        return

    stem = f"{args.date}_{imagery['tile']}"
    processed_dir = Path(imagery["processed_dir"])
    ndvi_path = processed_dir / f"{stem}_ndvi.tif"
    if not ndvi_path.exists():
        raise SystemExit(f"Missing NDVI for {args.date}. Run cultivos.compute_ndvi first")

    with rasterio.open(ndvi_path) as src:
        ndvi = src.read(1)

    valid = ~np.isnan(ndvi)
    mixed = mixed_pixels(ndvi, settings["mixed_ndvi_difference"]) & valid
    mixed_share = 100 * mixed.sum() / valid.sum()
    print()
    print(f"Date: {args.date}")
    print(f"Mixed pixels (next to a very different surface): {mixed_share:.1f} %")
    print(f"Clean pixels: {100 - mixed_share:.1f} %")

    map_path = processed_dir / f"{stem}_mixed_map.png"
    write_map(map_path, ndvi, mixed, imagery["ndvi"]["preview"])
    print(f"Saved: {map_path} ({map_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
