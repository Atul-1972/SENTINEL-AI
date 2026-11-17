export const API_TARGET = __SENTINEL_API_TARGET__;

async function request(path, options = {}, accepted = [200]) {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
    signal: AbortSignal.timeout(45000),
  });
  const data = await response.json().catch(() => null);
  if (!accepted.includes(response.status)) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message ||
          (Array.isArray(detail) ? detail[0]?.msg : null) ||
          `API request failed (${response.status}).`;
    throw new Error(message);
  }
  if (data === null)
    throw new Error(
      "The API returned an unexpected response. Check the connection.",
    );
  return data;
}

export const api = {
  health: () => request("/health", {}, [200, 503]),
  stats: () => request("/stats"),
  modelInfo: () => request("/model-info"),
  alerts: () => request("/alerts?limit=100"),
  history: () => request("/predictions?limit=100"),
  detail: (id) => request(`/predictions/${id}`),
  predict: (flows) =>
    request("/predict-batch", {
      method: "POST",
      body: JSON.stringify({ flows }),
    }),
};
