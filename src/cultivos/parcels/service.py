"""Create, import, list, rename and delete parcels."""

from collections import Counter
from pathlib import PurePath

from cultivos.catalog import db
from cultivos.config import load_parcels_config
from cultivos.parcels import store
from cultivos.parcels.files import read_parcel_file
from cultivos.parcels.geometry import ParcelError, check_polygon, clean_name, split_polygons

DRAWN = "drawn"
FROM_FILE = "file"


def limits(config: dict | None = None) -> dict:
    config = config or load_parcels_config()
    return {
        "max_area_ha": config["max_area_ha"],
        "min_area_ha": config["min_area_ha"],
        "name_max_length": config["name_max_length"],
        "file_types": config["file_types"],
        "max_file_bytes": config["max_file_bytes"],
    }


def list_parcels() -> dict:
    config = load_parcels_config()
    with db.connect() as connection:
        store.ensure_schema(connection)
        features = store.list_parcels(connection, config["code_prefix"])
    return {"type": "FeatureCollection", "features": features, "limits": limits(config)}


def get_parcel(parcel_id: int) -> dict:
    with db.connect() as connection:
        store.ensure_schema(connection)
        return store.get_parcel(connection, parcel_id, load_parcels_config()["code_prefix"])


def create_drawn(name: str, geometry: dict) -> dict:
    config = load_parcels_config()
    name = clean_name(name, config)
    polygons = split_polygons(geometry)
    if len(polygons) != 1:
        raise ParcelError("Dibujá un solo polígono por parcela.")
    checked = check_polygon(polygons[0], config)
    with db.connect() as connection:
        store.ensure_schema(connection)
        return _insert(connection, name, checked, DRAWN, None, config)


def import_file(filename: str, content: bytes) -> dict:
    """Save every valid polygon of the file as a parcel; report the ones rejected and why."""
    config = load_parcels_config()
    filename = PurePath(filename or "").name
    stem = PurePath(filename).stem or "Parcela"

    entries, rejected = [], []
    for found in read_parcel_file(filename, content, config):
        try:
            entries.extend((found.name, polygon) for polygon in split_polygons(found.geometry))
        except ParcelError as error:
            rejected.append({"name": found.name or stem, "reason": str(error)})

    names = _unique_names([name for name, _ in entries], stem, config["name_max_length"])
    created = []
    with db.connect() as connection:
        store.ensure_schema(connection)
        for name, (_, polygon) in zip(names, entries):
            try:
                checked = check_polygon(polygon, config)
            except ParcelError as error:
                rejected.append({"name": name, "reason": str(error)})
                continue
            created.append(_insert(connection, name, checked, FROM_FILE, filename, config))
    return {"file": filename, "created": created, "rejected": rejected}


def rename(parcel_id: int, name: str) -> dict:
    config = load_parcels_config()
    name = clean_name(name, config)
    with db.connect() as connection:
        store.ensure_schema(connection)
        return store.rename_parcel(connection, parcel_id, name, config["code_prefix"])


def delete(parcel_id: int) -> None:
    with db.connect() as connection:
        store.ensure_schema(connection)
        store.delete_parcel(connection, parcel_id)


def rejection_summary(result: dict) -> str:
    reasons = "; ".join(f"{item['name']}: {item['reason']}" for item in result["rejected"])
    return f"No se guardó ninguna parcela de {result['file']}. {reasons}"


def _insert(connection, name: str, checked, origin: str, source_file: str | None, config: dict) -> dict:
    return store.insert_parcel(
        connection,
        name=name,
        polygon=checked.polygon,
        area_ha=checked.area_ha,
        below_minimum=checked.below_minimum,
        origin=origin,
        source_file=source_file,
        code_prefix=config["code_prefix"],
    )


def _unique_names(names: list[str | None], stem: str, max_length: int) -> list[str]:
    """Missing names take the file name; repeated names get a number."""
    base = [" ".join((name or stem).split())[:max_length] for name in names]
    totals = Counter(base)
    seen = Counter()
    result = []
    for name in base:
        seen[name] += 1
        result.append(f"{name} ({seen[name]})" if totals[name] > 1 else name)
    return result

