"""Job endpoints (C2-T3): state and progress of a background task."""

from fastapi import APIRouter, HTTPException

from cultivos.catalog.db import CatalogUnavailable
from cultivos.jobs import service
from cultivos.jobs.store import JobNotFound

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(job_id: int) -> dict:
    """State (queued, running, done, failed), current step, progress and result of a job."""
    try:
        return service.get_job(job_id)
    except JobNotFound as error:
        raise HTTPException(status_code=404, detail=f"No existe la tarea {error}.") from error
    except CatalogUnavailable as error:
        raise HTTPException(status_code=503, detail=f"{error}. ¿Está levantado el servicio database?") from error
