import { useEffect } from "react";
import { formatDate, formatMonthLong, formatNumber } from "../../format.js";
import { STATUS_CLASS } from "./sheet.js";

const PLAY_INTERVAL_MS = 1200;

function sceneText(month) {
  if (!month.scene) return month.status_text;
  const clean = month.valid_share === null ? "" : ` · ${formatNumber(100 * month.valid_share)} % de la parcela limpia`;
  const status = month.status === "ok" ? "" : ` · ${month.status_text}`;
  return `Imagen del ${formatDate(month.scene.date)}${clean}${status}`;
}

export default function MonthTimeline({ months, selected, onSelect, playing, onPlaying }) {
  const index = months.findIndex((month) => month.month === selected);
  const current = months[index];
  const withScene = months.filter((month) => month.scene);

  useEffect(() => {
    if (!playing || withScene.length < 2) return undefined;
    const timer = setInterval(() => {
      onSelect((previous) => {
        const position = withScene.findIndex((month) => month.month === previous);
        return withScene[(position + 1) % withScene.length].month;
      });
    }, PLAY_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [playing, months]);

  const step = (delta) => months.length && onSelect(months[(index + delta + months.length) % months.length].month);
  const position = (offset) => (months.length > 1 ? (offset / (months.length - 1)) * 100 : 50);
  const campaignStarts = months
    .map((month, offset) => ({ month, offset }))
    .filter(({ month, offset }) => offset === 0 || month.campaign !== months[offset - 1].campaign);

  return (
    <section className="floating timeline parcel-timeline">
      <div className="timeline-head">
        <div className="timeline-buttons">
          <button className="icon-button" onClick={() => step(-1)} disabled={!months.length} title="Mes anterior">
            ‹
          </button>
          <button className="icon-button play" onClick={() => onPlaying(!playing)} disabled={withScene.length < 2} title="Reproducir los meses con imagen">
            {playing ? "❚❚" : "▶"}
          </button>
          <button className="icon-button" onClick={() => step(1)} disabled={!months.length} title="Mes siguiente">
            ›
          </button>
        </div>
        <div className="timeline-title">
          {current && (
            <>
              <strong>
                {formatMonthLong(current.month)} · campaña {current.campaign}
              </strong>
              <span className="muted">{sceneText(current)}</span>
            </>
          )}
        </div>
      </div>
      <div className="timeline-track">
        <div className="timeline-line">
          {months.map((month, offset) => (
            <button
              key={month.month}
              className={`timeline-dot ${STATUS_CLASS[month.status] ?? "cloud-unknown"} ${month.month === selected ? "selected" : ""}`}
              style={{ left: `${position(offset)}%` }}
              title={`${formatMonthLong(month.month)} · ${month.status_text}`}
              onClick={() => onSelect(month.month)}
            />
          ))}
          {campaignStarts.map(({ month, offset }) => (
            <span key={month.campaign} className="campaign-mark" style={{ left: `${position(offset)}%` }}>
              {month.campaign}
            </span>
          ))}
        </div>
      </div>
      <div className="timeline-key muted small">
        <span className="timeline-dot static cloud-low" /> con dato
        <span className="timeline-dot static cloud-mid" /> nublado
        <span className="timeline-dot static cloud-unknown" /> sin imagen útil
        <span className="timeline-dot static cloud-high" /> error de lectura
      </div>
    </section>
  );
}
