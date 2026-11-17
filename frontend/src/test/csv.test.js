import test from "node:test";
import assert from "node:assert/strict";
import Papa from "papaparse";
import {
  MAX_ROWS,
  normalizeHeaders,
  parseFlowCsv,
  resultCsv,
} from "../services/csv.js";

const features = ["Flow Duration", "Flow Bytes/s"];

test("CSV parsing preserves numeric values, trims headers and keeps labels outside features", () => {
  const result = parseFlowCsv(
    "\uFEFF Flow Duration, Flow Bytes/s, Label\n-1,1.5e3,BENIGN\n0,2.5,DDoS",
    features,
  );
  assert.deepEqual(result.records[0].features, {
    "Flow Duration": -1,
    "Flow Bytes/s": 1500,
  });
  assert.equal(result.records[1].knownLabel, "DDoS");
  assert.equal(result.records[1].row, 2);
  assert.equal(Object.keys(result.records[0].features).length, 2);
});

test("repeated header suffixes cannot collide with existing columns", () => {
  const { names, renamed } = normalizeHeaders([
    " Fwd Header Length",
    "Fwd Header Length",
    "Fwd Header Length__duplicate_2",
  ]);
  assert.deepEqual(names, [
    "Fwd Header Length",
    "Fwd Header Length__duplicate_3",
    "Fwd Header Length__duplicate_2",
  ]);
  assert.equal(renamed.length, 1);
});

test("original duplicate CSV headers retain distinct feature values", () => {
  const expected = ["Fwd Header Length", "Fwd Header Length__duplicate_2"];
  const result = parseFlowCsv(
    "Fwd Header Length,Fwd Header Length\n10,99",
    expected,
  );
  assert.deepEqual(result.records[0].features, {
    "Fwd Header Length": 10,
    "Fwd Header Length__duplicate_2": 99,
  });
});

test("known missing and infinite values become null for saved preprocessing", () => {
  const result = parseFlowCsv(
    "Flow Duration,Flow Bytes/s\n1,Infinity\n2,NaN\n3,\n4,null",
    features,
  );
  assert.equal(result.convertedMissing, 4);
  assert.ok(
    result.records.every((row) => row.features["Flow Bytes/s"] === null),
  );
});

test("extra CSV metadata is excluded from API feature payloads", () => {
  const result = parseFlowCsv(
    "Flow Duration,Flow Bytes/s,Comment\n1,2,example",
    features,
  );
  assert.deepEqual(result.ignoredColumns, ["Comment"]);
  assert.deepEqual(Object.keys(result.records[0].features), features);
});

for (const [name, text, message] of [
  ["missing columns", "Other,Flow Bytes/s\n1,2", /Missing 1/],
  [
    "invalid numeric text",
    "Flow Duration,Flow Bytes/s\nword,2",
    /finite numeric/,
  ],
  [
    "oversized numeric values",
    "Flow Duration,Flow Bytes/s\n1e99,2",
    /finite numeric/,
  ],
  ["unequal cell counts", "Flow Duration,Flow Bytes/s\n1,2,3", /expected 2/],
  [
    "all missing inputs",
    "Flow Duration,Flow Bytes/s\nNaN,Infinity",
    /no usable/,
  ],
  [
    "ambiguous targets",
    "Flow Duration,Flow Bytes/s,Label, Label\n1,2,BENIGN,DDoS",
    /Multiple Label/,
  ],
  ["missing rows", "Flow Duration,Flow Bytes/s", /at least one flow/],
])
  test(`rejects ${name} before any prediction`, () =>
    assert.throws(() => parseFlowCsv(text, features), message));

test("a large file is rejected rather than silently taking its first records", () => {
  const text = "Flow Duration,Flow Bytes/s\n" + "1,2\n".repeat(MAX_ROWS + 1);
  assert.throws(() => parseFlowCsv(text, features), /at most 20,000/);
});

test("the full 20,000-row subset is accepted without truncation", () => {
  const text = "Flow Duration,Flow Bytes/s\n" + "1,2\n".repeat(MAX_ROWS);
  assert.equal(parseFlowCsv(text, features).records.length, MAX_ROWS);
});

test("result exports label probabilities and escape spreadsheet formulas", () => {
  const csv = resultCsv([
    {
      id: 1,
      input_row: 1,
      predicted_class: "ATTACK",
      known_label: "=1+1",
      confidence: 0.95,
      attack_probability: 0.95,
      anomaly_flag: false,
      anomaly_score: -0.1,
      model_version: "test",
      source: "historical",
    },
  ]);
  const result = Papa.parse(csv, { header: true }).data[0];
  assert.equal(result.model_probability_uncalibrated, "0.95");
  assert.equal(result.known_label, "'=1+1");
});
