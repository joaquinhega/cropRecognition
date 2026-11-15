import { useEffect, useRef, useState } from "react";
import { GeoJSON, ImageOverlay, LayersControl, MapContainer, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { LABEL_CLASSES, LabelPolygons, PolygonDrawer, classColor } from "./LabelTools.jsx";

const BOUNDARY_STYLE = { color: "#b03a2e", weight: 2, fillOpacity: 0.08 };
const BOUNDARY_ATTRIBUTION = "Límite: IGN vía datos.gob.ar (CC BY 4.0)";
const STREETS_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const STREETS_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
const SATELLITE_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const SATELLITE_ATTRIBUTION =
  "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community";
const MAX_ZOOM = 20;
const SATELLITE_NATIVE_ZOOM = 18;
const DEFAULT_OPACITY = 0.8;
const LAYER_OPTIONS = [
  { id: "rgb", label: "Color real" },
  { id: "ndvi", label: "Verdor (NDVI)" },
];

function formatDate(date) {
  return new Date(`${date}T12:00:00`).toLocaleDateString("es-AR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default function App() {
  const [apiStatus, setApiStatus] = useState("verificando...");
  const [imagery, setImagery] = useState(null);
  const [boundary, setBoundary] = useState(null);
  const [error, setError] = useState(null);
  const [date, setDate] = useState(null);
  const [layer, setLayer] = useState("rgb");
  const [opacity, setOpacity] = useState(DEFAULT_OPACITY);
  const [labeling, setLabeling] = useState(false);
  const [drawing, setDrawing] = useState(false);
  const [labels, setLabels] = useState([]);
  const [activeClass, setActiveClass] = useState(LABEL_CLASSES[0].id);
  const [selectedId, setSelectedId] = useState(null);
  const nextLabelId = useRef(1);

  function addLabel(points) {
    const id = nextLabelId.current++;
    setLabels((current) => [...current, { id, cls: activeClass, points }]);
    setSelectedId(id);
  }

  function changeSelectedClass(cls) {
    setLabels((current) => current.map((label) => (label.id === selectedId ? { ...label, cls } : label)));
  }

  function deleteSelected() {
    setLabels((current) => current.filter((label) => label.id !== selectedId));
    setSelectedId(null);
  }

  function toggleLabeling() {
    setLabeling((current) => !current);
    setDrawing(false);
    setSelectedId(null);
  }

  useEffect(() => {
    fetch("/api/health")
      .then((response) => response.json())
      .then((data) => setApiStatus(data.status === "ok" ? "conectada" : "con errores"))
      .catch(() => setApiStatus("sin conexión"));

    fetch("/api/imagery")
      .then((response) => response.json())
      .then((data) => {
        setImagery(data);
        if (data.dates.length) setDate(data.dates[data.dates.length - 1].date);
      })
      .catch(() => setError("No se pudo cargar la lista de imágenes."));

    fetch("/api/boundary")
      .then((response) => (response.ok ? response.json() : null))
      .then(setBoundary)
      .catch(() => {});
  }, []);

  if (error) return <p className="message">{error}</p>;
  if (!imagery) return <p className="message">Cargando imágenes...</p>;
  if (!imagery.dates.length) {
    return (
      <p className="message">
        Todavía no hay imágenes. Ejecutá: docker compose run --rm api python -m cultivos.clip_scene --date
        AAAA-MM-DD
      </p>
    );
  }

  const selected = imagery.dates.find((item) => item.date === date);
  const activeLayer = selected.has_ndvi ? layer : "rgb";

  return (
    <>
      <div className="status">API: {apiStatus}</div>

      <div className="panel">
        <h2>Agrelo</h2>

        <h3>Fecha</h3>
        <div className="buttons">
          {imagery.dates.map((item) => (
            <button
              key={item.date}
              className={item.date === date ? "active" : ""}
              onClick={() => setDate(item.date)}
            >
              {formatDate(item.date)}
            </button>
          ))}
        </div>

        <h3>Qué mostrar</h3>
        <div className="buttons">
          {LAYER_OPTIONS.map((option) => (
            <button
              key={option.id}
              className={option.id === activeLayer ? "active" : ""}
              disabled={option.id === "ndvi" && !selected.has_ndvi}
              onClick={() => setLayer(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>

        <h3>Transparencia de la imagen</h3>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={opacity}
          onChange={(event) => setOpacity(Number(event.target.value))}
        />

        {activeLayer === "ndvi" && (
          <p className="hint">Marrón: sin vegetación. Verde oscuro: mucha vegetación. Transparente: nubes o sombras.</p>
        )}

        <h3>Etiquetas</h3>
        <div className="buttons">
          <button className={labeling ? "active" : ""} onClick={toggleLabeling}>
            {labeling ? "Etiquetar: activado" : "Etiquetar: desactivado"}
          </button>
        </div>

        {labeling && (
          <>
            <h3>Clase del próximo polígono</h3>
            <div className="buttons">
              {LABEL_CLASSES.map((item) => (
                <button
                  key={item.id}
                  className={item.id === activeClass ? "active" : ""}
                  disabled={drawing}
                  onClick={() => setActiveClass(item.id)}
                >
                  <span className="swatch" style={{ background: item.color }} />
                  {item.label}
                </button>
              ))}
            </div>

            <div className="buttons spaced">
              <button className={drawing ? "active" : ""} onClick={() => setDrawing((current) => !current)}>
                {drawing ? "Cancelar dibujo" : "Dibujar polígono"}
              </button>
            </div>
            {drawing && (
              <p className="hint">
                Clic para cada vértice. Para cerrar, clic en el primer punto. Esc cancela.
              </p>
            )}

            <p className="hint">
              {LABEL_CLASSES.map(
                (item) => `${item.label}: ${labels.filter((label) => label.cls === item.id).length}`,
              ).join(" · ")}
            </p>

            {selectedId && !drawing && (
              <>
                <h3>Polígono seleccionado</h3>
                <div className="buttons">
                  {LABEL_CLASSES.map((item) => (
                    <button
                      key={item.id}
                      className={labels.find((label) => label.id === selectedId).cls === item.id ? "active" : ""}
                      onClick={() => changeSelectedClass(item.id)}
                    >
                      <span className="swatch" style={{ background: classColor(item.id) }} />
                      Marcar como {item.label.toLowerCase()}
                    </button>
                  ))}
                  <button onClick={deleteSelected}>Borrar</button>
                </div>
              </>
            )}
            <p className="hint">Los polígonos se pierden al recargar la página (el guardado llega en A2-T2).</p>
          </>
        )}
      </div>

      <MapContainer className="map" bounds={imagery.bounds} maxZoom={MAX_ZOOM}>
        <LayersControl position="bottomright">
          <LayersControl.BaseLayer checked name="Satélite (Esri)">
            <TileLayer
              url={SATELLITE_URL}
              attribution={SATELLITE_ATTRIBUTION}
              maxNativeZoom={SATELLITE_NATIVE_ZOOM}
              maxZoom={MAX_ZOOM}
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Calles (OpenStreetMap)">
            <TileLayer url={STREETS_URL} attribution={STREETS_ATTRIBUTION} maxZoom={MAX_ZOOM} />
          </LayersControl.BaseLayer>
          {boundary && (
            <LayersControl.Overlay name="Límite de Luján de Cuyo">
              <GeoJSON data={boundary} style={BOUNDARY_STYLE} attribution={BOUNDARY_ATTRIBUTION} />
            </LayersControl.Overlay>
          )}
        </LayersControl>
        <ImageOverlay
          url={`/api/imagery/${selected.date}/${activeLayer}.png`}
          bounds={imagery.bounds}
          opacity={opacity}
        />
        {labeling && (
          <>
            <LabelPolygons labels={labels} selectedId={selectedId} drawing={drawing} onSelect={setSelectedId} />
            <PolygonDrawer
              drawing={drawing}
              color={classColor(activeClass)}
              onCreated={addLabel}
              onFinish={() => setDrawing(false)}
            />
          </>
        )}
      </MapContainer>
    </>
  );
}
