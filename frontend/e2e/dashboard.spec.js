import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";

const report = (name) => path.resolve("..", "reports", name);

test("real API dashboard shows saved metrics, navigation and honest integration states", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: /API Connected/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Security overview", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await page.screenshot({
    path: report("frontend-overview.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("link", { name: "Model performance", exact: true })
    .click();
  await expect(
    page.getByRole("table", { name: "test confusion matrix" }),
  ).toBeVisible();
  await expect(page.getByText("99.85%", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Validation", exact: true }).click();
  await expect(
    page.getByRole("table", { name: "validation confusion matrix" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "MLOps monitoring", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Data drift · Evidently" }),
  ).toBeVisible();
  await expect(
    page.getByText("Not configured", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Saved training candidates" }),
  ).toBeVisible();
  await expect(
    page.getByText("XGBoost baseline", { exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("CSV upload performs real batch predictions, filters, exports and opens saved flow details", async ({
  page,
  request,
}) => {
  const before = await (
    await request.get("http://127.0.0.1:8001/stats")
  ).json();
  await page.goto("/#detection");
  await expect(
    page.getByRole("button", { name: /API Connected/ }),
  ).toBeVisible();
  await page
    .getByLabel("Upload traffic CSV")
    .setInputFiles(path.resolve("..", "data/sample/historical_demo_flows.csv"));
  await expect(
    page.getByRole("button", { name: "Analyze flows", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Analyze flows", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Analysis complete", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".data-table tbody tr")).toHaveCount(10);
  await page.getByRole("button", { name: "Attack", exact: true }).click();
  await expect(page.locator(".data-table tbody tr")).toHaveCount(5);
  await page.getByRole("button", { name: "All flows", exact: true }).click();
  const downloaded = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export results", exact: true })
    .click();
  const file = await downloaded;
  const saved = report("frontend-predictions.csv");
  await file.saveAs(saved);
  expect(await readFile(saved, "utf8")).toContain(
    "model_probability_uncalibrated",
  );
  await page
    .getByRole("button", { name: /Inspect flow/ })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Input features" }),
  ).toBeVisible();
  await page.getByLabel("Search input features").fill("Flow Bytes/s");
  await expect(page.locator(".feature-list > div")).toHaveCount(1);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog").first()).not.toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: report("frontend-detection.png"),
    fullPage: true,
    animations: "disabled",
  });
  const after = await (await request.get("http://127.0.0.1:8001/stats")).json();
  expect(after.total_flows).toBe(before.total_flows + 10);
});

test("mobile navigation works without page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: /API Connected/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("link", { name: "Threat analysis", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Threat analysis", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.goto("/#overview");
  await expect(
    page.getByRole("button", { name: /API Connected/ }),
  ).toBeVisible();
  await page.screenshot({
    path: report("frontend-mobile.png"),
    fullPage: true,
    animations: "disabled",
  });
});

test("offline API state is visible and does not fabricate zero-valued metrics", async ({
  page,
}) => {
  await page.route("**/api/**", (route) => route.abort());
  await page.goto("/");
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(
    page.getByText("The API connection needs attention"),
  ).toBeVisible();
  await expect(page.locator(".metric-value").first()).toHaveText("—");
  await expect(
    page.getByRole("button", { name: /API Disconnected/ }),
  ).toBeVisible();
});

test("batch-boundary fixture stops cleanly and resumes only remaining records", async ({ page }) => {
  let releaseFirst;
  let firstRequested;
  const requested = new Promise(resolve => { firstRequested = resolve; });
  const held = new Promise(resolve => { releaseFirst = resolve; });
  const batchSizes = [];
  // Test-only response fixture: no fabricated rows are written to the actual database.
  await page.route('**/api/predict-batch', async route => {
    const flows = route.request().postDataJSON().flows;
    const start = batchSizes.reduce((sum, count) => sum + count, 0);
    batchSizes.push(flows.length);
    if (batchSizes.length === 1) { firstRequested(); await held; }
    await route.fulfill({ json: { count: flows.length, results: flows.map((flow, index) => ({
      id: 900000 + start + index, created_at: '2026-11-17T18:00:00Z',
      predicted_class: 'BENIGN', predicted_attack_category: null,
      confidence: .9, confidence_type: 'uncalibrated_model_probability', attack_probability: .1,
      anomaly_score: -.1, anomaly_flag: false, risk_level: 'LOW', risk_score: 0,
      model_version: 'browser-test-fixture', source: flow.source,
    })) } });
  });
  await page.goto('/#detection');
  await expect(page.getByRole('button', { name: /API Connected/ })).toBeVisible();
  const original = await readFile(path.resolve('..', 'data/sample/historical_demo_flows.csv'), 'utf8');
  const lines = original.trim().split(/\r?\n/);
  const csv = lines[0] + '\n' + (lines[1] + '\n').repeat(1001);
  await page.getByLabel('Upload traffic CSV').setInputFiles({ name: 'batch-boundary-fixture.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
  await page.getByRole('button', { name: 'Analyze flows', exact: true }).click();
  await requested;
  await page.getByRole('button', { name: 'Stop after batch', exact: true }).click();
  releaseFirst();
  await expect(page.getByRole('button', { name: 'Resume analysis', exact: true })).toBeEnabled();
  expect(batchSizes).toEqual([1000]);
  await page.getByRole('button', { name: 'Resume analysis', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Analysis complete', exact: true })).toBeVisible();
  expect(batchSizes).toEqual([1000, 1]);
  await expect(page.getByText('1,001 actual predictions returned by the API', { exact: true })).toBeVisible();
});
