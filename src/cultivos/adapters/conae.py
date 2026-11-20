"""CONAE SAOCOM catalog: radar products, metadata search only (no account needed to search)."""

import json
from collections.abc import Callable

import httpx

from cultivos.adapters.base import (
    SOURCE_COLLECTION_PROPERTY,
    SOURCE_PROPERTY,
    Adapter,
    SearchRequest,
    SourceError,
    collection_template,
)

COLLECTION_KEY = "saocom-1"
PLATFORM_PREFIX = "SAO1"


class ConaeSaocomAdapter(Adapter):
    def __init__(self, source_id: str, config: dict, http_get: Callable[..., httpx.Response] | None = None):
        super().__init__(source_id, config)
        self._http_get = http_get or httpx.get

    @property
    def _collection(self) -> dict:
        return self.config["collections"][COLLECTION_KEY]

    def query_params(self, request: SearchRequest, offset: int, limit: int) -> dict:
        west, south, east, north = request.bbox
        polygon = {
            "type": "Polygon",
            "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
        }
        filters = [
            {"field": "geom", "op": "intersects", "value": polygon},
            {"field": "frameEndTime", "op": "ge", "value": f"{request.start.isoformat()}T00:00:00Z"},
            {"field": "frameStartTime", "op": "le", "value": f"{request.end.isoformat()}T23:59:59Z"},
        ]
        order = [{"field": "frameStartTime", "ord": "desc"}, {"field": "productId", "ord": "desc"}]
        return {
            "limit": limit,
            "offset": offset,
            "q": json.dumps(filters, separators=(",", ":")),
            "order_by": json.dumps(order, separators=(",", ":")),
        }

    def _page(self, request: SearchRequest, offset: int, limit: int) -> dict:
        url = f"{self.config['url']}{self.config['search_path']}"
        try:
            response = self._http_get(url, params=self.query_params(request, offset, limit), timeout=self.config["timeout_s"])
        except httpx.HTTPError as error:
            raise SourceError(f"El catálogo SAOCOM no responde: {error}") from error
        if response.status_code != 200:
            raise SourceError(f"El catálogo SAOCOM respondió {response.status_code}: {response.text[:200]}")
        try:
            return response.json()
        except ValueError as error:
            raise SourceError("El catálogo SAOCOM devolvió una respuesta que no es JSON.") from error

    def search(self, request: SearchRequest) -> list[dict]:
        products: list[dict] = []
        while len(products) < request.limit:
            page = self._page(request, len(products), min(self.config["page_size"], request.limit - len(products)))
            products.extend(page["results"])
            if not page["results"] or len(products) >= page["count"]:
                break
        return [self.normalize(product) for product in products]

    def normalize(self, product: dict) -> dict:
        geometry = product["geom"]
        xs = [point[0] for point in geometry["coordinates"][0]]
        ys = [point[1] for point in geometry["coordinates"][0]]
        product_id = product["productId"]
        platform_code = product_id[product_id.find(PLATFORM_PREFIX) : product_id.find(PLATFORM_PREFIX) + len(PLATFORM_PREFIX) + 1]
        assets = {}
        if product.get("thumbnail"):
            assets["thumbnail"] = {
                "href": f"{self.config['url']}{product['thumbnail']}",
                "type": "image/png",
                "roles": ["thumbnail"],
                "title": "Miniatura del catálogo SAOCOM",
            }
        return {
            "type": "Feature",
            "stac_version": "1.0.0",
            "id": product_id,
            "collection": self._collection["catalog_id"],
            "geometry": geometry,
            "bbox": [min(xs), min(ys), max(xs), max(ys)],
            "properties": {
                "datetime": product["frameStartTime"],
                "platform": platform_code.lower().replace("sao1", "saocom-1") if platform_code else None,
                "sar:instrument_mode": product.get("acquisitionMode"),
                "sat:orbit_state": (product.get("orbitDirection") or "").lower() or None,
                "saocom:polarization": product.get("polarization"),
                "saocom:processing_level": product.get("processingLevel"),
                "saocom:sensor_sub_mode": product.get("sensorSubMode"),
                "saocom:side_looking": product.get("sideLooking"),
                "saocom:catalog_id": product.get("id"),
                "saocom:download_allowed": product.get("areaPermissions", {}).get("download", False),
                SOURCE_PROPERTY: self.source_id,
                SOURCE_COLLECTION_PROPERTY: COLLECTION_KEY,
            },
            "assets": assets,
            "links": [{"rel": "via", "href": f"{self.config['url']}/catalog/#/", "title": "Catálogo SAOCOM"}],
        }

    def get_item(self, catalog_collection: str, item_id: str) -> dict:
        raise SourceError("El catálogo SAOCOM se consulta por zona y período; no por id.")

    def collections(self) -> list[dict]:
        return [collection_template(self.source_id, self.config, self._collection)]
