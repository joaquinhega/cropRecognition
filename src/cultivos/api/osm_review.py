"""D1-T0 endpoints: review the OSM vineyard sample by hand before training."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cultivos.adapters import UnknownSource
from cultivos.adapters.base import SourceError
from cultivos.catalog.db import CatalogUnavailable
from cultivos.osm_review import ReviewError, ReviewNotFound, read_review, reference_scene, save_verdict

router = APIRouter(prefix="/osm-review")


class Verdict(BaseModel):
    verdict: str
    note: str = ""


def _run(action, *args):
    try:
        return action(*args)
    except ReviewNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ReviewError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (UnknownSource, SourceError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except CatalogUnavailable as error:
        raise HTTPException(status_code=503, detail=f"{error}. ¿Está levantado el servicio database?") from error


@router.get("")
def review() -> dict:
    """The sample polygons with their verdicts and the outcome so far."""
    return _run(read_review)


@router.get("/{n}/scene")
def scene(n: int) -> dict:
    """Reference Sentinel-2 scene for polygon n (1-based), with its TiTiler layers."""
    return _run(reference_scene, n)


@router.put("/{n}")
def verdict(n: int, body: Verdict) -> dict:
    """Save the verdict for polygon n and return the updated outcome."""
    return _run(save_verdict, n, body.verdict, body.note)
