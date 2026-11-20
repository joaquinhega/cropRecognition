import pytest

from cultivos.zones import ZoneError, bbox_area_km2, parse_bbox, resolve_area


def test_named_zone_is_resolved():
    area = resolve_area("agrelo", None)
    assert area["name"] == "Agrelo"
    assert 3 < area["area_km2"] < 5


def test_free_bbox_takes_priority():
    area = resolve_area("agrelo", "-68.9,-33.2,-68.8,-33.1")
    assert area["id"] is None
    assert area["bbox"] == [-68.9, -33.2, -68.8, -33.1]


@pytest.mark.parametrize("text", ["1,2,3", "a,b,c,d", "-68.8,-33.1,-68.9,-33.2"])
def test_bad_bbox_is_rejected(text):
    with pytest.raises(ZoneError):
        parse_bbox(text)


def test_too_large_area_is_rejected():
    with pytest.raises(ZoneError):
        resolve_area(None, "-70,-36,-66,-32")


def test_unknown_zone_is_rejected():
    with pytest.raises(ZoneError):
        resolve_area("no-existe", None)


def test_area_of_one_degree_near_mendoza():
    assert 10000 < bbox_area_km2([-69, -34, -68, -33]) < 10600
