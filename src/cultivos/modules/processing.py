"""Full processing of a parcel, run by the worker: index series (C2-T1) and climate (C2-T2)."""

from collections.abc import Callable
from datetime import date

from shapely.geometry import shape

from cultivos.adapters import get_adapter
from cultivos.catalog import db
from cultivos.config import load_parcels_config, load_processing_config
from cultivos.modules import store
from cultivos.modules.campaigns import all_months, campaigns_until
from cultivos.modules.parcel_climate import process_climate
from cultivos.modules.parcel_series import pending_months, process_indices
from cultivos.parcels import store as parcels_store

KIND = "parcel_processing"

Progress = Callable[[str, int, int], None]


def run(parcel_id: int, progress: Progress, *, today: date | None = None) -> dict:
    """Process one parcel and return a summary for the job."""
    config = load_processing_config()
    today = today or date.today()
    with db.connect() as connection:
        parcels_store.ensure_schema(connection)
        parcel = parcels_store.get_parcel(connection, parcel_id, load_parcels_config()["code_prefix"])
    polygon = shape(parcel["geometry"])

    campaign_config = config["campaigns"]
    campaigns = campaigns_until(today, campaign_config["first_month"], campaign_config["count"])
    months = all_months(campaigns)
    pending = pending_months(parcel_id, months)
    total = len(pending) + 1

    if pending:
        process_indices(
            parcel_id,
            polygon,
            pending,
            config=config,
            adapter=get_adapter(config["imagery"]["source"]),
            today=today,
            report=lambda step, done: progress(step, done, total),
        )
    progress("Clima de NASA POWER", len(pending), total)
    climate = process_climate(parcel_id, polygon, campaigns, adapter=get_adapter(config["climate"]["source"]), today=today)
    progress("Terminada", total, total)
    with db.connect() as connection:
        by_status = store.status_counts(connection, parcel_id, months[0].start)

    return {
        "campaigns": [campaign.label for campaign in campaigns],
        "months": {
            "total": len(months),
            "computed": len(pending),
            "reused": len(months) - len(pending),
            "by_status": by_status,
        },
        "climate": climate,
    }
