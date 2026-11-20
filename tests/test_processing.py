"""Processing a parcel end to end: queue, worker, series and climate. Runs only when the database answers (inside docker compose).

Sentinel-2 and NASA POWER are replaced by synthetic scenes on disk and a fake daily series; the items they produce
are removed from the catalog at the end.
"""

from datetime import date, timedelta
from functools import partial
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from cultivos.adapters.earth_search import EarthSearchAdapter
from cultivos.adapters.power import PowerAdapter
from cultivos.api.main import app
from cultivos.catalog import db
from cultivos.config import load_sources_config
from cultivos.jobs import store as jobs_store
from cultivos.jobs import worker
from cultivos.modules import processing
from tests.fake_s2 import AGRELO_PARCEL, CLOUD, SceneArea, make_scene

client = TestClient(app)
TODAY = date(2026, 10, 15)
TEST_PREFIX = "TEST-C2-"


def _postgis_available() -> bool:
    try:
        with db.connect() as connection:
            connection.execute("SELECT postgis_version()")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _postgis_available(), reason="PostGIS no disponible")


class FakeSearch:
    def __init__(self, items: list[dict]):
        self._items = items

    def items_as_dicts(self):
        return iter(self._items)


class FakeEarthSearch:
    """Answers like pystac-client, filtering the synthetic items by date."""

    def __init__(self, items: list[dict]):
        self.items = items
        self.searches = []

    def search(self, collections, bbox, datetime, query, sortby, max_items):
        start, end = (date.fromisoformat(part) for part in datetime.split("/"))
        self.searches.append((start, end))
        return FakeSearch([item for item in self.items if start <= date.fromisoformat(item["properties"]["datetime"][:10]) <= end])


class FakeResponse:
    status_code = 200

    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def fake_power_get(url: str, timeout: float) -> FakeResponse:
    """One mm of rain and 20 °C every day of the requested period."""
    query = parse_qs(urlparse(url).query)
    start = date.fromisoformat(f"{query['start'][0][:4]}-{query['start'][0][4:6]}-{query['start'][0][6:]}")
    end = date.fromisoformat(f"{query['end'][0][:4]}-{query['end'][0][4:6]}-{query['end'][0][6:]}")
    days = [(start + timedelta(days=offset)).strftime("%Y%m%d") for offset in range((end - start).days + 1)]
    values = {"T2M": 20.0, "T2M_MAX": 28.0, "T2M_MIN": 12.0, "PRECTOTCORR": 1.0}
    parameter = {name: {day: value for day in days} for name, value in values.items()}
    return FakeResponse({"properties": {"parameter": parameter}, "header": {"fill_value": -999.0}})


@pytest.fixture
def scenes(tmp_path):
    area = SceneArea([-68.8975, -33.136, -68.8932, -33.1333])
    folder = tmp_path / "s2"
    return [
        make_scene(folder, f"{TEST_PREFIX}JUL", "2026-07-12", area, cloud_cover=30),
        make_scene(folder, f"{TEST_PREFIX}AUG-CLOUDY", "2026-08-03", area, cloud_cover=2, scl=CLOUD),
        make_scene(folder, f"{TEST_PREFIX}AUG-CLEAR", "2026-08-21", area, cloud_cover=40),
        make_scene(folder, f"{TEST_PREFIX}SEP", "2026-09-09", area, cloud_cover=60, scl=CLOUD),
    ]


@pytest.fixture
def sources(scenes, monkeypatch):
    config = load_sources_config()
    earth_search = FakeEarthSearch(scenes)
    adapters = {
        "earth-search": EarthSearchAdapter("earth-search", config["earth-search"], open_client=lambda url, timeout: earth_search),
        "nasa-power": PowerAdapter("nasa-power", config["nasa-power"], http_get=fake_power_get),
    }
    monkeypatch.setattr(processing, "get_adapter", adapters.__getitem__)
    monkeypatch.setitem(worker.RUNNERS, processing.KIND, partial(processing.run, today=TODAY))
    yield earth_search
    with db.connect() as connection:
        rows = connection.execute(
            "SELECT id, collection FROM pgstac.items WHERE id LIKE %s OR (collection = 'nasa-power-daily' AND id LIKE %s)",
            [f"{TEST_PREFIX}%", "power-%-20230701-20261015"],
        ).fetchall()
        for item_id, collection in rows:
            connection.execute("SELECT pgstac.delete_item(%s, %s)", [item_id, collection])


@pytest.fixture
def parcel():
    response = client.post("/parcels", json={"name": "test procesamiento", "geometry": AGRELO_PARCEL})
    assert response.status_code == 201
    parcel_id = response.json()["id"]
    yield parcel_id
    client.delete(f"/parcels/{parcel_id}")


def run_queued(job: dict) -> dict:
    """Run this job as the worker would, without taking other jobs that may be waiting in the shared database."""
    with db.connect() as connection:
        connection.execute("UPDATE platform.jobs SET status = 'running', attempts = attempts + 1, heartbeat_at = now() WHERE id = %s", [job["id"]])
        worker.run_job(connection, jobs_store.get_job(connection, job["id"]))
    return client.get(f"/jobs/{job['id']}").json()


def months_of(series: dict) -> dict:
    return {month["month"]: month for campaign in series["campaigns"] for month in campaign["months"]}


def test_processing_builds_series_and_climate_and_reuses_closed_months(sources, parcel):
    queued = client.post(f"/parcels/{parcel}/process")
    assert queued.status_code == 202
    job = queued.json()["job"]
    assert queued.json()["created"] is True
    assert job["status"] == "queued"

    again = client.post(f"/parcels/{parcel}/process").json()
    assert again["created"] is False
    assert again["job"]["id"] == job["id"]
    assert client.get(f"/parcels/{parcel}/jobs").json()["jobs"][0]["id"] == job["id"]

    finished = run_queued(job)
    assert finished["status"] == "done", finished["error"]
    assert finished["progress"] == {"done": 41, "total": 41}
    assert finished["result"]["campaigns"] == ["2023/24", "2024/25", "2025/26", "2026/27"]
    assert finished["result"]["months"]["by_status"] == {"ok": 2, "cloudy": 1, "no_scene": 37}
    assert len(sources.searches) == 4
    assert sources.searches[-1] == (date(2026, 7, 1), date(2026, 10, 31))

    series = client.get(f"/parcels/{parcel}/series").json()
    assert [campaign["campaign"] for campaign in series["campaigns"]] == ["2023/24", "2024/25", "2025/26", "2026/27"]
    months = months_of(series)
    assert months["2026-07"]["indices"]["NDVI"]["mean"] == pytest.approx(0.75)
    assert months["2026-07"]["scene"]["date"] == "2026-07-12"
    assert months["2026-08"]["scene"]["id"] == f"{TEST_PREFIX}AUG-CLEAR"
    assert months["2026-08"]["candidates"] == 2
    assert months["2026-09"]["status"] == "cloudy"
    assert months["2026-09"]["indices"] is None
    assert months["2026-10"]["status"] == "no_scene"
    assert months["2026-10"]["complete"] is False
    assert "Copernicus Sentinel 2026" in series["source"]["attribution"]

    climate = client.get(f"/parcels/{parcel}/climate").json()
    current = climate["campaigns"][-1]
    assert current["campaign"] == "2026/27"
    assert [month["month"] for month in current["months"]] == ["2026-07", "2026-08", "2026-09", "2026-10"]
    assert current["months"][0]["PRECTOTCORR"] == 31.0
    assert current["months"][0]["T2M"] == 20.0
    assert current["months"][-1]["days"] == 15

    second = client.post(f"/parcels/{parcel}/process").json()
    assert second["created"] is True
    finished = run_queued(second["job"])
    assert finished["status"] == "done"
    assert finished["result"]["months"]["computed"] == 1
    assert finished["result"]["months"]["reused"] == 39
    assert sources.searches[-1] == (date(2026, 10, 1), date(2026, 10, 31))


def test_deleting_the_parcel_removes_its_jobs_and_results(sources):
    parcel_id = client.post("/parcels", json={"name": "test borrar", "geometry": AGRELO_PARCEL}).json()["id"]
    job = client.post(f"/parcels/{parcel_id}/process").json()["job"]
    run_queued(job)
    assert client.delete(f"/parcels/{parcel_id}").status_code == 204
    assert client.get(f"/jobs/{job['id']}").status_code == 404
    with db.connect() as connection:
        left = connection.execute("SELECT count(*) FROM platform.parcel_index_months WHERE parcel_id = %s", [parcel_id]).fetchone()[0]
    assert left == 0


def test_cut_jobs_go_back_to_the_queue_and_fail_after_the_last_attempt(parcel):
    job = client.post(f"/parcels/{parcel}/process").json()["job"]
    with db.connect() as connection, connection.transaction(force_rollback=True):
        connection.execute(
            "UPDATE platform.jobs SET status = 'running', attempts = 1, heartbeat_at = now() - interval '1 hour' WHERE id = %s",
            [job["id"]],
        )
        jobs_store.recover_stale(connection, stale_seconds=300, max_attempts=3)
        assert jobs_store.get_job(connection, job["id"])["status"] == "queued"

        connection.execute(
            "UPDATE platform.jobs SET status = 'running', attempts = 3, heartbeat_at = now() - interval '1 hour' WHERE id = %s",
            [job["id"]],
        )
        jobs_store.recover_stale(connection, stale_seconds=300, max_attempts=3)
        failed = jobs_store.get_job(connection, job["id"])
        assert failed["status"] == "failed"
        assert "3 veces" in failed["error"]


def test_claim_takes_a_queued_job_and_marks_it_running(parcel):
    client.post(f"/parcels/{parcel}/process")
    with db.connect() as connection, connection.transaction(force_rollback=True):
        claimed = jobs_store.claim_next(connection)
        assert claimed["status"] == "running"
        assert claimed["attempts"] >= 1


def test_missing_parcel_cannot_be_processed():
    assert client.post("/parcels/999999999/process").status_code == 404
    assert client.get("/parcels/999999999/series").status_code == 404
    assert client.get("/jobs/999999999").status_code == 404
