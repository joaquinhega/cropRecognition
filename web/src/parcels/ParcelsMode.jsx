import { useEffect, useRef, useState } from "react";
import { MapContainer, Polygon, ZoomControl, useMap } from "react-leaflet";
import L from "leaflet";
import { deleteResource, getJson, sendFile, sendJson } from "../api.js";
import { bboxToBounds, formatNumber, plural } from "../format.js";
import { PolygonDrawer } from "../LabelTools.jsx";
import BaseLayers, { MAX_ZOOM } from "../map/BaseLayers.jsx";
import { CursorPosition } from "../map/MapHelpers.jsx";
import ParcelDetails from "./ParcelDetails.jsx";
import ParcelList from "./ParcelList.jsx";
import UploadResult from "./UploadResult.jsx";

const PARCEL_COLOR = "#4cc38a";
const SMALL_PARCEL_COLOR = "#ff8a65";
const SELECTED_COLOR = "#f2b544";
const PENDING_STYLE = { color: "#ffffff", weight: 2, dashArray: "6 6", fillOpacity: 0.1 };

const toPositions = (geometry) => geometry.coordinates.map((ring) => ring.map(([lng, lat]) => [lat, lng]));

function toGeometry(points) {
  const ring = points.map(([lat, lng]) => [lng, lat]);
  return { type: "Polygon", coordinates: [[...ring, ring[0]]] };
}

function FocusParcels({ parcels, focus }) {
  const map = useMap();
  useEffect(() => {
    const shown = parcels.filter((parcel) => focus.ids.includes(parcel.id));
    if (!shown.length) return;
    const bounds = L.latLngBounds(shown.flatMap((parcel) => toPositions(parcel.geometry)[0]));
    map.fitBounds(bounds, { maxZoom: 17, paddingTopLeft: [320, 40], paddingBottomRight: [40, 40] });
  }, [focus.key]);
  return null;
}

export default function ParcelsMode({ zones, infoTarget, onLayerCount }) {
  const defaultZone = zones.zones.find((zone) => zone.id === zones.default_zone);
  const fileInput = useRef(null);
  const [collection, setCollection] = useState(null);
  const [error, setError] = useState(null);
  const [drawing, setDrawing] = useState(false);
  const [pending, setPending] = useState(null);
  const [pendingName, setPendingName] = useState("");
  const [saving, setSaving] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [focus, setFocus] = useState({ ids: [], key: 0 });

  const parcels = collection?.features ?? [];
  const limits = collection?.limits;
  const selected = parcels.find((parcel) => parcel.id === selectedId);

  const focusOn = (ids) => setFocus((current) => ({ ids, key: current.key + 1 }));

  async function reload() {
    const body = await getJson("/parcels");
    setCollection(body);
    return body.features;
  }

  useEffect(() => {
    onLayerCount(0);
    reload()
      .then((features) => focusOn(features.map((parcel) => parcel.id)))
      .catch((failure) => setError(failure.message));
  }, []);

  async function run(action) {
    setError(null);
    setSaving(true);
    try {
      return await action();
    } catch (failure) {
      setError(failure.message);
      return null;
    } finally {
      setSaving(false);
    }
  }

  function startDrawing() {
    setDrawing((current) => !current);
    setPending(null);
    setSelectedId(null);
    setUploadResult(null);
    setError(null);
  }

  function finishDrawing(points) {
    setPending(points);
    setPendingName(`Parcela ${parcels.length + 1}`);
  }

  async function savePending() {
    const parcel = await run(() => sendJson("POST", "/parcels", { name: pendingName, geometry: toGeometry(pending) }));
    if (!parcel) return;
    setPending(null);
    await reload();
    setSelectedId(parcel.id);
  }

  async function uploadFile(event) {
    const file = event.target.files[0];
    event.target.value = "";
    if (!file) return;
    setPending(null);
    setUploadResult(null);
    const result = await run(() => sendFile("/parcels/import", file));
    if (!result) return;
    setUploadResult(result);
    await reload();
    const ids = result.created.map((parcel) => parcel.id);
    setSelectedId(ids[0] ?? null);
    focusOn(ids);
  }

  async function rename(name) {
    if (await run(() => sendJson("PATCH", `/parcels/${selectedId}`, { name }))) await reload();
  }

  async function remove() {
    await run(() => deleteResource(`/parcels/${selectedId}`));
    setSelectedId(null);
    await reload().catch((failure) => setError(failure.message));
  }

  function select(id) {
    setSelectedId(id);
    focusOn([id]);
  }

  const totalHa = parcels.reduce((sum, parcel) => sum + parcel.properties.area_ha, 0);
  const headline = parcels.length
    ? `${plural(parcels.length, "parcela guardada", "parcelas guardadas")}, ${formatNumber(totalHa, 1)} ha en total.`
    : "Todavía no hay parcelas. Dibujá una en el mapa o subí un archivo.";

  return (
    <>
      <section className="floating panel labeling-panel">
        <h2>Mi parcela</h2>
        {!collection && !error && <p className="hint">Cargando parcelas…</p>}
        {collection && <p className="headline">{headline}</p>}

        <h3>Agregar</h3>
        <div className="buttons">
          <button className={drawing ? "active" : ""} onClick={startDrawing} disabled={saving || !collection}>
            {drawing ? "Cancelar dibujo" : "Dibujar parcela"}
          </button>
          <button onClick={() => fileInput.current.click()} disabled={saving || drawing || !collection}>
            Subir archivo (GeoJSON, KML o KMZ)
          </button>
        </div>
        <input
          ref={fileInput}
          className="hidden-input"
          type="file"
          accept={limits?.file_types.join(",")}
          onChange={uploadFile}
        />
        {drawing && <p className="hint">Clic para cada vértice. Para cerrar, clic en el primer punto. Esc cancela.</p>}

        {pending && (
          <>
            <h3>Nombre de la parcela</h3>
            <input
              className="text-input"
              value={pendingName}
              maxLength={limits?.name_max_length}
              autoFocus
              onChange={(event) => setPendingName(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && savePending()}
            />
            <div className="buttons spaced">
              <button className="primary" onClick={savePending} disabled={saving}>
                Guardar parcela
              </button>
              <button onClick={() => setPending(null)} disabled={saving}>
                Descartar dibujo
              </button>
            </div>
          </>
        )}

        {saving && <p className="hint">Guardando…</p>}
        {error && <p className="warning">{error}</p>}
        {uploadResult && <UploadResult result={uploadResult} />}

        {limits && (
          <p className="hint">
            Máximo {formatNumber(limits.max_area_ha)} ha por parcela. Las de menos de {formatNumber(limits.min_area_ha)} ha
            se guardan con aviso. No uses el nombre del titular ni de la finca.
          </p>
        )}

        {parcels.length > 0 && (
          <ParcelList parcels={parcels} selectedId={selectedId} disabled={drawing} onSelect={select} />
        )}
        {selected && !drawing && !pending && (
          <ParcelDetails
            key={selected.id}
            parcel={selected}
            limits={limits}
            saving={saving}
            onRename={rename}
            onDelete={remove}
          />
        )}
      </section>

      <MapContainer className="map" bounds={bboxToBounds(defaultZone.bbox)} maxZoom={MAX_ZOOM} zoomControl={false}>
        <BaseLayers defaultId="satellite" />
        <ZoomControl position="bottomright" />
        <CursorPosition target={infoTarget} />
        <FocusParcels parcels={parcels} focus={focus} />
        {parcels.map((parcel) => {
          const isSelected = parcel.id === selectedId;
          const color = isSelected
            ? SELECTED_COLOR
            : parcel.properties.below_minimum
              ? SMALL_PARCEL_COLOR
              : PARCEL_COLOR;
          return (
            <Polygon
              key={`${parcel.id}-${drawing}`}
              positions={toPositions(parcel.geometry)}
              interactive={!drawing}
              pathOptions={{ color, weight: isSelected ? 3 : 2, fillColor: color, fillOpacity: isSelected ? 0.3 : 0.15 }}
              eventHandlers={{ click: () => setSelectedId(parcel.id) }}
            />
          );
        })}
        {pending && <Polygon positions={pending} pathOptions={PENDING_STYLE} interactive={false} />}
        <PolygonDrawer
          drawing={drawing}
          color={PARCEL_COLOR}
          onCreated={finishDrawing}
          onFinish={() => setDrawing(false)}
        />
      </MapContainer>
    </>
  );
}
