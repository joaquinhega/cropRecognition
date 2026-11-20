"""Load one NDVI image into the STAC catalog as a throwaway test item (B1-T1)."""

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import rasterio
from rasterio.shutil import copy as raster_copy
from rasterio.warp import transform_bounds

CONFIG_PATH = Path("config/catalog_test.json")
COG_MEDIA_TYPE = "image/tiff; application=geotiff; profile=cloud-optimized"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def make_cog(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    raster_copy(source, target, driver="COG", compress="DEFLATE", blocksize=256)


def read_geometry(path: Path) -> tuple[list[float], int]:
    with rasterio.open(path) as dataset:
        bbox = transform_bounds(dataset.crs, "EPSG:4326", *dataset.bounds)
        return list(bbox), dataset.crs.to_epsg()


def build_collection(config: dict, bbox: list[float]) -> dict:
    return {
        "type": "Collection",
        "stac_version": "1.0.0",
        "id": config["collection_id"],
        "description": "Test collection with one NDVI image (B1-T1). Derived from Sentinel-2 L2A, Copernicus.",
        "license": "proprietary",
        "extent": {
            "spatial": {"bbox": [bbox]},
            "temporal": {"interval": [[config["datetime"], config["datetime"]]]},
        },
        "links": [],
    }


def build_item(config: dict, bbox: list[float], epsg: int) -> dict:
    west, south, east, north = bbox
    href = str(Path(config["container_root"]) / config["cog_path"])
    return {
        "type": "Feature",
        "stac_version": "1.0.0",
        "id": config["item_id"],
        "collection": config["collection_id"],
        "bbox": bbox,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
        },
        "properties": {"datetime": config["datetime"], "proj:epsg": epsg},
        "assets": {
            config["render"]["assets"]: {
                "href": href,
                "type": COG_MEDIA_TYPE,
                "roles": ["data"],
                "title": "NDVI",
            }
        },
        "links": [],
    }


def send(method: str, url: str, body: dict) -> int:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def create_or_replace(create_url: str, replace_url: str, body: dict) -> None:
    status = send("POST", create_url, body)
    if status == 409:
        status = send("PUT", replace_url, body)
    if status >= 300:
        raise SystemExit(f"El catálogo respondió {status} en {create_url}")


def viewer_url(config: dict) -> str:
    render = urllib.parse.urlencode(config["render"])
    base = f"{config['raster_url']}/collections/{config['collection_id']}/items/{config['item_id']}"
    return f"{base}/WebMercatorQuad/map.html?{render}"


def main() -> None:
    config = load_config()
    make_cog(Path(config["source_path"]), Path(config["cog_path"]))
    bbox, epsg = read_geometry(Path(config["cog_path"]))

    stac = config["stac_url"]
    collection_id = config["collection_id"]
    create_or_replace(
        f"{stac}/collections",
        f"{stac}/collections/{collection_id}",
        build_collection(config, bbox),
    )
    create_or_replace(
        f"{stac}/collections/{collection_id}/items",
        f"{stac}/collections/{collection_id}/items/{config['item_id']}",
        build_item(config, bbox, epsg),
    )
    print(f"COG creado en {config['cog_path']}")
    print(f"Ítem cargado: {config['collection_id']}/{config['item_id']}")
    print(f"Abrí en el navegador: {viewer_url(config)}")


if __name__ == "__main__":
    main()
