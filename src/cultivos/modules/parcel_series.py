"""C2-T1: monthly series of vegetation indices for a parcel, one scene per month."""

from collections.abc import Callable
from datetime import date

from shapely.geometry import Polygon

from cultivos.adapters.base import Adapter, SearchRequest
from cultivos.catalog import db
from cultivos.catalog.ingest import ingest
from cultivos.modules import store
from cultivos.modules.campaigns import Month, is_complete
from cultivos.modules.indices import parcel_indices
from cultivos.modules.scenes import SceneReadError, choose_scene, read_bands

Report = Callable[[str, int], None]


def pending_months(parcel_id: int, months: list[Month]) -> list[Month]:
    """Months that still need work: never processed, still open, or that failed to read."""
    with db.connect() as connection:
        store.ensure_schema(connection)
        done = store.final_months(connection, parcel_id)
    return [month for month in months if month.key not in done]


def search_scenes(adapter: Adapter, polygon: Polygon, months: list[Month], imagery: dict) -> dict[str, list[dict]]:
    """Search the source once for the span of the months, save the items in our catalog and group them by month."""
    request = SearchRequest(
        bbox=list(polygon.bounds),
        start=months[0].start,
        end=months[-1].end,
        max_cloud_cover=imagery["max_scene_cloud_cover"],
        limit=imagery["search_limit"],
    )
    items = [item for item in adapter.search(request) if item["collection"] == imagery["collection"]]
    ingest(adapter, items)
    wanted = {month.key for month in months}
    by_month: dict[str, list[dict]] = {key: [] for key in wanted}
    for item in items:
        key = item["properties"]["datetime"][:7]
        if key in wanted:
            by_month[key].append(item)
    return by_month


def evaluate_month(month: Month, candidates: list[dict], polygon: Polygon, config: dict, today: date) -> dict:
    """Status and index summaries of one month, ready to store."""
    imagery = config["imagery"]
    row = {
        "month": month.start,
        "campaign": month.campaign,
        "status": "no_scene",
        "scene_id": None,
        "scene_collection": None,
        "scene_datetime": None,
        "scene_cloud_cover": None,
        "valid_share": None,
        "valid_pixels": None,
        "parcel_pixels": None,
        "candidates": len(candidates),
        "indices": None,
    }
    if candidates:
        pick = choose_scene(candidates, polygon, imagery)
        choice = pick.choice
        if choice is None:
            row["status"] = "error" if pick.read_errors else "no_pixels"
        else:
            item = choice.item
            row.update(
                scene_id=item["id"],
                scene_collection=item["collection"],
                scene_datetime=item["properties"]["datetime"],
                scene_cloud_cover=item["properties"].get("eo:cloud_cover"),
                valid_share=round(choice.share, 4),
                valid_pixels=choice.valid_pixels,
                parcel_pixels=choice.parcel_pixels,
            )
            if choice.share < imagery["min_valid_share"]:
                row["status"] = "cloudy"
            else:
                try:
                    bands = read_bands(item, choice.grid, imagery)
                    row.update(status="ok", indices=parcel_indices(bands, choice.valid, config))
                except SceneReadError:
                    row["status"] = "error"
    row["complete"] = row["status"] != "error" and is_complete(month, today, config["campaigns"]["late_days"])
    return row


def process_indices(
    parcel_id: int,
    polygon: Polygon,
    months: list[Month],
    *,
    config: dict,
    adapter: Adapter,
    today: date,
    report: Report,
) -> None:
    """Compute and store the given months, searching once per campaign."""
    imagery = config["imagery"]
    by_campaign: dict[str, list[Month]] = {}
    for month in months:
        by_campaign.setdefault(month.campaign, []).append(month)

    done = 0
    for campaign, campaign_months in by_campaign.items():
        report(f"Buscando imágenes de la campaña {campaign}", done)
        scenes = search_scenes(adapter, polygon, campaign_months, imagery)
        for month in campaign_months:
            report(f"Índices de {month.key} (campaña {campaign})", done)
            row = evaluate_month(month, scenes[month.key], polygon, config, today)
            with db.connect() as connection:
                store.save_index_month(connection, parcel_id, row)
            done += 1
