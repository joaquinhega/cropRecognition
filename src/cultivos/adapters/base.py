"""Common contract for every data source (D-037): search, get item, assets, license and cost."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

SOURCE_PROPERTY = "cultivos:source"
SOURCE_COLLECTION_PROPERTY = "cultivos:source_collection"


class SourceError(RuntimeError):
    """A source could not answer (network, quota, bad response)."""


@dataclass(frozen=True)
class SearchRequest:
    bbox: list[float]
    start: date
    end: date
    max_cloud_cover: float | None = None
    limit: int = 100


@dataclass(frozen=True)
class Quote:
    amount: float = 0.0
    currency: str = "USD"
    note: str = "Fuente gratuita"


@dataclass
class SearchResult:
    source_id: str
    items: list[dict] = field(default_factory=list)
    error: str | None = None


class Adapter(ABC):
    """One adapter per source. Items are returned as STAC Item dicts, already normalized:
    their `collection` is the id in our own catalog and their properties name the source."""

    def __init__(self, source_id: str, config: dict):
        self.source_id = source_id
        self.config = config

    @abstractmethod
    def search(self, request: SearchRequest) -> list[dict]:
        """Find items that intersect the request, normalized for our catalog."""

    @abstractmethod
    def get_item(self, catalog_collection: str, item_id: str) -> dict:
        """Fetch one item from the source, normalized for our catalog."""

    @abstractmethod
    def collections(self) -> list[dict]:
        """STAC Collections this adapter writes into our catalog."""

    def assets(self, item: dict) -> dict:
        """Assets of an item, as STAC asset dicts keyed by name."""
        return item.get("assets", {})

    def quote(self, request: SearchRequest) -> Quote:
        """Cost of getting the data. Free sources return zero."""
        return Quote()

    def info(self) -> dict:
        """Public description of the source: name, license, resolution, limits."""
        return source_info(self.source_id, self.config)


def source_info(source_id: str, config: dict) -> dict:
    collections = [
        {
            "catalog_id": collection["catalog_id"],
            "title": collection["title"],
            "resolution": _resolution_label(collection),
            "license": collection["license_title"],
            "license_url": collection.get("license_url"),
            "attribution": collection["attribution"],
            "limits": collection["limits"],
        }
        for collection in config.get("collections", {}).values()
    ]
    return {
        "id": source_id,
        "name": config["name"],
        "provider": config["provider"],
        "kind": config["kind"],
        "status": config["status"],
        "requires_account": config["requires_account"],
        "cost": config["cost"],
        "note": config.get("note"),
        "resolution": config.get("resolution_label"),
        "license": config.get("license_title"),
        "collections": collections,
    }


def attribution_text(template: str, catalog: dict | None) -> str:
    """Fill the {year} of an attribution with the years of the data we hold."""
    if "{year}" not in template:
        return template
    if not catalog:
        return template.replace(" {year}", "").replace("{year}", "")
    first, last = catalog["first"][:4], catalog["last"][:4]
    return template.format(year=first if first == last else f"{first}-{last}")


def _resolution_label(collection: dict) -> str:
    if "resolution_m" in collection:
        return f"{collection['resolution_m']} m"
    return collection["resolution_label"]


def collection_template(source_id: str, config: dict, collection: dict, extra: dict | None = None) -> dict:
    """STAC Collection for our catalog, with license, provider and attribution."""
    links = []
    if collection.get("license_url"):
        links.append({"rel": "license", "href": collection["license_url"], "title": collection["license_title"]})
    return {
        "type": "Collection",
        "stac_version": "1.0.0",
        "id": collection["catalog_id"],
        "title": collection["title"],
        "description": collection["description"],
        "license": collection["license"],
        "providers": [
            {"name": config["provider"], "roles": ["producer", "host"], "url": config.get("url")},
        ],
        "extent": {
            "spatial": {"bbox": [[-180, -90, 180, 90]]},
            "temporal": {"interval": [[None, None]]},
        },
        "links": links,
        SOURCE_PROPERTY: source_id,
        "cultivos:attribution": collection["attribution"],
        "cultivos:license_title": collection["license_title"],
        "cultivos:limits": collection["limits"],
        "cultivos:resolution": _resolution_label(collection),
        **(extra or {}),
    }
