export async function fetchSeriesSummary() {
  const response = await fetch("/api/series/summary");
  if (!response.ok) throw new Error(`Error ${response.status}`);
  return response.json();
}
