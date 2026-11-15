const JSON_HEADERS = { "Content-Type": "application/json" };

async function request(path, options) {
  const response = await fetch(`/api${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Error ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

function toLabel(feature) {
  const properties = feature.properties;
  return {
    id: properties.id_lote,
    cls: properties.clase,
    points: feature.geometry.coordinates[0].slice(0, -1).map(([lng, lat]) => [lat, lng]),
    criterio: properties.criterio,
    confianza: properties.confianza,
    areaHa: properties.area_ha,
    small: properties.menor_al_minimo,
    imageDate: properties.imagen_referencia.fecha,
  };
}

export const fetchLabelOptions = () => request("/labels/options");

export async function fetchLabels() {
  const collection = await request("/labels");
  return collection.features.map(toLabel);
}

export async function createLabel({ cls, points, date }) {
  const feature = await request("/labels", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ clase: cls, vertices: points, fecha: date }),
  });
  return toLabel(feature);
}

export async function updateLabel(id, changes) {
  const feature = await request(`/labels/${id}`, {
    method: "PATCH",
    headers: JSON_HEADERS,
    body: JSON.stringify(changes),
  });
  return toLabel(feature);
}

export const deleteLabel = (id) => request(`/labels/${id}`, { method: "DELETE" });
