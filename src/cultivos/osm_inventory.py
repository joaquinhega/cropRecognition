import json
import random
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import shapely
from osm2geojson import json2geojson
from pyproj import Transformer
from shapely import make_valid
from shapely.geometry import box, shape
from shapely.ops import unary_union

from cultivos.config import load_inventory_config, load_labels_config, load_zone_config

POLYGON_TYPES = {"Polygon", "MultiPolygon"}


def project(geom, transformer: Transformer):
    return shapely.transform(
        geom, lambda coords: np.column_stack(transformer.transform(coords[:, 0], coords[:, 1]))
    )


def build_query(province_iso: str, tag_filter: str, timeout_s: int) -> str:
    return (
        f"[out:json][timeout:{timeout_s}];"
        f'area["ISO3166-2"="{province_iso}"]->.a;'
        f"nwr{tag_filter}(area.a);out geom;"
    )


def fetch_overpass(url: str, query: str, timeout_s: int) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"User-Agent": "cropRecognition"})
    with urllib.request.urlopen(request, timeout=timeout_s + 60) as response:
        return json.load(response)


def to_polygons(overpass_json: dict, projector: Transformer) -> list[dict]:
    collection = json2geojson(overpass_json)
    polygons = []
    for feature in collection["features"]:
        geometry = feature.get("geometry")
        if not geometry or geometry["type"] not in POLYGON_TYPES:
            continue
        geom = make_valid(shape(geometry))
        if geom.is_empty:
            continue
        projected = project(geom, projector)
        props = feature.get("properties", {})
        polygons.append(
            {
                "geom": geom,
                "projected": projected,
                "osm_type": props.get("type"),
                "osm_id": props.get("id"),
                "tags": props.get("tags", {}),
                "area_ha": projected.area / 10000,
            }
        )
    return polygons


def oasis_of(geom, oases: dict) -> str:
    point = geom.representative_point()
    for name, bbox in oases.items():
        if box(*bbox).contains(point):
            return name
    return "fuera de oasis"


def summarize(polygons: list[dict], min_area_ha: float) -> dict:
    big = [p for p in polygons if p["area_ha"] >= min_area_ha]
    by_oasis: dict[str, dict] = {}
    for p in polygons:
        entry = by_oasis.setdefault(p["oasis"], {"n": 0, "ha": 0.0, "n_min": 0, "ha_min": 0.0})
        entry["n"] += 1
        entry["ha"] += p["area_ha"]
        if p["area_ha"] >= min_area_ha:
            entry["n_min"] += 1
            entry["ha_min"] += p["area_ha"]
    return {
        "polygons": len(polygons),
        "ha_total": round(sum(p["area_ha"] for p in polygons), 1),
        "polygons_min_area": len(big),
        "ha_min_area": round(sum(p["area_ha"] for p in big), 1),
        "by_oasis": {
            name: {k: round(v, 1) if isinstance(v, float) else v for k, v in entry.items()}
            for name, entry in by_oasis.items()
        },
    }


def agreement_with_labels(polygons: list[dict], projector: Transformer, area_bbox: list[float]) -> dict:
    labels_path = Path(load_labels_config()["path"])
    if not labels_path.exists():
        return {"error": f"No existe {labels_path}"}
    labels = json.loads(labels_path.read_text(encoding="utf-8"))["features"]
    osm_union = unary_union([p["projected"] for p in polygons])
    in_area = [p for p in polygons if box(*area_bbox).intersects(p["geom"])]
    area_box = project(box(*area_bbox), projector)
    result: dict = {
        "osm_polygons_in_area": len(in_area),
        "osm_ha_clipped_to_area": round(osm_union.intersection(area_box).area / 10000, 1),
        "area_ha": round(area_box.area / 10000, 1),
        "by_class": {},
    }
    for feature in labels:
        props = feature["properties"]
        label_geom = project(make_valid(shape(feature["geometry"])), projector)
        if label_geom.area == 0:
            continue
        covered = label_geom.intersection(osm_union).area / label_geom.area
        entry = result["by_class"].setdefault(
            props["clase"], {"n": 0, "ha": 0.0, "covered_sum": 0.0, "covered_ge_half": 0}
        )
        entry["n"] += 1
        entry["ha"] += label_geom.area / 10000
        entry["covered_sum"] += covered
        entry["covered_ge_half"] += int(covered >= 0.5)
    for entry in result["by_class"].values():
        entry["mean_covered"] = round(entry.pop("covered_sum") / entry["n"], 2)
        entry["ha"] = round(entry["ha"], 1)
    return result


def write_layer(path: Path, polygons: list[dict]) -> None:
    features = [
        {
            "type": "Feature",
            "geometry": json.loads(json.dumps(p["geom"].__geo_interface__)),
            "properties": {
                "osm": f"{p['osm_type']}/{p['osm_id']}",
                "tags": p["tags"],
                "area_ha": round(p["area_ha"], 3),
                "oasis": p["oasis"],
            },
        }
        for p in polygons
    ]
    collection = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    config = load_inventory_config()
    osm = config["osm"]
    min_area_ha = load_labels_config()["min_area_ha"]
    area_bbox = load_zone_config()["work_area"]["bbox"]
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    projector = Transformer.from_crs("EPSG:4326", config["area_crs"], always_xy=True)

    report: dict = {"min_area_ha": min_area_ha, "layers": {}}
    for name, tag_filter in osm["layers"].items():
        print(f"[{name}] consultando Overpass...")
        query = build_query(osm["province_iso"], tag_filter, osm["timeout_s"])
        raw = fetch_overpass(osm["overpass_url"], query, osm["timeout_s"])
        polygons = to_polygons(raw, projector)
        for p in polygons:
            p["oasis"] = oasis_of(p["geom"], config["oases"])
        write_layer(out_dir / f"osm-{name}.geojson", polygons)
        layer = summarize(polygons, min_area_ha)

        if name == osm["reference_layer"]:
            union_ha = unary_union([p["projected"] for p in polygons]).area / 10000
            layer["ha_union"] = round(union_ha, 1)
            layer["reference"] = {
                "area_ha": osm["reference_area_ha"],
                "note": osm["reference_note"],
                "osm_over_reference": round(layer["ha_total"] / osm["reference_area_ha"], 3),
                "osm_union_over_reference": round(union_ha / osm["reference_area_ha"], 3),
            }
            layer["agreement_with_labels"] = agreement_with_labels(polygons, projector, area_bbox)
            big = [p for p in polygons if p["area_ha"] >= min_area_ha]
            sample = random.Random(osm["review_seed"]).sample(
                big, min(osm["review_sample_size"], len(big))
            )
            write_layer(out_dir / f"osm-{name}-muestra-revision.geojson", sample)
        report["layers"][name] = layer
        print(json.dumps(layer, ensure_ascii=False, indent=2))

    report_path = out_dir / "osm-resumen.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Resumen guardado en {report_path}")


if __name__ == "__main__":
    main()
