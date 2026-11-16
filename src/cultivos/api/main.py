import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

from cultivos.config import load_zone_config
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
from cultivos.split import SplitError, SplitExists, create_split, read_split
from cultivos.viewer import LAYERS, image_bounds, list_dates, render_png

app = FastAPI(title="cropRecognition API")


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


@app.get("/imagery")
def imagery() -> dict:
    dates = list_dates()
    bounds = image_bounds(dates[0]["date"]) if dates else None
    return {"bounds": bounds, "dates": dates}


@app.get("/imagery/{date}/{layer}.png")
def imagery_image(date: str, layer: str) -> Response:
    if layer not in LAYERS:
        raise HTTPException(status_code=404, detail=f"Capa desconocida: {layer}")
    try:
        png = render_png(date, layer)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"No hay datos para {date}. Ejecutá clip_scene y compute_ndvi para esa fecha.",
        )
    return Response(content=png, media_type="image/png")


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
