"""Jobs as the API sees them: queue the processing of a parcel and follow its state."""

from cultivos.catalog import db
from cultivos.config import load_parcels_config, load_processing_config
from cultivos.jobs import store
from cultivos.modules.processing import KIND as PARCEL_PROCESSING
from cultivos.parcels import store as parcels_store


def process_parcel(parcel_id: int) -> dict:
    """Queue the processing of a parcel; if it is already queued or running, return that job."""
    with db.connect() as connection:
        store.ensure_schema(connection)
        parcels_store.get_parcel(connection, parcel_id, load_parcels_config()["code_prefix"])
        job, created = store.enqueue(connection, PARCEL_PROCESSING, parcel_id)
    return {"job": job, "created": created}


def parcel_jobs(parcel_id: int) -> dict:
    """Latest jobs of a parcel, newest first."""
    with db.connect() as connection:
        store.ensure_schema(connection)
        parcels_store.get_parcel(connection, parcel_id, load_parcels_config()["code_prefix"])
        jobs = store.parcel_jobs(connection, parcel_id, load_processing_config()["jobs"]["list_limit"])
    return {"jobs": jobs}


def get_job(job_id: int) -> dict:
    with db.connect() as connection:
        store.ensure_schema(connection)
        return store.get_job(connection, job_id)
