import { useEffect, useState } from "react";
import { GeoJSON, LayersControl, MapContainer, TileLayer, ZoomControl } from "react-leaflet";
import { getJson } from "../api.js";
import { bboxToBounds, formatDate } from "../format.js";
import LabelDetails from "../LabelDetails.jsx";
import { FocusLabel, LABEL_CLASSES, LabelPolygons, PolygonDrawer, classColor } from "../LabelTools.jsx";
import {
  createLabel,
  deleteLabel,
  fetchLabelOptions,
  fetchLabels,
  isPending,
  reviewLabels,
  updateLabel,
} from "../labelsApi.js";
import BaseLayers, { MAX_ZOOM } from "../map/BaseLayers.jsx";
import { CursorPosition } from "../map/MapHelpers.jsx";
import ReviewPanel from "../ReviewPanel.jsx";
import SeriesChart from "../SeriesChart.jsx";
import { fetchSeriesSummary } from "../seriesApi.js";
import SplitBlocks from "../SplitBlocks.jsx";
import SplitPanel from "../SplitPanel.jsx";
import { createSplit, fetchSplit } from "../splitApi.js";

const BOUNDARY_STYLE = { color: "#ff8a65", weight: 2, fillOpacity: 0.05 };
const BOUNDARY_ATTRIBUTION = "Límite: IGN vía datos.gob.ar (CC BY 4.0)";
const DEFAULT_OPACITY = 0.8;
const LOAD_CLIPS_COMMAND = "docker compose run --rm api python -m cultivos.catalog.load_clips";

export default function LabelingMode({ infoTarget, onLayerCount }) {
  const [imagery, setImagery] = useState(null);
  const [boundary, setBoundary] = useState(null);
  const [error, setError] = useState(null);
  const [date, setDate] = useState(null);
  const [layer, setLayer] = useState("rgb");
  const [opacity, setOpacity] = useState(DEFAULT_OPACITY);
  const [labeling, setLabeling] = useState(false);
  const [drawing, setDrawing] = useState(false);
  const [labels, setLabels] = useState([]);
  const [labelOptions, setLabelOptions] = useState(null);
  const [labelError, setLabelError] = useState(null);
  const [activeClass, setActiveClass] = useState(LABEL_CLASSES[0].id);
  const [selectedId, setSelectedId] = useState(null);
  const [focus, setFocus] = useState(null);
  const [split, setSplit] = useState(null);
  const [showBlocks, setShowBlocks] = useState(true);
  const [series, setSeries] = useState(null);
  const [showSeries, setShowSeries] = useState(false);

  function goTo(id) {
    setSelectedId(id);
    setFocus((current) => ({ id, key: (current?.key ?? 0) + 1 }));
  }

  async function saveChange(action) {
    setLabelError(null);
    try {
      await action();
      if (split?.created) setSplit(await fetchSplit());
    } catch (failure) {
      setLabelError(`No se pudo guardar: ${failure.message}`);
    }
  }

  const makeSplit = () =>
    saveChange(async () => {
      setSplit(await createSplit());
      setShowBlocks(true);
    });

  const addLabel = (points) =>
    saveChange(async () => {
      const label = await createLabel({ cls: activeClass, points, date });
      setLabels((current) => [...current, label]);
      setSelectedId(label.id);
    });

  const changeSelected = (changes) =>
    saveChange(async () => {
      const updated = await updateLabel(selectedId, changes);
      setLabels((current) => current.map((label) => (label.id === updated.id ? updated : label)));
    });

  const markReviewed = () =>
    saveChange(async () => {
      const pendingIds = labels.filter(isPending).map((label) => label.id);
      const index = pendingIds.indexOf(selectedId);
      const updated = await updateLabel(selectedId, { estado: "revisada" });
      setLabels((current) => current.map((label) => (label.id === updated.id ? updated : label)));
      const next = pendingIds.slice(index + 1).concat(pendingIds.slice(0, Math.max(index, 0)))[0];
      if (next) goTo(next);
    });

  const reviewMany = (ids) =>
    saveChange(async () => {
      const updated = await reviewLabels(ids);
      setLabels((current) => current.map((label) => updated.find((item) => item.id === label.id) ?? label));
    });

  const deleteSelected = () =>
    saveChange(async () => {
      await deleteLabel(selectedId);
      setLabels((current) => current.filter((label) => label.id !== selectedId));
      setSelectedId(null);
    });

  function toggleLabeling() {
    setLabeling((current) => !current);
    setDrawing(false);
    setSelectedId(null);
  }

  useEffect(() => {
    getJson("/labels/imagery")
      .then((data) => {
        setImagery(data);
        if (data.dates.length) setDate(data.dates[data.dates.length - 1].date);
      })
      .catch((failure) => setError(`No se pudieron cargar las imágenes de Agrelo: ${failure.message}`));

    fetch("/api/boundary")
      .then((response) => (response.ok ? response.json() : null))
      .then(setBoundary)
      .catch(() => {});

    fetchSplit()
      .then(setSplit)
      .catch(() => {});

    fetchSeriesSummary()
      .then(setSeries)
      .catch(() => {});

    Promise.all([fetchLabelOptions(), fetchLabels()])
      .then(([options, saved]) => {
        setLabelOptions(options);
        setLabels(saved);
      })
      .catch(() => setLabelError("No se pudieron cargar las etiquetas guardadas."));
  }, []);

  useEffect(() => onLayerCount(imagery?.dates.length ? 1 : 0), [imagery]);

  if (error) return <p className="message">{error}</p>;
  if (!imagery) return <p className="message">Cargando imágenes...</p>;
  if (!imagery.dates.length) {
    return (
      <p className="message">
        Los recortes de Agrelo todavía no están en el catálogo. Ejecutá: <code>{LOAD_CLIPS_COMMAND}</code>
      </p>
    );
  }

  const selected = imagery.dates.find((item) => item.date === date);
  const selectedLabel = labels.find((label) => label.id === selectedId);
  const activeLayer = selected.layers[layer] ? layer : "rgb";

  return (
    <>
      <div className="floating panel labeling-panel">
        <h2>Etiquetar · Agrelo</h2>
        {imagery.missing.length > 0 && (
          <p className="warning">
            {imagery.missing.length} fechas no están en el catálogo. Ejecutá: <code>{LOAD_CLIPS_COMMAND}</code>
          </p>
        )}

        <h3>Fecha</h3>
        <div className="buttons">
          {imagery.dates.map((item) => (
            <button
              key={item.date}
              className={item.date === date ? "active" : ""}
              onClick={() => setDate(item.date)}
            >
              {formatDate(item.date, "long")}
            </button>
          ))}
        </div>

        <h3>Qué mostrar</h3>
        <div className="buttons">
          {imagery.layers.map((option) => (
            <button
              key={option.id}
              className={option.id === activeLayer ? "active" : ""}
              disabled={!selected.layers[option.id]}
              onClick={() => setLayer(option.id)}
            >
              {option.title}
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

        <p className="hint">{imagery.layers.find((option) => option.id === activeLayer)?.how_to_read}</p>

        <h3>Series de NDVI</h3>
        <div className="buttons">
          <button className={showSeries ? "active" : ""} onClick={() => setShowSeries((current) => !current)}>
            {showSeries ? "Gráfico: visible" : "Gráfico: oculto"}
          </button>
        </div>

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
              {` · Sin criterio: ${labels.filter((label) => !label.criterio).length}`}
            </p>
            {labelError && <p className="warning">{labelError}</p>}

            {!drawing && (
              <ReviewPanel labels={labels} selectedId={selectedId} onGo={goTo} onReviewMany={reviewMany} />
            )}

            {selectedLabel && labelOptions && !drawing && (
              <LabelDetails
                label={selectedLabel}
                options={labelOptions}
                onChange={changeSelected}
                onDelete={deleteSelected}
                onMarkReviewed={markReviewed}
                role={split?.roles?.[selectedLabel.id]}
              />
            )}

            <SplitPanel
              split={split}
              showBlocks={showBlocks}
              onToggleBlocks={() => setShowBlocks((current) => !current)}
              onCreate={makeSplit}
            />
            <p className="hint">Los cambios se guardan solos en data/labels/.</p>
          </>
        )}
      </div>

      {showSeries && <SeriesChart summary={series} onClose={() => setShowSeries(false)} />}

      <MapContainer className="map" bounds={bboxToBounds(imagery.bbox)} maxZoom={MAX_ZOOM} zoomControl={false}>
        <BaseLayers defaultId="satellite">
          {boundary && (
            <LayersControl.Overlay name="Límite de Luján de Cuyo">
              <GeoJSON data={boundary} style={BOUNDARY_STYLE} attribution={BOUNDARY_ATTRIBUTION} />
            </LayersControl.Overlay>
          )}
        </BaseLayers>
        <ZoomControl position="bottomright" />
        <CursorPosition target={infoTarget} />
        <TileLayer
          key={`${selected.id}-${activeLayer}`}
          url={selected.layers[activeLayer]}
          bounds={bboxToBounds(selected.bbox)}
          opacity={opacity}
          maxZoom={MAX_ZOOM}
          zIndex={10}
        />
        {labeling && (
          <>
            {split?.created && showBlocks && <SplitBlocks split={split} />}
            <LabelPolygons labels={labels} selectedId={selectedId} drawing={drawing} onSelect={setSelectedId} />
            <FocusLabel label={labels.find((label) => label.id === focus?.id)} focusKey={focus?.key} />
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
