import { useEffect, useState } from "react";
import L from "leaflet";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const BOUNDARY_STYLE = { color: "#b03a2e", weight: 2, fillOpacity: 0.08 };
const BOUNDARY_ATTRIBUTION = "Límite: IGN vía datos.gob.ar (CC BY 4.0)";
const TILES_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILES_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

export default function App() {
  const [apiStatus, setApiStatus] = useState("verificando...");
  const [boundary, setBoundary] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/api/health")
      .then((response) => response.json())
      .then((data) => setApiStatus(data.status === "ok" ? "conectada" : "con errores"))
      .catch(() => setApiStatus("sin conexión"));

    fetch("/api/boundary")
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail);
        setBoundary(body);
      })
      .catch((err) => setError(err.message || "No se pudo cargar el límite."));
  }, []);

  return (
    <>
      <div className="status">API: {apiStatus}</div>
      {boundary ? (
        <MapContainer className="map" bounds={L.geoJSON(boundary).getBounds()}>
          <TileLayer url={TILES_URL} attribution={TILES_ATTRIBUTION} />
          <GeoJSON data={boundary} style={BOUNDARY_STYLE} attribution={BOUNDARY_ATTRIBUTION} />
        </MapContainer>
      ) : (
        <p className="message">{error ?? "Cargando límite..."}</p>
      )}
    </>
  );
}
