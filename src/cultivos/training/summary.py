"""D1-T1: what the API shows of a training dataset: its summary, the curves per class and the sample pixels."""

import numpy as np

from cultivos.config import load_processing_config, load_training_config
from cultivos.training import dataset

BUILD_COMMAND = "docker compose run --rm api python -m cultivos.training.build_table"
FEATURES_COMMAND = "docker compose run --rm api python -m cultivos.training.features"


class UnknownIndexName(ValueError):
    pass


def _not_ready() -> dict:
    return {"available": False, "command": BUILD_COMMAND}


def class_curves(summary: dict, observations: list[dict], pixels: list[dict], index: str, config: dict) -> dict:
    """Median and central band of the index per class and month, with how many pixels had data."""
    column = index.lower()
    months = [info["month"] for info in summary["months"]]
    position = {month: number for number, month in enumerate(months)}
    class_of = {pixel["pixel_id"]: pixel["class"] for pixel in pixels}
    values = {name: [[] for _ in months] for name in summary["classes"]}
    for row in observations:
        if row.get(column) not in (None, "") and row["month"] in position:
            values[class_of[row["pixel_id"]]][position[row["month"]]].append(float(row[column]))

    low, mid, high = config["summary"]["percentiles"]
    decimals = config["summary"]["decimals"]

    def stat(entries: list[float], q: float) -> float | None:
        return round(float(np.percentile(entries, q)), decimals) if entries else None

    return {
        "index": index,
        "months": months,
        "classes": {
            name: {
                "with_data": [len(entries) for entries in per_month],
                "p25": [stat(entries, low) for entries in per_month],
                "median": [stat(entries, mid) for entries in per_month],
                "p75": [stat(entries, high) for entries in per_month],
            }
            for name, per_month in values.items()
        },
    }


def read_training(index: str | None = None) -> dict:
    config = load_training_config()
    root = dataset.folder(config)
    summary_path = root / "summary.json"
    if not summary_path.exists():
        return _not_ready()
    indices = load_index_names()
    index = index or config["summary"]["default_index"]
    if index not in indices:
        raise UnknownIndexName(f"Índice desconocido: {index}. Opciones: {', '.join(indices)}.")
    summary = dataset.read_json(summary_path)
    pixels = dataset.read_pixels(root / "pixels.csv")
    observations = dataset.read_rows(root / "observations.csv")
    features_path = root / "features.json"
    features = (
        {"available": True, **dataset.read_json(features_path)}
        if features_path.exists()
        else {"available": False, "command": FEATURES_COMMAND}
    )
    return {
        "available": True,
        **summary,
        "indices": indices,
        "curves": class_curves(summary, observations, pixels, index, config),
        "features": features,
    }


def load_index_names() -> list[str]:
    return list(load_processing_config()["indices"])


def read_pixels_geojson() -> dict:
    config = load_training_config()
    path = dataset.folder(config) / "pixels.csv"
    if not path.exists():
        return {"type": "FeatureCollection", "features": [], **_not_ready()}
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [pixel["lon"], pixel["lat"]]},
                "properties": {"pixel_id": pixel["pixel_id"], "class": pixel["class"], "map_value": pixel["map_value"]},
            }
            for pixel in dataset.read_pixels(path)
        ],
    }
