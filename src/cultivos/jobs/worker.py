"""Worker: takes jobs from the queue and runs them. It is the `worker` service of docker compose."""

import signal
import time
import traceback

from psycopg import errors as pg_errors

from cultivos.adapters.base import SourceError
from cultivos.catalog import db
from cultivos.catalog.db import CatalogUnavailable
from cultivos.config import load_processing_config
from cultivos.jobs import store
from cultivos.modules import processing
from cultivos.parcels.store import ParcelNotFound

RUNNERS = {processing.KIND: processing.run}


class WorkerStopping(BaseException):
    """Raised by the stop signal; BaseException so that no task code swallows it."""


def _stop(signum, frame) -> None:
    raise WorkerStopping()


def error_text(error: Exception) -> str:
    if isinstance(error, ParcelNotFound):
        return "La parcela ya no existe."
    if isinstance(error, pg_errors.ForeignKeyViolation):
        return "La parcela se borró durante el procesamiento."
    if isinstance(error, (SourceError, CatalogUnavailable)):
        return str(error)
    return f"Error inesperado ({type(error).__name__}): {error}"


def run_job(connection, job: dict) -> None:
    job_id = job["id"]
    runner = RUNNERS.get(job["kind"])
    if runner is None:
        store.fail(connection, job_id, f"Tipo de tarea desconocido: {job['kind']}.")
        return

    def progress(step: str, done: int, total: int) -> None:
        store.report(connection, job_id, step, done, total)
        print(f"[tarea {job_id}] {done}/{total} {step}", flush=True)

    print(f"[tarea {job_id}] {job['kind']} de la parcela {job['parcel_id']} (intento {job['attempts']})", flush=True)
    try:
        result = runner(job["parcel_id"], progress)
    except WorkerStopping:
        store.release(connection, job_id, "En cola: el worker se reinició")
        print(f"[tarea {job_id}] devuelta a la cola", flush=True)
        raise
    except Exception as error:
        traceback.print_exc()
        message = error_text(error)
        store.fail(connection, job_id, message)
        print(f"[tarea {job_id}] falló: {message}", flush=True)
        return
    store.finish(connection, job_id, result)
    print(f"[tarea {job_id}] terminada", flush=True)


def run_once() -> bool:
    """Recover cut jobs, then run the next queued job if there is one. Returns whether a job ran."""
    config = load_processing_config()["worker"]
    with db.connect() as connection:
        store.ensure_schema(connection)
        recovered = store.recover_stale(connection, config["stale_seconds"], config["max_attempts"])
        if recovered:
            print(f"{recovered} tarea(s) cortada(s) vuelven a la cola o se marcan fallidas", flush=True)
        job = store.claim_next(connection)
        if job is None:
            return False
        run_job(connection, job)
    return True


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    poll_seconds = load_processing_config()["worker"]["poll_seconds"]
    print("Worker listo: esperando tareas", flush=True)
    try:
        while True:
            try:
                ran = run_once()
            except CatalogUnavailable as error:
                print(f"{error}. Reintento en {poll_seconds} s", flush=True)
                ran = False
            if not ran:
                time.sleep(poll_seconds)
    except WorkerStopping:
        print("Worker detenido", flush=True)


if __name__ == "__main__":
    main()
