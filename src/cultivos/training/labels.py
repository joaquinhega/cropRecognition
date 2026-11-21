"""D1-T1: training labels from a crop map (Mapa Nacional de Cultivos): legend to classes and a homogeneous sample."""

import unicodedata

import numpy as np
from rasterio.transform import Affine, xy

COORD_DECIMALS = 6


def normalize(text: str) -> str:
    """Lowercase without accents, so 'Maíz' matches 'maiz'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def map_legend(legend: dict[int, str], config: dict) -> dict[int, str | None]:
    """Class of every map value: the class whose keyword appears in its label, the rest class, or None (excluded or ambiguous)."""
    classes = config["classes"]
    excluded = [normalize(keyword) for keyword in config["exclude_keywords"]]
    excluded_values = set(config["exclude_values"])
    rest = [name for name, spec in classes.items() if spec.get("rest")]
    mapping = {}
    for value, label in legend.items():
        text = normalize(label)
        if value in excluded_values or any(keyword in text for keyword in excluded):
            mapping[value] = None
            continue
        matches = [
            name
            for name, spec in classes.items()
            if any(normalize(keyword) in text for keyword in spec.get("label_keywords", []))
        ]
        if len(matches) == 1:
            mapping[value] = matches[0]
        elif not matches and rest:
            mapping[value] = rest[0]
        else:
            mapping[value] = None
    return mapping


def homogeneous(data: np.ndarray, radius: int) -> np.ndarray:
    """True where the pixel and every neighbor within `radius` (a square) share the value. Edges are False."""
    height, width = data.shape
    mask = np.zeros(data.shape, dtype=bool)
    if height <= 2 * radius or width <= 2 * radius:
        return mask
    center = data[radius : height - radius, radius : width - radius]
    inner = np.ones(center.shape, dtype=bool)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            neighbor = data[radius + dy : height - radius + dy, radius + dx : width - radius + dx]
            inner &= neighbor == center
    mask[radius : height - radius, radius : width - radius] = inner
    return mask


def sample_pixels(
    data: np.ndarray, transform: Affine, mapping: dict[int, str | None], classes: list[str], sample: dict
) -> tuple[list[dict], dict]:
    """Random pixels per class, only from homogeneous patches, at the center of each map pixel (lon, lat)."""
    candidates_mask = homogeneous(data, sample["homogeneous_radius"])
    rng = np.random.default_rng(sample["seed"])
    pixels, stats = [], {}
    for name in classes:
        values = [value for value, target in mapping.items() if target == name]
        candidates = np.flatnonzero(candidates_mask & np.isin(data, values))
        size = min(sample["per_class"], candidates.size)
        chosen = np.sort(rng.choice(candidates, size=size, replace=False)) if size else candidates[:0]
        rows, cols = np.unravel_index(chosen, data.shape)
        lons, lats = xy(transform, rows, cols)
        for row, col, lon, lat in zip(rows, cols, np.atleast_1d(lons), np.atleast_1d(lats)):
            pixels.append(
                {
                    "class": name,
                    "map_value": int(data[row, col]),
                    "lon": round(float(lon), COORD_DECIMALS),
                    "lat": round(float(lat), COORD_DECIMALS),
                }
            )
        stats[name] = {"candidates": int(candidates.size), "sampled": int(size)}
    return pixels, stats


def mismatched(pixels: list[dict], mapping: dict[int, str | None]) -> list[dict]:
    """Sample pixels whose map value no longer belongs to their class under the current mapping."""
    return [pixel for pixel in pixels if mapping.get(pixel["map_value"]) != pixel["class"]]
