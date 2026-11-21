import numpy as np
import pytest

from cultivos.config import load_training_config
from cultivos.models import baseline, blocks, evaluate
from cultivos.training import dataset, summary

SETTINGS = {"block_size_m": 3000, "folds": 5, "buffer_m": 500, "seed": 42}
MONTHS = [f"{year}-{month:02d}" for year, month in [(2024, m) for m in range(7, 13)] + [(2025, m) for m in range(1, 7)]]


def _grid(count: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    return -60.75 + rng.random(count) * 0.2, -33.95 + rng.random(count) * 0.2


def test_blocks_are_squares_of_the_configured_size():
    points = np.array([[100.0, 100.0], [2999.0, 2999.0], [3001.0, 100.0], [-1.0, 100.0]])
    assert blocks.block_ids(points, 3000) == ["0_0", "0_0", "1_0", "-1_0"]


def test_folds_cover_every_block_with_similar_sizes():
    names = [f"b{n % 40}" for n in range(400)]
    folds = blocks.assign_folds(names, 5, seed=1)
    assert set(folds) == set(names) and set(folds.values()) == set(range(5))
    sizes = np.bincount([folds[name] for name in names])
    assert sizes.max() - sizes.min() <= 10
    assert folds == blocks.assign_folds(names, 5, seed=1)


def test_buffer_leaves_out_training_pixels_near_the_test():
    points = np.array([[0.0, 0.0], [300.0, 0.0], [700.0, 0.0]])
    test = np.array([True, False, False])
    assert blocks.buffer_mask(points, test, 500).tolist() == [True, True, False]


def test_split_never_trains_with_test_pixels_or_their_neighbors():
    lon, lat = _grid(600)
    result = blocks.split(lon, lat, SETTINGS)
    assert result["crs"] == "EPSG:32720"
    points = blocks.to_meters(lon, lat, result["crs"])
    tested = np.zeros(len(lon), dtype=bool)
    for current in result["rounds"]:
        assert not (current["train"] & current["test"]).any()
        gaps = np.linalg.norm(points[current["train"]][:, None] - points[current["test"]][None], axis=2)
        assert gaps.min() >= SETTINGS["buffer_m"]
        tested |= current["test"]
    assert tested.all()


def test_baseline_uses_only_the_monthly_index():
    names = ["ndvi_m01", "ndvi_m12", "ndvi_min_value", "ndvi_mean", "ndre_m01", "ndvi_peak_month"]
    assert baseline.columns(names, {"index": "ndvi"}) == ["ndvi_m01", "ndvi_m12"]


def test_baseline_rule_reads_as_questions_by_month():
    values = np.array([[0.2, 0.9], [0.3, 0.8], [0.8, 0.2], [0.9, 0.3]])
    model = baseline.make({"max_depth": 2}, seed=0).fit(values, np.array(["otros", "otros", "maiz", "maiz"]))
    rule = baseline.describe(model, ["ndvi_m06", "ndvi_m10"], MONTHS, 3)
    assert rule["leaf"] is False and rule["index"] == "NDVI"
    assert rule["month"] in ("2024-12", "2025-04")
    leaves = [rule["yes"], rule["no"]]
    assert {leaf["class"] for leaf in leaves} == {"otros", "maiz"}
    assert sum(leaf["pixels"] for leaf in leaves) == 4


def _write_features(folder, count_per_class=120):
    rng = np.random.default_rng(3)
    lon, lat = _grid(count_per_class * 3, seed=5)
    shapes = {"soja": (0.5, 0.3), "maiz": (0.85, 0.5), "otros": (0.4, 0.7)}
    names = [f"ndvi_m{n:02d}" for n in range(1, 13)] + ["ndvi_min_value"]
    rows = []
    classes = [klass for klass in shapes for _ in range(count_per_class)]
    for number, klass in enumerate(classes):
        december, april = shapes[klass]
        values = {name: round(float(rng.random() * 0.1 + 0.2), 4) for name in names}
        values["ndvi_m06"], values["ndvi_m10"] = float(december), float(april)
        values["ndvi_m03"] = ""
        rows.append({"pixel_id": f"P-{number + 1:05d}", "class": klass, "lon": lon[number], "lat": lat[number], **values})
    dataset.write_rows(folder / "features.csv", ["pixel_id", "class", "lon", "lat", *names], rows)
    dataset.write_json(folder / "features.json", {"month_keys": MONTHS})
    dataset.write_rows(
        folder / "pixels.csv",
        dataset.PIXEL_FIELDS,
        [{"pixel_id": row["pixel_id"], "class": row["class"], "map_value": 1, "lon": row["lon"], "lat": row["lat"]} for row in rows],
    )


@pytest.fixture
def trained(tmp_path, monkeypatch):
    config = {**load_training_config(), "output_dir": str(tmp_path)}
    monkeypatch.setattr(evaluate, "load_training_config", lambda: config)
    monkeypatch.setattr(summary, "load_training_config", lambda: config)
    _write_features(dataset.folder(config))
    return config, evaluate.run("baseline")


def test_baseline_cross_validation_end_to_end(trained):
    config, report = trained
    assert report["columns"] == 12
    assert report["evaluation"]["targets"] == ["soja", "maiz"]
    assert len(report["rounds"]) == config["evaluation"]["folds"]
    assert sum(item["test"] for item in report["rounds"]) == 360
    assert report["accuracy"] == 1.0
    assert all(report["per_class"][name]["meets_target"] for name in ("soja", "maiz"))
    assert "meets_target" not in report["per_class"]["otros"]
    assert np.trace(report["confusion"]["matrix"]) == 360
    folder = evaluate.models_folder(config)
    assert len(dataset.read_rows(folder / "folds.csv")) == 360
    assert len(dataset.read_rows(folder / "baseline-predictions.csv")) == 360


def test_api_side_reads_models_and_folds(trained):
    config, _ = trained
    models = summary.read_models(dataset.folder(config), config)
    assert models["available"] is True and [item["model"] for item in models["results"]] == ["baseline"]
    assert models["evaluation"]["targets"] == ["soja", "maiz"]
    pixels = summary.read_pixels_geojson()["features"]
    assert {feature["properties"]["fold"] for feature in pixels} <= set(range(1, config["evaluation"]["folds"] + 1))


def test_models_missing_explain_the_command(tmp_path, monkeypatch):
    config = {**load_training_config(), "output_dir": str(tmp_path)}
    monkeypatch.setattr(evaluate, "load_training_config", lambda: config)
    assert summary.read_models(dataset.folder(config), config)["available"] is False
    with pytest.raises(evaluate.ModelError, match="features"):
        evaluate.run("baseline")
    with pytest.raises(evaluate.ModelError, match="desconocido"):
        evaluate.run("xyz")
