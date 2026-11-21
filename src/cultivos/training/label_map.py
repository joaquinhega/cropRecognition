"""D1-T1: clip of the crop map (Mapa Nacional de Cultivos, Zenodo) over the training zone, downloaded once."""

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.errors import RasterioError
from rasterio.transform import Affine
from rasterio.windows import Window

from cultivos.clip_scene import window_for
from cultivos.mnc_coverage import get_json, get_text, parse_legend

CLIP_NAME = "labels-map.tif"
LEGEND_NAME = "labels-legend.json"


class LabelMapError(RuntimeError):
    """The crop map could not be found, read or does not cover the zone."""


def _record_files(config: dict) -> dict[str, str]:
    try:
        record = get_json(f"{config['zenodo_api_url']}{config['record_id']}")
    except OSError as error:
        raise LabelMapError(f"No se pudo leer el registro {config['record_id']} de Zenodo: {error}") from error
    files = {entry["key"]: entry["links"]["self"] for entry in record["files"]}
    missing = [name for name in (config["map_file"], config["legend_file"]) if name not in files]
    if missing:
        raise LabelMapError(f"El registro {config['record_id']} no tiene {', '.join(missing)}. Tiene: {', '.join(files)}.")
    return files


def _download_clip(url: str, bbox: list[float], path: Path) -> None:
    try:
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
            with rasterio.open(f"/vsicurl/{url}") as src:
                window = window_for(src, bbox).intersection(Window(0, 0, src.width, src.height))
                data = src.read(1, window=window)
                profile = {
                    "driver": "GTiff",
                    "width": data.shape[1],
                    "height": data.shape[0],
                    "count": 1,
                    "dtype": data.dtype,
                    "crs": src.crs,
                    "transform": src.window_transform(window),
                    "nodata": src.nodata,
                    "compress": "deflate",
                }
    except (RasterioError, ValueError) as error:
        raise LabelMapError(f"No se pudo recortar el mapa de cultivos sobre la zona: {error}") from error
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)


def load_label_map(config: dict, bbox: list[float], folder: Path) -> tuple[np.ndarray, Affine, dict[int, str]]:
    """Map values, their transform and the legend for the zone. Downloads the clip the first time only."""
    clip_path, legend_path = folder / CLIP_NAME, folder / LEGEND_NAME
    if not (clip_path.exists() and legend_path.exists()):
        files = _record_files(config)
        try:
            legend = parse_legend(get_text(files[config["legend_file"]]))
        except OSError as error:
            raise LabelMapError(f"No se pudo leer la leyenda {config['legend_file']}: {error}") from error
        if not legend:
            raise LabelMapError(f"La leyenda {config['legend_file']} no tiene clases.")
        _download_clip(files[config["map_file"]], bbox, clip_path)
        legend_path.write_text(json.dumps(legend, ensure_ascii=False, indent=2), encoding="utf-8")

    with rasterio.open(clip_path) as src:
        data, transform = src.read(1), src.transform
    legend = {int(value): label for value, label in json.loads(legend_path.read_text(encoding="utf-8")).items()}
    if not np.isin(data, list(legend)).any():
        raise LabelMapError("El mapa de cultivos no tiene clases sobre la zona: ¿la zona está dentro de su cobertura?")
    return data, transform, legend
