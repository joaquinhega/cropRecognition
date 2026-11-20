"""Monthly index and climate results per parcel, in PostGIS next to the parcels."""

from datetime import date
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from cultivos.parcels import store as parcels_store

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

_schema_ready = False


def ensure_schema(connection: psycopg.Connection) -> None:
    global _schema_ready
    if not _schema_ready:
        parcels_store.ensure_schema(connection)
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        _schema_ready = True


def final_months(connection: psycopg.Connection, parcel_id: int) -> set[str]:
    """Months already processed that will not change (complete and without read errors)."""
    rows = connection.execute(
        "SELECT month FROM platform.parcel_index_months WHERE parcel_id = %s AND complete AND status <> 'error'",
        [parcel_id],
    ).fetchall()
    return {f"{row[0]:%Y-%m}" for row in rows}


def save_index_month(connection: psycopg.Connection, parcel_id: int, row: dict) -> None:
    connection.execute(
        """
        INSERT INTO platform.parcel_index_months (
            parcel_id, month, campaign, status, scene_id, scene_collection, scene_datetime, scene_cloud_cover,
            valid_share, valid_pixels, parcel_pixels, candidates, indices, complete, processed_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (parcel_id, month) DO UPDATE SET
            campaign = EXCLUDED.campaign, status = EXCLUDED.status, scene_id = EXCLUDED.scene_id,
            scene_collection = EXCLUDED.scene_collection, scene_datetime = EXCLUDED.scene_datetime,
            scene_cloud_cover = EXCLUDED.scene_cloud_cover, valid_share = EXCLUDED.valid_share,
            valid_pixels = EXCLUDED.valid_pixels, parcel_pixels = EXCLUDED.parcel_pixels,
            candidates = EXCLUDED.candidates, indices = EXCLUDED.indices, complete = EXCLUDED.complete,
            processed_at = now()
        """,
        [
            parcel_id,
            row["month"],
            row["campaign"],
            row["status"],
            row["scene_id"],
            row["scene_collection"],
            row["scene_datetime"],
            row["scene_cloud_cover"],
            row["valid_share"],
            row["valid_pixels"],
            row["parcel_pixels"],
            row["candidates"],
            Jsonb(row["indices"]) if row["indices"] is not None else None,
            row["complete"],
        ],
    )


def status_counts(connection: psycopg.Connection, parcel_id: int, since: date) -> dict[str, int]:
    rows = connection.execute(
        """
        SELECT status, count(*) FROM platform.parcel_index_months
        WHERE parcel_id = %s AND month >= %s GROUP BY status
        """,
        [parcel_id, since],
    ).fetchall()
    return {status: count for status, count in rows}


def index_months(connection: psycopg.Connection, parcel_id: int) -> list[dict]:
    cursor = connection.execute(
        """
        SELECT month, campaign, status, scene_id, scene_collection, scene_datetime, scene_cloud_cover,
               valid_share, valid_pixels, parcel_pixels, candidates, indices, complete, processed_at
        FROM platform.parcel_index_months WHERE parcel_id = %s ORDER BY month
        """,
        [parcel_id],
    )
    names = [column.name for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def replace_climate(
    connection: psycopg.Connection, parcel_id: int, months: list[dict], point: tuple[float, float], item_id: str
) -> None:
    """Climate is cheap to fetch and its last days change, so every run replaces it whole."""
    with connection.transaction():
        connection.execute("DELETE FROM platform.parcel_climate_months WHERE parcel_id = %s", [parcel_id])
        for month in months:
            connection.execute(
                """
                INSERT INTO platform.parcel_climate_months
                    (parcel_id, month, campaign, days, valid_days, weather, point, item_id)
                VALUES (%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
                """,
                [
                    parcel_id,
                    month["month"],
                    month["campaign"],
                    month["days"],
                    month["valid_days"],
                    Jsonb(month["weather"]),
                    point[0],
                    point[1],
                    item_id,
                ],
            )


def climate_months(connection: psycopg.Connection, parcel_id: int) -> list[dict]:
    cursor = connection.execute(
        """
        SELECT month, campaign, days, valid_days, weather, ST_X(point) AS lon, ST_Y(point) AS lat, item_id, processed_at
        FROM platform.parcel_climate_months WHERE parcel_id = %s ORDER BY month
        """,
        [parcel_id],
    )
    names = [column.name for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def month_date(key: str) -> date:
    year, month = map(int, key.split("-"))
    return date(year, month, 1)
