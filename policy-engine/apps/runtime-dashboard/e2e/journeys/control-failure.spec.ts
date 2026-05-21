import { expect, test } from "@playwright/test";

import {
  applyRuntimeApiScenario,
  installDashboardTestState,
} from "../helpers/runtime-dashboard";

const INTERFACE_MODE_STORAGE_KEY = "polisyos.runtime.interface-mode";

test.describe("runtime-dashboard control operational failures", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
    await page.addInitScript((storageKey) => {
      window.localStorage.setItem(storageKey, "clerk");
    }, INTERFACE_MODE_STORAGE_KEY);
  });

  test("@smoke renders a terminal provider failure envelope from a rejected NL launch", async ({
    page,
  }) => {
    const jobId = "job_provider_failure_route_fixture";
    const evidenceBundlePath =
      ".polisyos/canary_evidence/20260412T091500Z_job_provider_failure_route_fixture";
    const failure = {
      artifact_refs: {
        evidence_bundle_path: evidenceBundlePath,
        provider_preflight_ref: "provider_preflight.json",
      },
      code: "llm_provider_preflight_failed",
      job_id: jobId,
      layer: "llm_gateway",
      message:
        "Gonka provider preflight failed before starting the long NL workflow.",
      model: "moonshotai/Kimi-K2.6",
      next_action:
        "Check Gonka model availability, API key validity, and endpoint health before retrying the production run.",
      phase: "provider_preflight",
      provider: "gonka",
      retryable: true,
      run_id: null,
      variant_failures: [
        {
          code: "no_endpoints_available",
          model: "moonshotai/Kimi-K2.6",
          retryable: true,
        },
      ],
    };

    await applyRuntimeApiScenario(page, "ok", [
      {
        matcher: "/api/v1/control/runs/nl",
        method: "POST",
        body: {
          job_id: jobId,
          message: "Provider preflight failed",
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-provider-failure-launch",
            source_kinds: ["control_job"],
          },
          run_id: null,
          status: "rejected",
        },
      },
      {
        matcher:
          /^\/api\/v1\/control\/jobs\/job_provider_failure_route_fixture$/,
        method: "GET",
        body: {
          blocking_quality_failures: [],
          capability_manifest_ref: null,
          effective_execution_profile: "production",
          error_message:
            "Provider preflight failed before starting the long NL workflow.",
          execution_status: "failed",
          failure,
          finished_at: "2026-04-12T09:15:04Z",
          job_id: jobId,
          kind: "natural_language_run",
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-provider-failure-job",
            source_kinds: ["control_job"],
          },
          pipeline_id: null,
          progress: {
            evidence_bundle_path: evidenceBundlePath,
            failure,
            status: "failed",
          },
          quality_gates: [],
          quality_status: null,
          requested_execution_profile: "production",
          run_id: null,
          started_at: "2026-04-12T09:15:01Z",
          state: "failed",
          submitted_at: "2026-04-12T09:15:00Z",
        },
      },
    ]);

    await page.goto("/");
    await expect(
      page.getByText("What policy would you like to analyze?"),
    ).toBeVisible();

    await page
      .getByPlaceholder("Ask a policy question...")
      .fill("Run a production canary with a real provider preflight.");
    await page.getByRole("button", { name: "Analyze" }).click();

    const failurePanel = page.getByRole("region", {
      name: "Control failure",
    });
    await expect(failurePanel).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Control quality" }),
    ).toHaveCount(0);
    await expect(
      failurePanel.getByText("llm_provider_preflight_failed"),
    ).toBeVisible();
    await expect(failurePanel.getByText("retryable")).toBeVisible();
    await expect(failurePanel.getByText("llm_gateway")).toBeVisible();
    await expect(
      failurePanel.getByText("provider_preflight", { exact: true }),
    ).toBeVisible();
    await expect(
      failurePanel.getByText("moonshotai/Kimi-K2.6", { exact: true }),
    ).toBeVisible();
    await expect(
      failurePanel.getByText("gonka", { exact: true }),
    ).toBeVisible();
    await expect(failurePanel.getByText(failure.message)).toBeVisible();
    await expect(failurePanel.getByText(failure.next_action)).toBeVisible();
    await expect(
      failurePanel.getByText(`Evidence: ${evidenceBundlePath}`),
    ).toBeVisible();
  });
});
