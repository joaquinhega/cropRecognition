import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from pystac import Item

from cultivos.clip_scene import clip_item, read_clip
from cultivos.compute_ndvi import build_ndvi, ndvi_path_for
from cultivos.config import load_imagery_config, load_series_config, load_zone_config
from cultivos.search_scenes import search_items


def month_keys(start: str, count: int) -> list[str]:
    year, month = map(int, start.split("-"))
    keys = []
    for offset in range(count):
        index = year * 12 + month - 1 + offset
        keys.append(f"{index // 12}-{index % 12 + 1:02d}")
    return keys


def group_by_month(items: list[Item], tile: str) -> dict[str, list[Item]]:
    by_month: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        if item.properties.get("grid:code") == tile:
            by_month[f"{item.datetime:%Y-%m}"].append(item)
    return by_month


def valid_share(item: Item, bbox: list[float], imagery: dict) -> float:
    scl, *_ = read_clip(item.assets[imagery["scl_band"]].href, bbox)
    return float(1 - np.isin(scl, imagery["ndvi"]["invalid_scl_classes"]).mean())


def best_scene(candidates: list[Item], bbox: list[float], imagery: dict) -> tuple[Item, float]:
    scored = [(valid_share(item, bbox, imagery), item) for item in candidates]
    share, item = max(scored, key=lambda pair: (pair[0], -pair[1].properties["eo:cloud_cover"]))
    return item, share


def main() -> None:
    series = load_series_config()
    imagery = load_imagery_config()
    bbox = load_zone_config()["work_area"]["bbox"]

    months = month_keys(series["start_month"], series["months"])
    search_imagery = {**imagery, "max_cloud_cover": series["max_scene_cloud_cover"]}
    candidates = group_by_month(search_items(bbox, search_imagery), imagery["tile"])

    dates = []
    for month in months:
        if not candidates[month]:
            print(f"{month}  no scene with cloud cover < {series['max_scene_cloud_cover']}% in tile {imagery['tile']}")
            continue
        item, share = best_scene(candidates[month], bbox, imagery)
        day = f"{item.datetime:%Y-%m-%d}"
        status = "already processed"
        if not ndvi_path_for(day, imagery).exists():
            clip_item(item, day, bbox, imagery)
            build_ndvi(day, imagery)
            status = "downloaded"
        print(f"{month}  {day}  valid in work area {100 * share:5.1f}%  of {len(candidates[month])} candidates  {status}")
        dates.append(day)

    path = Path(series["dates_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dates, indent=2), encoding="utf-8")
    print(f"Dates in the series: {len(dates)} of {len(months)} months")
    print(f"Saved: {path}")


if __name__ == "__main__":
    main()
