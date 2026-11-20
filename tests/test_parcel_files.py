import io
import json
import zipfile
from pathlib import Path

import pytest

from cultivos.config import load_parcels_config
from cultivos.parcels.files import read_parcel_file
from cultivos.parcels.geometry import ParcelError

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = load_parcels_config()


def read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_geojson_keeps_names():
    found = read_parcel_file("parcels_sample.geojson", read("parcels_sample.geojson"), CONFIG)
    assert [item.name for item in found] == ["Lote norte", "Lote chico"]


def test_kml_reads_placemarks_and_holes():
    found = read_parcel_file("parcels_sample.kml", read("parcels_sample.kml"), CONFIG)
    assert [item.name for item in found] == ["Cuadro 1", "Cuadro 2 con galpón"]
    assert len(found[1].geometry["coordinates"]) == 2


def test_kmz_is_unzipped():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("doc.kml", read("parcels_sample.kml"))
    found = read_parcel_file("lotes.KMZ", buffer.getvalue(), CONFIG)
    assert len(found) == 2


def test_bare_geometry_and_points_are_handled():
    polygon = json.loads(read("parcels_sample.geojson"))["features"][0]["geometry"]
    assert len(read_parcel_file("a.json", json.dumps(polygon).encode(), CONFIG)) == 1
    points = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]}}]}
    with pytest.raises(ParcelError, match="no tiene polígonos"):
        read_parcel_file("a.geojson", json.dumps(points).encode(), CONFIG)


def test_other_projection_is_rejected():
    data = json.loads(read("parcels_sample.geojson"))
    data["crs"] = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32719"}}
    with pytest.raises(ParcelError, match="otra proyección"):
        read_parcel_file("a.geojson", json.dumps(data).encode(), CONFIG)


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("lotes.shp", b"x", "Formato no admitido"),
        ("lotes.geojson", b"", "vacío"),
        ("lotes.geojson", b"{not json", "GeoJSON válido"),
        ("lotes.kml", b"<kml><Placemark>", "KML válido"),
        ("lotes.kmz", b"not a zip", "dañado"),
    ],
)
def test_bad_files_explain_why(filename, content, message):
    with pytest.raises(ParcelError, match=message):
        read_parcel_file(filename, content, CONFIG)
