"""Checks a parcel polygon and measures its geodesic area (valid anywhere on Earth)."""

import re
from dataclasses import dataclass

from pyproj import Geod
from shapely import force_2d
from shapely.errors import ShapelyError
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.geometry.polygon import orient
from shapely.validation import explain_validity

_GEOD = Geod(ellps="WGS84")
SQUARE_METERS_PER_HA = 10_000
COUNTERCLOCKWISE = 1.0

_INVALID_REASONS = {
    "Self-intersection": "el borde se cruza consigo mismo",
    "Ring Self-intersection": "el borde se toca a sí mismo",
    "Too few points": "tiene muy pocos vértices",
    "Hole lies outside shell": "tiene un hueco fuera del borde",
    "Nested holes": "tiene huecos uno dentro de otro",
    "Interior is disconnected": "un hueco parte la parcela en dos",
    "Nested shells": "tiene un borde dentro de otro",
    "Duplicate Rings": "tiene bordes repetidos",
}


class ParcelError(ValueError):
    pass


@dataclass(frozen=True)
class CheckedPolygon:
    polygon: Polygon
    area_ha: float
    below_minimum: bool


def format_ha(value: float) -> str:
    text = f"{value:,.1f}" if value < 100 else f"{value:,.0f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def split_polygons(geometry: dict) -> list[Polygon]:
    """Polygons in a GeoJSON geometry; a MultiPolygon gives one per part."""
    kind = geometry.get("type") if isinstance(geometry, dict) else None
    if kind not in ("Polygon", "MultiPolygon"):
        raise ParcelError(f"Se esperaba un polígono y llegó {kind or 'otra cosa'}.")
    try:
        parsed = shape(geometry)
    except (ShapelyError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        raise ParcelError("Las coordenadas del polígono no se pueden leer.") from None
    return list(parsed.geoms) if isinstance(parsed, MultiPolygon) else [parsed]


def _invalid_reason(polygon: Polygon) -> str:
    explanation = explain_validity(polygon)
    match = re.match(r"([^\[]+)\[([-\d.e]+) ([-\d.e]+)", explanation)
    if not match:
        return f"la forma no es válida ({explanation})"
    reason = _INVALID_REASONS.get(match.group(1).strip(), f"la forma no es válida ({match.group(1).strip()})")
    lon, lat = float(match.group(2)), float(match.group(3))
    return f"{reason} cerca de {lat:.5f}, {lon:.5f}"


def check_polygon(polygon: Polygon, config: dict) -> CheckedPolygon:
    """Validate shape and size; raise ParcelError with a plain-language reason."""
    polygon = force_2d(polygon)
    if polygon.is_empty:
        raise ParcelError("El polígono está vacío.")
    west, south, east, north = polygon.bounds
    if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
        raise ParcelError("Las coordenadas no son longitud y latitud en grados (EPSG:4326).")
    if len(set(polygon.exterior.coords)) < 3:
        raise ParcelError("El polígono necesita al menos tres vértices distintos.")
    if not polygon.is_valid:
        raise ParcelError(f"El polígono no es válido: {_invalid_reason(polygon)}.")

    polygon = orient(polygon, COUNTERCLOCKWISE)
    area_ha = _GEOD.geometry_area_perimeter(polygon)[0] / SQUARE_METERS_PER_HA
    if area_ha > config["max_area_ha"]:
        raise ParcelError(
            f"Tiene {format_ha(area_ha)} ha y el máximo es {format_ha(config['max_area_ha'])} ha. "
            "Dividila en parcelas más chicas."
        )
    return CheckedPolygon(
        polygon=polygon,
        area_ha=area_ha,
        below_minimum=area_ha < config["min_area_ha"],
    )


def clean_name(name: str | None, config: dict) -> str:
    cleaned = " ".join((name or "").split())
    if not cleaned:
        raise ParcelError("Poné un nombre a la parcela.")
    if len(cleaned) > config["name_max_length"]:
        raise ParcelError(f"El nombre puede tener hasta {config['name_max_length']} caracteres.")
    return cleaned
