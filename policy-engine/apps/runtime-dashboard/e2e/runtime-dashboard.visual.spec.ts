import { expect, test, type Locator, type Page } from "@playwright/test";

import { readFixtureMetadata } from "./helpers/runtime-dashboard";

const LIVE_STORAGE_KEY = "polisyos.runtime.disableLive";
const THEME_STORAGE_KEY = "polisyos.runtime.theme";
const INTERFACE_MODE_STORAGE_KEY = "polisyos.runtime.interface-mode";
const STORYBOOK_BASE_URL = "http://127.0.0.1:6006";
let fixtureMetadata: ReturnType<typeof readFixtureMetadata>;

async function openEvidencePrimitiveStory(page: Page, storyId: string) {
  await page.goto(
    `${STORYBOOK_BASE_URL}/iframe.html?id=${encodeURIComponent(storyId)}&viewMode=story`,
  );
  const story = page.locator("#storybook-root");
  await expect(story).toBeVisible({ timeout: 15_000 });
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
  return story;
}

async function openPrintSurface(
  page: Page,
  {
    path,
    readyTestId,
    selector,
  }: {
    path: string;
    readyTestId: string;
    selector: string;
  },
): Promise<Locator> {
  await page.setViewportSize({ width: 794, height: 1123 });
  await page.emulateMedia({ media: "print" });
  await page.goto(path);
  await expect(page.getByTestId(readyTestId)).toBeVisible();
  await expect(page.locator(selector)).toBeVisible();
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
  return page.locator(selector);
}

test.describe("runtime-dashboard visual baselines", () => {
  test.use({
    viewport: { width: 1440, height: 1200 },
  });

  test.beforeAll(() => {
    fixtureMetadata = readFixtureMetadata();
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
    await page.goto(`/runs/${fixtureMetadata.core_run_id}/overview`);
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
      `/evidence?runId=${fixtureMetadata.core_run_id}&focus=promotion&promotionId=${fixtureMetadata.promotion_candidate_id}`,
    );
    await expect(
      page.getByTestId(
        `promotion-approve-${fixtureMetadata.promotion_candidate_id}`,
      ),
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
    await page.goto(`/runs/${fixtureMetadata.core_run_id}/overview`);
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
    await page.goto(`/runs/${fixtureMetadata.core_run_id}/deck`);
    await expect(page.getByTestId("run-deck-page")).toBeVisible();
    await expect(page.getByTestId("run-deck-slide-evidence")).toHaveScreenshot(
      "run-deck-content-slide.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("renders candidate output in candidate clothing", async ({ page }) => {
    const story = await openEvidencePrimitiveStory(
      page,
      "ds4-evidence-primitives--candidate-clothing",
    );
    const candidate = story.getByTestId("candidate-frame");
    const ownerProjection = story.getByTestId("owner-projection-unavailable");
    await expect(candidate).toHaveAttribute(
      "data-authority-posture",
      "candidate",
    );
    await expect(ownerProjection).toHaveAttribute(
      "data-interaction-state",
      "unavailable",
    );
    await expect(
      story.locator('[data-authority-posture="owner-projection"]'),
    ).toHaveCount(0);
    const [candidateBorder, ownerBorder] = await Promise.all([
      candidate.evaluate((element) => getComputedStyle(element).borderStyle),
      ownerProjection.evaluate(
        (element) => getComputedStyle(element).borderStyle,
      ),
    ]);
    expect(candidateBorder).toBe("dashed");
    expect(ownerBorder).not.toBe(candidateBorder);
    await expect(story).toHaveScreenshot("ds4-candidate-clothing.png", {
      animations: "disabled",
      caret: "hide",
    });
  });

  test("marks fixture-only content and bars it from authority slots", async ({
    page,
  }) => {
    const story = await openEvidencePrimitiveStory(
      page,
      "ds4-evidence-primitives--fixture-only",
    );
    await expect(story.locator("#story-fixture-envelope")).toHaveAttribute(
      "data-fixture-authority",
      "fixture_only",
    );
    await expect(story.locator("#story-fixture-evidence")).toHaveAttribute(
      "data-fixture-authority",
      "fixture_only",
    );
    await expect(
      story.getByTestId("authority-badge-fixture-rejection"),
    ).toHaveAttribute("data-fixture-rejection", /fixture provenance/i);
    await expect(story.locator("[data-authority-recognition]")).toHaveCount(0);
    await expect(story).toHaveScreenshot("ds4-fixture-only-boundary.png", {
      animations: "disabled",
      caret: "hide",
    });
  });

  test("renders every DS4 evidence primitive", async ({ page }) => {
    const story = await openEvidencePrimitiveStory(
      page,
      "ds4-evidence-primitives--all-primitives",
    );
    for (const locator of [
      story.getByTestId("authority-badge-fixture-rejection"),
      story.getByTestId("candidate-frame"),
      story.getByTestId("blocker-card"),
      story.locator("#story-envelope-chip"),
      story.locator("#story-evidence-link"),
      story.getByTestId("provenance-popover-content"),
      story.getByTestId("time-semantics-source-state"),
      story.getByTestId("weakest-link-explainer"),
    ]) {
      await expect(locator).toBeVisible();
    }
    await expect(
      story.getByTestId("authority-badge-fixture-rejection"),
    ).toHaveAttribute("data-fixture-rejection", /fixture provenance/i);
    await expect(story.locator("[data-authority-recognition]")).toHaveCount(0);
    await expect(story.getByTestId("candidate-frame")).toHaveAttribute(
      "data-authority-posture",
      "candidate",
    );
    await expect(story.getByTestId("blocker-card")).toHaveAttribute(
      "data-producer-blocker-code",
      "fixture_missing_grounded_effect",
    );
    await expect(story.locator("#story-envelope-chip")).toHaveAttribute(
      "data-fixture-authority",
      "fixture_only",
    );
    await expect(story.locator("#story-evidence-link")).toHaveAttribute(
      "data-evidence-claim",
      "reference-only",
    );
    await expect(story).toHaveScreenshot("ds4-evidence-primitives.png", {
      animations: "disabled",
      caret: "hide",
    });
    await page.setViewportSize({ width: 393, height: 852 });
    await expect(story.getByTestId("weakest-link-explainer")).toBeVisible();
    await page.emulateMedia({
      forcedColors: "active",
      reducedMotion: "reduce",
    });
    await expect(story.locator("#story-evidence-link")).toBeVisible();
    await page.emulateMedia({ media: "print" });
    await expect(story.getByTestId("candidate-frame")).toBeVisible();
  });

  test("decision packet reading view A4 print", async ({ page }) => {
    const surface = await openPrintSurface(page, {
      path: `/artifacts/${fixtureMetadata.decision_packet_artifact_id}?tab=content&view=reading`,
      readyTestId: "artifact-page",
      selector: ".monograph-layout",
    });
    await expect(surface).toHaveScreenshot(
      "decision-reading-view-a4-print.png",
      {
        animations: "disabled",
        caret: "hide",
        maxDiffPixels: 100,
      },
    );
  });

  test("run detail A4 print", async ({ page }) => {
    const surface = await openPrintSurface(page, {
      path: `/runs/${fixtureMetadata.core_run_id}/overview?trust=expanded`,
      readyTestId: "run-detail-page",
      selector: '[data-testid="run-detail-page"]',
    });
    await expect(surface).toHaveScreenshot("run-detail-a4-print.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 100,
    });
  });

  test("bureaucratic document A4 print", async ({ page }) => {
    const surface = await openPrintSurface(page, {
      path: `/artifacts/${fixtureMetadata.decision_packet_artifact_id}?tab=bureaucratic&genre=postanova_kmu&trust=expanded`,
      readyTestId: "artifact-page",
      selector: '[data-testid="artifact-page"]',
    });
    await expect(surface).toHaveScreenshot(
      "bureaucratic-document-a4-print.png",
      {
        animations: "disabled",
        caret: "hide",
        maxDiffPixels: 100,
      },
    );
  });

  test("policy compare A4 print", async ({ page }) => {
    const surface = await openPrintSurface(page, {
      path: `/runs/compare?base=${fixtureMetadata.core_run_id}&target=${fixtureMetadata.core_run_id_secondary}&trust=compact`,
      readyTestId: "policy-diff-view",
      selector: '[data-testid="policy-diff-view"]',
    });
    await expect(surface).toHaveScreenshot("policy-compare-a4-print.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 100,
    });
  });

  test("counterfactual scenario A4 print", async ({ page }) => {
    const surface = await openPrintSurface(page, {
      path: `/compose?scenario_id=scn_rate_cut_25bps&cf_mode=actual_vs_scenario`,
      readyTestId: "composer-page",
      selector: '[data-testid="composer-page"]',
    });
    await expect(surface).toHaveScreenshot("scenario-a4-print.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 100,
    });
  });
});
