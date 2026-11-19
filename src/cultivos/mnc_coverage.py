import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import rasterio
from rasterio.errors import WindowError
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

from cultivos.config import load_inventory_config, load_zone_config


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "cropRecognition"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def get_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "cropRecognition"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def parse_legend(qml_text: str) -> dict[int, str]:
    legend = {}
    for element in ET.fromstring(qml_text).iter():
        if element.tag.endswith("paletteEntry") or element.tag.endswith("item"):
            value, label = element.attrib.get("value"), element.attrib.get("label")
            if value is not None and label is not None:
                try:
                    legend[int(float(value))] = label
                except ValueError:
                    continue
    return legend


def read_counts(dataset, bbox: list[float]) -> dict:
    left, bottom, right, top = transform_bounds("EPSG:4326", dataset.crs, *bbox)
    window = from_bounds(left, bottom, right, top, dataset.transform)
    full = Window(0, 0, dataset.width, dataset.height)
    try:
        window = window.intersection(full).round_offsets().round_lengths()
    except WindowError:
        return {"covered": False}
    if window.width <= 0 or window.height <= 0:
        return {"covered": False}
    data = dataset.read(1, window=window)
    values, counts = np.unique(data, return_counts=True)
    return {
        "covered": True,
        "pixels": int(data.size),
        "nodata": dataset.nodata,
        "counts": {int(v): int(c) for v, c in zip(values, counts)},
    }


def main() -> None:
    config = load_inventory_config()
    mnc = config["mnc"]
    record_id = sys.argv[1] if len(sys.argv) > 1 else mnc["record_id"]
    areas = dict(config["oases"])
    work_area = load_zone_config()["work_area"]
    areas[work_area["name"]] = work_area["bbox"]

    record = get_json(f"{mnc['zenodo_api_url']}{record_id}")
    print(f"Registro {record_id}: {record['metadata']['title']}")
    print(f"Licencia: {record['metadata'].get('license', {}).get('id', 'no informada')}")
    files = {f["key"]: f["links"]["self"] for f in record["files"]}
    legends = {}
    for key, url in files.items():
        if key.lower().endswith(".qml"):
            legends[key] = parse_legend(get_text(url))

    report = {"record": record_id, "files": {}}
    for key, url in files.items():
        if not key.lower().endswith((".tif", ".tiff")):
            continue
        print(f"\n== {key}")
        legend = next(iter(legends.values()), {}) if legends else {}
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
            with rasterio.open(f"/vsicurl/{url}") as dataset:
                bounds = transform_bounds(dataset.crs, "EPSG:4326", *dataset.bounds)
                info = {
                    "crs": str(dataset.crs),
                    "size": [dataset.width, dataset.height],
                    "bounds_4326": [round(v, 3) for v in bounds],
                }
                print(f"raster: {json.dumps(info)}")
                result = {"raster": info}
                for name, bbox in areas.items():
                    counts = read_counts(dataset, bbox)
                    if counts["covered"]:
                        counts["classes"] = {
                            str(value): {
                                "label": legend.get(value, "?"),
                                "pixels": pixels,
                                "ha": round(pixels * mnc["pixel_ha"], 1),
                            }
                            for value, pixels in counts.pop("counts").items()
                        }
                    result[name] = counts
                    print(f"-- {name}: {json.dumps(counts, ensure_ascii=False)}")
                report["files"][key] = result

    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"mnc-{record_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResumen guardado en {path}")


if __name__ == "__main__":
    main()
