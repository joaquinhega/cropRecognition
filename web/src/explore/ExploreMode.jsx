import { useEffect, useMemo, useState } from "react";
import { MapContainer, Rectangle, TileLayer, ZoomControl } from "react-leaflet";
import { areaParams, getJson } from "../api.js";
import { CLEAN_CLOUD_PERCENT, bboxToBounds, formatDate, isoDaysAgo, plural, todayIso } from "../format.js";
import BaseLayers, { MAX_ZOOM } from "../map/BaseLayers.jsx";
import { CursorPosition, FitBounds, RectangleDrawer } from "../map/MapHelpers.jsx";
import ClimateCard from "./ClimateCard.jsx";
import LayersPanel from "./LayersPanel.jsx";
import Legend from "./Legend.jsx";
import SearchPanel from "./SearchPanel.jsx";
import Timeline from "./Timeline.jsx";

const DEFAULT_LAYERS = ["rgb"];
const DEFAULT_OPACITY = 0.9;
const AREA_STYLE = { color: "#ffffff", weight: 1.5, dashArray: "6 6", fill: false };
const SEARCHABLE_KINDS = ["imagen", "radar"];
const LOCAL_SOURCE = "local";

const bySourceFirst = (a, b) => (a.source === LOCAL_SOURCE) - (b.source === LOCAL_SOURCE) || a.title.localeCompare(b.title);

function groupByDate(items) {
  const groups = new Map();
  for (const item of items) {
    const group = groups.get(item.date) ?? { date: item.date, items: [], cloud: null };
    group.items.push(item);
    if (item.cloud_cover !== null && item.cloud_cover !== undefined) {
      group.cloud = group.cloud === null ? item.cloud_cover : Math.min(group.cloud, item.cloud_cover);
    }
    groups.set(item.date, group);
  }
  return [...groups.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export default function ExploreMode({ zones, sources, collections, onCollectionsChange, infoTarget, onLayerCount }) {
  const defaultZone = zones.zones.find((zone) => zone.id === zones.default_zone);
  const defaults = sources.search_defaults;
  const imagerySources = sources.sources.filter((source) => SEARCHABLE_KINDS.includes(source.kind));
  const imageryCollections = collections.filter((collection) => collection.layers.length).sort(bySourceFirst);

  const [area, setArea] = useState({ ...defaultZone, area_km2: null });
  const [drawing, setDrawing] = useState(false);
  const [period, setPeriod] = useState({ start: isoDaysAgo(defaults.days), end: todayIso() });
  const [maxCloud, setMaxCloud] = useState(defaults.max_cloud_cover);
  const [selectedSources, setSelectedSources] = useState(
    imagerySources.filter((source) => source.status === "activa").map((source) => source.id),
  );
  const [collectionId, setCollectionId] = useState(imageryCollections[0]?.id ?? null);
  const [activeLayers, setActiveLayers] = useState(DEFAULT_LAYERS);
  const [opacity, setOpacity] = useState(DEFAULT_OPACITY);
  const [items, setItems] = useState([]);
  const [selectedDate, setSelectedDate] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchResult, setSearchResult] = useState(null);
  const [climate, setClimate] = useState(null);
  const [climateState, setClimateState] = useState({ loading: false, error: null });
  const [message, setMessage] = useState(null);
  const [collapsed, setCollapsed] = useState({ layers: false, search: false, climate: true });

  const collection = imageryCollections.find((item) => item.id === collectionId);
  const toggleCollapsed = (key) => setCollapsed((current) => ({ ...current, [key]: !current[key] }));

  async function loadItems() {
    if (!collectionId) return;
    try {
      const body = await getJson("/catalog/items", {
        ...areaParams(area),
        start: period.start,
        end: period.end,
        collections: collectionId,
      });
      setArea((current) => ({ ...current, area_km2: body.area.area_km2 }));
      setItems(body.items);
      setMessage(null);
    } catch (failure) {
      setItems([]);
      setMessage(failure.message);
    }
  }

  useEffect(() => {
    loadItems();
  }, [area.id, area.bbox.join(","), period.start, period.end, collectionId]);

  const dates = useMemo(
    () => groupByDate(items).filter((entry) => entry.cloud === null || entry.cloud <= maxCloud),
    [items, maxCloud],
  );

  useEffect(() => {
    if (!dates.some((entry) => entry.date === selectedDate)) {
      const clean = dates.filter((entry) => entry.cloud !== null && entry.cloud < CLEAN_CLOUD_PERCENT);
      const latest = (clean.length ? clean : dates).at(-1);
      setSelectedDate(latest ? latest.date : null);
      setPlaying(false);
    }
  }, [dates]);

  useEffect(() => {
    setClimate(null);
    setClimateState({ loading: false, error: null });
  }, [area.id, area.bbox.join(","), period.start, period.end]);

  const layers = (collection?.layers ?? []).filter((layer) => activeLayers.includes(layer.id));
  useEffect(() => onLayerCount(layers.length), [layers.length]);
  const current = dates.find((entry) => entry.date === selectedDate);

  function chooseZone(zoneId) {
    const zone = zones.zones.find((item) => item.id === zoneId);
    if (zone) setArea({ ...zone, area_km2: null });
  }

  function chooseCollection(id) {
    setCollectionId(id);
    const available = imageryCollections.find((item) => item.id === id)?.layers.map((layer) => layer.id) ?? [];
    setActiveLayers((current) => {
      const kept = current.filter((layer) => available.includes(layer));
      return kept.length ? kept : available.slice(0, 1);
    });
  }

  function toggleLayer(layerId) {
    setActiveLayers((current) =>
      current.includes(layerId) ? current.filter((id) => id !== layerId) : [...current, layerId],
    );
  }

  async function search() {
    setSearching(true);
    setSearchResult(null);
    try {
      const body = await getJson("/search", {
        ...areaParams(area),
        start: period.start,
        end: period.end,
        max_cloud_cover: maxCloud,
        sources: selectedSources.join(","),
      });
      setSearchResult(body);
      onCollectionsChange();
      await loadItems();
    } catch (failure) {
      setMessage(failure.message);
    } finally {
      setSearching(false);
    }
  }

  async function loadClimate() {
    setClimateState({ loading: true, error: null });
    try {
      setClimate(await getJson("/climate", { ...areaParams(area), start: period.start, end: period.end }));
      setClimateState({ loading: false, error: null });
      onCollectionsChange();
    } catch (failure) {
      setClimateState({ loading: false, error: failure.message });
    }
  }

  const headline = collection
    ? dates.length
      ? `${area.name}: ${plural(dates.length, "fecha", "fechas")} de ${collection.title} entre ${formatDate(dates[0].date)} y ${formatDate(dates[dates.length - 1].date)}.`
      : `${area.name}: todavía no hay imágenes de ${collection.title} en el catálogo para este período.`
    : "Todavía no hay colecciones en el catálogo. Buscá en las fuentes para empezar.";

  return (
    <>
      <LayersPanel
        headline={headline}
        collections={imageryCollections}
        collectionId={collectionId}
        onCollection={chooseCollection}
        activeLayers={activeLayers}
        onToggleLayer={toggleLayer}
        opacity={opacity}
        onOpacity={setOpacity}
        collapsed={collapsed.layers}
        onCollapse={() => toggleCollapsed("layers")}
      />

      <div className="right-column">
        <SearchPanel
          zones={zones.zones}
          area={area}
          onZone={chooseZone}
          drawing={drawing}
          onDraw={() => setDrawing((value) => !value)}
          period={period}
          onPeriod={setPeriod}
          maxCloud={maxCloud}
          onMaxCloud={setMaxCloud}
          imagerySources={imagerySources}
          selectedSources={selectedSources}
          onToggleSource={(id) =>
            setSelectedSources((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]))
          }
          searching={searching}
          onSearch={search}
          result={searchResult}
          collapsed={collapsed.search}
          onCollapse={() => toggleCollapsed("search")}
        />
        <ClimateCard
          climate={climate}
          loading={climateState.loading}
          error={climateState.error}
          onLoad={loadClimate}
          collapsed={collapsed.climate}
          onCollapse={() => toggleCollapsed("climate")}
        />
      </div>

      {message && <div className="toast warning-toast">{message}</div>}

      <Timeline
        period={period}
        dates={dates}
        selected={selectedDate}
        onSelect={setSelectedDate}
        playing={playing}
        onPlaying={setPlaying}
      />
      <Legend layers={layers} />

      <MapContainer className="map" bounds={bboxToBounds(area.bbox)} maxZoom={MAX_ZOOM} zoomControl={false}>
        <BaseLayers />
        <ZoomControl position="bottomright" />
        <FitBounds bbox={area.bbox} padding={[80, 80]} />
        <CursorPosition target={infoTarget} />
        <Rectangle bounds={bboxToBounds(area.bbox)} pathOptions={AREA_STYLE} interactive={false} />
        {current &&
          layers.flatMap((layer, layerIndex) =>
            current.items.filter((item) => item.layers[layer.id]).map((item) => (
              <TileLayer
                key={`${item.collection}-${item.id}-${layer.id}`}
                url={item.layers[layer.id]}
                bounds={item.bbox ? bboxToBounds(item.bbox) : undefined}
                opacity={opacity}
                maxZoom={MAX_ZOOM}
                zIndex={10 + layerIndex}
                attribution={collection?.attribution}
              />
            )),
          )}
        <RectangleDrawer
          drawing={drawing}
          onCreated={(bbox) => setArea({ id: null, name: "Recuadro dibujado", bbox, area_km2: null })}
          onFinish={() => setDrawing(false)}
        />
      </MapContainer>
    </>
  );
}
