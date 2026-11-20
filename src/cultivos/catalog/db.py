"""Access to our own STAC catalog (pgSTAC). Connection settings come from the PG* environment variables."""

from contextlib import contextmanager
from collections.abc import Iterator

import psycopg
from psycopg.types.json import Jsonb


class CatalogUnavailable(RuntimeError):
    pass


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    try:
        connection = psycopg.connect("", autocommit=True, connect_timeout=5, options="-c search_path=pgstac,public")
    except psycopg.OperationalError as error:
        raise CatalogUnavailable(f"No se pudo conectar al catálogo: {error}") from error
    try:
        yield connection
    finally:
        connection.close()


def upsert_collection(connection: psycopg.Connection, collection: dict) -> None:
    connection.execute("SELECT pgstac.upsert_collection(%s)", [Jsonb(collection)])


def upsert_items(connection: psycopg.Connection, items: list[dict]) -> None:
    if items:
        connection.execute("SELECT pgstac.upsert_items(%s)", [Jsonb(items)])


def update_extents(connection: psycopg.Connection) -> None:
    connection.execute("SELECT pgstac.update_collection_extents()")


def existing_ids(connection: psycopg.Connection, collection: str, ids: list[str]) -> set[str]:
    rows = connection.execute(
        "SELECT id FROM pgstac.items WHERE collection = %s AND id = ANY(%s)", [collection, ids]
    ).fetchall()
    return {row[0] for row in rows}


def search(connection: psycopg.Connection, query: dict) -> list[dict]:
    result = connection.execute("SELECT pgstac.search(%s)", [Jsonb(query)]).fetchone()[0]
    return result.get("features", [])


def collections(connection: psycopg.Connection) -> list[dict]:
    rows = connection.execute("SELECT content FROM pgstac.collections ORDER BY id").fetchall()
    return [row[0] for row in rows]


def collection_stats(connection: psycopg.Connection) -> dict[str, dict]:
    rows = connection.execute(
        """
        SELECT collection, count(*), min(datetime), max(end_datetime)
        FROM pgstac.items
        GROUP BY collection
        """
    ).fetchall()
    return {
        collection: {"items": count, "first": first.date().isoformat(), "last": last.date().isoformat()}
        for collection, count, first, last in rows
    }
