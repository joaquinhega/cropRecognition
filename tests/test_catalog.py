"""Integration with pgSTAC. Runs only when the database answers (inside docker compose)."""

from datetime import date

import pytest

from cultivos.adapters.earth_search import EarthSearchAdapter
from cultivos.catalog import db, items
from cultivos.catalog.db import CatalogUnavailable
from cultivos.catalog.ingest import ingest
from cultivos.config import load_sources_config

TEST_COLLECTION = "test-earth-search-sentinel-2-l2a"


def _database_available() -> bool:
    try:
        with db.connect() as connection:
            connection.execute("SELECT pgstac.get_version()")
        return True
    except (CatalogUnavailable, Exception):
        return False


pytestmark = pytest.mark.skipif(not _database_available(), reason="pgSTAC no disponible")


@pytest.fixture
def adapter():
    config = load_sources_config()["earth-search"]
    collection = {**config["collections"]["sentinel-2-l2a"], "catalog_id": TEST_COLLECTION}
    test_config = {**config, "collections": {"sentinel-2-l2a": collection}}
    yield EarthSearchAdapter("earth-search", test_config, open_client=lambda url, timeout: None)
    with db.connect() as connection:
        connection.execute("DELETE FROM pgstac.items WHERE collection = %s", [TEST_COLLECTION])
        connection.execute("DELETE FROM pgstac.collections WHERE id = %s", [TEST_COLLECTION])


def test_ingest_saves_once_and_updates_after(adapter, earth_search_item):
    item = adapter.normalize(earth_search_item, "sentinel-2-l2a")
    assert ingest(adapter, [item]) == {"saved": 1, "new": 1}
    assert ingest(adapter, [item]) == {"saved": 1, "new": 0}


def test_saved_items_are_found_by_zone_and_period(adapter, earth_search_item):
    ingest(adapter, [adapter.normalize(earth_search_item, "sentinel-2-l2a")])
    found = items.find([-68.9005, -33.149, -68.8795, -33.131], date(2026, 1, 1), date(2026, 1, 31), [TEST_COLLECTION])
    assert [item["id"] for item in found] == [earth_search_item["id"]]
    outside = items.find([-60.0, -30.0, -59.9, -29.9], date(2026, 1, 1), date(2026, 1, 31), [TEST_COLLECTION])
    assert outside == []


def test_stats_report_count_and_dates(adapter, earth_search_item):
    ingest(adapter, [adapter.normalize(earth_search_item, "sentinel-2-l2a")])
    with db.connect() as connection:
        stats = db.collection_stats(connection)[TEST_COLLECTION]
    assert stats == {"items": 1, "first": "2026-01-19", "last": "2026-01-19"}
