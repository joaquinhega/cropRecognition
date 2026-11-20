const SOURCE_NAMES = { "earth-search": "Earth Search", "nasa-power": "NASA POWER", "conae-saocom": "CONAE", local: "Subproyecto A" };

export default function SourceTag({ collection }) {
  const parts = [collection.title, collection.resolution, SOURCE_NAMES[collection.source] ?? collection.source];
  return <div className="source-tag">{parts.filter(Boolean).join(" · ")}</div>;
}
