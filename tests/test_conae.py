"""CONAE SAOCOM adapter, with a response recorded from the public catalog (2026-11-19)."""

import json
from datetime import date

import httpx
import pytest

from cultivos.adapters.base import SOURCE_PROPERTY, SearchRequest, SourceError
from cultivos.adapters.conae import ConaeSaocomAdapter
from cultivos.config import load_sources_config

REQUEST = SearchRequest(bbox=[-68.9005, -33.149, -68.8795, -33.131], start=date(2026, 8, 21), end=date(2026, 11, 19), limit=50)


def adapter_with(pages, status=200):
    calls = []

    def fake_get(url, params, timeout):
        calls.append({"url": url, **params})
        return httpx.Response(status, json=pages[min(len(calls) - 1, len(pages) - 1)])

    return ConaeSaocomAdapter("conae-saocom", load_sources_config()["conae-saocom"], http_get=fake_get), calls


def test_query_has_zone_period_and_order(saocom_page):
    adapter, calls = adapter_with([saocom_page])
    adapter.search(REQUEST)
    call = calls[0]
    assert call["url"] == "https://catalog.saocom.conae.gov.ar/api/catalog/"
    filters = json.loads(call["q"])
    assert filters[0]["field"] == "geom" and filters[0]["op"] == "intersects"
    assert filters[1] == {"field": "frameEndTime", "op": "ge", "value": "2026-08-21T00:00:00Z"}
    assert filters[2] == {"field": "frameStartTime", "op": "le", "value": "2026-11-19T23:59:59Z"}
    assert json.loads(call["order_by"])[0] == {"field": "frameStartTime", "ord": "desc"}


def test_products_become_stac_items(saocom_page):
    adapter, _ = adapter_with([saocom_page])
    items = adapter.search(REQUEST)
    assert [item["id"] for item in items] == ["EOL1ASARSAO1A15838302", "EOL1ASARSAO1A15838324"]
    item = items[0]
    assert item["collection"] == "conae-saocom-1"
    assert item["properties"]["platform"] == "saocom-1a"
    assert item["properties"]["sar:instrument_mode"] == "STRIPMAP"
    assert item["properties"]["sat:orbit_state"] == "ascending"
    assert item["properties"]["saocom:download_allowed"] is False
    assert item["properties"][SOURCE_PROPERTY] == "conae-saocom"
    assert item["bbox"] == [-69.162072, -33.564522, -68.70945, -32.89018]
    assert item["assets"]["thumbnail"]["href"].startswith("https://catalog.saocom.conae.gov.ar/thumbnails/")


def test_pages_until_count(saocom_page):
    first = {**saocom_page, "results": saocom_page["results"][:1], "count": 2}
    second = {**saocom_page, "results": saocom_page["results"][1:], "count": 2, "offset": 1}
    adapter, calls = adapter_with([first, second])
    items = adapter.search(REQUEST)
    assert len(items) == 2
    assert [call["offset"] for call in calls] == [0, 1]


def test_bad_status_becomes_source_error():
    adapter, _ = adapter_with([{"detail": "error"}], status=500)
    with pytest.raises(SourceError):
        adapter.search(REQUEST)
