"""Save what an adapter returns into our catalog (B2-T3)."""

from cultivos.adapters.base import Adapter
from cultivos.catalog import db


def ingest(adapter: Adapter, items: list[dict]) -> dict:
    """Upsert the adapter's collections and the given items. Returns how many were new."""
    by_collection: dict[str, list[dict]] = {}
    for item in items:
        by_collection.setdefault(item["collection"], []).append(item)

    with db.connect() as connection:
        for collection in adapter.collections():
            db.upsert_collection(connection, collection)
        new = 0
        for collection_id, group in by_collection.items():
            already = db.existing_ids(connection, collection_id, [item["id"] for item in group])
            new += len(group) - len(already)
            db.upsert_items(connection, group)
        db.update_extents(connection)
    return {"saved": len(items), "new": new}
