"""Vegetation indices from Sentinel-2 reflectance and their summary over the clean pixels of a parcel."""

import numpy as np


class UnknownIndex(ValueError):
    pass


def reflectance(values: np.ndarray, imagery: dict) -> np.ndarray:
    return (values.astype("float64") - imagery["dn_offset"]) / imagery["dn_scale"]


def normalized_difference(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return (first - second) / (first + second)


def evi(bands: dict[str, np.ndarray], spec: dict) -> np.ndarray:
    nir, red, blue = bands["nir"], bands["red"], bands["blue"]
    with np.errstate(divide="ignore", invalid="ignore"):
        denominator = nir + spec["red_coefficient"] * red - spec["blue_coefficient"] * blue + spec["canopy"]
        return spec["gain"] * (nir - red) / denominator


def compute(bands: dict[str, np.ndarray], specs: dict) -> dict[str, np.ndarray]:
    """Every configured index from reflectance arrays keyed by band role (red, nir, ...)."""
    result = {}
    for name, spec in specs.items():
        if spec["kind"] == "normalized_difference":
            first, second = spec["bands"]
            result[name] = normalized_difference(bands[first], bands[second])
        elif spec["kind"] == "evi":
            result[name] = evi(bands, spec)
        else:
            raise UnknownIndex(f"Tipo de índice desconocido: {spec['kind']}")
    return result


def summarize(values: np.ndarray, statistics: dict) -> dict | None:
    """Mean and spread of the finite values; None when there is nothing to summarize."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return None
    decimals = statistics["decimals"]
    low, high = np.percentile(finite, [statistics["low_percentile"], statistics["high_percentile"]])
    return {
        "mean": round(float(finite.mean()), decimals),
        "p25": round(float(low), decimals),
        "p75": round(float(high), decimals),
    }


def parcel_indices(raw_bands: dict[str, np.ndarray], valid: np.ndarray, config: dict) -> dict[str, dict | None]:
    """Index summaries over the valid pixels. `raw_bands` hold digital numbers on the same grid as `valid`."""
    bands = {role: reflectance(values[valid], config["imagery"]) for role, values in raw_bands.items()}
    return {name: summarize(values, config["statistics"]) for name, values in compute(bands, config["indices"]).items()}
