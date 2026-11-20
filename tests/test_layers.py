from urllib.parse import parse_qs, urlparse

from cultivos.catalog.items import layer_url, summarize
from cultivos.config import load_layers_config

ITEM = {
    "id": "S2B_19HED_20260119_0_L2A",
    "collection": "earth-search-sentinel-2-l2a",
    "bbox": [-69.0, -33.5, -67.9, -32.5],
    "properties": {"datetime": "2026-01-19T14:27:31Z", "eo:cloud_cover": 3.2, "cultivos:source": "earth-search"},
}


def test_every_layer_has_title_and_reading_help():
    for collection, layers in load_layers_config().items():
        for layer_id, layer in layers.items():
            assert layer["title"] and layer["how_to_read"], f"{collection}/{layer_id}"
            assert layer["params"]["assets"], f"{collection}/{layer_id}"


def test_ndvi_url_repeats_assets_and_keeps_the_expression():
    params = load_layers_config()["earth-search-sentinel-2-l2a"]["ndvi"]["params"]
    url = urlparse(layer_url(ITEM["collection"], ITEM["id"], params))
    query = parse_qs(url.query)
    assert url.path.endswith("/tiles/WebMercatorQuad/{z}/{x}/{y}.png")
    assert query["assets"] == ["nir", "red"]
    assert query["expression"] == ["(b1-b2)/(b1+b2)"]


def test_categorical_colormap_is_sent_as_json():
    params = load_layers_config()["earth-search-sentinel-2-l2a"]["clouds"]["params"]
    query = parse_qs(urlparse(layer_url(ITEM["collection"], ITEM["id"], params)).query)
    assert query["colormap"][0].startswith('{"3":[')


def test_summary_has_date_cloud_and_layers(monkeypatch):
    monkeypatch.setenv("RASTER_PUBLIC_URL", "/raster")
    summary = summarize(ITEM)
    assert summary["date"] == "2026-01-19"
    assert summary["cloud_cover"] == 3.2
    assert summary["source"] == "earth-search"
    assert set(summary["layers"]) == {"rgb", "false-color", "ndvi", "clouds"}
    assert summary["layers"]["rgb"].startswith("/raster/collections/earth-search-sentinel-2-l2a/items/")
