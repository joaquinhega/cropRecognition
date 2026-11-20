const UTC = { timeZone: "UTC" };

export function formatDate(date, month = "short") {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString("es-AR", { ...UTC, day: "numeric", month, year: "numeric" });
}

export function formatDateTime(iso) {
  return new Date(iso).toLocaleString("es-AR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function formatMonth(month) {
  return new Date(`${month}-15T12:00:00Z`).toLocaleDateString("es-AR", { ...UTC, month: "short", year: "2-digit" });
}

export function formatMonthLong(month) {
  return new Date(`${month}-15T12:00:00Z`).toLocaleDateString("es-AR", { ...UTC, month: "long", year: "numeric" });
}

export function monthName(month) {
  return new Date(`${month}-15T12:00:00Z`).toLocaleDateString("es-AR", { ...UTC, month: "long" });
}

export function formatNumber(value, digits = 0) {
  return value.toLocaleString("es-AR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function isoDaysAgo(days, from = new Date()) {
  const date = new Date(from);
  date.setUTCDate(date.getUTCDate() - days);
  return date.toISOString().slice(0, 10);
}

export const todayIso = () => new Date().toISOString().slice(0, 10);

export function bboxToBounds([west, south, east, north]) {
  return [
    [south, west],
    [north, east],
  ];
}

export const CLEAN_CLOUD_PERCENT = 10;

export function cloudClass(cloud) {
  if (cloud === null || cloud === undefined) return "cloud-unknown";
  if (cloud < CLEAN_CLOUD_PERCENT) return "cloud-low";
  if (cloud < 40) return "cloud-mid";
  return "cloud-high";
}

export const plural = (count, one, many) => `${formatNumber(count)} ${count === 1 ? one : many}`;
