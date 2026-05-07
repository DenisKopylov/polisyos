import { expect, test, type Page } from "@playwright/test";

import { readFixtureMetadata } from "./helpers/runtime-dashboard";

const FIXTURE_RUN_ID = "R_core_api_001";
const FIXTURE_PROMOTION_ID = "promotion_fixture_001";
const FIXTURE_METADATA = readFixtureMetadata();
const LIVE_STORAGE_KEY = "polisyos.runtime.disableLive";
const THEME_STORAGE_KEY = "polisyos.runtime.theme";
const INTERFACE_MODE_STORAGE_KEY = "polisyos.runtime.interface-mode";
const FIXTURE_DECISION_PACKET_ID = FIXTURE_METADATA.decision_packet_artifact_id;

async function expectPrintSnapshot(
  page: Page,
  {
    path,
    readyTestId,
    selector,
    snapshot,
  }: {
    path: string;
    readyTestId: string;
    selector: string;
    snapshot: string;
  },
) {
  await page.setViewportSize({ width: 794, height: 1123 });
  await page.emulateMedia({ media: "print" });
  await page.goto(path);
  await expect(page.getByTestId(readyTestId)).toBeVisible();
  await expect(page.locator(selector)).toBeVisible();
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
  await expect(page.locator(selector)).toHaveScreenshot(snapshot, {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 100,
  });
  await page.emulateMedia({ media: "screen" });
}

test.describe("runtime-dashboard visual baselines", () => {
  test.use({
    viewport: { width: 1440, height: 1200 },
  });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript((storageKey) => {
      window.localStorage.setItem(storageKey, "true");
    }, LIVE_STORAGE_KEY);
  });

  test("command center shell", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Command Center" }),
    ).toBeVisible();
    await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
      "command-center-shell.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("scenario composer dark theme", async ({ page }) => {
    await page.addInitScript((storageKey) => {
      window.localStorage.setItem(storageKey, "dark");
    }, THEME_STORAGE_KEY);
    await page.goto("/compose");
    await expect(
      page.getByRole("heading", { name: "Scenario Composer" }),
    ).toBeVisible();
    await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
      "scenario-composer-dark.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("run detail overview", async ({ page }) => {
    await page.goto(`/runs/${FIXTURE_RUN_ID}/overview`);
    await expect(page.getByTestId("run-detail-page")).toBeVisible();
    await expect(page.getByTestId("run-detail-summary")).toHaveScreenshot(
      "run-detail-summary.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("evidence promotion focus", async ({ page }) => {
    await page.goto(
      `/evidence?runId=${FIXTURE_RUN_ID}&focus=promotion&promotionId=${FIXTURE_PROMOTION_ID}`,
    );
    await expect(
      page.getByTestId(`promotion-approve-${FIXTURE_PROMOTION_ID}`),
    ).toBeVisible();
    await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
      "evidence-promotion-focus.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("clerk chat shell-lite", async ({ page }) => {
    await page.addInitScript((storageKey) => {
      window.localStorage.setItem(storageKey, "clerk");
    }, INTERFACE_MODE_STORAGE_KEY);
    await page.goto("/");
    await expect(
      page.getByText("What policy would you like to analyze?"),
    ).toBeVisible();
    await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
      "clerk-chat-shell-lite.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("dark evidence fabric", async ({ page }) => {
    await page.addInitScript((storageKey) => {
      window.localStorage.setItem(storageKey, "dark");
    }, THEME_STORAGE_KEY);
    await page.goto("/evidence");
    await expect(page.getByTestId("evidence-page")).toBeVisible();
    await expect(page.getByTestId("evidence-source-atlas-panel")).toBeVisible();
    await expect(page.getByTestId("evidence-page")).toHaveScreenshot(
      "dark-evidence-fabric.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("mobile command center", async ({ page }) => {
    await page.setViewportSize({ width: 393, height: 852 });
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Command Center" }),
    ).toBeVisible();
    await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
      "mobile-command-center.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("mobile run detail overview", async ({ page }) => {
    await page.setViewportSize({ width: 393, height: 852 });
    await page.goto(`/runs/${FIXTURE_RUN_ID}/overview`);
    await expect(page.getByTestId("run-detail-page")).toBeVisible();
    await expect(page.getByTestId("run-detail-summary")).toHaveScreenshot(
      "mobile-run-detail-overview.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("logo mark sizes", async ({ page }) => {
    await page.goto("/");
    await page.setContent(`
      <main style="display:grid;place-items:center;min-height:100vh;background:#f4f0e5;">
        <div id="logo-mark-grid" style="display:flex;align-items:flex-end;gap:24px;padding:32px;border:1px solid rgba(41,43,43,0.12);border-radius:24px;background:rgba(255,255,255,0.76);">
          <img alt="logo-16" src="http://127.0.0.1:5173/atlas/favicon.svg" width="16" height="16" />
          <img alt="logo-32" src="http://127.0.0.1:5173/atlas/logo-mark.svg" width="32" height="32" />
          <img alt="logo-48" src="http://127.0.0.1:5173/atlas/logo-mark.svg" width="48" height="48" />
        </div>
      </main>
    `);
    await expect(page.locator("#logo-mark-grid")).toHaveScreenshot(
      "logo-mark-16-32-48.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("run deck content slide", async ({ page }) => {
    await page.goto(`/runs/${FIXTURE_RUN_ID}/deck`);
    await expect(page.getByTestId("run-deck-page")).toBeVisible();
    await expect(page.getByTestId("run-deck-slide-evidence")).toHaveScreenshot(
      "run-deck-content-slide.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("decision packet reading view A4 print", async ({ page }) => {
    await expectPrintSnapshot(page, {
      path: `/artifacts/${FIXTURE_DECISION_PACKET_ID}?tab=content&view=reading`,
      readyTestId: "artifact-page",
      selector: ".monograph-layout",
      snapshot: "decision-reading-view-a4-print.png",
    });
  });

  test("run detail A4 print", async ({ page }) => {
    await expectPrintSnapshot(page, {
      path: `/runs/${FIXTURE_RUN_ID}/overview?trust=expanded`,
      readyTestId: "run-detail-page",
      selector: '[data-testid="run-detail-page"]',
      snapshot: "run-detail-a4-print.png",
    });
  });

  test("bureaucratic document A4 print", async ({ page }) => {
    await expectPrintSnapshot(page, {
      path: `/artifacts/${FIXTURE_DECISION_PACKET_ID}?tab=bureaucratic&genre=postanova_kmu&trust=expanded`,
      readyTestId: "artifact-page",
      selector: '[data-testid="artifact-page"]',
      snapshot: "bureaucratic-document-a4-print.png",
    });
  });

  test("policy compare A4 print", async ({ page }) => {
    await expectPrintSnapshot(page, {
      path: `/runs/compare?base=${FIXTURE_METADATA.core_run_id}&target=${FIXTURE_METADATA.core_run_id_secondary}&trust=compact`,
      readyTestId: "run-compare-page",
      selector: '[data-testid="run-compare-page"]',
      snapshot: "policy-compare-a4-print.png",
    });
  });

  test("counterfactual scenario A4 print", async ({ page }) => {
    await expectPrintSnapshot(page, {
      path: `/compose?scenario_id=scn_rate_cut_25bps&cf_mode=actual_vs_scenario`,
      readyTestId: "composer-page",
      selector: '[data-testid="composer-page"]',
      snapshot: "scenario-a4-print.png",
    });
  });
});
