import { LABEL_CLASSES } from "./LabelTools.jsx";

const WIDTH = 600;
const HEIGHT = 270;
const MARGIN = { top: 10, right: 14, bottom: 28, left: 38 };
const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const TOP_SEPARATED = 3;

const toTime = (date) => new Date(`${date}T12:00:00Z`).getTime();

function monthStarts(first, last) {
  const ticks = [];
  const start = new Date(first);
  let cursor = Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 1);
  while (cursor <= last) {
    ticks.push({ time: cursor, label: MONTHS[new Date(cursor).getUTCMonth()] });
    const next = new Date(cursor);
    cursor = Date.UTC(next.getUTCFullYear(), next.getUTCMonth() + 1, 1);
  }
  return ticks;
}

function mostSeparated(summary) {
  const [first, second] = LABEL_CLASSES.map((item) => summary.classes[item.id]);
  if (!first || !second) return [];
  return summary.dates
    .map((date, index) => ({ date, gap: Math.abs(first.median[index] - second.median[index]) }))
    .sort((a, b) => b.gap - a.gap)
    .slice(0, TOP_SEPARATED);
}

export default function SeriesChart({ summary, onClose }) {
  if (!summary?.available) {
    return (
      <div className="series-chart">
        <button className="close" onClick={onClose}>Cerrar</button>
        <p className="hint">
          Falta la tabla de entrenamiento. Ejecutá: docker compose run --rm api python -m cultivos.build_tables
        </p>
      </div>
    );
  }

  const times = summary.dates.map(toTime);
  const first = times[0];
  const last = times[times.length - 1];
  const all = LABEL_CLASSES.flatMap((item) => {
    const data = summary.classes[item.id];
    return data ? [...data.p25, ...data.p75] : [];
  });
  const low = Math.floor(Math.min(...all) * 10) / 10;
  const high = Math.ceil(Math.max(...all) * 10) / 10;

  const x = (time) => MARGIN.left + ((time - first) / (last - first)) * (WIDTH - MARGIN.left - MARGIN.right);
  const y = (value) => MARGIN.top + ((high - value) / (high - low)) * (HEIGHT - MARGIN.top - MARGIN.bottom);
  const line = (values) => values.map((value, index) => `${x(times[index])},${y(value)}`);
  const grid = [];
  for (let value = low; value <= high + 1e-9; value += 0.1) grid.push(Math.round(value * 10) / 10);

  return (
    <div className="series-chart">
      <button className="close" onClick={onClose}>Cerrar</button>
      <h3>NDVI por fecha: entrenamiento</h3>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%">
        {grid.map((value) => (
          <g key={value}>
            <line x1={MARGIN.left} x2={WIDTH - MARGIN.right} y1={y(value)} y2={y(value)} style={{ stroke: "var(--grid)" }} />
            <text x={MARGIN.left - 6} y={y(value) + 4} textAnchor="end" fontSize="11" style={{ fill: "var(--muted)" }}>
              {value.toFixed(1)}
            </text>
          </g>
        ))}
        {monthStarts(first, last).map((tick) => (
          <g key={tick.time}>
            <line x1={x(tick.time)} x2={x(tick.time)} y1={MARGIN.top} y2={HEIGHT - MARGIN.bottom} style={{ stroke: "var(--grid)" }} />
            <text x={x(tick.time)} y={HEIGHT - 10} textAnchor="middle" fontSize="11" style={{ fill: "var(--muted)" }}>
              {tick.label}
            </text>
          </g>
        ))}
        {LABEL_CLASSES.map((item) => {
          const data = summary.classes[item.id];
          if (!data) return null;
          const band = [...line(data.p75), ...line(data.p25).reverse()].join(" ");
          return (
            <g key={item.id}>
              <polygon points={band} fill={item.color} opacity="0.18" />
              <polyline points={line(data.median).join(" ")} fill="none" stroke={item.color} strokeWidth="2" />
              {data.median.map((value, index) => (
                <circle key={summary.dates[index]} cx={x(times[index])} cy={y(value)} r="3" fill={item.color} />
              ))}
            </g>
          );
        })}
      </svg>
      <p className="hint">
        {LABEL_CLASSES.map((item) => {
          const data = summary.classes[item.id];
          return data ? (
            <span key={item.id}>
              <span className="swatch" style={{ background: item.color }} />
              {item.label}: {data.pixels} píxeles{"  "}
            </span>
          ) : null;
        })}
      </p>
      <p className="hint">Línea: mediana. Banda: del percentil 25 al 75 (la mitad central de los píxeles).</p>
      <p className="hint">
        Fechas con más diferencia entre medianas: {mostSeparated(summary).map((item) => `${item.date} (${item.gap.toFixed(2)})`).join(", ")}.
      </p>
    </div>
  );
}
