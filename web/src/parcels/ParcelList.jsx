import { formatNumber } from "../format.js";

export default function ParcelList({ parcels, selectedId, disabled, onSelect }) {
  return (
    <>
      <h3>Parcelas</h3>
      <div className="buttons parcel-list">
        {parcels.map((parcel) => (
          <button
            key={parcel.id}
            className={`parcel-row ${parcel.id === selectedId ? "active" : ""}`}
            disabled={disabled}
            onClick={() => onSelect(parcel.id)}
          >
            <span className="parcel-name">{parcel.properties.name}</span>
            {parcel.properties.below_minimum && <span className="badge small-parcel">chica</span>}
            <span className="parcel-area">{formatNumber(parcel.properties.area_ha, 1)} ha</span>
          </button>
        ))}
      </div>
    </>
  );
}
