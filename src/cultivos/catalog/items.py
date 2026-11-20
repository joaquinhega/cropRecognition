"""Read items back from our catalog and describe them for the viewer, with TiTiler layer URLs."""

import json
import os
from datetime import date
from urllib.parse import urlencode

from cultivos.adapters.base import SOURCE_PROPERTY
from cultivos.catalog import db
from cultivos.config import load_catalog_config, load_layers_config

TILE_PATH = "tiles/WebMercatorQuad/{z}/{x}/{y}.png"


def raster_base_url() -> str:
    return os.environ.get("RASTER_PUBLIC_URL", "/raster").rstrip("/")


def layer_url(collection: str, item_id: str, params: dict) -> str:
    values = {key: _query_value(value) for key, value in params.items()}
    query = urlencode(values, doseq=True)
    return f"{raster_base_url()}/collections/{collection}/items/{item_id}/{TILE_PATH}?{query}"


def _query_value(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, dict):
        return json.dumps(value, separators=(",", ":"))
    return value


def collection_layers(collection: str) -> list[dict]:
    layers = load_layers_config().get(collection, {})
    return [
        {"id": layer_id, "title": layer["title"], "how_to_read": layer["how_to_read"], "legend": layer.get("legend")}
        for layer_id, layer in layers.items()
    ]


def summarize(item: dict) -> dict:
    properties = item["properties"]
    moment = properties.get("datetime") or properties.get("start_datetime")
    layers = load_layers_config().get(item["collection"], {})
    return {
        "id": item["id"],
        "collection": item["collection"],
        "source": properties.get(SOURCE_PROPERTY),
        "datetime": moment,
        "date": moment[:10],
        "cloud_cover": properties.get("eo:cloud_cover"),
        "tile": properties.get("grid:code"),
        "platform": properties.get("platform"),
        "bbox": item.get("bbox"),
        "layers": {layer_id: layer_url(item["collection"], item["id"], layer["params"]) for layer_id, layer in layers.items()},
    }


def find(bbox: list[float], start: date, end: date, collections: list[str] | None = None) -> list[dict]:
    query = {
        "bbox": bbox,
        "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
        "limit": load_catalog_config()["catalog_query_limit"],
        "sortby": [{"field": "datetime", "direction": "desc"}],
    }
    if collections:
        query["collections"] = collections
    with db.connect() as connection:
        return [summarize(item) for item in db.search(connection, query)]
