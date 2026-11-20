import { useState } from "react";
import { LegendEntry } from "../../explore/Legend.jsx";
import SourceTag from "../../SourceTag.jsx";
import { formatDate, formatMonthLong, formatNumber, monthName } from "../../format.js";
import CampaignClimate from "./CampaignClimate.jsx";
import IndexChart from "./IndexChart.jsx";
import { campaignColors, flattenMonths, formatIndex, lowerFirst } from "./sheet.js";

const NO_IMAGE = "none";

function baselineText(comparison) {
  const count = comparison.earlier.length;
  const which = count === 1 ? `la campaña ${comparison.earlier[0].campaign}` : `las ${count} campañas anteriores`;
  return `promedio de ${monthName(comparison.month)} en ${which} (${formatIndex(comparison.baseline)})`;
}

/** Plain-language conclusion: latest month of the campaign in progress against the earlier ones. */
export function headlineText(comparison, info) {
  if (!comparison) return null;
  const name = lowerFirst(info.title);
  if (!comparison.month) return `Campaña ${comparison.campaign}: todavía no hay meses con dato de ${name}.`;
  const when = `${monthName(comparison.month)}${comparison.complete ? "" : " (mes en curso)"}`;
  const start = `Campaña ${comparison.campaign}, ${when}: ${name} ${formatIndex(comparison.value)}`;
  if (comparison.trend === null) return `${start}. No hay ${monthName(comparison.month)} con dato en campañas anteriores para comparar.`;
  if (comparison.trend === "similar") return `${start}, parecido al ${baselineText(comparison)}.`;
  const direction = comparison.trend === "above" ? "por encima" : "por debajo";
  const amount =
    comparison.percent !== null ? `${formatNumber(Math.abs(comparison.percent))} %` : formatIndex(Math.abs(comparison.difference));
  return `${start}, ${amount} ${direction} del ${baselineText(comparison)}.`;
}

function MonthCard({ month, index }) {
  if (!month) return null;
  const summary = month.indices?.[index];
  return (
    <p className="month-card">
      <strong>{formatMonthLong(month.month)}</strong>
      {summary
        ? ` · ${index} ${formatIndex(summary.mean)} (rango ${formatIndex(summary.p25)} a ${formatIndex(summary.p75)})`
        : ` · ${month.status_text}`}
      {month.scene && (
        <span className="muted">
          {" "}
          · imagen del {formatDate(month.scene.date)}
          {month.valid_share !== null && `, ${formatNumber(100 * month.valid_share)} % limpia`}
        </span>
      )}
    </p>
  );
}

export default function ParcelSheet({ sheet, selectedMonth, onSelectMonth, imageLayer, onImageLayer, collapsed, onCollapse }) {
  const [index, setIndex] = useState("NDVI");
  const { series, climate } = sheet;

  const header = (
    <header className="panel-header">
      <h2>Ficha{series ? ` · ${series.parcel.name}` : ""}</h2>
      <button className="icon-button" onClick={onCollapse} title={collapsed ? "Mostrar" : "Plegar"}>
        {collapsed ? "+" : "−"}
      </button>
    </header>
  );

  if (collapsed) return <section className="floating panel parcel-sheet collapsed">{header}</section>;

  const months = series ? flattenMonths(series) : [];
  const processed = months.length > 0;
  const month = months.find((entry) => entry.month === selectedMonth);
  const info = series?.indices[index];
  const colors = campaignColors(series?.campaigns.map((campaign) => campaign.campaign) ?? []);
  const layer = series?.layers.find((entry) => entry.id === imageLayer);

  return (
    <section className="floating panel parcel-sheet">
      {header}
      {sheet.loading && <p className="hint">Cargando la ficha…</p>}
      {sheet.error && <p className="warning">{sheet.error}</p>}
      {series && !processed && <p className="hint">Todavía no está procesada. Usá “Procesar parcela” para armar su ficha.</p>}

      {processed && (
        <>
          <p className="hint">
            {formatNumber(series.parcel.area_ha, 2)} ha · {series.campaigns.length} campañas, de{" "}
            {formatMonthLong(months[0].month)} a {formatMonthLong(months[months.length - 1].month)}
          </p>
          <p className="headline">{headlineText(series.comparison[index], info)}</p>

          <h3>Índice</h3>
          <div className="buttons segmented">
            {Object.entries(series.indices).map(([name, spec]) => (
              <button key={name} className={name === index ? "active" : ""} onClick={() => setIndex(name)} title={spec.title}>
                {name}
              </button>
            ))}
          </div>
          <p className="hint">
            <strong>{info.title}:</strong> {info.how_to_read}
          </p>

          <IndexChart series={series} index={index} colors={colors} selectedMonth={selectedMonth} onSelectMonth={onSelectMonth} />
          <div className="campaign-key small">
            {series.campaigns.map((campaign) => (
              <span key={campaign.campaign}>
                <span className="swatch" style={{ background: colors[campaign.campaign] }} />
                {campaign.campaign}
              </span>
            ))}
          </div>
          <p className="hint small">
            Línea: promedio de la parcela. Banda: rango de la mitad central de los píxeles en la campaña del mes elegido; si es
            ancha, la parcela no es pareja. Clic en un punto para ver ese mes en el mapa.
          </p>
          <MonthCard month={month} index={index} />
          <SourceTag collection={{ title: series.source.collection, resolution: series.source.resolution, source: "earth-search" }} />
          <p className="hint small">
            {series.rules.scene} {series.rules.statistics}
            {series.scenes && ` Imágenes del ${formatDate(series.scenes.first)} al ${formatDate(series.scenes.last)}.`}{" "}
            {series.source.attribution}.
          </p>

          <h3>Imagen en el mapa</h3>
          <div className="buttons segmented">
            {series.layers.map((entry) => (
              <button key={entry.id} className={entry.id === imageLayer ? "active" : ""} onClick={() => onImageLayer(entry.id)}>
                {entry.title}
              </button>
            ))}
            <button className={imageLayer === NO_IMAGE ? "active" : ""} onClick={() => onImageLayer(NO_IMAGE)}>
              Ninguna
            </button>
          </div>
          {layer && <p className="hint">{layer.how_to_read}</p>}
          {layer && <LegendEntry layer={layer} />}
          {!month?.scene && imageLayer !== NO_IMAGE && <p className="hint">Este mes no tiene imagen para mostrar.</p>}

          <h3>Clima</h3>
          {climate && (
            <CampaignClimate climate={climate} firstMonth={series.campaign_first_month} colors={colors} selectedMonth={selectedMonth} />
          )}
        </>
      )}
    </section>
  );
}
