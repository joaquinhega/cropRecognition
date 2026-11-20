from datetime import date

import httpx
import pytest

from cultivos.adapters import active_adapters, all_sources_info
from cultivos.adapters.base import SOURCE_PROPERTY, SearchRequest, SourceError, attribution_text
from cultivos.adapters.earth_search import EarthSearchAdapter
from cultivos.adapters.power import PowerAdapter, monthly
from cultivos.config import load_sources_config

REQUEST = SearchRequest(bbox=[-68.9005, -33.149, -68.8795, -33.131], start=date(2026, 1, 1), end=date(2026, 1, 31), max_cloud_cover=40, limit=10)


class FakeSearch:
    def __init__(self, items):
        self._items = items

    def items_as_dicts(self):
        return iter(self._items)


class FakeClient:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return FakeSearch(self.items)


def earth_search(items):
    client = FakeClient(items)
    adapter = EarthSearchAdapter("earth-search", load_sources_config()["earth-search"], open_client=lambda url, timeout: client)
    return adapter, client


def test_only_active_sources_get_an_adapter():
    adapters = active_adapters()
    assert set(adapters) == {"earth-search", "nasa-power", "conae-saocom"}
    statuses = {source["id"]: source["status"] for source in all_sources_info()}
    assert statuses["nasa-hls"] == "postergada"


def test_earth_search_normalizes_items_for_our_catalog(earth_search_item):
    adapter, client = earth_search([earth_search_item])
    items = adapter.search(REQUEST)
    assert len(items) == 1
    item = items[0]
    assert item["collection"] == "earth-search-sentinel-2-l2a"
    assert item["properties"][SOURCE_PROPERTY] == "earth-search"
    assert item["links"] == [
        {
            "rel": "via",
            "href": earth_search_item["links"][0]["href"],
            "type": "application/geo+json",
            "title": "Ítem en Earth Search",
        }
    ]
    assert item["assets"]["red"]["href"].startswith("https://sentinel-cogs")


def test_earth_search_sends_the_cloud_filter_and_period(earth_search_item):
    adapter, client = earth_search([earth_search_item])
    adapter.search(REQUEST)
    call = client.calls[0]
    assert call["collections"] == ["sentinel-2-l2a"]
    assert call["datetime"] == "2026-01-01/2026-01-31"
    assert call["query"] == {"eo:cloud_cover": {"lte": 40}}
    assert call["max_items"] == 10


def test_earth_search_collection_has_license_and_attribution():
    adapter, _ = earth_search([])
    collection = adapter.collections()[0]
    assert collection["id"] == "earth-search-sentinel-2-l2a"
    assert collection["links"][0]["rel"] == "license"
    assert "Copernicus" in collection["cultivos:attribution"]


def test_earth_search_network_error_becomes_source_error():
    def broken(url, timeout):
        raise OSError("sin red")

    adapter = EarthSearchAdapter("earth-search", load_sources_config()["earth-search"], open_client=broken)
    with pytest.raises(SourceError):
        adapter.search(REQUEST)


def power(payload, status=200):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return httpx.Response(status, json=payload)

    return PowerAdapter("nasa-power", load_sources_config()["nasa-power"], http_get=fake_get), calls


def test_power_parses_series_and_drops_fill_values(power_payload):
    adapter, _ = power(power_payload)
    rows = adapter.parse_series(power_payload)
    assert [row["date"] for row in rows] == ["2026-01-30", "2026-01-31", "2026-02-01"]
    assert rows[2]["T2M_MAX"] is None
    assert rows[1]["PRECTOTCORR"] == 5.5


def test_power_monthly_uses_mean_and_sum(power_payload):
    adapter, _ = power(power_payload)
    result = monthly(adapter.parse_series(power_payload), adapter.config["parameters"])
    january = result[0]
    assert january["month"] == "2026-01"
    assert january["T2M"] == 25.0
    assert january["PRECTOTCORR"] == 5.5
    assert result[1]["T2M_MAX"] is None


def test_power_item_points_to_the_query(power_payload):
    adapter, calls = power(power_payload)
    items = adapter.search(REQUEST)
    item = items[0]
    assert item["collection"] == "nasa-power-daily"
    assert item["properties"]["start_datetime"] == "2026-01-01T00:00:00Z"
    assert item["properties"]["end_datetime"] == "2026-01-31T23:59:59Z"
    assert item["assets"]["data"]["href"] == calls[0]
    assert "community=AG" in calls[0]
    assert "start=20260101" in calls[0]


def test_power_bad_status_becomes_source_error(power_payload):
    adapter, _ = power({"messages": ["error"]}, status=422)
    with pytest.raises(SourceError):
        adapter.search(REQUEST)


@pytest.mark.parametrize(
    "catalog, expected",
    [
        ({"first": "2025-11-15", "last": "2026-10-31"}, "Copernicus Sentinel 2025-2026"),
        ({"first": "2026-01-01", "last": "2026-03-01"}, "Copernicus Sentinel 2026"),
        (None, "Copernicus Sentinel"),
    ],
)
def test_attribution_years(catalog, expected):
    assert attribution_text("Copernicus Sentinel {year}", catalog) == expected
