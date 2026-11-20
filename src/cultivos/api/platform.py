"""Platform endpoints (subproject B): zones, sources, search across sources, catalog and climate."""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from cultivos.adapters import UnknownSource, active_adapters, all_sources_info, get_adapter
from cultivos.adapters.base import SearchRequest, SourceError, attribution_text
from cultivos.catalog import db, items
from cultivos.catalog.db import CatalogUnavailable
from cultivos.catalog.ingest import ingest
from cultivos.config import load_catalog_config, load_sources_config
from cultivos.zones import ZoneError, list_zones, resolve_area

router = APIRouter()

CLIMATE_SOURCE = "nasa-power"
SEARCHABLE_KINDS = ("imagen", "radar")


def _area(zone: str | None, bbox: str | None) -> dict:
    try:
        return resolve_area(zone, bbox)
    except ZoneError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _period(start: date | None, end: date | None) -> tuple[date, date]:
    end = end or date.today()
    start = start or end - timedelta(days=load_catalog_config()["search_defaults"]["days"])
    if start > end:
        raise HTTPException(status_code=422, detail="La fecha de inicio es posterior a la de fin.")
    return start, end


def _catalog_error(error: CatalogUnavailable) -> HTTPException:
    return HTTPException(status_code=503, detail=f"{error}. ¿Está levantado el servicio database?")


@router.get("/zones")
def zones() -> dict:
    return list_zones()


@router.get("/sources")
def sources() -> dict:
    """Every source with its license, resolution and limits, plus what our catalog holds from it."""
    stats, catalog_error = {}, None
    try:
        with db.connect() as connection:
            stats = db.collection_stats(connection)
    except CatalogUnavailable as error:
        catalog_error = str(error)

    result = []
    for source in all_sources_info():
        for collection in source["collections"]:
            collection["catalog"] = stats.get(collection["catalog_id"])
            collection["attribution"] = attribution_text(collection["attribution"], collection["catalog"])
        result.append(source)
    catalog_config = load_catalog_config()
    local = catalog_config["local_clips"]
    return {
        "sources": result,
        "search_defaults": catalog_config["search_defaults"],
        "local": {"collection_id": local["collection_id"], "title": local["title"], "catalog": stats.get(local["collection_id"])},
        "catalog_error": catalog_error,
    }


@router.get("/search")
def search(
    zone: str | None = None,
    bbox: str | None = Query(None, description="oeste,sur,este,norte en grados"),
    start: date | None = None,
    end: date | None = None,
    sources: str | None = Query(None, description="Ids separados por coma; por defecto, las fuentes de imágenes y radar activas"),
    max_cloud_cover: float | None = None,
    limit: int | None = None,
) -> dict:
    """Search the sources for a zone, save what they return in our catalog and summarize it."""
    area = _area(zone, bbox)
    start, end = _period(start, end)
    defaults = load_catalog_config()["search_defaults"]
    adapters = active_adapters()
    if sources:
        requested = [source.strip() for source in sources.split(",") if source.strip()]
    else:
        config = load_sources_config()
        requested = [source_id for source_id in adapters if config[source_id]["kind"] in SEARCHABLE_KINDS]

    request = SearchRequest(
        bbox=area["bbox"],
        start=start,
        end=end,
        max_cloud_cover=defaults["max_cloud_cover"] if max_cloud_cover is None else max_cloud_cover,
        limit=limit or defaults["limit"],
    )
    results = []
    for source_id in requested:
        entry = {"source": source_id, "found": 0, "new": 0, "error": None, "items": []}
        try:
            adapter = get_adapter(source_id)
            found = adapter.search(request)
            saved = ingest(adapter, found)
            entry.update(found=len(found), new=saved["new"], items=[items.summarize(item) for item in found])
        except (UnknownSource, SourceError) as error:
            entry["error"] = str(error)
        except CatalogUnavailable as error:
            raise _catalog_error(error) from error
        results.append(entry)

    return {
        "area": area,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "max_cloud_cover": request.max_cloud_cover,
        "results": results,
    }


@router.get("/catalog/collections")
def catalog_collections() -> list[dict]:
    """Collections in our catalog with their layers, how to read them, source tag and limits."""
    try:
        with db.connect() as connection:
            collections = db.collections(connection)
            stats = db.collection_stats(connection)
    except CatalogUnavailable as error:
        raise _catalog_error(error) from error
    return [
        {
            "id": collection["id"],
            "title": collection.get("title", collection["id"]),
            "source": collection.get("cultivos:source"),
            "resolution": collection.get("cultivos:resolution"),
            "license": collection.get("cultivos:license_title"),
            "attribution": attribution_text(collection.get("cultivos:attribution", ""), stats.get(collection["id"])),
            "limits": collection.get("cultivos:limits"),
            "layers": items.collection_layers(collection["id"]),
            "catalog": stats.get(collection["id"]),
        }
        for collection in collections
    ]


@router.get("/catalog/items")
def catalog_items(
    zone: str | None = None,
    bbox: str | None = None,
    start: date | None = None,
    end: date | None = None,
    collections: str | None = Query(None, description="Ids separados por coma"),
) -> dict:
    """Items already in our catalog for a zone and period (no call to the sources)."""
    area = _area(zone, bbox)
    start, end = _period(start, end)
    wanted = [collection.strip() for collection in collections.split(",")] if collections else None
    try:
        found = items.find(area["bbox"], start, end, wanted)
    except CatalogUnavailable as error:
        raise _catalog_error(error) from error
    return {"area": area, "start": start.isoformat(), "end": end.isoformat(), "items": found}


@router.get("/climate")
def climate(zone: str | None = None, bbox: str | None = None, start: date | None = None, end: date | None = None) -> dict:
    """Daily and monthly weather for the center of a zone (NASA POWER), saved in the catalog."""
    area = _area(zone, bbox)
    start, end = _period(start, end)
    try:
        adapter = get_adapter(CLIMATE_SOURCE)
        result = adapter.climate(area["bbox"], start, end)
        ingest(adapter, [result["item"]])
    except UnknownSource as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except SourceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except CatalogUnavailable as error:
        raise _catalog_error(error) from error

    info = adapter.info()
    collection = info["collections"][0]
    return {
        "area": area,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "point": result["item"]["geometry"]["coordinates"],
        "parameters": adapter.config["parameters"],
        "source": {
            "name": info["name"],
            "resolution": collection["resolution"],
            "license": collection["license"],
            "attribution": attribution_text(collection["attribution"], None),
            "limits": collection["limits"],
        },
        "item_id": result["item"]["id"],
        "daily": result["daily"],
        "monthly": result["monthly"],
    }
