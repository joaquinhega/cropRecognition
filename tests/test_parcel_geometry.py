import pytest
from shapely.geometry import Polygon

from cultivos.config import load_parcels_config
from cultivos.parcels.geometry import ParcelError, check_polygon, clean_name, format_ha, split_polygons

CONFIG = load_parcels_config()
METERS_PER_DEGREE_LAT = 110_900
METERS_PER_DEGREE_LON = 93_210


def square(side_m: float, lon: float = -68.89, lat: float = -33.14) -> Polygon:
    dx, dy = side_m / METERS_PER_DEGREE_LON, side_m / METERS_PER_DEGREE_LAT
    return Polygon([(lon, lat), (lon, lat + dy), (lon + dx, lat + dy), (lon + dx, lat)])


def test_area_is_measured_in_hectares():
    checked = check_polygon(square(200), CONFIG)
    assert checked.area_ha == pytest.approx(4, rel=0.01)
    assert not checked.below_minimum


def test_polygon_is_stored_counterclockwise():
    assert check_polygon(square(200), CONFIG).polygon.exterior.is_ccw


def test_small_parcel_is_flagged_not_rejected():
    checked = check_polygon(square(80), CONFIG)
    assert checked.below_minimum
    assert checked.area_ha == pytest.approx(0.64, rel=0.02)


def test_parcel_over_the_maximum_is_rejected():
    with pytest.raises(ParcelError, match="máximo es 1.000 ha"):
        check_polygon(square(3500), CONFIG)


def test_self_crossing_border_is_rejected_with_its_place():
    bowtie = Polygon([(-68.895, -33.140), (-68.890, -33.135), (-68.890, -33.140), (-68.895, -33.135)])
    with pytest.raises(ParcelError, match="se cruza consigo mismo cerca de -33.1375"):
        check_polygon(bowtie, CONFIG)


def test_projected_coordinates_are_rejected():
    projected = Polygon([(500000, 6330000), (500400, 6330000), (500400, 6330300)])
    with pytest.raises(ParcelError, match="EPSG:4326"):
        check_polygon(projected, CONFIG)


def test_hole_reduces_the_area():
    outer = square(300)
    hole = square(100, lon=-68.889, lat=-33.139)
    checked = check_polygon(Polygon(outer.exterior.coords, [hole.exterior.coords]), CONFIG)
    assert checked.area_ha == pytest.approx(8, rel=0.02)


def test_multipolygon_gives_one_polygon_per_part():
    geometry = {
        "type": "MultiPolygon",
        "coordinates": [[list(square(100).exterior.coords)], [list(square(100, lon=-68.88).exterior.coords)]],
    }
    assert len(split_polygons(geometry)) == 2


def test_points_are_not_parcels():
    with pytest.raises(ParcelError, match="llegó Point"):
        split_polygons({"type": "Point", "coordinates": [-68.89, -33.14]})


def test_names_are_trimmed_and_required():
    assert clean_name("  Lote   norte ", CONFIG) == "Lote norte"
    with pytest.raises(ParcelError):
        clean_name("   ", CONFIG)
    with pytest.raises(ParcelError):
        clean_name("x" * (CONFIG["name_max_length"] + 1), CONFIG)


def test_hectares_use_argentine_format():
    assert format_ha(1234.4) == "1.234"
    assert format_ha(12.34) == "12,3"
