import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
import rasterio
from rasterio import features
from rasterio.transform import xy
from rasterio.warp import transform_geom

from cultivos.compute_ndvi import ndvi_path_for
from cultivos.config import load_imagery_config, load_labels_config, load_series_config
from cultivos.labels import read_labels
from cultivos.split import EXCLUDED, OUTSIDE, TEST, TRAIN, read_split


def read_dates(series: dict) -> list[str]:
    path = Path(series["dates_path"])
    if not path.exists():
        raise SystemExit("Missing the list of dates. Run cultivos.fetch_series first")
    return json.loads(path.read_text(encoding="utf-8"))


def load_stack(dates: list[str], imagery: dict):
    layers = []
    reference = None
    for day in dates:
        path = ndvi_path_for(day, imagery)
        if not path.exists():
            raise SystemExit(f"Missing NDVI for {day}. Run cultivos.fetch_series first")
        with rasterio.open(path) as src:
            grid = (src.transform, src.crs, src.shape)
            if reference is None:
                reference = grid
            elif grid != reference:
                raise SystemExit(f"The grid of {day} differs from the first date")
            layers.append(src.read(1))
    transform, crs, _ = reference
    return np.stack(layers), transform, crs


def label_pixels(feature: dict, shape: tuple[int, int], transform, crs) -> tuple[np.ndarray, np.ndarray]:
    geometry = transform_geom("EPSG:4326", crs, feature["geometry"])
    mask = features.rasterize(
        [(geometry, 1)], out_shape=shape, transform=transform, all_touched=False, dtype="uint8"
    )
    return np.nonzero(mask)


def is_apt(properties: dict) -> bool:
    return properties["confianza"] == "alta" and not properties["menor_al_minimo"]


def format_value(value: float) -> str:
    return "" if np.isnan(value) else f"{value:.4f}"


def main() -> None:
    series = load_series_config()
    imagery = load_imagery_config()
    classes = load_labels_config()["classes"]
    dates = read_dates(series)
    stack, transform, crs = load_stack(dates, imagery)

    split = read_split()
    if not split["created"]:
        raise SystemExit("Missing the test split. Create it first (A2-T4)")
    roles = split["roles"]

    output = Path(series["output_path"])
    output.parent.mkdir(parents=True, exist_ok=True)

    pixels_by_group: Counter = Counter()
    pixel_labels: Counter = Counter()
    empty_labels = []
    missing_by_date = np.zeros(len(dates))
    total_rows = 0

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id_lote", "clase", "confianza", "apta", "rol", "x", "y", *[f"ndvi_{day}" for day in dates]])
        for feature in read_labels()["features"]:
            properties = feature["properties"]
            rows, cols = label_pixels(feature, stack.shape[1:], transform, crs)
            if not len(rows):
                empty_labels.append(properties["id_lote"])
                continue
            role = roles[properties["id_lote"]]
            values = stack[:, rows, cols].T
            xs, ys = xy(transform, rows, cols)
            for x, y, row, col, series_values in zip(xs, ys, rows, cols, values):
                writer.writerow(
                    [
                        properties["id_lote"],
                        properties["clase"],
                        properties["confianza"],
                        int(is_apt(properties)),
                        role,
                        f"{x:.1f}",
                        f"{y:.1f}",
                        *[format_value(value) for value in series_values],
                    ]
                )
                pixel_labels[(int(row), int(col))] += 1
            pixels_by_group[(properties["clase"], role)] += len(rows)
            missing_by_date += np.isnan(values).sum(axis=0)
            total_rows += len(rows)

    print(f"Dates in the series: {len(dates)} ({dates[0]} to {dates[-1]})")
    print(f"Pixel rows written: {total_rows}")
    shown_roles = [TRAIN, TEST, EXCLUDED, OUTSIDE]
    print(f"{'class':<10}" + "".join(f"{role:>15}" for role in shown_roles))
    for clase in classes:
        print(f"{clase:<10}" + "".join(f"{pixels_by_group[(clase, role)]:>15}" for role in shown_roles))
    overlapping = sum(1 for count in pixel_labels.values() if count > 1)
    print(f"Pixels covered by more than one label: {overlapping}")
    if empty_labels:
        print(f"Labels without any pixel center inside: {', '.join(empty_labels)}")
    print("Missing NDVI (clouds, shadows) per date:")
    for day, missing in zip(dates, missing_by_date):
        print(f"  {day}  {100 * missing / total_rows:5.1f} %")
    print(f"Saved: {output} ({output.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
