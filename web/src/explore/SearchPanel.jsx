import { formatNumber, plural } from "../format.js";

const SOURCE_LABELS = { "earth-search": "Earth Search (Sentinel-2)", "conae-saocom": "CONAE (SAOCOM, solo metadatos)" };

function ResultLine({ result }) {
  if (result.error) return <p className="warning">{SOURCE_LABELS[result.source] ?? result.source}: {result.error}</p>;
  return (
    <p className="hint">
      {SOURCE_LABELS[result.source] ?? result.source}: {plural(result.found, "escena encontrada", "escenas encontradas")},{" "}
      {plural(result.new, "nueva", "nuevas")} en el catálogo.
    </p>
  );
}

export default function SearchPanel({
  zones,
  area,
  onZone,
  drawing,
  onDraw,
  period,
  onPeriod,
  maxCloud,
  onMaxCloud,
  imagerySources,
  selectedSources,
  onToggleSource,
  searching,
  onSearch,
  result,
  collapsed,
  onCollapse,
}) {
  return (
    <section className={`floating panel search-panel ${collapsed ? "collapsed" : ""}`}>
      <header className="panel-header">
        <h2>Zona y búsqueda</h2>
        <button className="icon-button" onClick={onCollapse} title={collapsed ? "Mostrar" : "Plegar"}>
          {collapsed ? "+" : "−"}
        </button>
      </header>
      {!collapsed && (
        <>
          <h3>Zona</h3>
          <select className="text-input" value={area.id ?? "custom"} onChange={(event) => onZone(event.target.value)}>
            {zones.map((zone) => (
              <option key={zone.id} value={zone.id}>
                {zone.name}
              </option>
            ))}
            {!area.id && <option value="custom">Recuadro dibujado</option>}
          </select>
          <div className="buttons spaced">
            <button className={drawing ? "active" : ""} onClick={onDraw}>
              {drawing ? "Cancelar dibujo" : "Dibujar un recuadro en el mapa"}
            </button>
          </div>
          {drawing && <p className="hint">Hacé clic y arrastrá para marcar la zona.</p>}
          <p className="hint">Superficie: {formatNumber(area.area_km2 ?? 0, 1)} km²</p>

          <h3>Período</h3>
          <div className="date-row">
            <input
              type="date"
              className="text-input"
              value={period.start}
              max={period.end}
              onChange={(event) => onPeriod({ ...period, start: event.target.value })}
            />
            <input
              type="date"
              className="text-input"
              value={period.end}
              min={period.start}
              onChange={(event) => onPeriod({ ...period, end: event.target.value })}
            />
          </div>

          <h3>Nubes máximas: {maxCloud} %</h3>
          <input type="range" min="0" max="100" step="5" value={maxCloud} onChange={(event) => onMaxCloud(Number(event.target.value))} />

          <h3>Fuentes</h3>
          {imagerySources.map((source) => (
            <label key={source.id} className={`check ${source.status !== "activa" ? "disabled" : ""}`}>
              <input
                type="checkbox"
                disabled={source.status !== "activa"}
                checked={selectedSources.includes(source.id)}
                onChange={() => onToggleSource(source.id)}
              />
              {source.name}
              {source.kind === "radar" && <span className="badge">radar</span>}
              {source.status !== "activa" && <span className="badge">{source.status}</span>}
            </label>
          ))}

          <div className="buttons spaced">
            <button className="primary" disabled={searching || !selectedSources.length} onClick={onSearch}>
              {searching ? "Buscando…" : "Buscar en las fuentes y guardar"}
            </button>
          </div>
          <p className="hint">Busca escenas nuevas en las fuentes y las guarda en el catálogo propio.</p>
          {result?.results.map((item) => (
            <ResultLine key={item.source} result={item} />
          ))}
        </>
      )}
    </section>
  );
}
