async function request(options) {
  const response = await fetch("/api/split", options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Error ${response.status}`);
  }
  return response.json();
}

export const fetchSplit = () => request();
export const createSplit = () => request({ method: "POST" });
