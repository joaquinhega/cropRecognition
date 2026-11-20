import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet-draw";
import "leaflet-draw/dist/leaflet.draw.css";
import { bboxToBounds, formatNumber } from "../format.js";

export function FitBounds({ bbox, padding = [40, 40] }) {
  const map = useMap();
  const key = bbox?.join(",");
  useEffect(() => {
    if (bbox) map.fitBounds(bboxToBounds(bbox), { padding, maxZoom: 16 });
  }, [key]);
  return null;
}

export function CursorPosition({ target }) {
  const [position, setPosition] = useState(null);
  useMapEvents({
    mousemove: (event) => setPosition(event.latlng),
    mouseout: () => setPosition(null),
  });
  if (!target) return null;
  const text = position
    ? `${formatNumber(position.lat, 4)}°, ${formatNumber(position.lng, 4)}°`
    : "Mové el cursor sobre el mapa";
  return createPortal(<span className="coords">{text}</span>, target);
}

export function RectangleDrawer({ drawing, onCreated, onFinish }) {
  const map = useMap();
  const onCreatedRef = useRef(onCreated);
  const onFinishRef = useRef(onFinish);
  onCreatedRef.current = onCreated;
  onFinishRef.current = onFinish;

  useEffect(() => {
    if (!drawing) return undefined;
    const handler = new L.Draw.Rectangle(map, { shapeOptions: { color: "#4cc38a", weight: 2 } });
    const handleCreated = (event) => {
      const bounds = event.layer.getBounds();
      onCreatedRef.current([bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()]);
    };
    const handleStop = () => onFinishRef.current();
    map.on(L.Draw.Event.CREATED, handleCreated);
    map.on(L.Draw.Event.DRAWSTOP, handleStop);
    handler.enable();
    return () => {
      map.off(L.Draw.Event.CREATED, handleCreated);
      map.off(L.Draw.Event.DRAWSTOP, handleStop);
      handler.disable();
    };
  }, [drawing, map]);

  return null;
}
