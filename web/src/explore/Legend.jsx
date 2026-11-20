const COLORMAPS = {
  rdylgn: ["#a50026", "#f46d43", "#fee08b", "#d9ef8b", "#66bd63", "#006837"],
};

function Gradient({ layer }) {
  const { legend } = layer;
  const colors = COLORMAPS[legend.colormap] ?? COLORMAPS.rdylgn;
  return (
    <div className="legend-entry">
      <div className="legend-title">{layer.title}</div>
      <div className="legend-bar" style={{ background: `linear-gradient(to right, ${colors.join(", ")})` }} />
      <div className="legend-scale">
        <span>{legend.min}</span>
        <span>{legend.max}</span>
      </div>
      <div className="legend-scale muted">
        <span>{legend.low}</span>
        <span>{legend.high}</span>
      </div>
    </div>
  );
}

function Categories({ layer }) {
  return (
    <div className="legend-entry">
      <div className="legend-title">{layer.title}</div>
      {layer.legend.categories.map((category) => (
        <div className="legend-category" key={category.label}>
          <span className="swatch" style={{ background: category.color }} />
          {category.label}
        </div>
      ))}
    </div>
  );
}

export function LegendEntry({ layer }) {
  if (!layer.legend) return null;
  return layer.legend.categories ? <Categories layer={layer} /> : <Gradient layer={layer} />;
}

export default function Legend({ layers }) {
  const withLegend = layers.filter((layer) => layer.legend);
  if (!withLegend.length) return null;
  return (
    <div className="floating legend">
      {withLegend.map((layer) => (
        <LegendEntry key={layer.id} layer={layer} />
      ))}
    </div>
  );
}
