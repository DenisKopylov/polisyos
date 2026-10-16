import { expect, test } from "@playwright/test";

import { lexSearchResponseSchema } from "../../src/api/validators";
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
    const candidateResponse = lexSearchResponseSchema.parse({
      meta: {
        generated_at: new Date().toISOString(),
        request_id: "playwright-lex-search",
        source_kinds: ["core_run"],
      },
      query: "budget",
      results: [
        {
          fact_id: "fact-budget-deficit-limit",
          subject_name: "budget_deficit_limit",
          predicate: "must_not_exceed",
          object_name: "projected GDP",
          fact_text: "Budget deficit must not exceed 3% of projected GDP",
          confidence: 0.41,
          norm_type: "constraint",
          action_canon: "must_not_exceed",
          norm_type_canon: "constraint",
          condition_text_uk: "",
          exception_text_uk: "",
          procedure_text_uk: "",
          thresholds_json: '{"max":3}',
          source_quote_uk: "",
          trust_tier: "search_candidate",
          grounding_status: "missing_quote",
          canonical_status: "raw",
          reference_resolution_status: "unresolved",
          structure_quality: "unassessed",
          constraint_type_canon: "numeric_ceiling",
          legal_unit_subtype: "fiscal_rule",
          route_class: "fiscal_constraint",
          empty_spo_retry_eligible: false,
          audit_miss_prone: true,
          reference_bearing: true,
          threshold_bearing: true,
          confidence_breakdown_json: "{}",
          hallucination_flags_json: "[]",
          quality_band: "candidate",
          doc_id: "fixture-document-budget",
          doc_family_id: "fixture-family-fiscal-compact",
          version_id: "fixture-version-2026",
          jurisdiction: "fixture",
          top_domain: "public_finance",
          effective_from: "2026-01-01",
          effective_to: "",
          temporal_state: "unknown",
          temporal_resolution_status: "not_established",
          temporal_source_scope: "unverified_source",
          temporal_source_kind: "fixture_candidate",
          temporal_provenance_json: "{}",
          doc_name: "Fiscal Compact (candidate fixture)",
          doc_reestr_code: "FC-2026",
          provision_anchor: "article-3",
          provision_citation: "Art. 3",
          similarity: 0.73,
        },
      ],
      total: 1,
      search_mode: "vector",
      vector_refusal_code: null,
      legal_relation_refusal: {
        code: "legal_source_relation_verification_not_established",
        status: "verification_missing",
      },
    });
    const malformedPresentRefusal = lexSearchResponseSchema.safeParse({
      ...candidateResponse,
      legal_relation_refusal: {
        code: "legal_source_relation_verification_not_established",
        status: "verified",
      },
    });
    expect(malformedPresentRefusal.success).toBe(false);
    if (malformedPresentRefusal.success) {
      throw new Error("malformed present Legal refusal passed the API schema");
    }
    expect(
      malformedPresentRefusal.error.issues.some(
        (issue) => issue.path.join(".") === "legal_relation_refusal.status",
      ),
    ).toBe(true);

    await page.goto("/knowledge");
    await waitForDashboardSurface(page, "knowledge");

    await expect(
      page.getByRole("heading", { name: /Graph statistics/i }),
    ).toBeVisible();

    await applyRuntimeApiScenario(page, "ok", [
      {
        matcher: "/api/v1/control/lex/search",
        method: "POST",
        body: candidateResponse,
      },
    ]);

    const searchInput = page.getByPlaceholder(/Search facts/i);
    await searchInput.fill("budget");
    await page.getByRole("button", { name: /^Search$/i }).click();

    await expect(page.getByText(/1 result for .budget./i)).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByRole("table").last()).toBeVisible();
    await expect(
      page
        .getByRole("table")
        .last()
        .getByText(/Budget deficit must not exceed/),
    ).toBeVisible();
    await expect(
      page.getByTestId("lex-search-legal-relation-refusal"),
    ).toContainText("legal_source_relation_verification_not_established");
    await expect(
      page.getByTestId("lex-search-legal-relation-refusal"),
    ).toContainText("Returned rows remain search candidates.");
    await expect(page.getByRole("button", { name: /Export CSV/i })).toHaveCount(
      0,
    );

    await page
      .getByRole("link", { name: /^Evidence Fabric$/i })
      .last()
      .click();
    await waitForDashboardSurface(page, "evidence");
  });
});
