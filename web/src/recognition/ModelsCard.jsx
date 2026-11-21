import { formatMonth, formatNumber } from "../format.js";

const percent = (share) => `${formatNumber(share * 100, 1)} %`;
const decimal = (value) => formatNumber(value, 2);
const metric = (value) => formatNumber(value, 3);

function Swatch({ info }) {
  return (
    <>
      <span className="swatch" style={{ background: info.color }} />
      {info.title}
    </>
  );
}

function RuleNode({ node, classes }) {
  if (node.leaf) {
    return (
      <span>
        <Swatch info={classes[node.class]} /> <span className="muted">({formatNumber(node.pixels)} píxeles)</span>
      </span>
    );
  }
  const missing = node.missing_goes === "yes" ? "Sí" : "No";
  return (
    <>
      <span>
        ¿{node.index} de {formatMonth(node.month)} ≤ {decimal(node.threshold)}?{" "}
        <span className="muted">(si no hay dato, va por {missing})</span>
      </span>
      <ul className="model-rule">
        <li>
          Sí → <RuleNode node={node.yes} classes={classes} />
        </li>
        <li>
          No → <RuleNode node={node.no} classes={classes} />
        </li>
      </ul>
    </>
  );
}

function ClassMetrics({ result, classes, target }) {
  return (
    <table className="training-months model-table">
      <thead>
        <tr className="muted">
          <td />
          <td>Precisión</td>
          <td>Recall</td>
          <td>F1</td>
        </tr>
      </thead>
      <tbody>
        {Object.entries(result.per_class).map(([name, metrics]) => (
          <tr key={name}>
            <td>
              <Swatch info={classes[name]} />
            </td>
            <td>{metric(metrics.precision)}</td>
            <td>{metric(metrics.recall)}</td>
            <td className={metrics.meets_target === false ? "warning" : ""}>
              {metric(metrics.f1)}
              {metrics.meets_target === true && " ✓"}
              {metrics.meets_target === false && ` < ${decimal(target)}`}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Confusion({ confusion, classes }) {
  return (
    <table className="training-months model-table">
      <thead>
        <tr className="muted">
          <td>Mapa ↓ · modelo →</td>
          {confusion.labels.map((name) => (
            <td key={name}>{classes[name].title}</td>
          ))}
        </tr>
      </thead>
      <tbody>
        {confusion.matrix.map((row, rowNumber) => (
          <tr key={confusion.labels[rowNumber]}>
            <td>
              <Swatch info={classes[confusion.labels[rowNumber]]} />
            </td>
            {row.map((count, column) => (
              <td key={column} className={column === rowNumber ? "model-hit" : ""}>
                {formatNumber(count)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Rounds({ rounds, classes }) {
  return (
    <details className="training-legend">
      <summary>Resultado de cada ronda</summary>
      <table className="training-months model-table">
        <thead>
          <tr className="muted">
            <td>Ronda</td>
            <td>Prueba</td>
            <td>Entrena</td>
            <td>Franja</td>
            {Object.keys(rounds[0].f1).map((name) => (
              <td key={name}>F1 {classes[name].title}</td>
            ))}
          </tr>
        </thead>
        <tbody>
          {rounds.map((item) => (
            <tr key={item.round}>
              <td>{item.round}</td>
              <td>{formatNumber(item.test)}</td>
              <td>{formatNumber(item.train)}</td>
              <td>{formatNumber(item.excluded)}</td>
              {Object.values(item.f1).map((value, column) => (
                <td key={column}>{decimal(value)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="hint">
        Prueba: píxeles de los bloques que se miden en esa ronda. Franja: píxeles que quedan fuera del entrenamiento por estar
        cerca de los de prueba.
      </p>
    </details>
  );
}

export default function ModelsCard({ models, classes }) {
  const { evaluation } = models;
  const targets = evaluation.targets.map((name) => classes[name].title).join(" y ");
  return (
    <>
      <p className="hint">
        Medición por bloques: la zona se corta en cuadrados de {formatNumber(evaluation.block_size_m / 1000)} km que se
        turnan en {evaluation.folds} rondas; en cada una el modelo aprende con unos y se mide con otros, dejando una franja de{" "}
        {formatNumber(evaluation.buffer_m)} m entre ambos. Meta: F1 de {decimal(evaluation.target_f1)} o más en {targets}.
      </p>
      {!models.available && (
        <p className="hint">
          Todavía no hay modelos medidos. Ejecutá: <code>{models.command}</code>
        </p>
      )}
      {models.results.map((result) => (
        <div key={result.model} className="model-result">
          <h4>{result.title}</h4>
          <p className="hint">{result.description}</p>
          <p className="hint">
            Acierto global {percent(result.accuracy)} · F1 promedio {decimal(result.macro_f1)} · {result.evaluation.blocks}{" "}
            bloques · {result.columns} variables
          </p>
          <ClassMetrics result={result} classes={classes} target={result.evaluation.target_f1} />
          <p className="hint">Con qué se confunde cada clase (en diagonal, los aciertos):</p>
          <Confusion confusion={result.confusion} classes={classes} />
          {result.rule && (
            <details className="training-legend" open>
              <summary>La regla (entrenada con todos los píxeles)</summary>
              <div className="model-rule-root">
                <RuleNode node={result.rule} classes={classes} />
              </div>
            </details>
          )}
          <Rounds rounds={result.rounds} classes={classes} />
        </div>
      ))}
    </>
  );
}
