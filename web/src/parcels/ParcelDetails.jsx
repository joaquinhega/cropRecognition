import { useState } from "react";
import { formatDate, formatNumber } from "../format.js";
import ProcessingStatus from "./ProcessingStatus.jsx";

function originText(properties) {
  return properties.origin === "file" ? `subida desde ${properties.source_file}` : "dibujada en el mapa";
}

export default function ParcelDetails({ parcel, limits, saving, onRename, onDelete, onProcessed }) {
  const { properties } = parcel;
  const [name, setName] = useState(properties.name);
  const [confirming, setConfirming] = useState(false);

  const saveName = () => {
    if (name.trim() && name.trim() !== properties.name) onRename(name.trim());
  };

  return (
    <>
      <h3>Parcela {properties.code}</h3>
      <p className="hint">
        {formatNumber(properties.area_ha, 2)} ha · {originText(properties)} · {formatDate(properties.created_at.slice(0, 10))}
      </p>
      {properties.below_minimum && (
        <p className="warning">
          Menor a {formatNumber(limits.min_area_ha)} ha: con imágenes de 10 m quedan muy pocos píxeles limpios, así que
          las curvas de índices van a ser poco confiables. El clima sirve igual.
        </p>
      )}

      <h3>Nombre</h3>
      <input
        className="text-input"
        value={name}
        maxLength={limits.name_max_length}
        onChange={(event) => setName(event.target.value)}
        onBlur={saveName}
        onKeyDown={(event) => event.key === "Enter" && event.target.blur()}
      />

      <ProcessingStatus parcelId={parcel.id} onDone={onProcessed} />

      <h3>Borrar</h3>
      <div className="buttons">
        {!confirming && (
          <button onClick={() => setConfirming(true)} disabled={saving}>
            Borrar parcela
          </button>
        )}
        {confirming && (
          <>
            <p className="warning">¿Borrar {properties.name}? No se puede deshacer.</p>
            <button className="danger" onClick={onDelete} disabled={saving}>
              Sí, borrar
            </button>
            <button onClick={() => setConfirming(false)} disabled={saving}>
              No
            </button>
          </>
        )}
      </div>
    </>
  );
}
