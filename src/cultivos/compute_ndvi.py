import argparse
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.crs import CRS
from rasterio.transform import Affine
from rasterio.warp import Resampling, reproject

from cultivos.config import load_imagery_config

RAMP_POSITIONS = [0.0, 0.25, 0.5, 1.0]
RAMP_COLORS = [(140, 90, 50), (230, 210, 90), (120, 190, 70), (20, 100, 30)]
MASKED_COLOR = (128, 128, 128)


def load_bands(path: Path) -> tuple[dict[str, np.ndarray], Affine, CRS]:
    with rasterio.open(path) as src:
        data = src.read()
        bands = {name: data[index] for index, name in enumerate(src.descriptions)}
        return bands, src.transform, src.crs


def load_scl_on_grid(path: Path, shape: tuple[int, int], transform: Affine, crs: CRS) -> np.ndarray:
    scl = np.zeros(shape, dtype="uint8")
    with rasterio.open(path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=scl,
            dst_transform=transform,
            dst_crs=crs,
            resampling=Resampling.nearest,
        )
    return scl


def to_reflectance(values: np.ndarray, imagery: dict) -> np.ndarray:
    return (values.astype("float32") - imagery["dn_offset"]) / imagery["dn_scale"]


def compute_ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    total = nir + red
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = np.where(total > 0, (nir - red) / total, np.nan)
    return ndvi.astype("float32")


def write_ndvi(path: Path, ndvi: np.ndarray, transform: Affine, crs: CRS) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=ndvi.shape[0],
        width=ndvi.shape[1],
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=np.nan,
        compress="deflate",
    ) as dst:
        dst.write(ndvi, 1)
        dst.set_band_description(1, "ndvi")


def render_ndvi(ndvi: np.ndarray, settings: dict) -> np.ndarray:
    low, high = settings["min"], settings["max"]
    position = np.clip((np.nan_to_num(ndvi) - low) / (high - low), 0, 1)
    colors = np.array(RAMP_COLORS, dtype="float32")
    channels = [np.interp(position, RAMP_POSITIONS, colors[:, channel]) for channel in range(3)]
    alpha = np.where(np.isnan(ndvi), 0, 255)
    return np.stack([*channels, alpha], axis=-1).astype("uint8")


def write_preview(path: Path, ndvi: np.ndarray, settings: dict) -> None:
    rgba = render_ndvi(ndvi, settings)
    rgb = rgba[..., :3].copy()
    rgb[rgba[..., 3] == 0] = MASKED_COLOR
    image = Image.fromarray(rgb)
    factor = settings["scale"]
    image.resize((image.width * factor, image.height * factor), Image.Resampling.NEAREST).save(path)


def ndvi_path_for(day: str, imagery: dict) -> Path:
    return Path(imagery["processed_dir"]) / f"{day}_{imagery['tile']}_ndvi.tif"


def build_ndvi(day: str, imagery: dict) -> tuple[np.ndarray, np.ndarray, Path]:
    settings = imagery["ndvi"]
    stem = f"{day}_{imagery['tile']}"
    raw_dir = Path(imagery["raw_dir"])
    bands_path = raw_dir / f"{stem}.tif"
    scl_path = raw_dir / f"{stem}_scl.tif"
    if not bands_path.exists() or not scl_path.exists():
        raise SystemExit(f"Missing clip for {day}. Run cultivos.clip_scene first")

    bands, transform, crs = load_bands(bands_path)
    red = to_reflectance(bands["red"], imagery)
    nir = to_reflectance(bands["nir"], imagery)
    scl = load_scl_on_grid(scl_path, red.shape, transform, crs)

    ndvi = compute_ndvi(red, nir)
    discarded = np.isin(scl, settings["invalid_scl_classes"])
    ndvi[discarded] = np.nan

    ndvi_path = ndvi_path_for(day, imagery)
    ndvi_path.parent.mkdir(parents=True, exist_ok=True)
    write_ndvi(ndvi_path, ndvi, transform, crs)
    return ndvi, discarded, ndvi_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Scene date, YYYY-MM-DD")
    parser.add_argument("--preview", action="store_true", help="Also save a colored PNG")
    args = parser.parse_args()

    imagery = load_imagery_config()
    settings = imagery["ndvi"]
    ndvi, discarded, ndvi_path = build_ndvi(args.date, imagery)

    valid = ~np.isnan(ndvi)
    print(f"Date: {args.date}")
    print(f"Discarded (clouds, shadows, bad pixels): {100 * discarded.mean():.1f} %")
    if not valid.any():
        print("No valid pixels left")
        return
    green = 100 * (ndvi[valid] > settings["green_threshold"]).mean()
    print(f"NDVI average {np.nanmean(ndvi):.2f} (min {np.nanmin(ndvi):.2f}, max {np.nanmax(ndvi):.2f})")
    print(f"Clearly green area (NDVI > {settings['green_threshold']}): {green:.1f} % of the valid pixels")
    print(f"Saved: {ndvi_path} ({ndvi_path.stat().st_size / 1024:.0f} KB)")

    if args.preview:
        preview_path = ndvi_path.with_name(f"{ndvi_path.stem}_preview.png")
        write_preview(preview_path, ndvi, settings["preview"])
        print(f"Saved: {preview_path} ({preview_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
