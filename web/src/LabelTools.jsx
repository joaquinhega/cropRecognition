import { useEffect, useRef } from "react";
import { Polygon, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet-draw";
import "leaflet-draw/dist/leaflet.draw.css";

export const LABEL_CLASSES = [
  { id: "vid", label: "Vid", color: "#8e24aa" },
  { id: "otros", label: "Otros", color: "#ef6c00" },
];

export function classColor(classId) {
  return LABEL_CLASSES.find((item) => item.id === classId).color;
}

export function PolygonDrawer({ drawing, color, onCreated, onFinish }) {
  const map = useMap();
  const onCreatedRef = useRef(onCreated);
  const onFinishRef = useRef(onFinish);
  onCreatedRef.current = onCreated;
  onFinishRef.current = onFinish;

  useEffect(() => {
    if (!drawing) return undefined;
    const handler = new L.Draw.Polygon(map, {
      showArea: false,
      allowIntersection: false,
      shapeOptions: { color },
    });
    const handleCreated = (event) => {
      const points = event.layer.getLatLngs()[0].map(({ lat, lng }) => [lat, lng]);
      onCreatedRef.current(points);
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
  }, [drawing, color, map]);

  return null;
}

export function LabelPolygons({ labels, selectedId, drawing, onSelect }) {
  return labels.map((label) => {
    const color = classColor(label.cls);
    const selected = label.id === selectedId;
    return (
      <Polygon
        key={`${label.id}-${drawing}`}
        positions={label.points}
        interactive={!drawing}
        pathOptions={{
          color,
          weight: selected ? 4 : 2,
          dashArray: selected ? "6 4" : null,
          fillColor: color,
          fillOpacity: selected ? 0.35 : 0.2,
        }}
        eventHandlers={{ click: () => onSelect(label.id) }}
      />
    );
  });
}

export function FocusLabel({ label, focusKey }) {
  const map = useMap();
  useEffect(() => {
    if (!label) return;
    map.fitBounds(L.latLngBounds(label.points), {
      maxZoom: 18,
      paddingTopLeft: [320, 40],
      paddingBottomRight: [40, 40],
    });
  }, [focusKey]);
  return null;
}
