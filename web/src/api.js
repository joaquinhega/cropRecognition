function cleanParams(params = {}) {
  return Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "");
}

export async function getJson(path, params) {
  const entries = cleanParams(params);
  const query = entries.length ? `?${new URLSearchParams(entries)}` : "";
  const response = await fetch(`/api${path}${query}`);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof body.detail === "string" ? body.detail : `Error ${response.status}`);
  }
  return body;
}

export function areaParams(area) {
  return area.id ? { zone: area.id } : { bbox: area.bbox.join(",") };
}
