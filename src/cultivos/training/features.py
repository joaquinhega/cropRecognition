"""D1-T2: model variables per pixel: monthly bands and indices (haze months removed) plus the shape of the season curve.

Run: docker compose run --rm api python -m cultivos.training.features
"""

import sys
import warnings
from datetime import date

import numpy as np

from cultivos.config import load_processing_config, load_training_config
from cultivos.training import dataset

PHENOLOGY = {
    "peak_value": "Pico de verdor",
    "peak_month": "Mes del pico",
    "min_value": "Verdor mínimo",
    "amplitude": "Subida del mínimo al pico",
    "mean": "Verdor promedio",
    "green_area": "Verdor acumulado sobre el mínimo",
    "rise_month": "Mes en que arranca a crecer",
    "fall_month": "Mes en que se seca",
    "green_months": "Meses verdes",
    "winter_mean": "Verdor de invierno",
    "summer_mean": "Verdor de verano",
}
MONTH_POSITIONS = {"peak_month", "rise_month", "fall_month"}


class FeaturesError(RuntimeError):
    """The training table is missing or incomplete."""


def matrices(observations: list[dict], pixel_ids: list[str], months: list[str], columns: list[str]) -> dict[str, np.ndarray]:
    """One pixels × months array per column, NaN where there is no observation."""
    row_of = {pixel_id: number for number, pixel_id in enumerate(pixel_ids)}
    col_of = {month: number for number, month in enumerate(months)}
    result = {column: np.full((len(pixel_ids), len(months)), np.nan) for column in columns}
    for observation in observations:
        row, col = row_of[observation["pixel_id"]], col_of.get(observation["month"])
        if col is None:
            continue
        for column in columns:
            if observation.get(column) not in (None, ""):
                result[column][row, col] = float(observation[column])
    return result


def _neighbor_mean(values: np.ndarray) -> np.ndarray:
    mean = np.full(values.shape, np.nan)
    mean[:, 1:-1] = (values[:, :-2] + values[:, 2:]) / 2
    return mean


def haze_mask(values: dict[str, np.ndarray], haze: dict) -> np.ndarray:
    """Months with the haze signature: the index drops below both neighbors, blue brightens and SWIR does not.

    Real drying also lowers the index and raises blue, but it raises SWIR too, so it is kept.
    First and last months, and months next to a gap, cannot be checked and are kept.
    """
    index, blue, swir = (values[haze[key]] for key in ("index", "blue", "swir"))
    drop = np.full(index.shape, np.nan)
    drop[:, 1:-1] = np.minimum(index[:, :-2], index[:, 2:]) - index[:, 1:-1]
    with np.errstate(invalid="ignore"):
        return (
            (drop > haze["min_index_drop"])
            & (blue - _neighbor_mean(blue) > haze["min_blue_rise"])
            & (swir - _neighbor_mean(swir) < haze["max_swir_rise"])
        )


def phenology(curve: np.ndarray, month_numbers: list[int], config: dict) -> dict[str, np.ndarray]:
    """Shape of each pixel's season curve. Month positions count from the first month of the campaign (0 = July)."""
    has_data = ~np.all(np.isnan(curve), axis=1)
    winter = [position for position, month in enumerate(month_numbers) if month in config["winter_months"]]
    summer = [position for position, month in enumerate(month_numbers) if month in config["summer_months"]]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        peak = np.nanmax(curve, axis=1)
        low = np.nanmin(curve, axis=1)
        amplitude = peak - low
        with np.errstate(invalid="ignore"):
            green = curve >= (low + config["half_amplitude_share"] * amplitude)[:, None]
        result = {
            "peak_value": peak,
            "peak_month": np.argmax(np.where(np.isnan(curve), -np.inf, curve), axis=1),
            "min_value": low,
            "amplitude": amplitude,
            "mean": np.nanmean(curve, axis=1),
            "green_area": np.nansum(curve - low[:, None], axis=1),
            "rise_month": np.argmax(green, axis=1),
            "fall_month": curve.shape[1] - 1 - np.argmax(green[:, ::-1], axis=1),
            "green_months": green.sum(axis=1),
            "winter_mean": np.nanmean(curve[:, winter], axis=1),
            "summer_mean": np.nanmean(curve[:, summer], axis=1),
        }
    return {name: np.where(has_data, values.astype(float), np.nan) for name, values in result.items()}


def _clean(value: float, decimals: int):
    return round(float(value), decimals) if np.isfinite(value) else ""


def _median(values: np.ndarray, decimals: int) -> float | None:
    finite = values[np.isfinite(values)]
    return round(float(np.median(finite)), decimals) if finite.size else None


def build() -> dict:
    config = load_training_config()
    processing = load_processing_config()
    imagery, indices = processing["imagery"], processing["indices"]
    settings = config["features"]
    decimals = settings["decimals"]
    root = dataset.folder(config)
    summary_path = root / "summary.json"
    if not summary_path.exists():
        raise FeaturesError("Falta la tabla de entrenamiento. Ejecutá primero: python -m cultivos.training.build_table")

    summary = dataset.read_json(summary_path)
    pixels = dataset.read_pixels(root / "pixels.csv")
    observations = dataset.read_rows(root / "observations.csv")
    months = [info["month"] for info in summary["months"]]
    month_numbers = [date.fromisoformat(f"{month}-01").month for month in months]
    band_roles = [role for role in imagery["assets"] if role != "scl"]
    columns = [*band_roles, *(name.lower() for name in indices)]
    pixel_ids = [pixel["pixel_id"] for pixel in pixels]

    values = matrices(observations, pixel_ids, months, columns)
    haze = haze_mask(values, {**settings["haze"], "index": settings["haze"]["index"].lower()})
    for column in columns:
        values[column][haze] = np.nan
    shape = phenology(values[settings["phenology_index"].lower()], month_numbers, settings)

    prefix = settings["phenology_index"].lower()
    monthly_names = [f"{column}_m{position + 1:02d}" for column in columns for position in range(len(months))]
    phenology_names = [f"{prefix}_{name}" for name in PHENOLOGY]
    fields = ["pixel_id", "class", "lon", "lat", *monthly_names, *phenology_names]
    rows = []
    for number, pixel in enumerate(pixels):
        row = {"pixel_id": pixel["pixel_id"], "class": pixel["class"], "lon": pixel["lon"], "lat": pixel["lat"]}
        for column in columns:
            for position in range(len(months)):
                row[f"{column}_m{position + 1:02d}"] = _clean(values[column][number, position], decimals)
        for name in PHENOLOGY:
            row[f"{prefix}_{name}"] = _clean(shape[name][number], decimals)
        rows.append(row)
    dataset.write_rows(root / "features.csv", fields, rows)

    classes = np.array([pixel["class"] for pixel in pixels])
    report = {
        "index": settings["phenology_index"],
        "pixels": len(pixels),
        "columns": {"monthly": len(monthly_names), "phenology": len(phenology_names), "total": len(monthly_names) + len(phenology_names)},
        "month_keys": months,
        "haze": {
            "removed": int(haze.sum()),
            "observations": int(np.isfinite(values[columns[0]]).sum() + haze.sum()),
            "by_month": {month: int(count) for month, count in zip(months, haze.sum(axis=0))},
            "rule": settings["haze"],
        },
        "phenology": {name: {"title": title, "month_position": name in MONTH_POSITIONS} for name, title in PHENOLOGY.items()},
        "classes": {
            name: {metric: _median(shape[metric][classes == name], decimals) for metric in PHENOLOGY}
            for name in summary["classes"]
        },
    }
    dataset.write_json(root / "features.json", report)
    return report


def main() -> None:
    try:
        report = build()
    except FeaturesError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    haze = report["haze"]
    print(f"Variables: {report['columns']['total']} por píxel ({report['columns']['monthly']} mensuales y {report['columns']['phenology']} de la curva de {report['index']}).")
    print(f"Meses descartados por bruma: {haze['removed']} de {haze['observations']} observaciones.")
    months = report["month_keys"]
    for name, metrics in report["classes"].items():
        peak = metrics["peak_month"]
        peak_text = months[int(round(peak))] if peak is not None else "sin dato"
        green = metrics["green_months"]
        green_text = f"{green:.0f}" if green is not None else "sin dato"
        print(
            f"  {name}: pico {metrics['peak_value']} en {peak_text}, {green_text} meses verdes, "
            f"invierno {metrics['winter_mean']}, verano {metrics['summer_mean']}"
        )


if __name__ == "__main__":
    main()
