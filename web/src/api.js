function cleanParams(params = {}) {
  return Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "");
}

function withQuery(path, params) {
  const entries = cleanParams(params);
  return entries.length ? `${path}?${new URLSearchParams(entries)}` : path;
}

async function request(path, options) {
  const response = await fetch(`/api${path}`, options);
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof body.detail === "string" ? body.detail : `Error ${response.status}`);
  }
  return body;
}

export function getJson(path, params) {
  return request(withQuery(path, params));
}

export function sendJson(method, path, data) {
  return request(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
}

export function sendFile(path, file) {
  return request(withQuery(path, { filename: file.name }), {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: file,
  });
}

export function deleteResource(path) {
  return request(path, { method: "DELETE" });
}

export function areaParams(area) {
  return area.id ? { zone: area.id } : { bbox: area.bbox.join(",") };
}
