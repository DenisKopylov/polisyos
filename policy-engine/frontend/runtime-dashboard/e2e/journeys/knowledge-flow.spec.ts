import { expect, test } from "@playwright/test";

import {
  applyRuntimeApiScenario,
  installDashboardTestState,
  waitForDashboardSurface,
} from "../helpers/runtime-dashboard";

test.describe("runtime-dashboard knowledge flow", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
  });

  test("@smoke navigates the knowledge graph workspace and inspects search results", async ({
    page,
  }) => {
    await page.goto("/knowledge");
    await waitForDashboardSurface(page, "knowledge");

    await expect(
      page.getByRole("heading", { name: /Graph statistics/i }),
    ).toBeVisible();

    await applyRuntimeApiScenario(page, "ok", [
      {
        matcher: "/api/v1/control/lex/search",
        method: "POST",
        body: {
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-lex-search",
            source_kinds: ["lex"],
          },
          query: "budget",
          results: [
            {
              action_canon: "must_not_exceed",
              condition_text_uk: "",
              confidence: 0.91,
              doc_name: "Fiscal Compact",
              doc_reestr_code: "FC-2026",
              exception_text_uk: "",
              fact_id: "fact-budget-deficit-limit",
              fact_text: "Budget deficit must not exceed 3% of projected GDP",
              norm_type: "constraint",
              norm_type_canon: "constraint",
              object_name: "projected GDP",
              predicate: "must_not_exceed",
              procedure_text_uk: "",
              provision_citation: "Art. 3",
              source_quote_uk: "",
              subject_name: "budget_deficit_limit",
              thresholds_json: '{"max":3}',
            },
          ],
          total: 1,
        },
      },
    ]);

    const searchInput = page.getByPlaceholder(/Search facts/i);
    await searchInput.fill("budget");
    await page.getByRole("button", { name: /^Search$/i }).click();

    await expect(page.getByText(/result\(s\) for "budget"/i)).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByRole("table").last()).toBeVisible();

    await page.getByTestId("shell-nav-evidenceFabric").click();
    await waitForDashboardSurface(page, "evidence");
  });
});
