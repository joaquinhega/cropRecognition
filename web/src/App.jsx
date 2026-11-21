import { useEffect, useState } from "react";
import "leaflet/dist/leaflet.css";
import { getJson } from "./api.js";
import ExploreMode from "./explore/ExploreMode.jsx";
import LabelingMode from "./label/LabelingMode.jsx";
import ParcelsMode from "./parcels/ParcelsMode.jsx";
import RecognitionMode from "./recognition/RecognitionMode.jsx";
import SourcesDrawer from "./SourcesDrawer.jsx";

const MODES = [
  { id: "explore", label: "Explorar" },
  { id: "parcels", label: "Mi parcela" },
  { id: "label", label: "Etiquetar" },
  { id: "recognition", label: "Reconocimiento" },
];

export default function App() {
  const [mode, setMode] = useState("explore");
  const [apiStatus, setApiStatus] = useState("verificando");
  const [zones, setZones] = useState(null);
  const [sources, setSources] = useState(null);
  const [collections, setCollections] = useState(null);
  const [error, setError] = useState(null);
  const [showSources, setShowSources] = useState(false);
  const [infoTarget, setInfoTarget] = useState(null);
  const [layerCount, setLayerCount] = useState(0);

  const refreshCatalog = () =>
    Promise.all([getJson("/sources"), getJson("/catalog/collections")])
      .then(([sourcesBody, collectionsBody]) => {
        setSources(sourcesBody);
        setCollections(collectionsBody);
      })
      .catch((failure) => setError(failure.message));

  useEffect(() => {
    getJson("/health")
      .then((body) => setApiStatus(body.status === "ok" ? "conectada" : "con errores"))
      .catch(() => setApiStatus("sin conexión"));
    getJson("/zones").then(setZones).catch((failure) => setError(failure.message));
    refreshCatalog();
  }, []);

  const ready = zones && sources && collections;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">◉</span> Plataforma satelital agro
        </div>
        <nav className="modes">
          {MODES.map((item) => (
            <button key={item.id} className={item.id === mode ? "active" : ""} onClick={() => setMode(item.id)}>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="topbar-info">
          <span ref={setInfoTarget} />
          <span className="muted">
            {layerCount} {layerCount === 1 ? "capa activa" : "capas activas"}
          </span>
        </div>
        <div className="topbar-actions">
          <button onClick={() => setShowSources(true)} disabled={!sources}>
            Fuentes y límites
          </button>
          <span className={`api-status ${apiStatus === "conectada" ? "ok" : "bad"}`}>API {apiStatus}</span>
        </div>
      </header>

      <main className="stage">
        {error && <p className="message warning">{error}</p>}
        {!error && !ready && <p className="message">Cargando la plataforma…</p>}
        {ready && mode === "explore" && (
          <ExploreMode
            zones={zones}
            sources={sources}
            collections={collections}
            onCollectionsChange={refreshCatalog}
            infoTarget={infoTarget}
            onLayerCount={setLayerCount}
          />
        )}
        {ready && mode === "parcels" && (
          <ParcelsMode zones={zones} infoTarget={infoTarget} onLayerCount={setLayerCount} />
        )}
        {ready && mode === "label" && <LabelingMode infoTarget={infoTarget} onLayerCount={setLayerCount} />}
        {ready && mode === "recognition" && (
          <RecognitionMode infoTarget={infoTarget} onLayerCount={setLayerCount} />
        )}
      </main>

      {showSources && sources && <SourcesDrawer sources={sources} onClose={() => setShowSources(false)} />}
    </div>
  );
}
