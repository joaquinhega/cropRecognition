import { LayersControl, TileLayer } from "react-leaflet";

export const MAX_ZOOM = 20;

export const BASE_LAYERS = [
  {
    id: "dark",
    name: "Mapa gris oscuro (Esri)",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    attribution: "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors",
    maxNativeZoom: 16,
  },
  {
    id: "satellite",
    name: "Satélite (Esri, solo referencia visual)",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
    maxNativeZoom: 18,
  },
  {
    id: "streets",
    name: "Calles (OpenStreetMap)",
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxNativeZoom: 19,
  },
];

export default function BaseLayers({ defaultId = "dark", nativeZoom = {}, children }) {
  return (
    <LayersControl position="bottomright">
      {BASE_LAYERS.map((layer) => (
        <LayersControl.BaseLayer key={layer.id} checked={layer.id === defaultId} name={layer.name}>
          <TileLayer
            url={layer.url}
            attribution={layer.attribution}
            maxNativeZoom={nativeZoom[layer.id] ?? layer.maxNativeZoom}
            maxZoom={MAX_ZOOM}
            subdomains={layer.subdomains ?? "abc"}
          />
        </LayersControl.BaseLayer>
      ))}
      {children}
    </LayersControl>
  );
}
