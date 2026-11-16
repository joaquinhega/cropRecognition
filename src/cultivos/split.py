
import json
import os
import random
from collections import Counter
from math import ceil
from pathlib import Path

import numpy as np
from rasterio import features
from rasterio.transform import from_origin
from rasterio.warp import transform

from cultivos.config import load_labels_config, load_split_config, load_zone_config
from cultivos.labels import read_labels, today_iso

TRAIN = "entrenamiento"
TEST = "prueba"
EXCLUDED = "excluida"
OUTSIDE = "fuera"
SPLIT_VERSION = 1


class SplitError(ValueError):
    pass


class SplitExists(SplitError):
    pass


def create_split() -> dict:
    config = load_split_config()
    path = Path(config["path"])
    if path.exists():
        raise SplitExists("La partición ya existe y está congelada. Para rehacerla hay que borrar el archivo y registrarlo en 02-decisiones.md.")
    if config["block_size_m"] % config["pixel_size_m"]:
        raise SplitError("El tamaño del bloque debe ser múltiplo del tamaño de píxel.")

    labels = read_labels()["features"]
    if not labels:
        raise SplitError("No hay etiquetas para repartir.")

    grid = _grid(config)
    blocks_by_label = {f["id"]: _block_pixels(f, grid, config["pixel_size_m"]) for f in labels}
    properties = {f["id"]: f["properties"] for f in labels}
    test_blocks, attempt = _choose_test_blocks(blocks_by_label, properties, config)

    data = {
        "version": SPLIT_VERSION,
        "created": today_iso(),
        "params": {
            "block_size_m": config["block_size_m"],
            "pixel_size_m": config["pixel_size_m"],
            "test_fraction": config["test_fraction"],
            "seed": config["seed"],
            "attempt": attempt,
            "min_labels_per_class": config["min_labels_per_class"],
        },
        "grid": grid,
        "test_blocks": sorted(test_blocks),
    }
    _write(path, data)
    return read_split()


def read_split() -> dict:
    config = load_split_config()
    path = Path(config["path"])
    if not path.exists():
        return {"created": False}

    data = json.loads(path.read_text(encoding="utf-8"))
    grid = data["grid"]
    test_blocks = set(data["test_blocks"])
    labels = read_labels()["features"]
    blocks_by_label = {f["id"]: _block_pixels(f, grid, data["params"]["pixel_size_m"]) for f in labels}
    roles = {label_id: _role(counts, test_blocks) for label_id, counts in blocks_by_label.items()}

    return {
        "created": True,
        "created_on": data["created"],
        "params": data["params"],
        "blocks": _blocks_geojson(grid, test_blocks),
        "roles": roles,
        "summary": _summary(grid, test_blocks, blocks_by_label, roles, {f["id"]: f["properties"] for f in labels}),
    }


def test_rectangles() -> list[tuple[float, float, float, float]]:
    path = Path(load_split_config()["path"])
    if not path.exists():
        raise SplitError("La partición no existe. Hay que crearla primero (A2-T4).")
    data = json.loads(path.read_text(encoding="utf-8"))
    grid = data["grid"]
    rectangles = []
    for block in data["test_blocks"]:
        row, col = map(int, block[1:].split("C"))
        x, y = grid["x0"] + col * grid["size"], grid["y0"] + row * grid["size"]
        rectangles.append((x, y, x + grid["size"], y + grid["size"]))
    return rectangles


def _grid(config: dict) -> dict:
    west, south, east, north = load_zone_config()["work_area"]["bbox"]
    xs, ys = transform("EPSG:4326", config["crs"], [west, east, west, east], [south, south, north, north])
    size = config["block_size_m"]
    x0, y0 = min(xs), min(ys)
    return {
        "crs": config["crs"],
        "x0": round(x0, 2),
        "y0": round(y0, 2),
        "size": size,
        "ncols": ceil((max(xs) - x0) / size),
        "nrows": ceil((max(ys) - y0) / size),
    }


def _block_id(row: int, col: int) -> str:
    return f"R{row}C{col}"


def _block_pixels(feature: dict, grid: dict, pixel_size: int) -> Counter:
    ring = feature["geometry"]["coordinates"][0]
    xs, ys = transform("EPSG:4326", grid["crs"], [p[0] for p in ring], [p[1] for p in ring])
    per_block = round(grid["size"] / pixel_size)
    top = grid["y0"] + grid["nrows"] * grid["size"]
    mask = features.rasterize(
        [({"type": "Polygon", "coordinates": [list(zip(xs, ys))]}, 1)],
        out_shape=(grid["nrows"] * per_block, grid["ncols"] * per_block),
        transform=from_origin(grid["x0"], top, pixel_size, pixel_size),
        all_touched=True,
        dtype="uint8",
    )
    rows, cols = np.nonzero(mask)
    return Counter(
        _block_id(grid["nrows"] - 1 - int(row), int(col))
        for row, col in zip(rows // per_block, cols // per_block)
    )


def _role(block_counts: Counter, test_blocks: set[str]) -> str:
    touched = set(block_counts)
    if not touched:
        return OUTSIDE
    if touched <= test_blocks:
        return TEST
    if not touched & test_blocks:
        return TRAIN
    return EXCLUDED


def _is_apt(properties: dict) -> bool:
    return properties["confianza"] == "alta" and not properties["menor_al_minimo"]


def _enough(roles: dict, properties: dict, minimum: int) -> bool:
    classes = load_labels_config()["classes"]
    for role in (TRAIN, TEST):
        for clase in classes:
            count = sum(
                1
                for label_id, value in roles.items()
                if value == role and properties[label_id]["clase"] == clase and _is_apt(properties[label_id])
            )
            if count < minimum:
                return False
    return True


def _choose_test_blocks(blocks_by_label: dict, properties: dict, config: dict) -> tuple[set[str], int]:
    pixels = Counter()
    for counts in blocks_by_label.values():
        pixels.update(counts)
    candidates = sorted(pixels)
    target = config["test_fraction"] * sum(pixels.values())

    for attempt in range(config["max_attempts"]):
        order = candidates[:]
        random.Random(config["seed"] + attempt).shuffle(order)
        test_blocks, accumulated = set(), 0
        for block in order:
            if accumulated >= target:
                break
            test_blocks.add(block)
            accumulated += pixels[block]
        roles = {label_id: _role(counts, test_blocks) for label_id, counts in blocks_by_label.items()}
        if _enough(roles, properties, config["min_labels_per_class"]):
            return test_blocks, attempt

    raise SplitError(
        "No se encontró una partición con suficientes etiquetas aptas (confianza alta, de 1 ha o más) "
        "de cada clase en entrenamiento y en prueba. Hace falta etiquetar más o usar bloques más chicos."
    )


def _blocks_geojson(grid: dict, test_blocks: set[str]) -> dict:
    size = grid["size"]
    blocks = []
    for row in range(grid["nrows"]):
        for col in range(grid["ncols"]):
            x, y = grid["x0"] + col * size, grid["y0"] + row * size
            lons, lats = transform(
                grid["crs"], "EPSG:4326", [x, x + size, x + size, x, x], [y, y, y + size, y + size, y]
            )
            block_id = _block_id(row, col)
            blocks.append(
                {
                    "type": "Feature",
                    "id": block_id,
                    "geometry": {"type": "Polygon", "coordinates": [[list(point) for point in zip(lons, lats)]]},
                    "properties": {"id": block_id, "role": TEST if block_id in test_blocks else TRAIN},
                }
            )
    return {"type": "FeatureCollection", "features": blocks}


def _summary(grid: dict, test_blocks: set[str], blocks_by_label: dict, roles: dict, properties: dict) -> dict:
    classes = load_labels_config()["classes"]
    pixels = Counter()
    for counts in blocks_by_label.values():
        pixels.update(counts)
    total_pixels = sum(pixels.values())
    test_pixels = sum(count for block, count in pixels.items() if block in test_blocks)

    def count(role: str, clase: str, only_apt: bool) -> int:
        return sum(
            1
            for label_id, value in roles.items()
            if value == role
            and properties[label_id]["clase"] == clase
            and (_is_apt(properties[label_id]) or not only_apt)
        )

    return {
        "blocks_total": grid["nrows"] * grid["ncols"],
        "blocks_test": len(test_blocks),
        "test_pixel_share": round(test_pixels / total_pixels, 3) if total_pixels else 0,
        "labels": {role: {clase: count(role, clase, False) for clase in classes} for role in (TRAIN, TEST, EXCLUDED)},
        "apt_labels": {role: {clase: count(role, clase, True) for clase in classes} for role in (TRAIN, TEST)},
        "outside": sum(1 for value in roles.values() if value == OUTSIDE),
    }


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)
