import { useState } from "react";
import SourceTag from "../SourceTag.jsx";

function LayerRow({ layer, active, onToggle }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`layer-row ${active ? "on" : ""}`}>
      <div className="layer-head">
        <label className="switch">
          <input type="checkbox" checked={active} onChange={onToggle} />
          <span className="slider" />
        </label>
        <span className="layer-title">{layer.title}</span>
        <button className="icon-button" title="Cómo leer esta capa" onClick={() => setOpen((current) => !current)}>
          {open ? "−" : "?"}
        </button>
      </div>
      {open && <p className="hint">{layer.how_to_read}</p>}
    </div>
  );
}

export default function LayersPanel({
  headline,
  collections,
  collectionId,
  onCollection,
  activeLayers,
  onToggleLayer,
  opacity,
  onOpacity,
  collapsed,
  onCollapse,
}) {
  const collection = collections.find((item) => item.id === collectionId);
  return (
    <section className={`floating panel layers-panel ${collapsed ? "collapsed" : ""}`}>
      <header className="panel-header">
        <h2>Capas</h2>
        <button className="icon-button" onClick={onCollapse} title={collapsed ? "Mostrar" : "Plegar"}>
          {collapsed ? "+" : "−"}
        </button>
      </header>
      {!collapsed && (
        <>
          {headline && <p className="headline">{headline}</p>}

          <h3>Imágenes</h3>
          <select className="text-input" value={collectionId ?? ""} onChange={(event) => onCollection(event.target.value)}>
            {collections.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
          {collection && <SourceTag collection={collection} />}

          <div className="layer-list">
            {collection?.layers.map((layer) => (
              <LayerRow
                key={layer.id}
                layer={layer}
                active={activeLayers.includes(layer.id)}
                onToggle={() => onToggleLayer(layer.id)}
              />
            ))}
          </div>

          <h3>Transparencia</h3>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={opacity}
            onChange={(event) => onOpacity(Number(event.target.value))}
          />

          {collection?.limits && (
            <p className="hint">
              <strong>Límite:</strong> {collection.limits}
            </p>
          )}
        </>
      )}
    </section>
  );
}
