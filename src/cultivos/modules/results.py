"""What the API returns for a processed parcel: index series and climate, grouped by campaign."""

from cultivos.adapters.base import attribution_text, source_info
from cultivos.catalog import db
from cultivos.config import load_parcels_config, load_processing_config, load_sources_config
from cultivos.modules import store
from cultivos.parcels import store as parcels_store


def _parcel(connection, parcel_id: int) -> dict:
    feature = parcels_store.get_parcel(connection, parcel_id, load_parcels_config()["code_prefix"])
    properties = feature["properties"]
    return {
        "id": feature["id"],
        "code": properties["code"],
        "name": properties["name"],
        "area_ha": properties["area_ha"],
        "below_minimum": properties["below_minimum"],
    }


def _source(source_id: str, catalog: dict | None) -> dict:
    info = source_info(source_id, load_sources_config()[source_id])
    collection = info["collections"][0]
    return {
        "name": info["name"],
        "collection": collection["title"],
        "resolution": collection["resolution"],
        "license": collection["license"],
        "attribution": attribution_text(collection["attribution"], catalog),
        "limits": collection["limits"],
    }


def _by_campaign(entries: list[dict]) -> list[dict]:
    campaigns: dict[str, list[dict]] = {}
    for entry in entries:
        campaigns.setdefault(entry.pop("campaign"), []).append(entry)
    return [{"campaign": label, "months": months} for label, months in campaigns.items()]


def _index_entry(row: dict, status_texts: dict) -> dict:
    scene = None
    if row["scene_id"]:
        scene = {
            "id": row["scene_id"],
            "collection": row["scene_collection"],
            "date": row["scene_datetime"].date().isoformat(),
            "cloud_cover": row["scene_cloud_cover"],
        }
    return {
        "campaign": row["campaign"],
        "month": f"{row['month']:%Y-%m}",
        "status": row["status"],
        "status_text": status_texts[row["status"]],
        "complete": row["complete"],
        "scene": scene,
        "valid_share": row["valid_share"],
        "valid_pixels": row["valid_pixels"],
        "parcel_pixels": row["parcel_pixels"],
        "candidates": row["candidates"],
        "indices": row["indices"],
    }


def series(parcel_id: int) -> dict:
    """Monthly index summaries of a parcel with the scene each one came from."""
    config = load_processing_config()
    imagery = config["imagery"]
    with db.connect() as connection:
        store.ensure_schema(connection)
        parcel = _parcel(connection, parcel_id)
        rows = store.index_months(connection, parcel_id)

    dates = sorted(row["scene_datetime"].date().isoformat() for row in rows if row["scene_datetime"])
    used = {"first": dates[0], "last": dates[-1]} if dates else None
    return {
        "parcel": parcel,
        "processed_at": max((row["processed_at"] for row in rows), default=None),
        "indices": {name: {"title": spec["title"], "how_to_read": spec["how_to_read"]} for name, spec in config["indices"].items()},
        "rules": {
            "scene": "Una imagen por mes: la que deja más superficie limpia de la parcela.",
            "pixels": "Cuentan los píxeles de 10 m cuyo centro cae dentro de la parcela; las bandas de 20 m se reparten en cuatro píxeles de 10 m.",
            "min_valid_share": imagery["min_valid_share"],
            "statistics": "Promedio de los píxeles limpios y rango entre el percentil 25 y el 75.",
        },
        "source": _source(imagery["source"], used),
        "campaigns": _by_campaign([_index_entry(row, config["month_status"]) for row in rows]),
    }


def climate(parcel_id: int) -> dict:
    """Monthly climate of a parcel (NASA POWER at its center)."""
    config = load_processing_config()
    source_id = config["climate"]["source"]
    parameters = load_sources_config()[source_id]["parameters"]
    with db.connect() as connection:
        store.ensure_schema(connection)
        parcel = _parcel(connection, parcel_id)
        rows = store.climate_months(connection, parcel_id)

    first = rows[0] if rows else None
    entries = [
        {"campaign": row["campaign"], "month": f"{row['month']:%Y-%m}", "days": row["days"], "valid_days": row["valid_days"], **row["weather"]}
        for row in rows
    ]
    return {
        "parcel": parcel,
        "processed_at": first["processed_at"] if first else None,
        "point": [first["lon"], first["lat"]] if first else None,
        "item_id": first["item_id"] if first else None,
        "parameters": parameters,
        "source": _source(source_id, None),
        "campaigns": _by_campaign(entries),
    }
