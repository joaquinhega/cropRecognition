import { plural } from "../format.js";

export default function UploadResult({ result }) {
  return (
    <div className="upload-result">
      <p className="hint">
        {result.file}: {plural(result.created.length, "parcela guardada", "parcelas guardadas")}
        {result.rejected.length > 0 && `, ${plural(result.rejected.length, "rechazada", "rechazadas")}`}.
      </p>
      {result.rejected.length > 0 && (
        <ul className="warning">
          {result.rejected.map((item, index) => (
            <li key={index}>
              {item.name}: {item.reason}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
