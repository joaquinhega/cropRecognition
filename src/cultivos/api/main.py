import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

from cultivos.config import load_zone_config

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
