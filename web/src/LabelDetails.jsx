import { useState } from "react";
import { LABEL_CLASSES, classColor } from "./LabelTools.jsx";

function CriterioInput({ value, suggestions, onSave }) {
  const [draft, setDraft] = useState(value);
  const save = () => {
    if (draft.trim() !== value) onSave(draft.trim());
  };
  return (
    <>
      <input
        className="text-input"
        list="criterio-options"
        value={draft}
        placeholder="Ej.: hileras de espaldero"
        onChange={(event) => setDraft(event.target.value)}
        onBlur={save}
        onKeyDown={(event) => event.key === "Enter" && event.target.blur()}
      />
      <datalist id="criterio-options">
        {suggestions.map((item) => (
          <option key={item} value={item} />
        ))}
      </datalist>
    </>
  );
}

export default function LabelDetails({ label, options, onChange, onDelete, onMarkReviewed }) {
  return (
    <>
      <h3>Polígono {label.id}</h3>
      <p className="hint">
        {label.areaHa.toLocaleString("es-AR")} ha · Sentinel-2, {label.imageDate}
      </p>
      <p className="hint">Estado: {label.estado}</p>
      {label.estado === "borrador" && label.reasons.length > 0 && (
        <p className="warning">A revisar: {label.reasons.join(", ")}.</p>
      )}
      {label.small && (
        <p className="warning">
          Menor a {options.min_area_ha} ha: no se usará para entrenar ni evaluar.
        </p>
      )}

      <h3>Clase</h3>
      <div className="buttons">
        {LABEL_CLASSES.map((item) => (
          <button
            key={item.id}
            className={item.id === label.cls ? "active" : ""}
            onClick={() => onChange({ clase: item.id })}
          >
            <span className="swatch" style={{ background: classColor(item.id) }} />
            {item.label}
          </button>
        ))}
      </div>

      <h3>Criterio</h3>
      <CriterioInput
        key={`${label.id}-${label.criterio}`}
        value={label.criterio}
        suggestions={options.criteria}
        onSave={(criterio) => onChange({ criterio })}
      />
      {!label.criterio && <p className="warning">Falta el criterio.</p>}

      <h3>Confianza</h3>
      <div className="buttons">
        {options.confidence_levels.map((level) => (
          <button
            key={level}
            className={level === label.confianza ? "active" : ""}
            onClick={() => onChange({ confianza: level })}
          >
            {level[0].toUpperCase() + level.slice(1)}
          </button>
        ))}
      </div>
      <p className="hint">Alta: seguro. Media: hay otra opción posible. Baja: dudoso, no se usa.</p>

      <div className="buttons spaced">
        {label.estado === "borrador" && (
          <button disabled={!label.criterio} onClick={onMarkReviewed}>
            Marcar como revisada
          </button>
        )}
        {label.estado === "revisada" && (
          <button onClick={() => onChange({ estado: "borrador" })}>Reabrir (volver a borrador)</button>
        )}
        <button onClick={onDelete}>Borrar</button>
      </div>
    </>
  );
}
