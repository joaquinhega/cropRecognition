"""Earth Search (Element 84): Sentinel-2 L2A as public COGs, no account needed."""

from collections.abc import Callable

from pystac_client import Client
from pystac_client.exceptions import APIError
from requests import RequestException

from cultivos.adapters.base import (
    SOURCE_COLLECTION_PROPERTY,
    SOURCE_PROPERTY,
    Adapter,
    SearchRequest,
    SourceError,
    collection_template,
)


class EarthSearchAdapter(Adapter):
    def __init__(self, source_id: str, config: dict, open_client: Callable[..., Client] = Client.open):
        super().__init__(source_id, config)
        self._open_client = open_client

    def _client(self) -> Client:
        try:
            return self._open_client(self.config["url"], timeout=self.config["timeout_s"])
        except (APIError, RequestException, OSError) as error:
            raise SourceError(f"Earth Search no responde: {error}") from error

    def _source_collection(self, catalog_collection: str) -> str:
        for source_collection, collection in self.config["collections"].items():
            if collection["catalog_id"] == catalog_collection:
                return source_collection
        raise SourceError(f"La colección {catalog_collection} no es de Earth Search.")

    def normalize(self, item: dict, source_collection: str) -> dict:
        collection = self.config["collections"][source_collection]
        origin = next((link["href"] for link in item.get("links", []) if link.get("rel") == "self"), None)
        properties = {
            **item["properties"],
            SOURCE_PROPERTY: self.source_id,
            SOURCE_COLLECTION_PROPERTY: source_collection,
        }
        links = [{"rel": "via", "href": origin, "type": "application/geo+json", "title": "Ítem en Earth Search"}]
        return {
            **item,
            "collection": collection["catalog_id"],
            "properties": properties,
            "links": links if origin else [],
        }

    def search(self, request: SearchRequest) -> list[dict]:
        client = self._client()
        items = []
        for source_collection, collection in self.config["collections"].items():
            query = None
            if request.max_cloud_cover is not None:
                query = {collection["cloud_property"]: {"lte": request.max_cloud_cover}}
            try:
                search = client.search(
                    collections=[source_collection],
                    bbox=request.bbox,
                    datetime=f"{request.start.isoformat()}/{request.end.isoformat()}",
                    query=query,
                    sortby=[{"field": "properties.datetime", "direction": "desc"}],
                    max_items=request.limit,
                )
                found = list(search.items_as_dicts())
            except (APIError, RequestException, OSError) as error:
                raise SourceError(f"Earth Search falló al buscar en {source_collection}: {error}") from error
            items.extend(self.normalize(item, source_collection) for item in found)
        return items

    def get_item(self, catalog_collection: str, item_id: str) -> dict:
        source_collection = self._source_collection(catalog_collection)
        client = self._client()
        try:
            item = client.get_collection(source_collection).get_item(item_id)
        except (APIError, RequestException, OSError) as error:
            raise SourceError(f"Earth Search falló al pedir {item_id}: {error}") from error
        if item is None:
            raise SourceError(f"Earth Search no tiene el ítem {item_id}.")
        return self.normalize(item.to_dict(), source_collection)

    def collections(self) -> list[dict]:
        return [
            collection_template(self.source_id, self.config, collection, {"summaries": {"gsd": [collection["resolution_m"]]}})
            for collection in self.config["collections"].values()
        ]
