import { formatMonth, formatNumber } from "../../format.js";
import { campaignMonthLabels, campaignPosition, consecutiveRuns, formatIndex } from "./sheet.js";

const WIDTH = 420;
const HEIGHT = 200;
const MARGIN = { top: 10, right: 10, bottom: 22, left: 32 };
const SLOTS = 12;
const STEP = 0.1;

function campaignPoints(campaign, index, firstMonth) {
  return campaign.months
    .filter((month) => month.status === "ok" && month.indices?.[index])
    .map((month) => ({ month: month.month, position: campaignPosition(month.month, firstMonth), ...month.indices[index] }))
    .sort((a, b) => a.position - b.position);
}

export default function IndexChart({ series, index, colors, selectedMonth, onSelectMonth }) {
  const firstMonth = series.campaign_first_month;
  const lines = series.campaigns.map((campaign) => ({
    campaign: campaign.campaign,
    points: campaignPoints(campaign, index, firstMonth),
  }));
  const values = lines.flatMap((line) => line.points.flatMap((point) => [point.p25, point.p75, point.mean]));
  if (!values.length) return <p className="hint">Ningún mes tiene dato de este índice todavía.</p>;

  const low = Math.floor(Math.min(...values) / STEP) * STEP;
  const high = Math.max(Math.ceil(Math.max(...values) / STEP) * STEP, low + STEP);
  const slot = (WIDTH - MARGIN.left - MARGIN.right) / SLOTS;
  const x = (position) => MARGIN.left + (position + 0.5) * slot;
  const y = (value) => MARGIN.top + ((high - value) / (high - low)) * (HEIGHT - MARGIN.top - MARGIN.bottom);
  const grid = [];
  for (let value = low; value <= high + 1e-9; value += STEP) grid.push(Math.round(value * 10) / 10);

  const selectedCampaign = series.campaigns.find((campaign) => campaign.months.some((month) => month.month === selectedMonth));
  const bandLine = lines.find((line) => line.campaign === selectedCampaign?.campaign) ?? lines[lines.length - 1];
  const current = lines[lines.length - 1].campaign;

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="chart sheet-chart">
      {grid.map((value) => (
        <g key={value}>
          <line x1={MARGIN.left} x2={WIDTH - MARGIN.right} y1={y(value)} y2={y(value)} className="grid-line" />
          <text x={MARGIN.left - 5} y={y(value) + 3} textAnchor="end" className="axis">
            {formatNumber(value, 1)}
          </text>
        </g>
      ))}
      {campaignMonthLabels(firstMonth).map((label, position) => (
        <text key={label} x={x(position)} y={HEIGHT - 6} textAnchor="middle" className="axis">
          {label}
        </text>
      ))}
      {selectedMonth && (
        <line
          x1={x(campaignPosition(selectedMonth, firstMonth))}
          x2={x(campaignPosition(selectedMonth, firstMonth))}
          y1={MARGIN.top}
          y2={HEIGHT - MARGIN.bottom}
          className="selected-month"
        />
      )}
      {consecutiveRuns(bandLine.points).map((run) => (
        <polygon
          key={run[0].month}
          points={[...run.map((point) => `${x(point.position)},${y(point.p75)}`), ...run.map((point) => `${x(point.position)},${y(point.p25)}`).reverse()].join(" ")}
          fill={colors[bandLine.campaign]}
          opacity="0.16"
        />
      ))}
      {lines.map((line) => {
        const isCurrent = line.campaign === current;
        return (
          <g key={line.campaign} opacity={isCurrent ? 1 : 0.85}>
            {consecutiveRuns(line.points).map((run) => (
              <polyline
                key={run[0].month}
                points={run.map((point) => `${x(point.position)},${y(point.mean)}`).join(" ")}
                fill="none"
                stroke={colors[line.campaign]}
                strokeWidth={isCurrent ? 2.5 : 1.5}
              />
            ))}
            {line.points.map((point) => (
              <circle
                key={point.month}
                cx={x(point.position)}
                cy={y(point.mean)}
                r={point.month === selectedMonth ? 5 : isCurrent ? 3.5 : 2.5}
                fill={colors[line.campaign]}
                className={`chart-point ${point.month === selectedMonth ? "selected" : ""}`}
                onClick={() => onSelectMonth(point.month)}
              >
                <title>
                  {`${formatMonth(point.month)} · ${formatIndex(point.mean)} (rango ${formatIndex(point.p25)} a ${formatIndex(point.p75)})`}
                </title>
              </circle>
            ))}
          </g>
        );
      })}
    </svg>
  );
}
