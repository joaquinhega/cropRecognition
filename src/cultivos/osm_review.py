"""D1-T0: manual review of the OSM vineyard sample before training (04-protocolo-etiquetado, D-042)."""

import json
from datetime import date
from pathlib import Path

from shapely.geometry import shape

from cultivos.adapters import get_adapter
from cultivos.adapters.base import SearchRequest
from cultivos.catalog import items as catalog_items
from cultivos.catalog.ingest import ingest
from cultivos.config import load_inventory_config, load_processing_config
from cultivos.labels import today_iso
from cultivos.modules.scenes import choose_scene

SHARE_EPSILON = 1e-9


class ReviewError(ValueError):
    """The request cannot be applied to the review."""


class ReviewNotFound(LookupError):
    """The sample or one of its polygons does not exist."""


def review_config() -> dict:
    return load_inventory_config()["osm"]["review"]


def _sample(config: dict) -> list[dict]:
    path = Path(config["sample_path"])
    if not path.exists():
        raise ReviewNotFound(
            f"Falta la muestra {path}. Ejecutá: docker compose run --rm api python -m cultivos.osm_inventory"
        )
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def _results(config: dict) -> dict:
    path = Path(config["results_path"])
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write_results(config: dict, results: dict) -> None:
    path = Path(config["results_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


def _feature(sample: list[dict], n: int) -> dict:
    if not 1 <= n <= len(sample):
        raise ReviewNotFound(f"La muestra tiene {len(sample)} polígonos; no existe el {n}.")
    return sample[n - 1]


def _view(n: int, feature: dict, entry: dict) -> dict:
    properties = feature["properties"]
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": {
            "n": n,
            "osm": properties["osm"],
            "oasis": properties.get("oasis"),
            "area_ha": properties.get("area_ha"),
            "verdict": entry.get("verdict"),
            "note": entry.get("note", ""),
            "reviewed_at": entry.get("reviewed_at"),
        },
    }


def summarize(sample: list[dict], results: dict, config: dict) -> dict:
    """Progress and outcome: OSM is doubtful when more than the allowed share of the sample does not match."""
    verdicts = config["verdicts"]
    counts = {verdict: 0 for verdict in verdicts}
    for feature in sample:
        verdict = results.get(feature["properties"]["osm"], {}).get("verdict")
        if verdict in counts:
            counts[verdict] += 1
    total = len(sample)
    reviewed = sum(counts.values())
    mismatches = sum(count for verdict, count in counts.items() if verdicts[verdict]["mismatch"])
    uncertain = sum(count for verdict, count in counts.items() if verdicts[verdict]["uncertain"])
    max_mismatches = int(config["max_mismatch_share"] * total + SHARE_EPSILON)
    if mismatches > max_mismatches:
        status = "doubtful"
    elif reviewed < total:
        status = "in_progress"
    else:
        status = "approved"
    return {
        "total": total,
        "reviewed": reviewed,
        "counts": counts,
        "mismatches": mismatches,
        "max_mismatch_share": config["max_mismatch_share"],
        "max_mismatches": max_mismatches,
        "uncertain_could_fail": status != "doubtful" and mismatches + uncertain > max_mismatches,
        "status": status,
    }


def read_review() -> dict:
    config = review_config()
    sample, results = _sample(config), _results(config)
    imagery = load_processing_config()["imagery"]
    return {
        "type": "FeatureCollection",
        "features": [_view(n, feature, results.get(feature["properties"]["osm"], {})) for n, feature in enumerate(sample, 1)],
        "summary": summarize(sample, results, config),
        "verdicts": [{"id": verdict, "title": info["title"], "help": info["help"]} for verdict, info in config["verdicts"].items()],
        "layers": catalog_items.collection_layers(imagery["collection"]),
        "reference": {"start": config["reference_start"], "end": config["reference_end"]},
    }


def save_verdict(n: int, verdict: str, note: str = "") -> dict:
    config = review_config()
    if verdict not in config["verdicts"]:
        raise ReviewError(f"Respuesta desconocida: {verdict}. Opciones: {', '.join(config['verdicts'])}.")
    sample, results = _sample(config), _results(config)
    feature = _feature(sample, n)
    osm_id = feature["properties"]["osm"]
    entry = results.get(osm_id, {})
    entry.update(verdict=verdict, note=note.strip(), reviewed_at=today_iso())
    results[osm_id] = entry
    _write_results(config, results)
    return {"feature": _view(n, feature, entry), "summary": summarize(sample, results, config)}


def _scene_view(scene: dict | None, reason: str | None = None) -> dict:
    if scene is None:
        return {"scene": None, "reason": reason}
    return {"scene": {**scene, "layers": catalog_items.item_layers(scene["collection"], scene["id"])}, "reason": None}


def reference_scene(n: int) -> dict:
    """Cleanest Sentinel-2 scene over the polygon in the reference period; chosen once and remembered."""
    config = review_config()
    sample, results = _sample(config), _results(config)
    feature = _feature(sample, n)
    osm_id = feature["properties"]["osm"]
    entry = results.get(osm_id, {})
    if entry.get("scene"):
        return _scene_view(entry["scene"])

    imagery = load_processing_config()["imagery"]
    polygon = shape(feature["geometry"])
    adapter = get_adapter(imagery["source"])
    request = SearchRequest(
        bbox=list(polygon.bounds),
        start=date.fromisoformat(config["reference_start"]),
        end=date.fromisoformat(config["reference_end"]),
        max_cloud_cover=imagery["max_scene_cloud_cover"],
        limit=imagery["search_limit"],
    )
    candidates = [item for item in adapter.search(request) if item["collection"] == imagery["collection"]]
    if not candidates:
        return _scene_view(None, "No hay imágenes de Sentinel-2 del polígono en el período de referencia.")
    pick = choose_scene(candidates, polygon, imagery)
    if pick.choice is None:
        return _scene_view(None, "No se pudo leer ninguna imagen del período sobre el polígono.")

    item = pick.choice.item
    ingest(adapter, [item])
    scene = {
        "id": item["id"],
        "collection": item["collection"],
        "date": item["properties"]["datetime"][:10],
        "valid_share": round(pick.choice.share, 4),
    }
    results = _results(config)
    results.setdefault(osm_id, {})["scene"] = scene
    _write_results(config, results)
    return _scene_view(scene)
