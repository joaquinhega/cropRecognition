import argparse
import json
from collections import Counter
from pathlib import Path

from pystac import Item
from pystac_client import Client

from cultivos.config import load_imagery_config, load_zone_config


def collect_coordinates(node: list, xs: list[float], ys: list[float]) -> None:
    if isinstance(node[0], (int, float)):
        xs.append(node[0])
        ys.append(node[1])
        return
    for child in node:
        collect_coordinates(child, xs, ys)


def boundary_bbox(path: Path) -> list[float]:
    collection = json.loads(path.read_text(encoding="utf-8"))
    xs: list[float] = []
    ys: list[float] = []
    for feature in collection["features"]:
        collect_coordinates(feature["geometry"]["coordinates"], xs, ys)
    return [min(xs), min(ys), max(xs), max(ys)]


def search_items(bbox: list[float], imagery: dict) -> list[Item]:
    client = Client.open(imagery["stac_url"])
    search = client.search(
        collections=[imagery["collection"]],
        bbox=bbox,
        datetime=imagery["date_range"],
        query={"eo:cloud_cover": {"lt": imagery["max_cloud_cover"]}},
    )
    return list(search.items())


def print_scenes(items: list[Item]) -> None:
    print("Scenes (oldest first):")
    for item in sorted(items, key=lambda item: item.datetime):
        tile = item.properties.get("grid:code", "unknown")
        cloud = item.properties["eo:cloud_cover"]
        print(f"  {item.datetime:%Y-%m-%d}  {tile}  cloud {cloud:5.1f}%  {item.id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", choices=["department", "work_area"], default="department")
    args = parser.parse_args()

    zone = load_zone_config()
    imagery = load_imagery_config()

    if args.area == "work_area":
        label = zone["work_area"]["name"]
        bbox = zone["work_area"]["bbox"]
    else:
        label = f"{zone['department']}, {zone['province']}"
        bbox = boundary_bbox(Path(zone["boundary_path"]))

    items = search_items(bbox, imagery)

    print(f"Zone: {label}")
    print(f"Bounding box: {bbox}")
    print(f"Date range: {imagery['date_range']}, cloud cover < {imagery['max_cloud_cover']}%")
    print(f"Scenes found: {len(items)}")
    if not items:
        return

    tiles = Counter(item.properties.get("grid:code", "unknown") for item in items)
    for tile, count in sorted(tiles.items()):
        print(f"  tile {tile}: {count} scenes")

    newest = max(items, key=lambda item: item.datetime)
    print(f"Newest scene: {newest.datetime:%Y-%m-%d}, cloud cover {newest.properties['eo:cloud_cover']:.1f}%")

    if args.area == "work_area":
        print_scenes(items)


if __name__ == "__main__":
    main()
