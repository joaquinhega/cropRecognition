import { useState } from "react";
import { isPending, isUndoubted } from "./labelsApi.js";

export default function ReviewPanel({ labels, selectedId, onGo, onReviewMany }) {
  const [confirming, setConfirming] = useState(false);
  const pending = labels.filter(isPending);
  const undoubted = labels.filter(isUndoubted);
  const reviewed = labels.filter((label) => label.estado === "revisada").length;
  const position = pending.findIndex((label) => label.id === selectedId);

  function go(step) {
    const target = pending[(position + step + pending.length) % pending.length];
    onGo(target.id);
  }

  function reviewUndoubted() {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    onReviewMany(undoubted.map((label) => label.id));
  }

  return (
    <>
      <h3>Revisión</h3>
      <p className="hint">
        Revisadas: {reviewed} · Dudosas pendientes: {pending.length} · Sin dudas pendientes: {undoubted.length}
      </p>
      <div className="buttons">
        {position < 0 ? (
          <button disabled={!pending.length} onClick={() => onGo(pending[0].id)}>
            Revisar dudosas ({pending.length})
          </button>
        ) : (
          <>
            <p className="hint">
              Dudosa {position + 1} de {pending.length}
            </p>
            <button disabled={pending.length < 2} onClick={() => go(-1)}>
              Anterior
            </button>
            <button disabled={pending.length < 2} onClick={() => go(1)}>
              Siguiente
            </button>
          </>
        )}
        <button disabled={!undoubted.length} onClick={reviewUndoubted} onBlur={() => setConfirming(false)}>
          {confirming
            ? `Confirmar: marcar ${undoubted.length} como revisadas`
            : `Marcar como revisadas las ${undoubted.length} sin dudas`}
        </button>
      </div>
    </>
  );
}
