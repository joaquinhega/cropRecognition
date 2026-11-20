import { formatDate, plural } from "./format.js";
import { BASE_LAYERS } from "./map/BaseLayers.jsx";

function CatalogLine({ catalog }) {
  if (!catalog) return <span className="muted">Sin ítems en el catálogo todavía.</span>;
  return (
    <span>
      {plural(catalog.items, "ítem", "ítems")} en el catálogo, del {formatDate(catalog.first)} al {formatDate(catalog.last)}.
    </span>
  );
}

function Collection({ collection }) {
  return (
    <div className="source-collection">
      <div className="source-tag">
        {collection.title} · {collection.resolution}
      </div>
      <dl>
        <dt>Licencia</dt>
        <dd>
          {collection.license_url ? (
            <a href={collection.license_url} target="_blank" rel="noreferrer">
              {collection.license}
            </a>
          ) : (
            collection.license
          )}
        </dd>
        <dt>Cómo citarla</dt>
        <dd>{collection.attribution}</dd>
        <dt>Límites</dt>
        <dd>{collection.limits}</dd>
        <dt>Catálogo propio</dt>
        <dd>
          <CatalogLine catalog={collection.catalog} />
        </dd>
      </dl>
    </div>
  );
}

function Source({ source }) {
  return (
    <article className={`source-card ${source.status}`}>
      <header>
        <h3>{source.name}</h3>
        <span className={`badge ${source.status}`}>{source.status}</span>
      </header>
      <p className="muted">
        {source.provider} · {source.kind} · {source.cost}
        {source.requires_account ? " · requiere cuenta" : " · sin cuenta"}
      </p>
      {source.note && <p className="hint">{source.note}</p>}
      {source.collections.map((collection) => (
        <Collection key={collection.catalog_id} collection={collection} />
      ))}
      {!source.collections.length && source.resolution && (
        <p className="hint">
          Resolución: {source.resolution} · Licencia: {source.license}
        </p>
      )}
    </article>
  );
}

export default function SourcesDrawer({ sources, onClose }) {
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(event) => event.stopPropagation()}>
        <header className="panel-header">
          <h2>Fuentes y límites</h2>
          <button className="icon-button" onClick={onClose} title="Cerrar">
            ×
          </button>
        </header>
        <p className="hint">
          Cada dato del mapa sale de una de estas fuentes. Las postergadas todavía no se consultan.
        </p>
        {sources.catalog_error && <p className="warning">{sources.catalog_error}</p>}
        {sources.sources.map((source) => (
          <Source key={source.id} source={source} />
        ))}

        <article className="source-card">
          <header>
            <h3>{sources.local.title}</h3>
            <span className="badge activa">local</span>
          </header>
          <p className="hint">
            <CatalogLine catalog={sources.local.catalog} />
          </p>
        </article>

        <article className="source-card">
          <header>
            <h3>Mapas base</h3>
          </header>
          <p className="hint">Solo sirven de referencia visual: no se usan para medir ni para entrenar.</p>
          <ul className="plain">
            {BASE_LAYERS.map((layer) => (
              <li key={layer.id} dangerouslySetInnerHTML={{ __html: `${layer.name}: ${layer.attribution}` }} />
            ))}
          </ul>
        </article>
      </aside>
    </div>
  );
}
