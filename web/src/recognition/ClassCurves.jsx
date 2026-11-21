import { formatMonth } from "../format.js";

const WIDTH = 600;
const HEIGHT = 260;
const MARGIN = { top: 10, right: 14, bottom: 28, left: 38 };
const GRID_STEP = 0.1;

function segments(values, point) {
  const result = [];
  let current = [];
  values.forEach((value, index) => {
    if (value === null) {
      if (current.length) result.push(current);
      current = [];
    } else {
      current.push(point(index, value));
    }
  });
  if (current.length) result.push(current);
  return result;
}

export default function ClassCurves({ curves, classes, indexTitle }) {
  const months = curves.months;
  const entries = Object.entries(curves.classes);
  const all = entries.flatMap(([, data]) => [...data.p25, ...data.p75]).filter((value) => value !== null);
  if (!all.length) return <p className="hint">Todavía no hay meses con dato para graficar.</p>;

  const low = Math.floor(Math.min(...all) / GRID_STEP) * GRID_STEP;
  const high = Math.ceil(Math.max(...all) / GRID_STEP) * GRID_STEP;
  const x = (index) => MARGIN.left + (index / Math.max(months.length - 1, 1)) * (WIDTH - MARGIN.left - MARGIN.right);
  const y = (value) => MARGIN.top + ((high - value) / (high - low || 1)) * (HEIGHT - MARGIN.top - MARGIN.bottom);
  const grid = [];
  for (let value = low; value <= high + 1e-9; value += GRID_STEP) grid.push(Math.round(value * 10) / 10);

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" role="img" aria-label={`${indexTitle} por mes y clase`}>
      {grid.map((value) => (
        <g key={value}>
          <line x1={MARGIN.left} x2={WIDTH - MARGIN.right} y1={y(value)} y2={y(value)} style={{ stroke: "var(--grid)" }} />
          <text x={MARGIN.left - 6} y={y(value) + 4} textAnchor="end" fontSize="11" style={{ fill: "var(--muted)" }}>
            {value.toFixed(1)}
          </text>
        </g>
      ))}
      {months.map((month, index) => (
        <text key={month} x={x(index)} y={HEIGHT - 10} textAnchor="middle" fontSize="11" style={{ fill: "var(--muted)" }}>
          {formatMonth(month)}
        </text>
      ))}
      {entries.map(([name, data]) => {
        const color = classes[name].color;
        const bands = segments(
          data.p25.map((value, index) => (value === null || data.p75[index] === null ? null : index)),
          (index) => index,
        );
        return (
          <g key={name}>
            {bands.map((indices) => (
              <polygon
                key={`band-${indices[0]}`}
                points={[
                  ...indices.map((index) => `${x(index)},${y(data.p75[index])}`),
                  ...[...indices].reverse().map((index) => `${x(index)},${y(data.p25[index])}`),
                ].join(" ")}
                fill={color}
                opacity="0.15"
              />
            ))}
            {segments(data.median, (index, value) => `${x(index)},${y(value)}`).map((points) => (
              <polyline key={`line-${points[0]}`} points={points.join(" ")} fill="none" stroke={color} strokeWidth="2" />
            ))}
            {data.median.map((value, index) =>
              value === null ? null : <circle key={months[index]} cx={x(index)} cy={y(value)} r="3" fill={color} />,
            )}
          </g>
        );
      })}
    </svg>
  );
}
