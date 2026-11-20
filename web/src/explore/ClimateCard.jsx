import { formatMonth, formatNumber } from "../format.js";

const WIDTH = 300;
const HEIGHT = 150;
const MARGIN = { top: 12, right: 30, bottom: 22, left: 30 };
const DAILY_LIMIT_DAYS = 62;
const RAIN = "PRECTOTCORR";
const TEMPERATURE = "T2M";

function scale(domain, range) {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  return (value) => r0 + ((value - d0) / (d1 - d0 || 1)) * (r1 - r0);
}

function Chart({ rows, labelOf }) {
  const rain = rows.map((row) => row[RAIN] ?? 0);
  const temps = rows.map((row) => row[TEMPERATURE]).filter((value) => value !== null);
  const x = (index) => MARGIN.left + (index + 0.5) * ((WIDTH - MARGIN.left - MARGIN.right) / rows.length);
  const barWidth = Math.max(((WIDTH - MARGIN.left - MARGIN.right) / rows.length) * 0.7, 1);
  const yRain = scale([0, Math.max(...rain, 1)], [HEIGHT - MARGIN.bottom, MARGIN.top]);
  const yTemp = scale([Math.min(...temps, 0), Math.max(...temps, 1)], [HEIGHT - MARGIN.bottom, MARGIN.top]);
  const line = rows
    .map((row, index) => (row[TEMPERATURE] === null ? null : `${x(index)},${yTemp(row[TEMPERATURE])}`))
    .filter(Boolean)
    .join(" ");
  const labelEvery = Math.ceil(rows.length / 6);

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="chart">
      {rows.map((row, index) => (
        <rect
          key={index}
          x={x(index) - barWidth / 2}
          y={yRain(row[RAIN] ?? 0)}
          width={barWidth}
          height={HEIGHT - MARGIN.bottom - yRain(row[RAIN] ?? 0)}
          className="bar-rain"
        />
      ))}
      <polyline points={line} className="line-temp" />
      {rows.map((row, index) =>
        index % labelEvery === 0 ? (
          <text key={index} x={x(index)} y={HEIGHT - 6} textAnchor="middle" className="axis">
            {labelOf(row)}
          </text>
        ) : null,
      )}
      <text x={4} y={MARGIN.top} className="axis rain">
        {formatNumber(Math.max(...rain, 0))} mm
      </text>
      <text x={WIDTH - 2} y={MARGIN.top} textAnchor="end" className="axis temp">
        {formatNumber(Math.max(...temps, 0))} °C
      </text>
    </svg>
  );
}

export default function ClimateCard({ climate, loading, error, onLoad, collapsed, onCollapse }) {
  const daily = climate && climate.daily.length <= DAILY_LIMIT_DAYS;
  const rows = climate ? (daily ? climate.daily : climate.monthly) : [];
  const totalRain = rows.reduce((sum, row) => sum + (row[RAIN] ?? 0), 0);
  const temps = climate ? climate.daily.map((row) => row[TEMPERATURE]).filter((value) => value !== null) : [];
  const meanTemp = temps.length ? temps.reduce((sum, value) => sum + value, 0) / temps.length : null;

  return (
    <section className={`floating panel climate-card ${collapsed ? "collapsed" : ""}`}>
      <header className="panel-header">
        <h2>Clima</h2>
        <button className="icon-button" onClick={onCollapse} title={collapsed ? "Mostrar" : "Plegar"}>
          {collapsed ? "+" : "−"}
        </button>
      </header>
      {!collapsed && (
        <>
          {climate && (
            <>
              <p className="headline">
                {formatNumber(totalRain)} mm de lluvia
                {meanTemp !== null && ` y ${formatNumber(meanTemp, 1)} °C de media`} en el período.
              </p>
              <Chart rows={rows} labelOf={(row) => (daily ? row.date.slice(8, 10) : formatMonth(row.month))} />
              <p className="hint">
                <span className="swatch rain" /> Lluvia {daily ? "por día" : "por mes"} · <span className="swatch temp" />{" "}
                Temperatura media
              </p>
              <div className="source-tag">
                {climate.source.name} · {climate.source.resolution}
              </div>
              <p className="hint">
                <strong>Límite:</strong> {climate.source.limits}
              </p>
            </>
          )}
          {error && <p className="warning">{error}</p>}
          <div className="buttons spaced">
            <button onClick={onLoad} disabled={loading}>
              {loading ? "Consultando…" : climate ? "Actualizar clima" : "Consultar clima del período"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
