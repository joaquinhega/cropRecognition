"""Parcel endpoints against PostGIS. Runs only when the database answers (inside docker compose)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cultivos.api.main import app
from cultivos.catalog import db

FIXTURES = Path(__file__).parent / "fixtures"
client = TestClient(app)


def _postgis_available() -> bool:
    try:
        with db.connect() as connection:
            connection.execute("SELECT postgis_version()")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _postgis_available(), reason="PostGIS no disponible")


@pytest.fixture
def created():
    ids = []
    yield ids
    for parcel_id in ids:
        client.delete(f"/parcels/{parcel_id}")


def upload(name: str):
    return client.post("/parcels/import", params={"filename": name}, content=(FIXTURES / name).read_bytes())


def test_drawn_parcel_is_saved_listed_renamed_and_deleted(created):
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-68.8975, -33.136], [-68.8932, -33.136], [-68.8932, -33.1333], [-68.8975, -33.1333], [-68.8975, -33.136]]],
    }
    response = client.post("/parcels", json={"name": "test dibujada", "geometry": geometry})
    assert response.status_code == 201
    parcel = response.json()
    created.append(parcel["id"])
    assert parcel["properties"]["code"].startswith("P-")
    assert parcel["properties"]["area_ha"] == pytest.approx(12, rel=0.02)
    assert parcel["properties"]["origin"] == "drawn"

    listed = client.get("/parcels").json()
    assert listed["limits"]["max_area_ha"] == 1000
    assert any(feature["id"] == parcel["id"] for feature in listed["features"])

    renamed = client.patch(f"/parcels/{parcel['id']}", json={"name": "test renombrada"}).json()
    assert renamed["properties"]["name"] == "test renombrada"

    assert client.delete(f"/parcels/{parcel['id']}").status_code == 204
    assert client.get(f"/parcels/{parcel['id']}").status_code == 404
    created.remove(parcel["id"])


def test_geojson_upload_flags_the_small_parcel(created):
    response = upload("parcels_sample.geojson")
    assert response.status_code == 201
    parcels = response.json()["created"]
    created.extend(parcel["id"] for parcel in parcels)
    flags = {parcel["properties"]["name"]: parcel["properties"]["below_minimum"] for parcel in parcels}
    assert flags == {"Lote norte": False, "Lote chico": True}


def test_kml_upload_keeps_the_hole(created):
    response = upload("parcels_sample.kml")
    assert response.status_code == 201
    parcels = response.json()["created"]
    created.extend(parcel["id"] for parcel in parcels)
    with_hole = next(parcel for parcel in parcels if parcel["properties"]["name"] == "Cuadro 2 con galpón")
    assert len(with_hole["geometry"]["coordinates"]) == 2
    assert with_hole["properties"]["area_ha"] == pytest.approx(8, rel=0.02)
    assert with_hole["properties"]["source_file"] == "parcels_sample.kml"


@pytest.mark.parametrize(("name", "message"), [("parcel_too_big.geojson", "máximo"), ("parcel_crossed.geojson", "se cruza")])
def test_rejected_upload_saves_nothing(name, message):
    before = len(client.get("/parcels").json()["features"])
    response = upload(name)
    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert len(client.get("/parcels").json()["features"]) == before


def test_drawn_parcel_over_the_maximum_is_rejected():
    geometry = {"type": "Polygon", "coordinates": [[[-68.92, -33.16], [-68.877, -33.16], [-68.877, -33.133], [-68.92, -33.133], [-68.92, -33.16]]]}
    response = client.post("/parcels", json={"name": "test grande", "geometry": geometry})
    assert response.status_code == 422
    assert "máximo es 1.000 ha" in response.json()["detail"]


def test_missing_parcel_is_404():
    assert client.patch("/parcels/999999999", json={"name": "x"}).status_code == 404
