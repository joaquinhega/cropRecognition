import { useEffect, useState } from "react";
import { CircleMarker, MapContainer, Rectangle, Tooltip, ZoomControl } from "react-leaflet";
import { bboxToBounds, formatMonth, formatNumber } from "../format.js";
import BaseLayers, { MAX_ZOOM } from "../map/BaseLayers.jsx";
import { CursorPosition, FitBounds } from "../map/MapHelpers.jsx";
import ClassCurves from "./ClassCurves.jsx";
import { fetchTraining, fetchTrainingPixels } from "./trainingApi.js";

const ZONE_STYLE = { color: "#ffd54f", weight: 2, fill: false };
const POINT_RADIUS = 3;
const ESRI_NATIVE_ZOOM = { satellite: 17 };

const percent = (share) => `${formatNumber(share * 100)} %`;
const SHOWN_METRICS = ["peak_month", "peak_value", "rise_month", "green_months", "winter_mean", "summer_mean"];

function metricText(features, name, value) {
  if (value === null || value === undefined) return "—";
  if (features.phenology[name].month_position) return formatMonth(features.month_keys[Math.round(value)]);
  return Number.isInteger(value) ? formatNumber(value) : formatNumber(value, 2);
}

function FeaturesCard({ features, classes }) {
  if (!features.available) {
    return (
      <p className="hint">
        Todavía no están las variables. Ejecutá: <code>{features.command}</code>
      </p>
    );
  }
  const names = Object.keys(classes);
  return (
    <>
      <p className="hint">
        {formatNumber(features.columns.total)} por píxel: {formatNumber(features.columns.monthly)} mensuales y{" "}
        {formatNumber(features.columns.phenology)} de la forma de la curva de {features.index}. Meses descartados por
        bruma: {formatNumber(features.haze.removed)} de {formatNumber(features.haze.observations)}.
      </p>
      <table className="training-months">
        <thead>
          <tr>
            <td className="muted">Valor típico</td>
            {names.map((name) => (
              <td key={name}>
                <span className="swatch" style={{ background: classes[name].color }} />
                {classes[name].title}
              </td>
            ))}
          </tr>
        </thead>
        <tbody>
          {SHOWN_METRICS.map((metric) => (
            <tr key={metric}>
              <td className="muted">{features.phenology[metric].title}</td>
              {names.map((name) => (
                <td key={name}>{metricText(features, metric, features.classes[name]?.[metric])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function MonthsTable({ months }) {
  return (
    <table className="training-months">
      <tbody>
        {months.map((info) => (
          <tr key={info.month}>
            <td>{formatMonth(info.month)}</td>
            <td className={info.share_with_data < 0.5 ? "warning" : ""}>{percent(info.share_with_data)} con dato</td>
            <td className="muted">
              {info.scenes.length} de {info.candidates} escenas
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function RecognitionMode({ infoTarget, onLayerCount }) {
  const [index, setIndex] = useState(null);
  const [training, setTraining] = useState(null);
  const [pixels, setPixels] = useState(null);
  const [error, setError] = useState(null);
  const [showChart, setShowChart] = useState(true);
  const [showPixels, setShowPixels] = useState(true);

  useEffect(() => {
    fetchTraining(index)
      .then(setTraining)
      .catch((failure) => setError(failure.message));
  }, [index]);

  useEffect(() => {
    fetchTrainingPixels()
      .then(setPixels)
      .catch(() => {});
  }, []);

  useEffect(() => onLayerCount(showPixels && pixels?.features.length ? 1 : 0), [showPixels, pixels]);

  if (error) return <p className="message warning">{error}</p>;
  if (!training) return <p className="message">Cargando los datos de entrenamiento…</p>;
  if (!training.available) {
    return (
      <p className="message">
        Todavía no hay datos de entrenamiento. Ejecutá: <code>{training.command}</code>
      </p>
    );
  }

  const classes = training.classes;
  const current = training.curves.index;
  const labels = training.labels;

  return (
    <>
      <div className="floating panel labeling-panel">
        <h2>Reconocimiento · entrenamiento</h2>
        <p className="hint">
          {training.zone.name} · campaña {training.campaign} · {formatNumber(training.pixels)} píxeles de 10 m
        </p>

        <h3>De dónde salen las clases</h3>
        <p className="hint">
          {labels.title} · {labels.license}
        </p>
        <p className="warning">{labels.limits}</p>

        <h3>Clases</h3>
        <ul className="training-classes">
          {Object.entries(classes).map(([name, info]) => (
            <li key={name}>
              <span className="swatch" style={{ background: info.color }} />
              {info.title}: {formatNumber(info.pixels)} píxeles
              {info.candidates !== null && <span className="muted"> de {formatNumber(info.candidates)} candidatos</span>}
            </li>
          ))}
        </ul>

        <h3>Variables del modelo</h3>
        <FeaturesCard features={training.features} classes={classes} />

        <h3>Qué mostrar</h3>
        <div className="buttons">
          {training.indices.map((name) => (
            <button key={name} className={name === current ? "active" : ""} onClick={() => setIndex(name)}>
              {name}
            </button>
          ))}
        </div>
        <div className="buttons">
          <button className={showChart ? "active" : ""} onClick={() => setShowChart((value) => !value)}>
            {showChart ? "Curvas: visibles" : "Curvas: ocultas"}
          </button>
          <button className={showPixels ? "active" : ""} onClick={() => setShowPixels((value) => !value)}>
            {showPixels ? "Píxeles: visibles" : "Píxeles: ocultos"}
          </button>
        </div>

        <h3>Meses (Sentinel-2)</h3>
        <MonthsTable months={training.months} />

        <details className="training-legend">
          <summary>Leyenda del mapa → clase</summary>
          <ul>
            {training.legend
              .filter((row) => row.map_pixels > 0)
              .map((row) => (
                <li key={row.value}>
                  {row.label} → {row.class ? classes[row.class].title : "excluida"}{" "}
                  <span className="muted">({formatNumber(row.map_pixels)} píxeles del mapa)</span>
                </li>
              ))}
          </ul>
        </details>
      </div>

      {showChart && (
        <div className="series-chart">
          <button className="close" onClick={() => setShowChart(false)}>
            Cerrar
          </button>
          <h3>
            {current} por mes y clase · campaña {training.campaign}
          </h3>
          <ClassCurves curves={training.curves} classes={classes} indexTitle={current} />
          <p className="hint">
            {Object.entries(classes).map(([name, info]) => (
              <span key={name}>
                <span className="swatch" style={{ background: info.color }} />
                {info.title}{"  "}
              </span>
            ))}
          </p>
          <p className="hint">
            Línea: mediana. Banda: del percentil 25 al 75 (la mitad central de los píxeles). Sin interpolar: un mes sin
            dato corta la línea.
          </p>
        </div>
      )}

      <MapContainer className="map" bounds={bboxToBounds(training.zone.bbox)} maxZoom={MAX_ZOOM} zoomControl={false} preferCanvas>
        <BaseLayers defaultId="satellite" nativeZoom={ESRI_NATIVE_ZOOM} />
        <ZoomControl position="bottomright" />
        <CursorPosition target={infoTarget} />
        <FitBounds bbox={training.zone.bbox} />
        <Rectangle bounds={bboxToBounds(training.zone.bbox)} pathOptions={ZONE_STYLE} interactive={false} />
        {showPixels &&
          pixels?.features.map((feature) => {
            const [lon, lat] = feature.geometry.coordinates;
            const info = classes[feature.properties.class];
            return (
              <CircleMarker
                key={feature.properties.pixel_id}
                center={[lat, lon]}
                radius={POINT_RADIUS}
                pathOptions={{ color: info.color, fillColor: info.color, fillOpacity: 0.9, weight: 1 }}
              >
                <Tooltip>
                  {feature.properties.pixel_id} · {info.title}
                </Tooltip>
              </CircleMarker>
            );
          })}
      </MapContainer>
    </>
  );
}
