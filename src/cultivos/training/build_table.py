"""D1-T1: build the training table of a zone: sample pixels from the crop map and their monthly Sentinel-2 series.

Run: docker compose run --rm api python -m cultivos.training.build_table
It can be interrupted and run again: the sample and the finished months are reused.
With --rebuild-sample the sample and its months are made again (the crop map clip is kept).
"""

import argparse
import sys
from datetime import date, datetime, timezone

import numpy as np

from cultivos.adapters import UnknownSource, get_adapter
from cultivos.adapters.base import SearchRequest, SourceError
from cultivos.catalog.db import CatalogUnavailable
from cultivos.catalog.ingest import ingest
from cultivos.config import load_processing_config, load_training_config
from cultivos.training import dataset
from cultivos.training.label_map import LabelMapError, load_label_map
from cultivos.training.labels import map_legend, mismatched, sample_pixels
from cultivos.training.series import month_observations
from cultivos.zones import ZoneError, resolve_area


def legend_report(legend: dict[int, str], mapping: dict, data: np.ndarray) -> list[dict]:
    values, counts = np.unique(data, return_counts=True)
    present = dict(zip(values.tolist(), counts.tolist()))
    return [
        {"value": value, "label": label, "class": mapping.get(value), "map_pixels": int(present.get(value, 0))}
        for value, label in sorted(legend.items())
    ]


def search_month(adapter, bbox: list[float], month, imagery: dict) -> list[dict]:
    """One search per month, so a zone over several tiles never hits the result limit of a long period."""
    request = SearchRequest(
        bbox=bbox,
        start=month.start,
        end=month.end,
        max_cloud_cover=imagery["max_scene_cloud_cover"],
        limit=imagery["search_limit"],
    )
    return [item for item in adapter.search(request) if item["collection"] == imagery["collection"]]


class SampleOutdated(RuntimeError):
    """The saved sample does not match the current class mapping."""


def clear_sample(root) -> None:
    """Remove the sample, its months and the merged table; keep the crop map clip and legend."""
    for path in [root / "pixels.csv", root / "sample.json", root / "observations.csv", root / "summary.json"]:
        path.unlink(missing_ok=True)
    for path in (root / "months").glob("*"):
        path.unlink()


def build(rebuild_sample: bool = False) -> dict:
    config = load_training_config()
    processing = load_processing_config()
    imagery, indices = processing["imagery"], processing["indices"]
    labels_config = config["labels"]
    classes = list(labels_config["classes"])
    area = resolve_area(config["zone"], None)
    root = dataset.folder(config)
    print(f"Zona: {area['name']} ({area['area_km2']} km²). Carpeta: {root}")

    data, transform, legend = load_label_map(labels_config, area["bbox"], root)
    mapping = map_legend(legend, labels_config)
    pixels_path = root / "pixels.csv"
    if rebuild_sample:
        clear_sample(root)
        print("Muestra anterior borrada: se arma de nuevo.")
    if pixels_path.exists():
        pixels = dataset.read_pixels(pixels_path)
        outdated = mismatched(pixels, mapping)
        if outdated:
            raise SampleOutdated(
                f"{len(outdated)} píxeles de la muestra ya no corresponden a su clase con la configuración actual. "
                "Volvé a correr con --rebuild-sample."
            )
        stats = None
        print(f"Muestra existente: {len(pixels)} píxeles (para rehacerla, borrá {pixels_path}).")
    else:
        sampled, stats = sample_pixels(data, transform, mapping, classes, config["sample"])
        pixels = dataset.write_pixels(pixels_path, sampled)
        dataset.write_json(root / "sample.json", stats)
        print(f"Muestra nueva: {len(pixels)} píxeles.")
    stats = stats or (dataset.read_json(root / "sample.json") if (root / "sample.json").exists() else {})

    print("\nLeyenda del mapa → clase:")
    legend_rows = legend_report(legend, mapping, data)
    for row in legend_rows:
        print(f"  {row['value']:>4}  {row['label']:<40} → {row['class'] or 'excluida'}  ({row['map_pixels']} píxeles en la zona)")
    for name in classes:
        info = stats.get(name, {})
        print(f"  {name}: {info.get('sampled', '?')} de {info.get('candidates', '?')} píxeles candidatos (manchas parejas)")

    band_roles = [role for role in imagery["assets"] if role != "scl"]
    fields = dataset.observation_fields(band_roles, list(indices))
    months = dataset.campaign_months(date.fromisoformat(config["campaign_start"]), config["months"])
    months_dir = root / "months"
    pending = [month for month in months if not (months_dir / f"{month.key}.json").exists()]
    lons = np.array([pixel["lon"] for pixel in pixels])
    lats = np.array([pixel["lat"] for pixel in pixels])
    ids = [pixel["pixel_id"] for pixel in pixels]

    if pending:
        adapter = get_adapter(imagery["source"])
        print(f"\nSeries de Sentinel-2: {len(pending)} meses por calcular (cada uno tarda unos minutos).")
        for number, month in enumerate(pending, 1):
            candidates = search_month(adapter, area["bbox"], month, imagery)
            rows, info = month_observations(month.key, candidates, lons, lats, imagery, indices)
            for row in rows:
                row["pixel_id"] = ids[row.pop("pixel")]
            used = {scene["id"] for scene in info["scenes"]}
            ingest(adapter, [item for item in candidates if item["id"] in used])
            dataset.write_rows(months_dir / f"{month.key}.csv", fields, rows)
            dataset.write_json(months_dir / f"{month.key}.json", info)
            print(
                f"  [{number}/{len(pending)}] {month.key}: {info['pixels_with_data']} de {len(pixels)} píxeles con dato "
                f"({info['share_with_data']:.0%}), {len(info['scenes'])} escenas de {info['candidates']}"
                + (f", {info['read_errors']} errores de lectura" if info["read_errors"] else "")
            )

    observations = []
    month_infos = []
    for month in months:
        observations.extend(dataset.read_rows(months_dir / f"{month.key}.csv"))
        month_infos.append(dataset.read_json(months_dir / f"{month.key}.json"))
    dataset.write_rows(root / "observations.csv", fields, observations)

    summary = {
        "dataset_id": config["dataset_id"],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "zone": area,
        "campaign": months[0].campaign,
        "months": month_infos,
        "labels": {key: labels_config[key] for key in ("title", "license", "attribution", "limits", "record_id", "map_file")},
        "legend": legend_rows,
        "classes": {
            name: {
                "title": spec["title"],
                "color": spec["color"],
                "candidates": stats.get(name, {}).get("candidates"),
                "pixels": sum(1 for pixel in pixels if pixel["class"] == name),
            }
            for name, spec in labels_config["classes"].items()
        },
        "pixels": len(pixels),
        "observations": len(observations),
        "imagery": {"source": imagery["source"], "collection": imagery["collection"]},
    }
    dataset.write_json(root / "summary.json", summary)
    print(f"\nListo: {len(pixels)} píxeles y {len(observations)} observaciones mensuales en {root}.")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Tabla de entrenamiento de la zona de config/training.json.")
    parser.add_argument("--rebuild-sample", action="store_true", help="Rehace la muestra y sus meses.")
    args = parser.parse_args()
    try:
        build(rebuild_sample=args.rebuild_sample)
    except (LabelMapError, ZoneError, UnknownSource, SourceError, CatalogUnavailable, SampleOutdated) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
