import numpy as np
import pytest

from cultivos.config import load_training_config
from cultivos.training.features import haze_mask, matrices, phenology

HAZE = {"index": "ndvi", "min_index_drop": 0.15, "blue": "blue", "min_blue_rise": 0.02, "swir": "swir", "max_swir_rise": 0.02}
CAMPAIGN = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]


def _rows(*values):
    return np.array(values, dtype=float)


def test_haze_needs_drop_brighter_blue_and_flat_swir():
    ndvi = _rows([0.6, 0.3, 0.6], [0.6, 0.3, 0.6], [0.6, 0.55, 0.6])
    blue = _rows([0.04, 0.08, 0.04], [0.04, 0.08, 0.04], [0.04, 0.08, 0.04])
    swir = _rows([0.25, 0.25, 0.25], [0.25, 0.35, 0.25], [0.25, 0.25, 0.25])
    mask = haze_mask({"ndvi": ndvi, "blue": blue, "swir": swir}, HAZE)
    assert mask.tolist() == [[False, True, False], [False, False, False], [False, False, False]]


def test_haze_skips_edges_and_gaps():
    ndvi = _rows([0.2, 0.6, np.nan, 0.3])
    blue = _rows([0.09, 0.04, np.nan, 0.09])
    swir = _rows([0.2, 0.2, np.nan, 0.2])
    assert not haze_mask({"ndvi": ndvi, "blue": blue, "swir": swir}, HAZE).any()


def test_phenology_finds_peak_season_and_green_months():
    settings = load_training_config()["features"]
    curve = _rows(
        [0.2, 0.2, 0.2, 0.2, 0.3, 0.8, 0.9, 0.6, 0.3, 0.2, 0.2, 0.2],
        [np.nan] * 12,
    )
    shape = phenology(curve, CAMPAIGN, settings)
    assert shape["peak_value"][0] == 0.9 and shape["peak_month"][0] == 6
    assert shape["rise_month"][0] == 5 and shape["fall_month"][0] == 7
    assert shape["green_months"][0] == 3
    assert shape["amplitude"][0] == pytest.approx(0.7)
    assert shape["winter_mean"][0] == pytest.approx(0.2)
    assert shape["summer_mean"][0] == pytest.approx((0.8 + 0.9 + 0.6 + 0.3) / 4)
    assert all(np.isnan(values[1]) for values in shape.values())


def test_matrices_place_observations_by_pixel_and_month():
    observations = [
        {"pixel_id": "P-2", "month": "2024-08", "ndvi": "0.5"},
        {"pixel_id": "P-1", "month": "2024-07", "ndvi": ""},
    ]
    result = matrices(observations, ["P-1", "P-2"], ["2024-07", "2024-08"], ["ndvi"])["ndvi"]
    assert np.isnan(result[0]).all() and result[1, 1] == 0.5
