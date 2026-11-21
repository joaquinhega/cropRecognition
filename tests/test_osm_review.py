import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from cultivos import osm_review
from cultivos.api.main import app
from cultivos.config import load_inventory_config

client = TestClient(app)


def _square(west: float, south: float, size: float = 0.01) -> dict:
    ring = [[west, south], [west + size, south], [west + size, south + size], [west, south + size], [west, south]]
    return {"type": "Polygon", "coordinates": [ring]}


@pytest.fixture
def review(tmp_path, monkeypatch):
    """A 30-polygon sample in a temporary folder, with the real verdicts and threshold."""
    features = [
        {
            "type": "Feature",
            "geometry": _square(-68.9 + index * 0.02, -33.14),
            "properties": {"osm": f"way/{index}", "tags": {"landuse": "vineyard"}, "area_ha": 10.0, "oasis": "Norte"},
        }
        for index in range(30)
    ]
    sample_path = tmp_path / "sample.geojson"
    sample_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    config = {
        **load_inventory_config()["osm"]["review"],
        "sample_path": str(sample_path),
        "results_path": str(tmp_path / "results.json"),
    }
    monkeypatch.setattr(osm_review, "review_config", lambda: config)
    return config


def _answer(first: int, count: int, verdict: str) -> None:
    for n in range(first, first + count):
        osm_review.save_verdict(n, verdict)


def test_review_starts_in_progress(review):
    body = osm_review.read_review()
    assert len(body["features"]) == 30
    assert body["features"][0]["properties"]["n"] == 1
    assert body["summary"]["status"] == "in_progress"
    assert body["summary"]["max_mismatches"] == 3


def test_three_mismatches_still_pass(review):
    _answer(1, 3, "no_coincide")
    _answer(4, 27, "coincide")
    summary = osm_review.read_review()["summary"]
    assert summary["mismatches"] == 3
    assert summary["status"] == "approved"


def test_four_mismatches_mark_osm_doubtful_before_finishing(review):
    _answer(1, 4, "no_coincide")
    assert osm_review.read_review()["summary"]["status"] == "doubtful"


def test_partial_counts_as_match_and_uncertain_is_flagged(review):
    _answer(1, 3, "no_coincide")
    _answer(4, 1, "dudoso")
    _answer(5, 26, "parcial")
    summary = osm_review.read_review()["summary"]
    assert summary["status"] == "approved"
    assert summary["uncertain_could_fail"] is True


def test_verdict_keeps_note_and_can_change(review):
    osm_review.save_verdict(2, "no_coincide", "  es un olivar ")
    result = osm_review.save_verdict(2, "coincide", "hileras visibles")
    assert result["feature"]["properties"]["verdict"] == "coincide"
    assert result["feature"]["properties"]["note"] == "hileras visibles"
    assert result["summary"]["reviewed"] == 1


def test_unknown_verdict_and_polygon_are_rejected(review):
    assert client.put("/osm-review/1", json={"verdict": "tal_vez"}).status_code == 422
    assert client.put("/osm-review/31", json={"verdict": "coincide"}).status_code == 404
    assert client.get("/osm-review/0/scene").status_code == 404


def test_reference_scene_is_chosen_once(review, monkeypatch, earth_search_item):
    searches, ingested = [], []
    item = {**earth_search_item, "collection": "earth-search-sentinel-2-l2a"}

    class Fake:
        def search(self, request):
            searches.append(request)
            return [item]

    monkeypatch.setattr(osm_review, "get_adapter", lambda source_id: Fake())
    monkeypatch.setattr(osm_review, "ingest", lambda adapter, items: ingested.extend(items))
    monkeypatch.setattr(
        osm_review, "choose_scene", lambda candidates, polygon, imagery: SimpleNamespace(choice=SimpleNamespace(item=item, share=0.97))
    )

    first = client.get("/osm-review/3/scene").json()
    second = osm_review.reference_scene(3)
    assert first["scene"]["id"] == item["id"]
    assert first["scene"]["valid_share"] == 0.97
    assert "ndvi" in first["scene"]["layers"]
    assert second["scene"]["id"] == item["id"]
    assert len(searches) == 1 and len(ingested) == 1
    assert str(searches[0].start) == review["reference_start"]


def test_reference_scene_without_images_explains_why(review, monkeypatch):
    monkeypatch.setattr(osm_review, "get_adapter", lambda source_id: SimpleNamespace(search=lambda request: []))
    body = osm_review.reference_scene(1)
    assert body["scene"] is None
    assert "No hay imágenes" in body["reason"]
