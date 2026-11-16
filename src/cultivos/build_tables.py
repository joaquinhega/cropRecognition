import csv
from collections import Counter
from pathlib import Path

import numpy as np

from cultivos.config import load_labels_config, load_series_config
from cultivos.labels import read_labels
from cultivos.split import TEST, TRAIN, test_rectangles


def read_table(path: Path) -> tuple[list[str], list[list[str]]]:
    if not path.exists():
        raise SystemExit("Missing the series table. Run cultivos.build_series first")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    return rows[0], rows[1:]


def distance_to_rectangles(x: np.ndarray, y: np.ndarray, rectangles: list[tuple]) -> np.ndarray:
    distances = np.full(x.shape, np.inf)
    for x0, y0, x1, y1 in rectangles:
        dx = np.maximum(np.maximum(x0 - x, x - x1), 0)
        dy = np.maximum(np.maximum(y0 - y, y - y1), 0)
        distances = np.minimum(distances, np.hypot(dx, dy))
    return distances


def write_table(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def drop_shared_pixels(rows: list[list[str]], position: dict) -> tuple[list[list[str]], int]:
    counts = Counter((row[position["x"]], row[position["y"]]) for row in rows)
    kept = [row for row in rows if counts[(row[position["x"]], row[position["y"]])] == 1]
    return kept, len(rows) - len(kept)


def class_counts(rows: list[list[str]], position: dict, classes: list[str]) -> str:
    counts = Counter(row[position["clase"]] for row in rows)
    return "  ".join(f"{clase} {counts[clase]}" for clase in classes)


def main() -> None:
    series = load_series_config()
    classes = load_labels_config()["classes"]
    header, rows = read_table(Path(series["output_path"]))
    position = {name: index for index, name in enumerate(header)}
    small = {
        feature["properties"]["id_lote"]
        for feature in read_labels()["features"]
        if feature["properties"]["menor_al_minimo"]
    }

    def eligible(row: list[str], confidence: list[str]) -> bool:
        return row[position["confianza"]] in confidence and row[position["id_lote"]] not in small

    train_role = [row for row in rows if row[position["rol"]] == TRAIN]
    test_role = [row for row in rows if row[position["rol"]] == TEST]

    train_eligible = [row for row in train_role if eligible(row, series["train_confidence"])]
    xs = np.array([float(row[position["x"]]) for row in train_eligible])
    ys = np.array([float(row[position["y"]]) for row in train_eligible])
    far = distance_to_rectangles(xs, ys, test_rectangles()) >= series["buffer_m"]
    train_far = [row for row, keep in zip(train_eligible, far) if keep]
    test_eligible = [row for row in test_role if eligible(row, series["test_confidence"])]

    train, train_shared = drop_shared_pixels(train_far, position)
    test, test_shared = drop_shared_pixels(test_eligible, position)

    write_table(Path(series["train_path"]), header, train)
    write_table(Path(series["test_path"]), header, test)

    train_pixels = {(row[position["x"]], row[position["y"]]) for row in train}
    in_both = sum(1 for row in test if (row[position["x"]], row[position["y"]]) in train_pixels)

    print("Training table")
    print(f"  pixels in training blocks: {len(train_role)}")
    print(f"  removed by confidence or size (< 1 ha): {len(train_role) - len(train_eligible)}")
    print(f"  removed by buffer (< {series['buffer_m']} m from a test block): {len(train_eligible) - len(train_far)}")
    print(f"  removed for belonging to more than one label: {train_shared}")
    print(f"  kept: {len(train)}  ({class_counts(train, position, classes)})")
    print("Test table")
    print(f"  pixels in test blocks: {len(test_role)}")
    print(f"  removed by confidence or size (< 1 ha): {len(test_role) - len(test_eligible)}")
    print(f"  removed for belonging to more than one label: {test_shared}")
    print(f"  kept: {len(test)}  ({class_counts(test, position, classes)})")
    print(f"Pixels in both tables: {in_both}")
    print(f"Saved: {series['train_path']} and {series['test_path']}")


if __name__ == "__main__":
    main()
