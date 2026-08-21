import {
  expect,
  test,
  type APIRequestContext,
  type Locator,
  type Page,
} from "@playwright/test";

import {
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "./helpers/runtime-dashboard";

const STORYBOOK_BASE_URL = "http://127.0.0.1:6006";
const FIXTURE_API_BASE_URL = "http://127.0.0.1:8000";
const VISUAL_CLOCK_TIME = "2026-01-01T00:00:00.000Z";
const BUREAUCRATIC_GENERATED_LINE =
  "Дата формування: 2026-01-01T00:00:00+00:00";
const VISUAL_CONNECTOR_ID = "worldbank.wdi@1.0.0";
let fixtureMetadata: ReturnType<typeof readFixtureMetadata>;

async function waitForVisualFonts(page: Page) {
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
}

async function waitForStableRender(locator: Locator, timeout = 15_000) {
  let consecutiveEqualSignatures = 0;
  let previousSignature: string | null = null;
  await expect
    .poll(
      async () => {
        const signature = await locator.evaluateAll((elements) =>
          JSON.stringify(
            elements.map((element) => {
              const bounds = element.getBoundingClientRect();
              const style = getComputedStyle(element);
              return {
                fontFamily: style.fontFamily,
                fontSize: style.fontSize,
                height: bounds.height,
                markup: element.innerHTML,
                width: bounds.width,
              };
            }),
          ),
        );
        consecutiveEqualSignatures =
          signature === previousSignature ? consecutiveEqualSignatures + 1 : 0;
        previousSignature = signature;
        return consecutiveEqualSignatures;
      },
      { timeout },
    )
    .toBeGreaterThanOrEqual(1);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function loadedConnectorIds(request: APIRequestContext) {
  const response = await request.get(
    `${FIXTURE_API_BASE_URL}/api/v1/control/data/connectors`,
  );
  expect(response.ok()).toBe(true);
  const payload: unknown = await response.json();
  if (!isRecord(payload) || !Array.isArray(payload.connectors)) {
    throw new TypeError("visual fixture expected connectors array");
  }
  return payload.connectors
    .filter(
      (connector): connector is Record<string, unknown> =>
        isRecord(connector) && connector.loaded === true,
    )
    .map((connector) => connector.connector_id)
    .filter(
      (connectorId): connectorId is string => typeof connectorId === "string",
    )
    .sort();
}

async function ensureDeterministicConnectorFixture(request: APIRequestContext) {
  const initiallyLoaded = await loadedConnectorIds(request);
  if (initiallyLoaded.length === 0) {
    const previewResponse = await request.post(
      `${FIXTURE_API_BASE_URL}/api/v1/control/data/preview`,
      {
        data: {
          allow_fallback: false,
          fetch_plan: {
            connector_id: "worldbank.wdi",
            dataset_id: "../unsafe",
            filters: {},
            max_preview_rows: 10,
            metric_id: "probe.metric",
            plan_id: "visual_fixture_worldbank_load",
            profile_id: "worldbank_wdi",
            quality_min: 0.6,
            source_lane: "fastlane",
          },
        },
      },
    );
    expect(previewResponse.ok()).toBe(true);
    const previewPayload: unknown = await previewResponse.json();
    if (!isRecord(previewPayload) || !isRecord(previewPayload.preview)) {
      throw new TypeError("visual fixture expected preview result");
    }
    expect(previewPayload.preview.status).toBe("error");
    expect(previewPayload.preview.message).toBe(
      "Unsafe World Bank indicator id: slash characters are not allowed",
    );
  } else {
    expect(initiallyLoaded).toEqual([VISUAL_CONNECTOR_ID]);
  }

  await expect
    .poll(() => loadedConnectorIds(request), { timeout: 15_000 })
    .toEqual([VISUAL_CONNECTOR_ID]);
}

function visualResponseMetadataPaths(coreRunId: string) {
  return [
    `/api/v1/runs/${encodeURIComponent(coreRunId)}/evidence-context`,
    "/api/v1/control/data/promotion/candidates",
    "/api/v1/control/data/connectors",
  ];
}

async function installVisualResponseMetadataFixture(
  page: Page,
  coreRunId: string,
) {
  for (const responsePath of visualResponseMetadataPaths(coreRunId)) {
    await page.route(`**${responsePath}`, async (route) => {
      const request = route.request();
      const pathname = decodeURIComponent(new URL(request.url()).pathname);
      if (request.method() !== "GET" || pathname !== responsePath) {
        await route.fallback();
        return;
      }

      const response = await route.fetch();
      const payload: unknown = await response.json();
      if (
        !isRecord(payload) ||
        !isRecord(payload.meta) ||
        typeof payload.meta.generated_at !== "string" ||
        payload.meta.generated_at.length === 0
      ) {
        throw new TypeError(
          `visual fixture expected nonempty meta.generated_at at ${responsePath}`,
        );
      }

      await route.fulfill({
        response,
        json: {
          ...payload,
          meta: {
            ...payload.meta,
            generated_at: VISUAL_CLOCK_TIME,
          },
        },
      });
    });
  }
}

async function installBureaucraticTimestampFixture(
  page: Page,
  artifactId: string,
) {
  const artifactPath = `/api/v1/artifacts/${artifactId}`;
  const renderPath = `${artifactPath}/render`;

  await page.route("**/api/v1/artifacts/**", async (route) => {
    const pathname = decodeURIComponent(
      new URL(route.request().url()).pathname,
    );
    if (pathname !== artifactPath && pathname !== renderPath) {
      await route.fallback();
      return;
    }

    const response = await route.fetch();
    const payload: unknown = await response.json();
    if (!isRecord(payload)) {
      throw new TypeError(
        `visual fixture expected object payload at ${pathname}`,
      );
    }

    if (pathname === artifactPath) {
      if (
        !isRecord(payload.artifact) ||
        typeof payload.artifact.created_at !== "string"
      ) {
        throw new TypeError("visual fixture expected artifact.created_at");
      }
      await route.fulfill({
        response,
        json: {
          ...payload,
          artifact: {
            ...payload.artifact,
            created_at: VISUAL_CLOCK_TIME,
          },
        },
      });
      return;
    }

    if (
      !isRecord(payload.document) ||
      typeof payload.document.render_timestamp !== "string"
    ) {
      throw new TypeError("visual fixture expected document.render_timestamp");
    }
    if (!Array.isArray(payload.document.blocks)) {
      throw new TypeError("visual fixture expected document.blocks");
    }
    let generatedLineCount = 0;
    const blocks = payload.document.blocks.map((block) => {
      if (!isRecord(block) || !Array.isArray(block.items)) {
        return block;
      }
      const items = block.items.map((item) => {
        if (typeof item === "string" && item.startsWith("Дата формування: ")) {
          generatedLineCount += 1;
          return BUREAUCRATIC_GENERATED_LINE;
        }
        return item;
      });
      return { ...block, items };
    });
    if (generatedLineCount !== 1) {
      throw new TypeError(
        `visual fixture expected one bureaucratic generated-at line, received ${generatedLineCount}`,
      );
    }
    await route.fulfill({
      response,
      json: {
        ...payload,
        document: {
          ...payload.document,
          blocks,
          render_timestamp: VISUAL_CLOCK_TIME,
        },
      },
    });
  });
}

async function waitForDashboardCharts(page: Page) {
  const charts = page.locator(
    '[data-testid="dashboard-page"] .recharts-responsive-container',
  );
  await expect(charts).toHaveCount(2);
  await expect(
    page
      .locator('[data-testid="dashboard-page"] .recharts-bar-rectangle')
      .first(),
  ).toBeVisible();
  await expect(
    page.locator('[data-testid="dashboard-page"] .recharts-line-curve').first(),
  ).toHaveAttribute("d", /^M.+L/);
  await expect
    .poll(() =>
      charts.evaluateAll((elements) =>
        elements.every((element) => {
          const bounds = element.getBoundingClientRect();
          return bounds.width > 0 && bounds.height > 0;
        }),
      ),
    )
    .toBe(true);
  await expect(page.locator("html")).toHaveAttribute(
    "data-reduced-motion",
    "reduce",
  );
  await waitForVisualFonts(page);

  await waitForStableRender(charts);
}

async function openEvidencePrimitiveStory(page: Page, storyId: string) {
  await page.goto(
    `${STORYBOOK_BASE_URL}/iframe.html?id=${encodeURIComponent(storyId)}&viewMode=story`,
  );
  const story = page.locator("#storybook-root");
  await expect(story).toBeVisible({ timeout: 15_000 });
  await waitForVisualFonts(page);
  return story;
}

async function openPrintSurface(
  page: Page,
  {
    path,
    readySelector,
    readyTestId,
    selector,
  }: {
    path: string;
    readySelector?: string;
    readyTestId: string;
    selector: string;
  },
): Promise<Locator> {
  await page.setViewportSize({ width: 794, height: 1123 });
  await page.emulateMedia({ media: "print" });
  await page.goto(path);
  await expect(page.getByTestId(readyTestId)).toBeVisible();
  await expect(page.locator(selector)).toBeVisible();
  if (readySelector) {
    await expect(page.locator(readySelector)).toBeVisible();
    await waitForStableRender(page.locator(readySelector));
  }
  await waitForVisualFonts(page);
  const surface = page.locator(selector);
  await waitForStableRender(surface);
  return surface;
}

test.describe("runtime-dashboard visual baselines", () => {
  test.use({
    viewport: { width: 1440, height: 1200 },
  });

  test.beforeAll(async ({ request }) => {
    fixtureMetadata = readFixtureMetadata();
    await ensureDeterministicConnectorFixture(request);
  });

  test.beforeEach(async ({ page }) => {
    await page.clock.setFixedTime(VISUAL_CLOCK_TIME);
    await installDashboardTestState(page);
    await installVisualResponseMetadataFixture(
      page,
      fixtureMetadata.core_run_id,
    );
    await page.emulateMedia({ reducedMotion: "reduce" });
  });

  test("binds visual response metadata to the visual clock", async ({
    page,
  }) => {
    const responsePaths = visualResponseMetadataPaths(
      fixtureMetadata.core_run_id,
    );

    await page.goto("/");
    const visualTimeBeforeWait = await page.evaluate(() =>
      new Date().toISOString(),
    );
    await page.waitForTimeout(50);
    const visualTimeAfterWait = await page.evaluate(() =>
      new Date().toISOString(),
    );
    expect(visualTimeBeforeWait).toBe(VISUAL_CLOCK_TIME);
    expect(visualTimeAfterWait).toBe(VISUAL_CLOCK_TIME);

    const generatedTimes = await page.evaluate(async (paths) => {
      return Promise.all(
        paths.map(async (path) => {
          const response = await fetch(path);
          if (!response.ok) {
            throw new Error(
              `visual fixture request failed at ${path}: ${response.status}`,
            );
          }
          const payload: unknown = await response.json();
          if (
            typeof payload !== "object" ||
            payload === null ||
            !("meta" in payload) ||
            typeof payload.meta !== "object" ||
            payload.meta === null ||
            !("generated_at" in payload.meta)
          ) {
            throw new TypeError(
              `visual fixture expected meta.generated_at at ${path}`,
            );
          }
          return payload.meta.generated_at;
        }),
      );
    }, responsePaths);

    for (const generatedAt of generatedTimes) {
      expect(generatedAt).toBe(VISUAL_CLOCK_TIME);
    }
  });

  test("command center shell", async ({ page }) => {
    await page.goto("/");
    await waitForDashboardSurface(page, "dashboard");
    await waitForDashboardCharts(page);
    await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
      "command-center-shell.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("scenario composer dark theme", async ({ page }) => {
    await installDashboardTestState(page, { theme: "dark" });
    await page.goto("/compose");
    await expect(
      page.getByRole("heading", { name: "Scenario Composer" }),
    ).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
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
    const catalogResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        response.request().method() === "GET" &&
        url.pathname === "/api/v1/control/data/catalog/search"
      );
    });
    await page.goto(
      `/evidence?runId=${fixtureMetadata.core_run_id}&focus=promotion&promotionId=${fixtureMetadata.promotion_candidate_id}`,
    );
    await expect(
      page.getByTestId(
        `promotion-approve-${fixtureMetadata.promotion_candidate_id}`,
      ),
    ).toBeVisible();
    const catalogResponse = await catalogResponsePromise;
    expect(catalogResponse.ok()).toBe(true);
    const catalogPayload: unknown = await catalogResponse.json();
    if (
      !isRecord(catalogPayload) ||
      typeof catalogPayload.query !== "string" ||
      typeof catalogPayload.total_matches !== "number"
    ) {
      throw new TypeError(
        "visual fixture expected a typed catalog search response",
      );
    }
    await expect(
      page.getByTestId("evidence-knowledge-weave-panel"),
    ).toContainText(
      `Catalog matches: ${catalogPayload.total_matches} for query \`${catalogPayload.query}\``,
    );
    const surface = page.getByTestId("evidence-page");
    await waitForVisualFonts(page);
    await waitForStableRender(surface);
    await expect(surface).toHaveScreenshot("evidence-promotion-focus.png", {
      animations: "disabled",
      caret: "hide",
    });
  });

  test("clerk chat shell-lite", async ({ page }) => {
    await installDashboardTestState(page, { interfaceMode: "clerk" });
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
    await installDashboardTestState(page, { theme: "dark" });
    await page.goto("/evidence");
    await expect(page.getByTestId("evidence-page")).toBeVisible();
    await expect(page.getByTestId("evidence-source-atlas-panel")).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    const surface = page.getByTestId("evidence-page");
    await waitForVisualFonts(page);
    await waitForStableRender(surface);
    await expect(surface).toHaveScreenshot("dark-evidence-fabric.png", {
      animations: "disabled",
      caret: "hide",
    });
  });

  test("mobile command center", async ({ page }) => {
    await page.setViewportSize({ width: 393, height: 852 });
    await page.goto("/");
    await waitForDashboardSurface(page, "dashboard");
    await waitForDashboardCharts(page);
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

  test("run detail print omits signed targets and preserves ordinary link targets", async ({
    page,
  }) => {
    const surface = await openPrintSurface(page, {
      path: `/runs/${fixtureMetadata.core_run_id}/overview?trust=expanded`,
      readyTestId: "run-detail-page",
      selector: '[data-testid="run-detail-page"]',
    });
    const signedLink = surface.locator('a[href^="/public/decisions/"]');
    await expect(signedLink).toHaveCount(1);
    await expect(signedLink).toBeVisible();
    const signedHref = await signedLink.getAttribute("href");
    expect(signedHref?.length).toBeGreaterThan(1_000);
    expect(
      await signedLink.evaluate(
        (element) => getComputedStyle(element, "::after").content,
      ),
    ).toBe("none");

    const ordinaryLinks = await surface
      .locator('a[href]:not([href^="/public/decisions/"]):visible')
      .evaluateAll((elements) =>
        elements.map((element) => ({
          href: element.getAttribute("href"),
          printedTarget: getComputedStyle(element, "::after").content,
        })),
      );
    expect(ordinaryLinks.length).toBeGreaterThan(0);
    for (const ordinaryLink of ordinaryLinks) {
      expect(ordinaryLink.href).not.toBeNull();
      expect(ordinaryLink.printedTarget).toContain(ordinaryLink.href);
    }
  });

  test("bureaucratic document A4 print", async ({ page }) => {
    await installBureaucraticTimestampFixture(
      page,
      fixtureMetadata.decision_packet_artifact_id,
    );
    const surface = await openPrintSurface(page, {
      path: `/artifacts/${fixtureMetadata.decision_packet_artifact_id}?tab=bureaucratic&genre=postanova_kmu&trust=expanded`,
      readySelector: ".bureaucratic-document",
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
