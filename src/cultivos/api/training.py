"""D1-T1 endpoints: the training dataset of the recognition (summary, curves per class, sample pixels)."""

from fastapi import APIRouter, HTTPException

from cultivos.training.summary import UnknownIndexName, read_pixels_geojson, read_training

router = APIRouter(prefix="/training")


@router.get("")
def training(index: str | None = None) -> dict:
    """Summary of the dataset with the curves of one index per class and month."""
    try:
        return read_training(index)
    except UnknownIndexName as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/pixels")
def pixels() -> dict:
    """Sample pixels as GeoJSON points with their class."""
    return read_pixels_geojson()
