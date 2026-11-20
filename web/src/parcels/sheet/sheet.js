import { useEffect, useState } from "react";
import { getJson } from "../../api.js";
import { formatNumber } from "../../format.js";

const MONTHS_PER_YEAR = 12;
const MONTH_LABELS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const OLDER_COLORS = ["#4aa3df", "#9b8ac9", "#6b7a8f", "#d08cc0"];
export const CURRENT_COLOR = "#4cc38a";

export const STATUS_CLASS = { ok: "cloud-low", cloudy: "cloud-mid", error: "cloud-high" };

const LOADING = { loading: true };

/** Series and climate of a parcel; while another parcel's data is still in memory it reports loading. */
export function useParcelSheet(parcelId, version) {
  const [state, setState] = useState({ parcelId: null });
  useEffect(() => {
    if (!parcelId) return undefined;
    let alive = true;
    Promise.all([getJson(`/parcels/${parcelId}/series`), getJson(`/parcels/${parcelId}/climate`)])
      .then(([series, climate]) => alive && setState({ parcelId, series, climate }))
      .catch((failure) => alive && setState({ parcelId, error: failure.message }));
    return () => {
      alive = false;
    };
  }, [parcelId, version]);
  return parcelId && state.parcelId === parcelId ? state : LOADING;
}

/** Colors by campaign, oldest first; the campaign in progress always gets the accent color. */
export function campaignColors(labels) {
  const older = labels.slice(0, -1);
  const colors = Object.fromEntries(older.map((label, index) => [label, OLDER_COLORS[(older.length - 1 - index) % OLDER_COLORS.length]]));
  if (labels.length) colors[labels[labels.length - 1]] = CURRENT_COLOR;
  return colors;
}

/** Position of a month (YYYY-MM) inside its campaign: 0 for the first month, 11 for the last. */
export function campaignPosition(month, firstMonth) {
  return (Number(month.slice(5, 7)) - firstMonth + MONTHS_PER_YEAR) % MONTHS_PER_YEAR;
}

export function campaignMonthLabels(firstMonth) {
  return Array.from({ length: MONTHS_PER_YEAR }, (_, offset) => MONTH_LABELS[(firstMonth - 1 + offset) % MONTHS_PER_YEAR]);
}

export const flattenMonths = (series) =>
  series.campaigns.flatMap((campaign) => campaign.months.map((month) => ({ ...month, campaign: campaign.campaign })));

export function defaultMonth(series) {
  const months = flattenMonths(series);
  const withScene = months.filter((month) => month.scene);
  return series.comparison?.NDVI?.month ?? withScene[withScene.length - 1]?.month ?? months[months.length - 1]?.month ?? null;
}

export const formatIndex = (value) => formatNumber(value, 2);

export function lowerFirst(text) {
  return text.charAt(0).toLowerCase() + text.slice(1);
}

/** Split a list of {position, ...} points into runs of consecutive positions, to draw lines with gaps. */
export function consecutiveRuns(points) {
  const runs = [];
  points.forEach((point) => {
    const run = runs[runs.length - 1];
    if (run && point.position === run[run.length - 1].position + 1) run.push(point);
    else runs.push([point]);
  });
  return runs;
}
