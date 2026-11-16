import { useState } from "react";

const ROLE_LABELS = [
  ["entrenamiento", "Entrenamiento"],
  ["prueba", "Prueba"],
  ["excluida", "Excluidas (cruzan)"],
];

function classCounts(counts) {
  return Object.entries(counts)
    .map(([clase, total]) => `${clase} ${total}`)
    .join(" · ");
}

export default function SplitPanel({ split, showBlocks, onToggleBlocks, onCreate }) {
  const [confirming, setConfirming] = useState(false);

  if (!split) return null;

  if (!split.created) {
    return (
      <>
        <h3>Partición de prueba</h3>
        <div className="buttons">
          <button
            onClick={() => {
              if (confirming) {
                setConfirming(false);
                onCreate();
              } else {
                setConfirming(true);
              }
            }}
            onBlur={() => setConfirming(false)}
          >
            {confirming ? "Confirmar: crear y congelar" : "Crear partición en bloques"}
          </button>
        </div>
        <p className="hint">Reserva bloques de 500 m solo para prueba. Una vez creada, se congela.</p>
      </>
    );
  }

  const { summary } = split;
  return (
    <>
      <h3>Partición de prueba</h3>
      <div className="buttons">
        <button className={showBlocks ? "active" : ""} onClick={onToggleBlocks}>
          {showBlocks ? "Bloques: visibles" : "Bloques: ocultos"}
        </button>
      </div>
      <p className="hint">
        Bloques de prueba: {summary.blocks_test} de {summary.blocks_total} (
        {Math.round(summary.test_pixel_share * 100)} % del área etiquetada). En rojo, de prueba.
      </p>
      {ROLE_LABELS.map(([role, label]) => (
        <p className="hint" key={role}>
          {label}: {classCounts(summary.labels[role])}
        </p>
      ))}
      <p className="hint">
        Aptas (confianza alta, 1 ha o más) — entrenamiento: {classCounts(summary.apt_labels.entrenamiento)}; prueba:{" "}
        {classCounts(summary.apt_labels.prueba)}.
      </p>
    </>
  );
}
