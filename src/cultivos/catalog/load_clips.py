"""Load the Agrelo clips from subproject A into our catalog, so TiTiler serves them (B3-T1)."""

from pathlib import Path

import rasterio
from rasterio.shutil import copy as raster_copy
from rasterio.warp import transform_bounds

from cultivos.adapters.base import SOURCE_PROPERTY
from cultivos.catalog import db
from cultivos.clips import clip_paths, list_dates
from cultivos.config import load_catalog_config, load_imagery_config

COG_MEDIA_TYPE = "image/tiff; application=geotiff; profile=cloud-optimized"
LOCAL_SOURCE = "local"
ACQUISITION_TIME = "T00:00:00Z"


def make_cog(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    raster_copy(source, target, driver="COG", compress="DEFLATE", blocksize=256)


def footprint(path: Path) -> tuple[list[float], int]:
    with rasterio.open(path) as dataset:
        return list(transform_bounds(dataset.crs, "EPSG:4326", *dataset.bounds)), dataset.crs.to_epsg()


def band_names(path: Path) -> list[str]:
    with rasterio.open(path) as dataset:
        return list(dataset.descriptions)


def build_collection(settings: dict) -> dict:
    return {
        "type": "Collection",
        "stac_version": "1.0.0",
        "id": settings["collection_id"],
        "title": settings["title"],
        "description": settings["description"],
        "license": "other",
        "extent": {"spatial": {"bbox": [[-180, -90, 180, 90]]}, "temporal": {"interval": [[None, None]]}},
        "links": [],
        SOURCE_PROPERTY: LOCAL_SOURCE,
        "cultivos:attribution": settings["attribution"],
        "cultivos:license_title": "Derivado de Copernicus Sentinel (uso libre, citar la fuente)",
        "cultivos:limits": "Solo cubre el recuadro de prueba de Agrelo. El NDVI ya tiene las nubes descartadas.",
        "cultivos:resolution": f"{settings['resolution_m']} m",
    }


def build_item(day: str, settings: dict, bands_cog: Path, ndvi_cog: Path | None, imagery: dict) -> dict:
    bbox, epsg = footprint(bands_cog)
    west, south, east, north = bbox
    root = Path(settings["container_root"])
    assets = {
        "bands": {
            "href": str(root / bands_cog),
            "type": COG_MEDIA_TYPE,
            "roles": ["data"],
            "title": "Bandas " + ", ".join(band_names(bands_cog)),
        }
    }
    if ndvi_cog:
        assets["ndvi"] = {"href": str(root / ndvi_cog), "type": COG_MEDIA_TYPE, "roles": ["data"], "title": "NDVI sin nubes"}
    return {
        "type": "Feature",
        "stac_version": "1.0.0",
        "id": day,
        "collection": settings["collection_id"],
        "bbox": bbox,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
        },
        "properties": {
            "datetime": f"{day}{ACQUISITION_TIME}",
            "proj:epsg": epsg,
            "grid:code": imagery["tile"],
            SOURCE_PROPERTY: LOCAL_SOURCE,
        },
        "assets": assets,
        "links": [],
    }


def main() -> None:
    settings = load_catalog_config()["local_clips"]
    imagery = load_imagery_config()
    cog_dir = Path(settings["cog_dir"])
    items = []
    for entry in list_dates():
        day = entry["date"]
        bands_path, _, ndvi_path = clip_paths(day, imagery)
        bands_cog = cog_dir / f"{day}_bands.tif"
        make_cog(bands_path, bands_cog)
        ndvi_cog = None
        if entry["has_ndvi"]:
            ndvi_cog = cog_dir / f"{day}_ndvi.tif"
            make_cog(ndvi_path, ndvi_cog)
        items.append(build_item(day, settings, bands_cog, ndvi_cog, imagery))

    with db.connect() as connection:
        db.upsert_collection(connection, build_collection(settings))
        db.upsert_items(connection, items)
        db.update_extents(connection)

    with_ndvi = sum(1 for item in items if "ndvi" in item["assets"])
    print(f"Colección {settings['collection_id']}: {len(items)} fechas cargadas ({with_ndvi} con NDVI).")
    print(f"COG en {cog_dir}/")


if __name__ == "__main__":
    main()
