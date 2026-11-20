"""C2-T2: monthly climate of a parcel from NASA POWER at its center, grouped by campaign."""

from datetime import date

from shapely.geometry import Polygon

from cultivos.adapters.power import PowerAdapter
from cultivos.catalog import db
from cultivos.catalog.ingest import ingest
from cultivos.modules import store
from cultivos.modules.campaigns import Campaign, all_months


def process_climate(parcel_id: int, polygon: Polygon, campaigns: list[Campaign], *, adapter: PowerAdapter, today: date) -> dict:
    """Fetch the daily series from the first campaign to today, save its item in our catalog and store monthly values."""
    months = all_months(campaigns)
    center = polygon.centroid
    result = adapter.climate_at(center.x, center.y, months[0].start, today)
    ingest(adapter, [result["item"]])

    campaign_of = {month.key: month.campaign for month in months}
    parameters = list(adapter.config["parameters"])
    rows = [
        {
            "month": store.month_date(entry["month"]),
            "campaign": campaign_of[entry["month"]],
            "days": entry["days"],
            "valid_days": entry["valid_days"],
            "weather": {name: entry[name] for name in parameters},
        }
        for entry in result["monthly"]
        if entry["month"] in campaign_of
    ]
    point = tuple(result["item"]["geometry"]["coordinates"])
    with db.connect() as connection:
        store.ensure_schema(connection)
        store.replace_climate(connection, parcel_id, rows, point, result["item"]["id"])
    return {"months": len(rows), "valid_days": sum(row["valid_days"] for row in rows), "item_id": result["item"]["id"]}
