import numpy as np
import pytest

from cultivos.config import load_processing_config
from cultivos.modules.indices import compute, parcel_indices, summarize

CONFIG = load_processing_config()


def test_indices_of_a_green_vine_pixel():
    bands = {name: np.array([value]) for name, value in {"blue": 0.03, "red": 0.05, "rededge": 0.15, "nir": 0.35, "swir": 0.2}.items()}
    result = {name: float(values[0]) for name, values in compute(bands, CONFIG["indices"]).items()}
    assert result["NDVI"] == pytest.approx(0.75)
    assert result["NDRE"] == pytest.approx(0.4)
    assert result["NDMI"] == pytest.approx(0.15 / 0.55)
    assert result["EVI"] == pytest.approx(2.5 * 0.3 / 1.425)


def test_summary_ignores_divisions_by_zero():
    values = np.array([0.2, 0.4, np.nan, np.inf, 0.6])
    assert summarize(values, CONFIG["statistics"]) == {"mean": 0.4, "p25": 0.3, "p75": 0.5}
    assert summarize(np.array([np.nan]), CONFIG["statistics"]) is None


def test_only_valid_pixels_count():
    raw = {"blue": [300, 300], "red": [500, 4000], "rededge": [1500, 4000], "nir": [3500, 4000], "swir": [2000, 4000]}
    raw = {name: np.array(values) for name, values in raw.items()}
    valid = np.array([True, False])
    assert parcel_indices(raw, valid, CONFIG)["NDVI"] == {"mean": 0.75, "p25": 0.75, "p75": 0.75}
