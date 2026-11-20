import { useEffect, useState } from "react";
import { getJson, sendJson } from "../api.js";
import { formatDateTime, formatNumber } from "../format.js";

const POLL_MS = 2000;
const ACTIVE = ["queued", "running"];

function summary(result) {
  const { total, by_status: byStatus } = result.months;
  const withData = byStatus.ok ?? 0;
  const parts = [`${formatNumber(withData)} de ${formatNumber(total)} meses con índices`];
  const cloudy = byStatus.cloudy ?? 0;
  const empty = (byStatus.no_scene ?? 0) + (byStatus.no_pixels ?? 0);
  if (cloudy) parts.push(`${formatNumber(cloudy)} nublados`);
  if (empty) parts.push(`${formatNumber(empty)} sin imagen útil`);
  if (byStatus.error) parts.push(`${formatNumber(byStatus.error)} con error de lectura (se reintentan)`);
  return `${parts.join(", ")}. Clima de ${formatNumber(result.climate.months)} meses.`;
}

function Progress({ job }) {
  const { done, total } = job.progress;
  const percent = total ? Math.round((100 * done) / total) : 0;
  return (
    <>
      <p className="hint">
        {job.status === "queued" ? "En cola: esperando al worker…" : `${job.step} · ${done} de ${total} pasos`}
      </p>
      <div className="progress">
        <span style={{ width: `${percent}%` }} />
      </div>
    </>
  );
}

export default function ProcessingStatus({ parcelId }) {
  const [job, setJob] = useState(undefined);
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);
  const active = job && ACTIVE.includes(job.status);

  useEffect(() => {
    getJson(`/parcels/${parcelId}/jobs`)
      .then((body) => setJob(body.jobs[0] ?? null))
      .catch((failure) => setError(failure.message));
  }, [parcelId]);

  useEffect(() => {
    if (!active) return undefined;
    const timer = setTimeout(() => {
      getJson(`/jobs/${job.id}`)
        .then(setJob)
        .catch((failure) => setError(failure.message));
    }, POLL_MS);
    return () => clearTimeout(timer);
  }, [job]);

  async function start() {
    setError(null);
    setSending(true);
    try {
      const body = await sendJson("POST", `/parcels/${parcelId}/process`, {});
      setJob(body.job);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <h3>Procesamiento</h3>
      {job === undefined && !error && <p className="hint">Consultando…</p>}
      {job === null && (
        <p className="hint">
          Sin procesar. Calcula los índices de cada mes de las últimas campañas y el clima de la parcela; tarda unos
          minutos la primera vez.
        </p>
      )}
      {active && <Progress job={job} />}
      {job?.status === "done" && (
        <>
          <p className="hint">Procesada el {formatDateTime(job.finished_at)}</p>
          <p>{summary(job.result)}</p>
          <div className="links">
            <a href={`/api/parcels/${parcelId}/series`} target="_blank" rel="noreferrer">
              Ver serie (JSON)
            </a>
            <a href={`/api/parcels/${parcelId}/climate`} target="_blank" rel="noreferrer">
              Ver clima (JSON)
            </a>
          </div>
        </>
      )}
      {job?.status === "failed" && <p className="warning">No terminó: {job.error}</p>}
      {error && <p className="warning">{error}</p>}
      {job !== undefined && !active && (
        <div className="buttons spaced">
          <button className="primary" onClick={start} disabled={sending}>
            {job === null ? "Procesar parcela" : job.status === "failed" ? "Reintentar" : "Volver a procesar"}
          </button>
        </div>
      )}
    </>
  );
}
