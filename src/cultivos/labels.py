import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rasterio.warp import transform

from cultivos.config import load_imagery_config, load_labels_config, load_zone_config
from cultivos.clips import list_dates

FROZEN_STATE = "congelada"
DRAFT_STATE = "borrador"
REVIEWED_STATE = "revisada"


class LabelError(ValueError):
    pass


class LabelNotFound(LookupError):
    pass


def label_options() -> dict:
    config = load_labels_config()
    keys = ("classes", "confidence_levels", "criteria", "min_area_ha")
    return {key: config[key] for key in keys}


def read_labels() -> dict:
    config = load_labels_config()
    collection = _read(config)
    return {**collection, "features": [_with_review(feature, config) for feature in collection["features"]]}


def review_reasons(properties: dict, config: dict) -> list[str]:
    reasons = []
    if not properties["criterio"]:
        reasons.append("sin criterio")
    if properties["confianza"] == "media":
        reasons.append("confianza media")
    if properties["confianza"] == "baja":
        reasons.append("confianza baja")
    for clase, criteria in config["criteria_by_class"].items():
        if clase != properties["clase"] and properties["criterio"] in criteria:
            if properties["criterio"] not in config["criteria_by_class"][properties["clase"]]:
                reasons.append("el criterio parece de otra clase")
    return reasons


def create_label(clase: str, vertices: list, fecha: str, criterio: str = "", confianza: str | None = None) -> dict:
    config = load_labels_config()
    confianza = confianza or config["default_confidence"]
    _check_choice(clase, config["classes"], "clase")
    _check_choice(confianza, config["confidence_levels"], "confianza")
    if fecha not in {item["date"] for item in list_dates()}:
        raise LabelError(f"No hay imagen para la fecha {fecha}.")

    ring = _ring(vertices)
    area_ha = round(_area_ha(ring, config["area_crs"]), 3)
    collection = _read(config)
    id_lote = f"L-{collection['next_id']:04d}"
    collection["next_id"] += 1

    feature = {
        "type": "Feature",
        "id": id_lote,
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {
            "id_lote": id_lote,
            "zona": load_zone_config()["work_area"]["name"],
            "clase": clase,
            "campana": config["campaign"],
            "imagen_referencia": {
                "satelite": config["satellite"],
                "fecha": fecha,
                "tile": load_imagery_config()["tile"],
            },
            "fuente_poligono": config["polygon_source"],
            "criterio": criterio.strip(),
            "confianza": confianza,
            "estado": DRAFT_STATE,
            "fecha_revision": _today(config),
            "area_ha": area_ha,
            "menor_al_minimo": area_ha < config["min_area_ha"],
        },
    }
    collection["features"].append(feature)
    _write(config, collection)
    return _with_review(feature, config)


def update_label(
    id_lote: str,
    clase: str | None = None,
    criterio: str | None = None,
    confianza: str | None = None,
    estado: str | None = None,
) -> dict:
    config = load_labels_config()
    collection = _read(config)
    feature = _find(collection, id_lote)
    properties = feature["properties"]
    if properties["estado"] == FROZEN_STATE:
        raise LabelError("La etiqueta está congelada y no se puede modificar.")

    if clase is not None:
        _check_choice(clase, config["classes"], "clase")
        properties["clase"] = clase
    if confianza is not None:
        _check_choice(confianza, config["confidence_levels"], "confianza")
        properties["confianza"] = confianza
    if criterio is not None:
        properties["criterio"] = criterio.strip()
    if estado is not None:
        _check_choice(estado, config["editable_states"], "estado")
        properties["estado"] = estado
    properties["fecha_revision"] = _today(config)

    _write(config, collection)
    return _with_review(feature, config)


def review_labels(ids: list[str]) -> list[dict]:
    config = load_labels_config()
    collection = _read(config)
    features = [_find(collection, id_lote) for id_lote in ids]
    today = _today(config)
    for feature in features:
        if feature["properties"]["estado"] == FROZEN_STATE:
            continue
        feature["properties"]["estado"] = REVIEWED_STATE
        feature["properties"]["fecha_revision"] = today
    _write(config, collection)
    return [_with_review(feature, config) for feature in features]


def delete_label(id_lote: str) -> None:
    config = load_labels_config()
    collection = _read(config)
    feature = _find(collection, id_lote)
    if feature["properties"]["estado"] == FROZEN_STATE:
        raise LabelError("La etiqueta está congelada y no se puede borrar.")
    collection["features"].remove(feature)
    _write(config, collection)


def _with_review(feature: dict, config: dict) -> dict:
    properties = {**feature["properties"], "motivos_revision": review_reasons(feature["properties"], config)}
    return {**feature, "properties": properties}


def _read(config: dict) -> dict:
    path = Path(config["path"])
    if not path.exists():
        return {"type": "FeatureCollection", "next_id": 1, "features": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write(config: dict, collection: dict) -> None:
    path = Path(config["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(collection, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _find(collection: dict, id_lote: str) -> dict:
    for feature in collection["features"]:
        if feature["properties"]["id_lote"] == id_lote:
            return feature
    raise LabelNotFound(id_lote)


def _check_choice(value: str, allowed: list[str], name: str) -> None:
    if value not in allowed:
        raise LabelError(f"Valor inválido para {name}: {value}. Opciones: {', '.join(allowed)}.")


def today_iso() -> str:
    return _today(load_labels_config())


def _today(config: dict) -> str:
    offset = timezone(timedelta(hours=config["utc_offset_hours"]))
    return datetime.now(offset).date().isoformat()


def _ring(vertices: list) -> list[list[float]]:
    points = []
    for lat, lng in vertices:
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise LabelError("Coordenada fuera de rango.")
        points.append([lng, lat])
    if len(points) < 3:
        raise LabelError("Un polígono necesita al menos 3 vértices.")
    return points + [points[0]]


def _area_ha(ring: list[list[float]], crs: str) -> float:
    xs, ys = transform("EPSG:4326", crs, [p[0] for p in ring], [p[1] for p in ring])
    twice_area = sum(xs[i] * ys[i + 1] - xs[i + 1] * ys[i] for i in range(len(xs) - 1))
    return abs(twice_area) / 2 / 10_000
