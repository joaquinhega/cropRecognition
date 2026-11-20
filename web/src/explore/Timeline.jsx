import { useEffect } from "react";
import { cloudClass, formatDate, formatNumber, plural } from "../format.js";

const PLAY_INTERVAL_MS = 1200;

const toTime = (date) => new Date(`${date}T12:00:00Z`).getTime();

export default function Timeline({ period, dates, selected, onSelect, playing, onPlaying }) {
  const index = dates.findIndex((entry) => entry.date === selected);
  const current = dates[index];

  useEffect(() => {
    if (!playing || dates.length < 2) return undefined;
    const timer = setInterval(() => {
      onSelect((previous) => {
        const position = dates.findIndex((entry) => entry.date === previous);
        return dates[(position + 1) % dates.length].date;
      });
    }, PLAY_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [playing, dates]);

  const start = toTime(period.start);
  const span = Math.max(toTime(period.end) - start, 1);
  const step = (delta) => dates.length && onSelect(dates[(index + delta + dates.length) % dates.length].date);

  return (
    <section className="floating timeline">
      <div className="timeline-head">
        <div className="timeline-buttons">
          <button className="icon-button" onClick={() => step(-1)} disabled={!dates.length} title="Fecha anterior">
            ‹
          </button>
          <button className="icon-button play" onClick={() => onPlaying(!playing)} disabled={dates.length < 2} title="Reproducir">
            {playing ? "❚❚" : "▶"}
          </button>
          <button className="icon-button" onClick={() => step(1)} disabled={!dates.length} title="Fecha siguiente">
            ›
          </button>
        </div>
        <div className="timeline-title">
          {current ? (
            <>
              <strong>{formatDate(current.date, "long")}</strong>
              <span className="muted">
                {current.cloud === null ? "nubes sin dato" : `${formatNumber(current.cloud, 1)} % de nubes`}
                {current.items.length > 1 ? ` · ${current.items.length} escenas` : ""}
              </span>
            </>
          ) : (
            <span className="muted">No hay imágenes en el catálogo para este período. Probá “Buscar en las fuentes”.</span>
          )}
        </div>
        <div className="muted small">{plural(dates.length, "fecha", "fechas")}</div>
      </div>
      <div className="timeline-track">
        <span className="timeline-edge">{formatDate(period.start)}</span>
        <div className="timeline-line">
          {dates.map((entry) => (
            <button
              key={entry.date}
              className={`timeline-dot ${cloudClass(entry.cloud)} ${entry.date === selected ? "selected" : ""}`}
              style={{ left: `${((toTime(entry.date) - start) / span) * 100}%` }}
              title={`${formatDate(entry.date)} · ${entry.cloud === null ? "sin dato" : `${formatNumber(entry.cloud, 1)} %`} de nubes`}
              onClick={() => onSelect(entry.date)}
            />
          ))}
        </div>
        <span className="timeline-edge">{formatDate(period.end)}</span>
      </div>
      <div className="timeline-key muted small">
        <span className="timeline-dot static cloud-low" /> menos de 10 % de nubes
        <span className="timeline-dot static cloud-mid" /> 10 a 40 %
        <span className="timeline-dot static cloud-high" /> más de 40 %
      </div>
    </section>
  );
}
