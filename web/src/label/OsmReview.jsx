import { useEffect, useState } from "react";
import { GeoJSON, MapContainer, TileLayer, ZoomControl } from "react-leaflet";
import { bboxToBounds, formatDate, formatNumber } from "../format.js";
import BaseLayers, { MAX_ZOOM } from "../map/BaseLayers.jsx";
import { CursorPosition, FitBounds } from "../map/MapHelpers.jsx";
import { fetchOsmReview, fetchReferenceScene, saveOsmVerdict } from "./osmReviewApi.js";

const NO_IMAGE = "none";
const DEFAULT_OPACITY = 0.8;
// Esri has no photo at its highest zoom in many rural areas of Mendoza; stretch the last level that exists everywhere.
const ESRI_NATIVE_ZOOM = { satellite: 17 };
const POLYGON_STYLE = { color: "#ffd54f", weight: 3, fill: false };
const OSM_URL = "https://www.openstreetmap.org/";
const VERDICT_COLORS = { coincide: "#4cc38a", parcial: "#4aa3df", no_coincide: "#e5534b", dudoso: "#8b95a3" };
const STATUS_TEXT = {
  in_progress: "Revisión en curso.",
  approved: "OSM aprobada: se usa como fuente de confianza media (entrena, no evalúa).",
  doubtful: "OSM dudosa: no coinciden más polígonos que el límite. Se aplica el respaldo pampeano (D-036).",
};

function featureBbox(feature) {
  const points = feature.geometry.coordinates.flat();
  const lons = points.map(([lon]) => lon);
  const lats = points.map(([, lat]) => lat);
  return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
}

function nextPending(features, current) {
  const ordered = features.slice(current).concat(features.slice(0, current - 1));
  return ordered.find((feature) => !feature.properties.verdict)?.properties.n ?? current;
}

function SummaryBox({ summary }) {
  const percent = formatNumber((summary.mismatches / summary.total) * 100);
  return (
    <div className="review-summary">
      <p>
        Revisados {summary.reviewed} de {summary.total} · No coinciden {summary.mismatches} ({percent} %); el límite
        es {summary.max_mismatches} ({formatNumber(summary.max_mismatch_share * 100)} %).
      </p>
      <p className={summary.status === "doubtful" ? "warning" : "hint"}>{STATUS_TEXT[summary.status]}</p>
      {summary.uncertain_could_fail && (
        <p className="warning">Si los dudosos no coincidieran, se pasaría el límite: conviene volver a mirarlos.</p>
      )}
    </div>
  );
}

function SceneStatus({ scene, error }) {
  if (error) return <p className="warning">{error}</p>;
  if (!scene) return <p className="hint">Buscando la imagen de Sentinel-2 más limpia sobre el polígono…</p>;
  if (!scene.scene) return <p className="warning">{scene.reason}</p>;
  return (
    <p className="hint">
      Sentinel-2 del {formatDate(scene.scene.date, "long")} · {formatNumber(scene.scene.valid_share * 100)} % del
      polígono sin nubes.
    </p>
  );
}

export default function OsmReview({ infoTarget, onLayerCount, onExit }) {
  const [review, setReview] = useState(null);
  const [error, setError] = useState(null);
  const [current, setCurrent] = useState(1);
  const [scenes, setScenes] = useState({});
  const [sceneErrors, setSceneErrors] = useState({});
  const [layer, setLayer] = useState(NO_IMAGE);
  const [opacity, setOpacity] = useState(DEFAULT_OPACITY);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchOsmReview()
      .then((body) => {
        setReview(body);
        setCurrent(nextPending(body.features, 1));
      })
      .catch((failure) => setError(failure.message));
  }, []);

  const feature = review?.features[current - 1];

  useEffect(() => {
    if (!feature) return;
    setNote(feature.properties.note ?? "");
    if (scenes[current] || sceneErrors[current]) return;
    fetchReferenceScene(current)
      .then((body) => setScenes((known) => ({ ...known, [current]: body })))
      .catch((failure) => setSceneErrors((known) => ({ ...known, [current]: failure.message })));
  }, [current, review !== null]);

  const scene = scenes[current]?.scene;
  const imageUrl = layer !== NO_IMAGE ? scene?.layers[layer] : null;

  useEffect(() => onLayerCount(imageUrl ? 1 : 0), [imageUrl]);

  async function answer(verdict) {
    setSaving(true);
    setError(null);
    try {
      const result = await saveOsmVerdict(current, verdict, note);
      const features = review.features.map((item) => (item.properties.n === current ? result.feature : item));
      setReview({ ...review, features, summary: result.summary });
      setCurrent(nextPending(features, current));
    } catch (failure) {
      setError(`No se pudo guardar: ${failure.message}`);
    } finally {
      setSaving(false);
    }
  }

  const go = (step) => setCurrent((n) => ((n - 1 + step + review.features.length) % review.features.length) + 1);

  if (!review) {
    return (
      <div className="floating panel labeling-panel">
        <h2>Revisar OSM · vid</h2>
        <p className={error ? "warning" : "hint"}>{error ?? "Cargando la muestra…"}</p>
        <div className="buttons">
          <button onClick={onExit}>Volver a Etiquetar</button>
        </div>
      </div>
    );
  }

  const properties = feature.properties;
  const bbox = featureBbox(feature);
  const layerInfo = review.layers.find((option) => option.id === layer);

  return (
    <>
      <div className="floating panel labeling-panel">
        <h2>Revisar OSM · vid</h2>
        <p className="hint">
          Muestra al azar de {review.summary.total} viñedos de OpenStreetMap en toda Mendoza. En cada uno, mirá si de
          verdad es viñedo: hileras en la foto de Esri y verde en Sentinel-2 de pleno verano.
        </p>
        <SummaryBox summary={review.summary} />

        <h3>
          Polígono {current} de {review.features.length}
        </h3>
        <div className="buttons">
          <button onClick={() => go(-1)}>‹ Anterior</button>
          <button onClick={() => go(1)}>Siguiente ›</button>
        </div>
        <p className="hint">
          {properties.oasis} · {formatNumber(properties.area_ha, 1)} ha ·{" "}
          <a href={`${OSM_URL}${properties.osm}`} target="_blank" rel="noreferrer">
            ver en OSM
          </a>
        </p>

        <h3>Imagen sobre la foto de Esri</h3>
        <div className="buttons">
          <button className={layer === NO_IMAGE ? "active" : ""} onClick={() => setLayer(NO_IMAGE)}>
            Solo Esri
          </button>
          {review.layers.map((option) => (
            <button
              key={option.id}
              className={option.id === layer ? "active" : ""}
              disabled={!scene}
              onClick={() => setLayer(option.id)}
            >
              {option.title}
            </button>
          ))}
        </div>
        <SceneStatus scene={scenes[current]} error={sceneErrors[current]} />
        {imageUrl && (
          <>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={opacity}
              onChange={(event) => setOpacity(Number(event.target.value))}
            />
            <p className="hint">{layerInfo?.how_to_read}</p>
          </>
        )}

        <h3>¿Es viñedo?</h3>
        <textarea
          className="text-input review-note"
          rows="2"
          placeholder="Nota opcional (por ejemplo: olivar, incluye una casa). Se guarda con la respuesta."
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
        <div className="buttons">
          {review.verdicts.map((option) => (
            <button
              key={option.id}
              className={properties.verdict === option.id ? "active" : ""}
              disabled={saving}
              title={option.help}
              onClick={() => answer(option.id)}
            >
              <span className="swatch" style={{ background: VERDICT_COLORS[option.id] }} />
              {option.title}
            </button>
          ))}
        </div>
        <ul className="review-help">
          {review.verdicts.map((option) => (
            <li key={option.id}>
              <strong>{option.title}:</strong> {option.help}
            </li>
          ))}
        </ul>
        {error && <p className="warning">{error}</p>}

        <h3>Todos</h3>
        <div className="review-grid">
          {review.features.map((item) => (
            <button
              key={item.properties.n}
              className={item.properties.n === current ? "active" : ""}
              style={{ borderBottomColor: VERDICT_COLORS[item.properties.verdict] ?? "transparent" }}
              title={item.properties.verdict ?? "Sin revisar"}
              onClick={() => setCurrent(item.properties.n)}
            >
              {item.properties.n}
            </button>
          ))}
        </div>
        <p className="hint">Las respuestas se guardan solas en data/inventory/.</p>
        <div className="buttons spaced">
          <button onClick={onExit}>Volver a Etiquetar</button>
        </div>
      </div>

      <MapContainer className="map" bounds={bboxToBounds(bbox)} maxZoom={MAX_ZOOM} zoomControl={false}>
        <BaseLayers defaultId="satellite" nativeZoom={ESRI_NATIVE_ZOOM} />
        <ZoomControl position="bottomright" />
        <CursorPosition target={infoTarget} />
        <FitBounds bbox={bbox} />
        {imageUrl && (
          <TileLayer key={`${current}-${layer}`} url={imageUrl} opacity={opacity} maxZoom={MAX_ZOOM} zIndex={10} />
        )}
        <GeoJSON key={current} data={feature} style={POLYGON_STYLE} />
      </MapContainer>
    </>
  );
}
