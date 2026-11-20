import numpy as np
import pytest
from pyproj import Geod
from shapely.geometry import shape

from cultivos.config import load_processing_config
from cultivos.modules.indices import parcel_indices
from cultivos.modules.scenes import SceneReadError, choose_scene, parcel_mask, read_bands, read_mask_grid, read_on_grid
from tests.fake_s2 import AGRELO_PARCEL, CLEAR, CLOUD, SceneArea, half_cloudy_scl, make_scene

IMAGERY = load_processing_config()["imagery"]
CONFIG = load_processing_config()
POLYGON = shape(AGRELO_PARCEL)
AREA = SceneArea(list(POLYGON.bounds))


def test_cloud_mask_defines_a_10_m_grid_that_the_bands_follow(tmp_path):
    gradient = np.tile(np.arange(AREA.shape(10)[1], dtype="uint16"), (AREA.shape(10)[0], 1))
    item = make_scene(tmp_path, "S1", "2026-07-10", AREA, cloud_cover=1, values={"red": gradient})
    scl, grid = read_mask_grid(item["assets"]["scl"]["href"], list(POLYGON.bounds), IMAGERY["grid_m"])
    assert grid.res == 10
    assert scl.shape == (grid.height, grid.width)
    red = read_on_grid(item["assets"]["red"]["href"], grid)
    swir = read_on_grid(item["assets"]["swir16"]["href"], grid)
    assert red.shape == swir.shape == scl.shape
    first_column = round((grid.transform.c - AREA.left) / 10)
    assert red[0, 0] == first_column
    assert red[0, 1] == first_column + 1


def test_parcel_mask_counts_the_pixels_whose_center_is_inside(tmp_path):
    item = make_scene(tmp_path, "S1", "2026-07-10", AREA, cloud_cover=1)
    _, grid = read_mask_grid(item["assets"]["scl"]["href"], list(POLYGON.bounds), IMAGERY["grid_m"])
    area_m2 = abs(Geod(ellps="WGS84").geometry_area_perimeter(POLYGON)[0])
    assert parcel_mask(POLYGON, grid).sum() == pytest.approx(area_m2 / 100, rel=0.03)


def test_least_cloudy_scene_is_tried_first_but_the_cleanest_wins(tmp_path):
    cloudy = make_scene(tmp_path, "CLOUDY", "2026-08-03", AREA, cloud_cover=2, scl=CLOUD)
    clear = make_scene(tmp_path, "CLEAR", "2026-08-13", AREA, cloud_cover=40)
    pick = choose_scene([clear, cloudy], POLYGON, IMAGERY)
    assert pick.choice.item["id"] == "CLEAR"
    assert pick.choice.share == 1
    assert pick.candidates == 2


def test_a_fully_clean_scene_stops_the_search(tmp_path):
    first = make_scene(tmp_path, "FIRST", "2026-08-03", AREA, cloud_cover=1)
    broken = make_scene(tmp_path, "BROKEN", "2026-08-13", AREA, cloud_cover=50)
    broken["assets"] = {**broken["assets"], "scl": {"href": str(tmp_path / "missing.tif")}}
    pick = choose_scene([broken, first], POLYGON, IMAGERY)
    assert pick.choice.item["id"] == "FIRST"
    assert pick.read_errors == 0


def test_unreadable_scene_is_skipped(tmp_path):
    good = make_scene(tmp_path, "GOOD", "2026-08-13", AREA, cloud_cover=50, scl=half_cloudy_scl(AREA))
    broken = make_scene(tmp_path, "BROKEN", "2026-08-03", AREA, cloud_cover=1)
    broken["assets"] = {**broken["assets"], "scl": {"href": str(tmp_path / "missing.tif")}}
    pick = choose_scene([broken, good], POLYGON, IMAGERY)
    assert pick.choice.item["id"] == "GOOD"
    assert pick.read_errors == 1


def test_cloudy_pixels_stay_out_of_the_indices(tmp_path):
    scl = half_cloudy_scl(AREA)
    nir = np.full(AREA.shape(10), 3500, dtype="uint16")
    nir[:, : 2 * (scl.shape[1] // 2)] = 9000
    item = make_scene(tmp_path, "HALF", "2026-08-13", AREA, cloud_cover=30, scl=scl, values={"nir": nir})
    choice = choose_scene([item], POLYGON, IMAGERY).choice
    assert 0.2 < choice.share < 0.8
    assert choice.valid_pixels < choice.parcel_pixels
    indices = parcel_indices(read_bands(item, choice.grid, IMAGERY), choice.valid, CONFIG)
    assert indices["NDVI"]["mean"] == pytest.approx(0.75)


def test_misaligned_band_is_refused(tmp_path):
    item = make_scene(tmp_path, "SHIFT", "2026-08-13", AREA, cloud_cover=1, shift_red_m=5)
    choice = choose_scene([item], POLYGON, IMAGERY).choice
    with pytest.raises(SceneReadError, match="alineado"):
        read_bands(item, choice.grid, IMAGERY)


def test_scene_classes_are_the_ones_of_sentinel_2():
    assert CLEAR not in IMAGERY["invalid_scl_classes"]
    assert CLOUD in IMAGERY["invalid_scl_classes"]
