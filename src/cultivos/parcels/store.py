"""Parcels table in PostGIS (same database as the catalog)."""

import json
from pathlib import Path

import psycopg
from shapely.geometry import Polygon, mapping

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
AREA_DECIMALS = 2

_COLUMNS = """
    id, name, ST_AsGeoJSON(geom)::json AS geometry, area_ha, below_minimum,
    origin, source_file, created_at, updated_at
"""

_schema_ready = False


class ParcelNotFound(LookupError):
    pass


def ensure_schema(connection: psycopg.Connection) -> None:
    global _schema_ready
    if not _schema_ready:
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        _schema_ready = True


def _feature(row: tuple, code_prefix: str) -> dict:
    parcel_id, name, geometry, area_ha, below_minimum, origin, source_file, created_at, updated_at = row
    return {
        "type": "Feature",
        "id": parcel_id,
        "geometry": geometry,
        "properties": {
            "code": f"{code_prefix}{parcel_id:04d}",
            "name": name,
            "area_ha": round(area_ha, AREA_DECIMALS),
            "below_minimum": below_minimum,
            "origin": origin,
            "source_file": source_file,
            "created_at": created_at.isoformat(),
            "updated_at": updated_at.isoformat(),
        },
    }


def list_parcels(connection: psycopg.Connection, code_prefix: str) -> list[dict]:
    rows = connection.execute(f"SELECT {_COLUMNS} FROM platform.parcels ORDER BY id").fetchall()
    return [_feature(row, code_prefix) for row in rows]


def get_parcel(connection: psycopg.Connection, parcel_id: int, code_prefix: str) -> dict:
    row = connection.execute(f"SELECT {_COLUMNS} FROM platform.parcels WHERE id = %s", [parcel_id]).fetchone()
    if row is None:
        raise ParcelNotFound(parcel_id)
    return _feature(row, code_prefix)


def insert_parcel(
    connection: psycopg.Connection,
    *,
    name: str,
    polygon: Polygon,
    area_ha: float,
    below_minimum: bool,
    origin: str,
    source_file: str | None,
    code_prefix: str,
) -> dict:
    row = connection.execute(
        f"""
        INSERT INTO platform.parcels (name, geom, area_ha, below_minimum, origin, source_file)
        VALUES (%s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s, %s, %s, %s)
        RETURNING {_COLUMNS}
        """,
        [name, json.dumps(mapping(polygon)), area_ha, below_minimum, origin, source_file],
    ).fetchone()
    return _feature(row, code_prefix)


def rename_parcel(connection: psycopg.Connection, parcel_id: int, name: str, code_prefix: str) -> dict:
    row = connection.execute(
        f"UPDATE platform.parcels SET name = %s, updated_at = now() WHERE id = %s RETURNING {_COLUMNS}",
        [name, parcel_id],
    ).fetchone()
    if row is None:
        raise ParcelNotFound(parcel_id)
    return _feature(row, code_prefix)


def delete_parcel(connection: psycopg.Connection, parcel_id: int) -> None:
    deleted = connection.execute("DELETE FROM platform.parcels WHERE id = %s", [parcel_id]).rowcount
    if not deleted:
        raise ParcelNotFound(parcel_id)
