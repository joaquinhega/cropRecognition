import SourceTag from "../../SourceTag.jsx";
import { formatMonth, formatNumber, monthName } from "../../format.js";
import { campaignMonthLabels, campaignPosition } from "./sheet.js";

const WIDTH = 420;
const HEIGHT = 130;
const MARGIN = { top: 10, right: 10, bottom: 22, left: 32 };
const SLOTS = 12;
const BAR_SHARE = 0.8;
const RAIN = "PRECTOTCORR";
const TEMPERATURE = "T2M";

function Frame({ firstMonth, ticks, y, selectedPosition, x, children }) {
  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="chart sheet-chart">
      {ticks.map((value) => (
        <g key={value}>
          <line x1={MARGIN.left} x2={WIDTH - MARGIN.right} y1={y(value)} y2={y(value)} className="grid-line" />
          <text x={MARGIN.left - 5} y={y(value) + 3} textAnchor="end" className="axis">
            {formatNumber(value)}
          </text>
        </g>
      ))}
      {campaignMonthLabels(firstMonth).map((label, position) => (
        <text key={label} x={x(position)} y={HEIGHT - 6} textAnchor="middle" className="axis">
          {label}
        </text>
      ))}
      {selectedPosition !== null && (
        <line x1={x(selectedPosition)} x2={x(selectedPosition)} y1={MARGIN.top} y2={HEIGHT - MARGIN.bottom} className="selected-month" />
      )}
      {children}
    </svg>
  );
}

const TICK_STEPS = [1, 2, 5, 10, 20, 50, 100, 200, 500];
const MAX_TICKS = 4;

function ticksFor(low, high) {
  const span = high - low || 1;
  const step = TICK_STEPS.find((candidate) => span / candidate <= MAX_TICKS) ?? TICK_STEPS[TICK_STEPS.length - 1];
  const start = Math.floor(low / step) * step;
  const end = Math.max(Math.ceil(high / step) * step, start + step);
  const ticks = [];
  for (let value = start; value <= end + 1e-9; value += step) ticks.push(value);
  return { ticks, low: start, high: end };
}

/** Rain of the campaign in progress so far against the same months of the earlier campaigns. */
function rainSoFar(campaigns) {
  const current = campaigns[campaigns.length - 1];
  const keys = current.months.filter((month) => month[RAIN] !== null).map((month) => month.month.slice(5));
  if (!keys.length) return null;
  const total = (campaign) => {
    const months = campaign.months.filter((month) => keys.includes(month.month.slice(5)) && month[RAIN] !== null);
    return months.length === keys.length ? months.reduce((sum, month) => sum + month[RAIN], 0) : null;
  };
  const earlier = campaigns.slice(0, -1).map(total).filter((value) => value !== null);
  const first = current.months[0].month;
  const last = current.months[current.months.length - 1].month;
  return {
    campaign: current.campaign,
    period: first === last ? monthName(first) : `${monthName(first)} a ${monthName(last)}`,
    value: total(current),
    average: earlier.length ? earlier.reduce((sum, value) => sum + value, 0) / earlier.length : null,
    count: earlier.length,
  };
}

export default function CampaignClimate({ climate, firstMonth, colors, selectedMonth }) {
  const campaigns = climate.campaigns;
  if (!campaigns.length) return <p className="hint">Sin clima todavía: procesá la parcela.</p>;

  const slot = (WIDTH - MARGIN.left - MARGIN.right) / SLOTS;
  const x = (position) => MARGIN.left + (position + 0.5) * slot;
  const selectedPosition = selectedMonth ? campaignPosition(selectedMonth, firstMonth) : null;
  const months = campaigns.flatMap((campaign) => campaign.months.map((month) => ({ ...month, campaign: campaign.campaign })));

  const rainValues = months.map((month) => month[RAIN]).filter((value) => value !== null);
  const rainScale = ticksFor(0, Math.max(...rainValues, 1));
  const yRain = (value) => MARGIN.top + ((rainScale.high - value) / (rainScale.high - rainScale.low)) * (HEIGHT - MARGIN.top - MARGIN.bottom);
  const barWidth = (slot * BAR_SHARE) / campaigns.length;

  const temps = months.map((month) => month[TEMPERATURE]).filter((value) => value !== null);
  const tempScale = temps.length ? ticksFor(Math.min(...temps), Math.max(...temps)) : ticksFor(0, 1);
  const yTemp = (value) => MARGIN.top + ((tempScale.high - value) / (tempScale.high - tempScale.low)) * (HEIGHT - MARGIN.top - MARGIN.bottom);

  const rain = rainSoFar(campaigns);
  const units = climate.parameters;

  return (
    <>
      {rain && rain.value !== null && (
        <p>
          Lluvia de {rain.period}: {formatNumber(rain.value)} mm en {rain.campaign}
          {rain.average !== null &&
            `; promedio de ${rain.count === 1 ? "la campaña anterior" : `las ${rain.count} anteriores`} en los mismos meses: ${formatNumber(rain.average)} mm`}
          .
        </p>
      )}

      <div className="chart-title">
        {units[RAIN].title} ({units[RAIN].monthly_unit ?? units[RAIN].unit})
      </div>
      <Frame firstMonth={firstMonth} ticks={rainScale.ticks} y={yRain} x={x} selectedPosition={selectedPosition}>
        {campaigns.map((campaign, campaignIndex) =>
          campaign.months
            .filter((month) => month[RAIN] !== null)
            .map((month) => {
              const left = x(campaignPosition(month.month, firstMonth)) - (slot * BAR_SHARE) / 2 + campaignIndex * barWidth;
              return (
                <rect
                  key={month.month}
                  x={left}
                  y={yRain(month[RAIN])}
                  width={Math.max(barWidth - 0.5, 0.5)}
                  height={yRain(0) - yRain(month[RAIN])}
                  fill={colors[campaign.campaign]}
                >
                  <title>{`${formatMonth(month.month)} · ${formatNumber(month[RAIN])} mm`}</title>
                </rect>
              );
            }),
        )}
      </Frame>

      <div className="chart-title">
        {units[TEMPERATURE].title} ({units[TEMPERATURE].unit})
      </div>
      <Frame firstMonth={firstMonth} ticks={tempScale.ticks} y={yTemp} x={x} selectedPosition={selectedPosition}>
        {campaigns.map((campaign, campaignIndex) => {
          const points = campaign.months
            .filter((month) => month[TEMPERATURE] !== null)
            .map((month) => ({ month: month.month, cx: x(campaignPosition(month.month, firstMonth)), cy: yTemp(month[TEMPERATURE]), value: month[TEMPERATURE] }))
            .sort((a, b) => a.cx - b.cx);
          const isCurrent = campaignIndex === campaigns.length - 1;
          return (
            <g key={campaign.campaign}>
              <polyline
                points={points.map((point) => `${point.cx},${point.cy}`).join(" ")}
                fill="none"
                stroke={colors[campaign.campaign]}
                strokeWidth={isCurrent ? 2.5 : 1.5}
              />
              {points.map((point) => (
                <circle key={point.month} cx={point.cx} cy={point.cy} r={isCurrent ? 3 : 2} fill={colors[campaign.campaign]}>
                  <title>{`${formatMonth(point.month)} · ${formatNumber(point.value, 1)} °C`}</title>
                </circle>
              ))}
            </g>
          );
        })}
      </Frame>

      <SourceTag collection={{ title: climate.source.collection, resolution: climate.source.resolution, source: "nasa-power" }} />
      <p className="warning small">{climate.source.limits}</p>
      <p className="hint small">{climate.source.attribution}.</p>
    </>
  );
}
