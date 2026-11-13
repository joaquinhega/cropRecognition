import { useEffect, useState } from "react";

export default function App() {
  const [status, setStatus] = useState("verificando...");

  useEffect(() => {
    fetch("/api/health")
      .then((response) => response.json())
      .then((data) => setStatus(data.status === "ok" ? "conectada" : "con errores"))
      .catch(() => setStatus("sin conexión"));
  }, []);

  return (
    <main>
      <h1>cropRecognition</h1>
      <p>API: {status}</p>
    </main>
  );
}
