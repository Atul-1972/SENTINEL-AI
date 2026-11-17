import test from "node:test";
import assert from "node:assert/strict";
import { number, percent, trafficSeries } from "../lib/format.js";

test("unavailable metrics remain distinct from measured zero", () => {
  assert.equal(number(null), "—");
  assert.equal(number(0), "0");
  assert.equal(percent(undefined), "—");
  assert.equal(percent(0), "0.00%");
  assert.equal(percent(0.9985), "99.85%");
});

test("submission chart pads only unrecorded hours with zero", () => {
  const result = trafficSeries([
    { hour_utc: "2026-11-17T14:00:00Z", flows: 4 },
    { hour_utc: "2026-11-17T16:00:00Z", flows: 7 },
  ]);
  assert.equal(result.length, 12);
  assert.equal(result.at(-1).time, "2026-11-17T16:00:00.000Z");
  assert.equal(result.at(-2).flows, 0);
  assert.equal(result.at(-3).flows, 4);
  assert.equal(
    result.reduce((sum, item) => sum + item.flows, 0),
    11,
  );
});

test("empty history produces an empty chart rather than a fabricated time series", () =>
  assert.deepEqual(trafficSeries([]), []));
