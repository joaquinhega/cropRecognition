import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response

from cultivos.config import load_zone_config
from cultivos.viewer import LAYERS, image_bounds, list_dates, render_png

app = FastAPI(title="cropRecognition API")


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
