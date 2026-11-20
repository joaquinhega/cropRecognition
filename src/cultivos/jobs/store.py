"""Job queue in Postgres: enqueue, claim with SKIP LOCKED, report progress, finish and recover cut jobs."""

from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from cultivos.parcels import store as parcels_store

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"
ACTIVE = (QUEUED, RUNNING)

_COLUMNS = """
    id, kind, parcel_id, status, step, progress_done, progress_total, attempts, result, error,
    created_at, started_at, heartbeat_at, finished_at
"""

_schema_ready = False


class JobNotFound(LookupError):
    pass


def ensure_schema(connection: psycopg.Connection) -> None:
    global _schema_ready
    if not _schema_ready:
        parcels_store.ensure_schema(connection)
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        _schema_ready = True


def _job(row: tuple) -> dict:
    (job_id, kind, parcel_id, status, step, done, total, attempts, result, error,
     created_at, started_at, heartbeat_at, finished_at) = row
    return {
        "id": job_id,
        "kind": kind,
        "parcel_id": parcel_id,
        "status": status,
        "step": step,
        "progress": {"done": done, "total": total},
        "attempts": attempts,
        "result": result,
        "error": error,
        "created_at": created_at.isoformat(),
        "started_at": started_at.isoformat() if started_at else None,
        "heartbeat_at": heartbeat_at.isoformat() if heartbeat_at else None,
        "finished_at": finished_at.isoformat() if finished_at else None,
    }


def enqueue(connection: psycopg.Connection, kind: str, parcel_id: int) -> tuple[dict, bool]:
    """Queue a job, unless the same kind is already queued or running for the parcel. Returns (job, created)."""
    row = connection.execute(
        f"""
        INSERT INTO platform.jobs (kind, parcel_id, step) VALUES (%s, %s, 'En cola')
        ON CONFLICT (kind, parcel_id) WHERE status IN ('queued', 'running') DO NOTHING
        RETURNING {_COLUMNS}
        """,
        [kind, parcel_id],
    ).fetchone()
    if row:
        return _job(row), True
    row = connection.execute(
        f"SELECT {_COLUMNS} FROM platform.jobs WHERE kind = %s AND parcel_id = %s AND status = ANY(%s) ORDER BY id DESC LIMIT 1",
        [kind, parcel_id, list(ACTIVE)],
    ).fetchone()
    return _job(row), False


def get_job(connection: psycopg.Connection, job_id: int) -> dict:
    row = connection.execute(f"SELECT {_COLUMNS} FROM platform.jobs WHERE id = %s", [job_id]).fetchone()
    if row is None:
        raise JobNotFound(job_id)
    return _job(row)


def parcel_jobs(connection: psycopg.Connection, parcel_id: int, limit: int) -> list[dict]:
    rows = connection.execute(
        f"SELECT {_COLUMNS} FROM platform.jobs WHERE parcel_id = %s ORDER BY id DESC LIMIT %s", [parcel_id, limit]
    ).fetchall()
    return [_job(row) for row in rows]


def claim_next(connection: psycopg.Connection) -> dict | None:
    """Take the oldest queued job; SKIP LOCKED lets several workers share the queue."""
    row = connection.execute(
        f"""
        UPDATE platform.jobs
        SET status = 'running', step = 'Empezando', attempts = attempts + 1,
            started_at = now(), heartbeat_at = now(), error = NULL
        WHERE id = (
            SELECT id FROM platform.jobs WHERE status = 'queued' ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1
        )
        RETURNING {_COLUMNS}
        """
    ).fetchone()
    return _job(row) if row else None


def report(connection: psycopg.Connection, job_id: int, step: str, done: int, total: int) -> None:
    connection.execute(
        """
        UPDATE platform.jobs SET step = %s, progress_done = %s, progress_total = %s, heartbeat_at = now()
        WHERE id = %s AND status = 'running'
        """,
        [step, done, total, job_id],
    )


def finish(connection: psycopg.Connection, job_id: int, result: dict) -> None:
    connection.execute(
        "UPDATE platform.jobs SET status = 'done', result = %s, finished_at = now(), heartbeat_at = now() WHERE id = %s",
        [Jsonb(result), job_id],
    )


def fail(connection: psycopg.Connection, job_id: int, error: str) -> None:
    connection.execute(
        "UPDATE platform.jobs SET status = 'failed', error = %s, finished_at = now(), heartbeat_at = now() WHERE id = %s",
        [error, job_id],
    )


def release(connection: psycopg.Connection, job_id: int, step: str) -> None:
    """Give a running job back to the queue (the worker is stopping)."""
    connection.execute("UPDATE platform.jobs SET status = 'queued', step = %s WHERE id = %s AND status = 'running'", [step, job_id])


def recover_stale(connection: psycopg.Connection, stale_seconds: int, max_attempts: int) -> int:
    """Running jobs without news for too long were cut (worker killed): queue them again, or fail them after max_attempts."""
    rows = connection.execute(
        """
        UPDATE platform.jobs
        SET status = CASE WHEN attempts >= %(max)s THEN 'failed' ELSE 'queued' END,
            step = CASE WHEN attempts >= %(max)s THEN step ELSE 'En cola de nuevo: se había cortado' END,
            error = CASE WHEN attempts >= %(max)s THEN 'Se cortó ' || attempts || ' veces sin terminar.' ELSE error END,
            finished_at = CASE WHEN attempts >= %(max)s THEN now() ELSE finished_at END
        WHERE status = 'running' AND heartbeat_at < now() - make_interval(secs => %(stale)s)
        RETURNING id
        """,
        {"max": max_attempts, "stale": stale_seconds},
    ).fetchall()
    return len(rows)
