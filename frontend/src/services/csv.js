import Papa from "papaparse";

export const MAX_ROWS = 20000;
export const MAX_FILE_BYTES = 25 * 1024 * 1024;
const NUMBER = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/;
const MISSING = /^(?:nan|na|n\/a|null|none|[+-]?(?:inf|infinity))?$/i;

export function normalizeHeaders(header) {
  const trimmed = header.map((name) =>
    String(name)
      .replace(/^\uFEFF/, "")
      .trim(),
  );
  if (trimmed.some((name) => !name))
    throw new Error("The CSV has an empty column name.");
  const reserved = new Set(trimmed);
  const used = new Set();
  const renamed = [];
  const names = trimmed.map((name, index) => {
    let result = name;
    let suffix = 2;
    if (used.has(name)) {
      result = `${name}__duplicate_${suffix}`;
      while (used.has(result) || reserved.has(result))
        result = `${name}__duplicate_${++suffix}`;
      renamed.push({ position: index + 1, original: name, renamed: result });
    }
    used.add(result);
    return result;
  });
  return { names, renamed };
}

export function parseFlowCsv(text, featureNames) {
  if (!featureNames?.length)
    throw new Error("Connect to the API to load the model schema first.");
  const parsed = Papa.parse(text, {
    skipEmptyLines: "greedy",
    preview: MAX_ROWS + 2,
  });
  if (parsed.errors.length)
    throw new Error(`CSV could not be read: ${parsed.errors[0].message}`);
  if (parsed.meta.truncated || parsed.data.length > MAX_ROWS + 1)
    throw new Error(
      `Choose a CSV with at most ${MAX_ROWS.toLocaleString()} flows. Use the prepared subset, not the full raw dataset.`,
    );
  if (parsed.data.length < 2)
    throw new Error("The CSV needs a header and at least one flow.");
  const rawHeader = parsed.data[0];
  if (
    rawHeader.filter((name) => name.trim().toLowerCase() === "label").length > 1
  )
    throw new Error(
      "Multiple Label columns are ambiguous. Keep a single target column.",
    );
  const { names, renamed } = normalizeHeaders(rawHeader);
  const missing = featureNames.filter((name) => !names.includes(name));
  if (missing.length)
    throw new Error(
      `Missing ${missing.length} required column(s): ${missing.slice(0, 4).join(", ")}${missing.length > 4 ? "…" : ""}`,
    );
  const positions = featureNames.map((name) => names.indexOf(name));
  const labelPosition = names.findIndex(
    (name) => name.toLowerCase() === "label",
  );
  let convertedMissing = 0;
  const records = parsed.data.slice(1).map((row, index) => {
    if (row.length !== names.length)
      throw new Error(
        `Record ${index + 1} has ${row.length} cells; expected ${names.length}. Check CSV separators and quotes.`,
      );
    const features = {};
    for (let i = 0; i < featureNames.length; i++) {
      const raw = row[positions[i]].trim();
      if (MISSING.test(raw)) {
        features[featureNames[i]] = null;
        convertedMissing++;
      } else {
        const value = NUMBER.test(raw) ? Number(raw) : NaN;
        if (!Number.isFinite(value) || Math.abs(value) > 3.4028234663852886e38)
          throw new Error(
            `Record ${index + 1}, ${featureNames[i]}: expected a finite numeric value.`,
          );
        features[featureNames[i]] = value;
      }
    }
    if (Object.values(features).every((value) => value === null))
      throw new Error(`Record ${index + 1} has no usable feature values.`);
    return {
      features,
      knownLabel: labelPosition < 0 ? null : row[labelPosition].trim(),
      row: index + 1,
    };
  });
  return {
    records,
    renamed,
    convertedMissing,
    ignoredColumns: names.filter(
      (name) => !featureNames.includes(name) && name.toLowerCase() !== "label",
    ),
  };
}

export function resultCsv(results) {
  return Papa.unparse(
    results.map((row) => ({
      record: row.input_row,
      prediction_id: row.id,
      predicted_class: row.predicted_class,
      known_label: row.known_label || "",
      risk_level: row.risk_level,
      risk_score: row.risk_score,
      model_probability_uncalibrated: row.confidence,
      attack_probability_uncalibrated: row.attack_probability,
      anomaly_flag: row.anomaly_flag,
      anomaly_score: row.anomaly_score,
      model_version: row.model_version,
      source: row.source,
      created_at: row.created_at,
    })),
    { escapeFormulae: true },
  );
}
