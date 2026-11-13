import json
from collections import Counter
from pathlib import Path

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


def main() -> None:
    zone = load_zone_config()
    imagery = load_imagery_config()
    bbox = boundary_bbox(Path(zone["boundary_path"]))

    client = Client.open(imagery["stac_url"])
    search = client.search(
        collections=[imagery["collection"]],
        bbox=bbox,
        datetime=imagery["date_range"],
        query={"eo:cloud_cover": {"lt": imagery["max_cloud_cover"]}},
    )
    items = list(search.items())

    print(f"Zone: {zone['department']}, {zone['province']}")
    print(f"Date range: {imagery['date_range']}, cloud cover < {imagery['max_cloud_cover']}%")
    print(f"Scenes found: {len(items)}")
    if not items:
        return

    tiles = Counter(item.properties.get("grid:code", "unknown") for item in items)
    for tile, count in sorted(tiles.items()):
        print(f"  tile {tile}: {count} scenes")

    newest = max(items, key=lambda item: item.datetime)
    print(f"Newest scene: {newest.datetime:%Y-%m-%d}, cloud cover {newest.properties['eo:cloud_cover']:.1f}%")


if __name__ == "__main__":
    main()
