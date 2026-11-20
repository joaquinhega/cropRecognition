import json
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

from cultivos.api.parcels import router as parcels_router
from cultivos.api.platform import router as platform_router
from cultivos.catalog import items as catalog_items
from cultivos.catalog.db import CatalogUnavailable
from cultivos.clips import list_dates
from cultivos.config import load_catalog_config, load_zone_config
from cultivos.labels import (
    LabelError,
    LabelNotFound,
    create_label,
    delete_label,
    label_options,
    read_labels,
    review_labels,
    update_label,
)
from cultivos.series_summary import summarize_series
from cultivos.split import SplitError, SplitExists, create_split, read_split

app = FastAPI(title="cropRecognition API")
app.include_router(platform_router)
app.include_router(parcels_router)


class NewLabel(BaseModel):
    clase: str
    vertices: list[tuple[float, float]]
    fecha: str
    criterio: str = ""
    confianza: str | None = None


class LabelChanges(BaseModel):
    clase: str | None = None
    criterio: str | None = None
    confianza: str | None = None
    estado: str | None = None


class ReviewRequest(BaseModel):
    ids: list[str]


def _run_label_action(action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except LabelNotFound as error:
        raise HTTPException(status_code=404, detail=f"No existe la etiqueta {error}.")
    except LabelError as error:
        raise HTTPException(status_code=422, detail=str(error))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/boundary")
def boundary() -> dict:
    path = Path(load_zone_config()["boundary_path"])
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Falta el límite de la zona. Ejecutá: docker compose run --rm api python -m cultivos.fetch_boundary",
        )
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/labels/imagery")
def labels_imagery() -> dict:
    """Dates of the Agrelo clips (A) with their TiTiler layers, for the labeling mode."""
    collection = load_catalog_config()["local_clips"]["collection_id"]
    bbox = load_zone_config()["work_area"]["bbox"]
    dates = list_dates()
    if not dates:
        return {"bbox": bbox, "layers": [], "dates": [], "missing": []}
    first, last = date.fromisoformat(dates[0]["date"]), date.fromisoformat(dates[-1]["date"])
    try:
        found = catalog_items.find(bbox, first, last, [collection])
    except CatalogUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    by_date = {item["date"]: item for item in found}
    missing = [entry["date"] for entry in dates if entry["date"] not in by_date]
    return {
        "bbox": bbox,
        "layers": catalog_items.collection_layers(collection),
        "dates": [by_date[entry["date"]] for entry in dates if entry["date"] in by_date],
        "missing": missing,
    }


@app.get("/labels/options")
def labels_options() -> dict:
    return label_options()


@app.get("/labels")
def labels() -> dict:
    return read_labels()


@app.post("/labels")
def labels_create(body: NewLabel) -> dict:
    return _run_label_action(
        create_label, body.clase, body.vertices, body.fecha, body.criterio, body.confianza
    )


@app.post("/labels/review")
def labels_review(body: ReviewRequest) -> list[dict]:
    return _run_label_action(review_labels, body.ids)


@app.patch("/labels/{id_lote}")
def labels_update(id_lote: str, body: LabelChanges) -> dict:
    return _run_label_action(update_label, id_lote, body.clase, body.criterio, body.confianza, body.estado)


@app.delete("/labels/{id_lote}", status_code=204)
def labels_delete(id_lote: str) -> Response:
    _run_label_action(delete_label, id_lote)
    return Response(status_code=204)


@app.get("/split")
def split() -> dict:
    return read_split()


@app.post("/split")
def split_create() -> dict:
    try:
        return create_split()
    except SplitExists as error:
        raise HTTPException(status_code=409, detail=str(error))
    except SplitError as error:
        raise HTTPException(status_code=422, detail=str(error))


@app.get("/series/summary")
def series_summary() -> dict:
    return summarize_series()
