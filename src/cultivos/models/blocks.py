"""D2-T1: spatial blocks for cross-validation. Pixels are grouped in square blocks, blocks rotate as the test fold,
and training pixels closer than a buffer to any test pixel are left out so neighbors never sit on both sides."""

import numpy as np
from pyproj import Transformer
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info
from sklearn.neighbors import KDTree


def metric_crs(lon: np.ndarray, lat: np.ndarray) -> str:
    """UTM zone that covers the pixels, to measure distances in meters."""
    area = AreaOfInterest(float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max()))
    info = query_utm_crs_info(datum_name="WGS 84", area_of_interest=area)
    return f"{info[0].auth_name}:{info[0].code}"


def to_meters(lon: np.ndarray, lat: np.ndarray, crs: str) -> np.ndarray:
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    x, y = transformer.transform(lon, lat)
    return np.column_stack([x, y])


def block_ids(points: np.ndarray, size: float) -> list[str]:
    cells = np.floor(points / size).astype(int)
    return [f"{column}_{row}" for column, row in cells]


def assign_folds(blocks: list[str], folds: int, seed: int) -> dict[str, int]:
    """Blocks in random order, each one to the fold with fewest pixels so far, so folds end up similar in size."""
    names, counts = np.unique(blocks, return_counts=True)
    order = np.random.default_rng(seed).permutation(len(names))
    sizes = np.zeros(folds, dtype=int)
    result = {}
    for position in order:
        fold = int(np.argmin(sizes))
        result[str(names[position])] = fold
        sizes[fold] += counts[position]
    return result


def buffer_mask(points: np.ndarray, test: np.ndarray, buffer: float) -> np.ndarray:
    """Pixels within the buffer distance of any test pixel (test pixels included)."""
    if not test.any() or buffer <= 0:
        return test.copy()
    tree = KDTree(points[test])
    near = tree.query_radius(points, r=buffer, count_only=True) > 0
    return near | test


def split(lon: np.ndarray, lat: np.ndarray, settings: dict) -> dict:
    """Block and fold of every pixel, and for each fold which pixels train and which test."""
    crs = metric_crs(lon, lat)
    points = to_meters(lon, lat, crs)
    blocks = block_ids(points, settings["block_size_m"])
    fold_of_block = assign_folds(blocks, settings["folds"], settings["seed"])
    fold = np.array([fold_of_block[block] for block in blocks])
    rounds = []
    for number in range(settings["folds"]):
        test = fold == number
        excluded = buffer_mask(points, test, settings["buffer_m"]) & ~test
        rounds.append({"test": test, "train": ~test & ~excluded, "excluded": excluded})
    return {"crs": crs, "blocks": blocks, "fold": fold, "rounds": rounds}
