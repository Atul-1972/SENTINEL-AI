export const number = (value) =>
  value == null ? "—" : new Intl.NumberFormat("en-IN").format(value);
export const percent = (value, digits = 2) =>
  value == null ? "—" : `${(value * 100).toFixed(digits)}%`;
export const score = (value) =>
  value == null ? "—" : Number(value).toFixed(4);
export const timestamp = (value) =>
  value
    ? new Date(value).toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "—";
export const shortTime = (value) =>
  value
    ? new Date(value).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "—";
export const bytes = (value) =>
  value == null
    ? "—"
    : value > 1e6
      ? `${(value / 1e6).toFixed(1)} MB`
      : `${(value / 1000).toFixed(1)} KB`;

export function download(content, name, type = "application/json") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function trafficSeries(buckets = []) {
  if (!buckets.length) return [];
  const end = Math.max(...buckets.map((row) => Date.parse(row.hour_utc)));
  const values = new Map(
    buckets.map((row) => [Date.parse(row.hour_utc), row.flows]),
  );
  return Array.from({ length: 12 }, (_, index) => {
    const time = end - (11 - index) * 3600000;
    return {
      time: new Date(time).toISOString(),
      hour: new Date(time).toLocaleTimeString("en-IN", {
        hour: "numeric",
        hour12: true,
      }),
      flows: values.get(time) || 0,
    };
  });
}
