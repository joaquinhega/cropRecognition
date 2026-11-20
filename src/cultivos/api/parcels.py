"""Parcel endpoints (subproject C): draw or upload, list, rename, delete, process and read its series and climate."""

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel

from cultivos.catalog.db import CatalogUnavailable
from cultivos.jobs import service as jobs
from cultivos.modules import results
from cultivos.parcels import service
from cultivos.parcels.geometry import ParcelError
from cultivos.parcels.store import ParcelNotFound

router = APIRouter(prefix="/parcels", tags=["parcels"])


class NewParcel(BaseModel):
    name: str
    geometry: dict


class ParcelChanges(BaseModel):
    name: str


def _run(action, *args):
    try:
        return action(*args)
    except ParcelNotFound as error:
        raise HTTPException(status_code=404, detail=f"No existe la parcela {error}.") from error
    except ParcelError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except CatalogUnavailable as error:
        raise HTTPException(status_code=503, detail=f"{error}. ¿Está levantado el servicio database?") from error


@router.get("")
def list_parcels() -> dict:
    """All parcels as a GeoJSON FeatureCollection, plus the size and file limits."""
    return _run(service.list_parcels)


@router.get("/limits")
def parcel_limits() -> dict:
    return service.limits()


@router.post("", status_code=201)
def create_parcel(parcel: NewParcel) -> dict:
    """Save a drawn polygon (GeoJSON geometry in longitude and latitude)."""
    return _run(service.create_drawn, parcel.name, parcel.geometry)


@router.post("/import", status_code=201)
async def import_parcels(request: Request, filename: str = Query(..., description="Nombre del archivo con su extensión")) -> dict:
    """Upload a GeoJSON, KML or KMZ file as the raw request body; each polygon becomes a parcel."""
    max_bytes = service.limits()["max_file_bytes"]
    if int(request.headers.get("content-length") or 0) > max_bytes:
        raise HTTPException(status_code=413, detail=f"El archivo supera el máximo de {max_bytes // 1_000_000} MB.")
    result = _run(service.import_file, filename, await request.body())
    if not result["created"]:
        raise HTTPException(status_code=422, detail=service.rejection_summary(result))
    return result


@router.get("/{parcel_id}")
def get_parcel(parcel_id: int) -> dict:
    return _run(service.get_parcel, parcel_id)


@router.patch("/{parcel_id}")
def rename_parcel(parcel_id: int, changes: ParcelChanges) -> dict:
    return _run(service.rename, parcel_id, changes.name)


@router.delete("/{parcel_id}", status_code=204)
def delete_parcel(parcel_id: int) -> Response:
    _run(service.delete, parcel_id)
    return Response(status_code=204)


@router.post("/{parcel_id}/process", status_code=202)
def process_parcel(parcel_id: int) -> dict:
    """Queue the series of indices and the climate of the parcel. The work runs in the worker; follow it at /jobs/{id}."""
    return _run(jobs.process_parcel, parcel_id)


@router.get("/{parcel_id}/jobs")
def parcel_jobs(parcel_id: int) -> dict:
    """Latest processing jobs of the parcel, newest first."""
    return _run(jobs.parcel_jobs, parcel_id)


@router.get("/{parcel_id}/series")
def parcel_series(parcel_id: int) -> dict:
    """Monthly NDVI, NDRE, NDMI and EVI by campaign, with the scene each month came from."""
    return _run(results.series, parcel_id)


@router.get("/{parcel_id}/climate")
def parcel_climate(parcel_id: int) -> dict:
    """Monthly temperature and rain by campaign (NASA POWER at the center of the parcel)."""
    return _run(results.climate, parcel_id)
