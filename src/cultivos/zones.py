"""Named zones and bounding boxes used to query sources and the catalog."""

from pyproj import Geod

from cultivos.config import load_zones_config

_GEOD = Geod(ellps="WGS84")


class ZoneError(ValueError):
    pass


def list_zones() -> dict:
    config = load_zones_config()
    zones = [{"id": zone_id, **zone} for zone_id, zone in config["zones"].items()]
    return {"default_zone": config["default_zone"], "zones": zones}


def bbox_area_km2(bbox: list[float]) -> float:
    west, south, east, north = bbox
    lons = [west, east, east, west]
    lats = [south, south, north, north]
    area_m2, _ = _GEOD.polygon_area_perimeter(lons, lats)
    return abs(area_m2) / 1e6


def parse_bbox(text: str) -> list[float]:
    try:
        values = [float(value) for value in text.split(",")]
    except ValueError:
        raise ZoneError("El recuadro debe tener cuatro números: oeste,sur,este,norte.") from None
    if len(values) != 4:
        raise ZoneError("El recuadro debe tener cuatro números: oeste,sur,este,norte.")
    west, south, east, north = values
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ZoneError("Recuadro inválido: revisá el orden oeste,sur,este,norte.")
    return values


def resolve_area(zone: str | None, bbox: str | None) -> dict:
    """Return {'id', 'name', 'bbox'} for a named zone or a free bbox, checking its size."""
    config = load_zones_config()
    if bbox:
        area = {"id": None, "name": "Recuadro dibujado", "bbox": parse_bbox(bbox)}
    else:
        zone_id = zone or config["default_zone"]
        if zone_id not in config["zones"]:
            raise ZoneError(f"No existe la zona {zone_id}.")
        area = {"id": zone_id, "name": config["zones"][zone_id]["name"], "bbox": config["zones"][zone_id]["bbox"]}

    area_km2 = bbox_area_km2(area["bbox"])
    if area_km2 > config["max_search_area_km2"]:
        raise ZoneError(
            f"El recuadro tiene {area_km2:,.0f} km² y el máximo es {config['max_search_area_km2']:,} km²."
        )
    return {**area, "area_km2": round(area_km2, 2)}
