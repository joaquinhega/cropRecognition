"""Reads parcel polygons from uploaded GeoJSON, KML or KMZ files."""

import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import PurePath
from xml.etree import ElementTree

from cultivos.parcels.geometry import ParcelError

KML_SUFFIX = ".kml"
KMZ_SUFFIX = ".kmz"
POLYGON_TYPES = ("Polygon", "MultiPolygon")


@dataclass(frozen=True)
class FilePolygon:
    name: str | None
    geometry: dict


def read_parcel_file(filename: str, content: bytes, config: dict) -> list[FilePolygon]:
    suffix = PurePath(filename).suffix.lower()
    if suffix not in config["file_types"]:
        raise ParcelError(f"Formato no admitido ({suffix or 'sin extensión'}). Subí un GeoJSON, KML o KMZ.")
    if not content:
        raise ParcelError("El archivo está vacío.")
    if len(content) > config["max_file_bytes"]:
        raise ParcelError(f"El archivo supera el máximo de {config['max_file_bytes'] // 1_000_000} MB.")

    if suffix == KMZ_SUFFIX:
        found = _read_kml(_unzip_kml(content, config["max_file_bytes"]))
    elif suffix == KML_SUFFIX:
        found = _read_kml(content)
    else:
        found = _read_geojson(content, config)

    if not found:
        raise ParcelError("El archivo no tiene polígonos.")
    if len(found) > config["max_polygons_per_file"]:
        raise ParcelError(f"El archivo tiene {len(found)} polígonos y el máximo es {config['max_polygons_per_file']}.")
    return found


def _read_geojson(content: bytes, config: dict) -> list[FilePolygon]:
    try:
        data = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ParcelError("El archivo no es un GeoJSON válido.") from None
    if not isinstance(data, dict):
        raise ParcelError("El archivo no es un GeoJSON válido.")

    crs_name = (data.get("crs") or {}).get("properties", {}).get("name")
    if crs_name and crs_name not in config["lonlat_crs_names"]:
        raise ParcelError(f"El archivo está en otra proyección ({crs_name}). Exportalo en latitud y longitud (EPSG:4326).")

    if data.get("type") == "FeatureCollection":
        features = data.get("features") or []
    elif data.get("type") == "Feature":
        features = [data]
    else:
        features = [{"type": "Feature", "geometry": data, "properties": {}}]

    found = []
    for feature in features:
        geometry = feature.get("geometry") if isinstance(feature, dict) else None
        if isinstance(geometry, dict) and geometry.get("type") in POLYGON_TYPES:
            found.append(FilePolygon(name=_property_name(feature.get("properties"), config), geometry=geometry))
    return found


def _property_name(properties: dict | None, config: dict) -> str | None:
    for key in config["name_properties"]:
        value = (properties or {}).get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _unzip_kml(content: bytes, max_bytes: int) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = [info for info in archive.infolist() if info.filename.lower().endswith(KML_SUFFIX)]
            if not names:
                raise ParcelError("El KMZ no tiene ningún KML adentro.")
            chosen = next((info for info in names if PurePath(info.filename).name.lower() == "doc.kml"), names[0])
            if chosen.file_size > max_bytes:
                raise ParcelError("El KML dentro del KMZ es demasiado grande.")
            return archive.read(chosen)
    except zipfile.BadZipFile:
        raise ParcelError("El archivo KMZ está dañado.") from None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [child for child in element.iter() if _local(child.tag) == name]


def _ring(boundary: ElementTree.Element) -> list[list[float]]:
    coordinates = next((item for item in _children(boundary, "coordinates")), None)
    if coordinates is None or not (coordinates.text or "").strip():
        raise ParcelError("Hay un polígono sin coordenadas en el KML.")
    try:
        points = [[float(value) for value in point.split(",")[:2]] for point in coordinates.text.split()]
    except ValueError:
        raise ParcelError("Hay coordenadas ilegibles en el KML.") from None
    if any(len(point) != 2 for point in points):
        raise ParcelError("Hay coordenadas ilegibles en el KML.")
    return points


def _polygon(element: ElementTree.Element) -> dict:
    rings = []
    for child in element:
        if _local(child.tag) == "outerBoundaryIs":
            rings.insert(0, _ring(child))
        elif _local(child.tag) == "innerBoundaryIs":
            rings.append(_ring(child))
    if not rings:
        raise ParcelError("Hay un polígono sin borde exterior en el KML.")
    return {"type": "Polygon", "coordinates": rings}


def _read_kml(content: bytes) -> list[FilePolygon]:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        raise ParcelError("El archivo no es un KML válido.") from None

    found = []
    for placemark in _children(root, "Placemark"):
        name_element = next((child for child in placemark if _local(child.tag) == "name"), None)
        name = (name_element.text or "").strip() if name_element is not None else ""
        for polygon in _children(placemark, "Polygon"):
            found.append(FilePolygon(name=name or None, geometry=_polygon(polygon)))
    return found
