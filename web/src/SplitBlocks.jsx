import { GeoJSON } from "react-leaflet";

const TEST_STYLE = { color: "#c62828", weight: 2, dashArray: "6 4", fillColor: "#c62828", fillOpacity: 0.18 };
const TRAIN_STYLE = { color: "#455a64", weight: 1, fillOpacity: 0 };

export default function SplitBlocks({ split }) {
  return (
    <GeoJSON
      key={`${split.created_on}-${split.params.attempt}`}
      data={split.blocks}
      style={(feature) => ({
        ...(feature.properties.role === "prueba" ? TEST_STYLE : TRAIN_STYLE),
        interactive: false,
      })}
    />
  );
}
