from fastapi.testclient import TestClient

from cultivos.adapters.base import SourceError
from cultivos.api import platform
from cultivos.api.main import app

client = TestClient(app)


def test_zones_lists_the_default_zone():
    body = client.get("/zones").json()
    assert body["default_zone"] == "agrelo"
    assert any(zone["id"] == "agrelo" for zone in body["zones"])


def test_search_rejects_a_bad_bbox():
    response = client.get("/search", params={"bbox": "1,2,3"})
    assert response.status_code == 422


def test_search_reports_a_source_error_without_failing(monkeypatch):
    class Broken:
        def search(self, request):
            raise SourceError("Earth Search no responde")

    monkeypatch.setattr(platform, "get_adapter", lambda source_id: Broken())
    response = client.get("/search", params={"zone": "agrelo", "sources": "earth-search"})
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["error"] == "Earth Search no responde"
    assert result["found"] == 0


def test_search_saves_what_the_source_returns(monkeypatch, earth_search_item):
    saved = []

    class Fake:
        def search(self, request):
            return [{**earth_search_item, "collection": "earth-search-sentinel-2-l2a"}]

    monkeypatch.setattr(platform, "get_adapter", lambda source_id: Fake())
    monkeypatch.setattr(platform, "ingest", lambda adapter, items: saved.extend(items) or {"saved": len(items), "new": len(items)})
    body = client.get("/search", params={"zone": "agrelo", "start": "2026-01-01", "end": "2026-01-31"}).json()
    assert body["results"][0]["found"] == 1
    assert body["results"][0]["new"] == 1
    assert body["results"][0]["items"][0]["date"] == "2026-01-19"
    assert saved[0]["id"] == earth_search_item["id"]


def test_old_imagery_endpoints_are_gone():
    assert client.get("/imagery").status_code == 404
