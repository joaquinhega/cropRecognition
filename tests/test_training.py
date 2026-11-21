from datetime import date
from functools import partial

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from pyproj import Transformer
from rasterio.transform import from_origin

from cultivos.api.main import app
from cultivos.config import load_processing_config, load_training_config
from cultivos.training import build_table, dataset, features, summary
from cultivos.training.labels import homogeneous, map_legend, sample_pixels
from cultivos.training.series import month_observations, read_points

client = TestClient(app)
LEGEND = {1: "Soja 1ra", 2: "Soja 2da", 3: "Maíz", 4: "Girasol", 5: "No agrícola", 6: "Sin dato", 7: "Maíz/Soja", 31: "Máscara", 255: "255"}
IMAGERY = load_processing_config()["imagery"]
INDICES = load_processing_config()["indices"]


def test_legend_maps_keywords_rest_and_exclusions():
    mapping = map_legend(LEGEND, load_training_config()["labels"])
    assert mapping == {1: "soja", 2: "soja", 3: "maiz", 4: "otros", 5: "otros", 6: None, 7: None, 31: None, 255: None}


def test_homogeneous_needs_every_neighbor_equal():
    data = np.ones((5, 5), dtype=int)
    data[0, 0] = 2
    mask = homogeneous(data, 1)
    assert not mask[0].any() and not mask[:, 0].any()
    assert not mask[1, 1]
    assert mask[2, 2] and mask[3, 3]


def test_sample_is_capped_reproducible_and_from_pixel_centers():
    data = np.full((10, 10), 1)
    data[:, 5:] = 3
    transform = from_origin(-60.0, -33.0, 0.001, 0.001)
    mapping = {1: "soja", 3: "maiz"}
    config = {"per_class": 5, "seed": 1, "homogeneous_radius": 1}
    first, stats = sample_pixels(data, transform, mapping, ["soja", "maiz", "otros"], config)
    second, _ = sample_pixels(data, transform, mapping, ["soja", "maiz", "otros"], config)
    assert first == second
    assert stats == {"soja": {"candidates": 24, "sampled": 5}, "maiz": {"candidates": 24, "sampled": 5}, "otros": {"candidates": 0, "sampled": 0}}
    soja = [pixel for pixel in first if pixel["class"] == "soja"]
    assert all(pixel["lon"] < -60.0 + 0.004 for pixel in soja)
    assert all(round((pixel["lon"] + 60.0) / 0.001 % 1, 6) == 0.5 for pixel in first)


def _item(item_id: str, day: str, cloud: float) -> dict:
    return {
        "id": item_id,
        "collection": IMAGERY["collection"],
        "properties": {"datetime": f"{day}T14:00:00Z", "eo:cloud_cover": cloud},
        "assets": {asset: {"href": f"{item_id}|{asset}"} for asset in IMAGERY["assets"].values()},
    }


def _fake_reader(clean_by_scene: dict[str, set[int]], href: str, lons, lats):
    """Points are numbered by their longitude; SCL 4 (vegetation) where clean, 9 (cloud) elsewhere; bands constant."""
    scene, asset = href.split("|")
    positions = [int(round(lon)) for lon in lons]
    if asset == IMAGERY["assets"]["scl"]:
        return np.array([4 if position in clean_by_scene[scene] else 9 for position in positions])
    value = {IMAGERY["assets"]["nir"]: 4000, IMAGERY["assets"]["red"]: 1000}.get(asset, 500)
    return np.full(len(positions), value)


def test_each_pixel_takes_the_best_ranked_clean_scene():
    lons = np.arange(5.0)
    lats = np.zeros(5)
    candidates = [_item("A", "2025-01-05", 1.0), _item("B", "2025-01-20", 30.0)]
    reader = partial(_fake_reader, {"A": {0, 1}, "B": {1, 2, 3}})
    rows, info = month_observations("2025-01", candidates, lons, lats, IMAGERY, INDICES, reader)
    by_pixel = {row["pixel"]: row for row in rows}
    assert {pixel: row["scene_id"] for pixel, row in by_pixel.items()} == {1: "B", 2: "B", 3: "B", 0: "A"}
    assert info["pixels_with_data"] == 4 and info["share_with_data"] == 0.8
    assert [scene["id"] for scene in info["scenes"]] == ["B", "A"]
    assert by_pixel[0]["ndvi"] == 0.6
    assert by_pixel[0]["nir"] == 0.4


def test_campaign_months_go_from_july_to_june():
    months = dataset.campaign_months(date(2024, 7, 1), 12)
    assert [months[0].key, months[-1].key] == ["2024-07", "2025-06"]
    assert {month.campaign for month in months} == {"2024/25"}


@pytest.fixture
def built(tmp_path, monkeypatch):
    """A whole build with a synthetic crop map and scenes, written to a temporary folder."""
    config = {**load_training_config(), "output_dir": str(tmp_path), "months": 2}
    config["sample"] = {**config["sample"], "per_class": 3}
    monkeypatch.setattr(build_table, "load_training_config", lambda: config)
    monkeypatch.setattr(summary, "load_training_config", lambda: config)

    data = np.full((12, 12), 5)
    data[:, :4], data[:, 4:8] = 1, 3
    transform = from_origin(-60.7, -33.8, 0.0003, 0.0003)
    monkeypatch.setattr(build_table, "load_label_map", lambda labels, bbox, folder: (data, transform, LEGEND))

    class Fake:
        def search(self, request):
            scenes = [_item("S1", "2024-07-10", 5.0), _item("S2", "2024-08-10", 5.0)]
            return [item for item in scenes if request.start.isoformat() <= item["properties"]["datetime"][:10] <= request.end.isoformat()]

    ingested = []
    monkeypatch.setattr(build_table, "get_adapter", lambda source: Fake())
    monkeypatch.setattr(build_table, "ingest", lambda adapter, items: ingested.extend(items))

    def reader(href, lons, lats):
        scene, asset = href.split("|")
        if asset == IMAGERY["assets"]["scl"]:
            return np.full(len(lons), 4 if scene == "S1" else 9)
        return np.full(len(lons), 3000)

    monkeypatch.setattr(build_table, "month_observations", partial(month_observations, reader=reader))
    result = build_table.build()
    return result, ingested


def test_build_writes_sample_observations_and_summary(built):
    result, ingested = built
    assert result["pixels"] == 9
    assert {name: info["pixels"] for name, info in result["classes"].items()} == {"soja": 3, "maiz": 3, "otros": 3}
    assert [info["pixels_with_data"] for info in result["months"]] == [9, 0]
    assert result["observations"] == 9
    assert [item["id"] for item in ingested] == ["S1"]


def test_build_stops_when_the_sample_no_longer_matches_the_mapping(built, monkeypatch):
    config = build_table.load_training_config()
    labels = {**config["labels"], "exclude_values": [*config["labels"]["exclude_values"], 5]}
    monkeypatch.setattr(build_table, "load_training_config", lambda: {**config, "labels": labels})
    with pytest.raises(build_table.SampleOutdated):
        build_table.build()
    assert build_table.build(rebuild_sample=True)["classes"]["otros"]["pixels"] == 0


def test_build_reuses_finished_months(built, monkeypatch):
    monkeypatch.setattr(build_table, "get_adapter", lambda source: pytest.fail("should not search again"))
    assert build_table.build()["observations"] == 9


def test_api_returns_curves_and_pixels(built):
    body = client.get("/training", params={"index": "NDVI"}).json()
    assert body["available"] is True
    assert body["curves"]["months"] == ["2024-07", "2024-08"]
    assert body["curves"]["classes"]["soja"]["with_data"] == [3, 0]
    assert body["curves"]["classes"]["soja"]["median"] == [0.0, None]
    pixels = client.get("/training/pixels").json()
    assert len(pixels["features"]) == 9
    assert client.get("/training", params={"index": "XYZ"}).status_code == 422


def test_api_explains_how_to_build_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(summary, "load_training_config", lambda: {**load_training_config(), "output_dir": str(tmp_path)})
    body = client.get("/training").json()
    assert body == {"available": False, "command": summary.BUILD_COMMAND}


def test_read_points_reads_values_and_marks_points_outside(tmp_path):
    path = tmp_path / "band.tif"
    values = np.arange(100, dtype="uint16").reshape(10, 10) + 1
    transform = from_origin(300000, 6250000, 10, 10)
    with rasterio.open(path, "w", driver="GTiff", width=10, height=10, count=1, dtype="uint16", crs="EPSG:32720", transform=transform) as dst:
        dst.write(values, 1)

    to_lonlat = Transformer.from_crs("EPSG:32720", "EPSG:4326", always_xy=True)
    inside_lon, inside_lat = to_lonlat.transform(300025, 6249975)
    outside_lon, outside_lat = to_lonlat.transform(299000, 6249975)
    result = read_points(str(path), np.array([inside_lon, outside_lon]), np.array([inside_lat, outside_lat]))
    assert result.tolist() == [values[2, 2], 0]


def test_features_from_a_synthetic_build(built, monkeypatch):
    monkeypatch.setattr(features, "load_training_config", summary.load_training_config)
    assert client.get("/training").json()["features"] == {"available": False, "command": summary.FEATURES_COMMAND}
    report = features.build()
    assert report["pixels"] == 9
    assert report["columns"] == {"monthly": 18, "phenology": 11, "total": 29}
    assert report["haze"]["removed"] == 0
    assert set(report["classes"]) == {"soja", "maiz", "otros"}
    body = client.get("/training").json()
    assert body["features"]["available"] is True
    assert body["features"]["columns"]["total"] == 29
