import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

import type { components } from "../src/api/types";
import {
  availableHumanDecisionGate,
  humanDecisionReviewEffectivenessFixture,
  humanDecisionSourceRef,
} from "../src/test/fixtures/humanDecision";
import { runPaperPacketFixture } from "../src/test/fixtures/runPaper";
import {
  installDashboardTestState,
  readFixtureMetadata,
} from "./helpers/runtime-dashboard";

type AcquisitionRoute = components["schemas"]["AcquisitionRouteProjection"];
type HumanDecisionGate = components["schemas"]["HumanDecisionGateResponse"];

const digest = (character: string) => `sha256:${character.repeat(64)}`;

async function horizontalOverflowOffenders(locator: Locator) {
  return locator.evaluate((root) =>
    [root, ...root.querySelectorAll("*")]
      .filter((element) => element.scrollWidth > element.clientWidth + 1)
      .map((element) => ({
        className: String(element.className),
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
        tagName: element.tagName,
      })),
  );
}

function acquisitionRoute(runId: string): AcquisitionRoute {
  return {
    authority_badge: "behavioral_fixture_not_production",
    authority_capability: "ready",
    cell_id: "cell-ds15",
    cost_basis: {
      record_content_hash: digest("c"),
      schema_version: "AcquisitionCostBasisRecord@1.0",
      total_amount: 1250,
    },
    execution_capability: "ready",
    external_nonclosures: [
      "fresh_positive_production_route:absent/unallocated",
    ],
    planner_record_id: "ds15-costed-acquisition",
    planner_report_hash: digest("e"),
    qualification_predicate: "not_established",
    qualification_reason: "policy_admission_missing",
    qualification_status: "pending_epoch_activation",
    recommended_strategy: "targeted_primary_data_collection",
    replay_pins: {
      compiled_content_hash: digest("a"),
      compiled_ref: digest("b"),
      cost_basis_hash: digest("c"),
      design_problem_ref: digest("d"),
      source_job_id: "source-job-ds15",
      terminal_event_id: "terminal-event-ds15",
    },
    route_id: digest("f"),
    route_projection_hash: digest("f"),
    route_status: "costed_actionable",
    run_id: runId,
    schema_version: "AcquisitionRouteProjection@1.0",
    tenant_id: "tenant-test",
    world_growth: "no_growth",
  };
}

function acquisitionHistory(terminal: boolean) {
  return {
    admission: terminal ? "not_established" : "not_reached",
    attempt_count: terminal ? 1 : 0,
    epoch_qualification: {
      appointment_state: "unappointed",
      appointment_would_establish:
        "authority to qualify native semantic production, append its history head and permit overlay activation",
      appointment_would_not_establish: [
        "gap shape",
        "passport validity",
        "positive delta",
        "re-entry",
      ],
      authority_owner_ref: null,
      authority_role: "semantic epoch policy-admission qualifier",
      code: "policy_admission_missing",
      epoch_state: "pending_epoch_activation",
      status: "not_established",
    },
    execution_phase: terminal ? "terminal" : "executing",
    overlay_epoch_count: 0,
    quarantine: terminal ? "raw_terminal" : "none",
    quarantine_count: terminal ? 1 : 0,
    raw_response_count: terminal ? 1 : 0,
    reentry: terminal ? "deeper_terminal" : "not_established",
    response_admitted_count: 0,
    terminal_count: terminal ? 1 : 0,
    world_growth: terminal ? "no_growth" : "not_established",
  } as const;
}

function acquisitionGrowthPacket(terminal: boolean) {
  return {
    absence_reason: null,
    as_of: "2026-08-28T12:00:00Z",
    authoritative_for: ["acquisition_gap_shape"],
    availability: "available",
    export_replay_contract: "policyos.runtime.export_replay_binding.v1",
    freshness: {
      basis: "request_observation",
      observed_at: "2026-08-28T12:00:00Z",
      source_as_of: null,
      state: "observed",
    },
    intended_audience: "REVIEWER",
    may_not_use_for: ["current_acquisition_authority"],
    packet_schema_version: "policyos.runtime.governed_projection_packet.v1",
    payload: {
      backlog: [],
      carrier_liveness: {
        carrier_disposition: "carrier_current",
        connector_id: "worldbank.wdi",
        execution_tier: "transport_ready",
        tier_decay_findings: [],
      },
      n13b_history: acquisitionHistory(terminal),
      schema_version: "policyos.runtime.acquisition_growth_projection.v1",
      structural_routes: [],
      summary: {
        actual_network_call_count: 18,
        backlog_count: 0,
        family_scorecard_count: 12,
        metric_resolution_count: 124,
        selected_record_count: 144,
        structural_route_count: 0,
      },
    },
    projection_hash: digest("1"),
    projection_id: "acquisition-growth",
    projection_rule_version: "policyos.runtime.governed_projection.v1",
    replay_address: "/api/v1/exports/governed-projections/acquisition-growth",
    source: {
      artifact_content_hash: digest("2"),
      declared_content_hash: null,
      related_artifact_bindings: [],
      relative_path: "acquisition-growth:N13a+N13b",
      validation: {
        bound_artifact_content_hash: digest("2"),
        bound_dependency_aggregate_identity: digest("3"),
        bound_dependency_count: 6,
        issue_codes: [],
        semantic_projection_hash: digest("4"),
        semantic_projection_hash_rule_version: "v1",
        status: "passed",
        validator_id:
          "governed_projection_validation_worker:validate_acquisition_growth",
        validator_version: "policyos.runtime.acquisition_growth_projection.v1",
      },
    },
    source_dependency_hash: digest("3"),
    source_rule_version: "GY-plan-rev18+3.5.12-D1-D6",
    source_schema_version: "policyos.runtime.acquisition_growth_projection.v1",
    stable_address: "/api/v1/exports/governed-projections/acquisition-growth",
  };
}

function gateForRun(runId: string): HumanDecisionGate {
  const gate = structuredClone(availableHumanDecisionGate());
  gate.run_id = runId;
  if (gate.contestability) {
    gate.contestability.href =
      `/runs/${encodeURIComponent(runId)}/case?` +
      new URLSearchParams({
        appeal_case_id: gate.contestability.case_id,
        source_kind: "agent_action_authority",
        source_ref: humanDecisionSourceRef,
      }).toString();
  }
  return gate;
}

async function installAcquisitionFixture(page: Page, runId: string) {
  const routePacket = acquisitionRoute(runId);
  const routeWire = ` ${JSON.stringify(routePacket)}\n`;
  const gate = gateForRun(runId);
  const paper = runPaperPacketFixture();
  const caseInspectionPacket = {
    ...paper,
    replay_address: `/api/v1/runs/${runId}/paper`,
    report_href: `/runs/${runId}/report#stage-trace`,
    run: { ...paper.run, run_id: runId },
    stable_address: `/api/v1/runs/${runId}/paper`,
  };
  let growthReads = 0;
  let jobReads = 0;

  await page.route("**/api/v1/auth/me", async (route) => {
    const response = await route.fetch();
    const payload = (await response.json()) as {
      permissions?: string[];
      [key: string]: unknown;
    };
    await route.fulfill({
      response,
      json: {
        ...payload,
        permissions: [
          ...new Set([
            ...(payload.permissions ?? []),
            "runs.review",
            "runs.human_decisions.create",
          ]),
        ],
      },
    });
  });

  await page.route(
    "**/api/v1/exports/governed-projections/acquisition-growth*",
    async (route) => {
      growthReads += 1;
      await route.fulfill({
        json: acquisitionGrowthPacket(growthReads > 1),
        status: 200,
      });
    },
  );

  await page.route(
    `**/api/v1/runs/${encodeURIComponent(runId)}/case-inspection*`,
    async (route) => {
      await route.fulfill({ json: caseInspectionPacket, status: 200 });
    },
  );

  await page.route(
    `**/api/v1/runs/${encodeURIComponent(runId)}/acquisition-routes**`,
    async (requestRoute) => {
      const request = requestRoute.request();
      const pathname = decodeURIComponent(new URL(request.url()).pathname);
      const base = `/api/v1/runs/${runId}/acquisition-routes`;
      const detail = `${base}/${routePacket.route_id}`;
      if (request.method() === "GET" && pathname === base) {
        await requestRoute.fulfill({
          json: { routes: [routePacket], run_id: runId },
          status: 200,
        });
        return;
      }
      if (request.method() === "GET" && pathname === detail) {
        await requestRoute.fulfill({
          body: routeWire,
          contentType: "application/json",
          status: 200,
        });
        return;
      }
      if (
        request.method() === "POST" &&
        pathname === `${detail}/decision-request`
      ) {
        const body = request.postDataJSON() as Record<string, unknown>;
        expect(body.route_projection_hash).toBe(
          routePacket.route_projection_hash,
        );
        expect(body.planner_report_hash).toBe(routePacket.planner_report_hash);
        expect(body.human_decision_record_ref).toBeUndefined();
        await requestRoute.fulfill({
          json: {
            authority_decision_ref: humanDecisionSourceRef,
            human_decision_request: { required_role: "budget_owner" },
            outcome: "decision_required",
            route_id: routePacket.route_id,
            run_id: runId,
            world_growth: "no_growth",
          },
          status: 200,
        });
        return;
      }
      if (request.method() === "POST" && pathname === `${detail}/execute`) {
        const body = request.postDataJSON() as Record<string, unknown>;
        expect(body.human_decision_record_ref).toBe(digest("5"));
        await requestRoute.fulfill({
          json: {
            authority_decision_ref: humanDecisionSourceRef,
            job_id: "acquisition-job-ds15",
            receipt_phase: "requested",
            route_id: routePacket.route_id,
            run_id: runId,
            status: "accepted",
            world_growth: "no_growth",
          },
          status: 202,
        });
        return;
      }
      await requestRoute.fallback();
    },
  );

  await page.route(
    `**/api/v1/runs/${encodeURIComponent(runId)}/human-decision-gate*`,
    async (route) => {
      await route.fulfill({ json: gate, status: 200 });
    },
  );
  await page.route(
    `**/api/v1/runs/${encodeURIComponent(runId)}/human-decisions/review-effectiveness`,
    async (route) => {
      await route.fulfill({
        json: humanDecisionReviewEffectivenessFixture({ run_id: runId }),
        status: 200,
      });
    },
  );
  await page.route(
    `**/api/v1/runs/${encodeURIComponent(runId)}/human-decisions`,
    async (route) => {
      expect(route.request().method()).toBe("POST");
      const body = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        json: {
          durable_event_id: "human-decision-event-ds15",
          record: body,
          record_digest: digest("5"),
          record_ref: digest("5"),
          reservation_id: "reservation-ds15",
          reservation_version: 1,
          run_id: runId,
        },
        status: 201,
      });
    },
  );

  await page.route(
    "**/api/v1/control/jobs/acquisition-job-ds15",
    async (route) => {
      jobReads += 1;
      const terminal = jobReads > 1;
      await route.fulfill({
        json: {
          effective_execution_profile: "production",
          job_id: "acquisition-job-ds15",
          kind: "acquisition",
          meta: { request_id: `job-read-${String(jobReads)}` },
          progress: terminal
            ? {
                receipt_phase: "terminal",
                terminal_receipt_ref: digest("6"),
              }
            : { receipt_phase: "executing" },
          run_id: runId,
          state: terminal ? "completed" : "running",
        },
        status: 200,
      });
    },
  );

  return { routePacket, routeWire };
}

test.describe("DS15 acquisition route loop", () => {
  test("refusal becomes an accountable button and a continuous terminal motion", async ({
    page,
  }) => {
    await installDashboardTestState(page, { theme: "light" });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const runId = readFixtureMetadata().core_run_id;
    const fixture = await installAcquisitionFixture(page, runId);

    await page.goto(`/runs/${encodeURIComponent(runId)}/case`);
    const flow = page.getByTestId("acquisition-approval-flow");
    await expect(page.getByTestId("case-workspace-page")).toBeVisible({
      timeout: 30_000,
    });
    await expect(flow).toBeVisible({ timeout: 30_000 });
    await expect(flow).toContainText("behavioral_fixture_not_production");
    await expect(flow).toContainText("pending_epoch_activation");
    await expect(flow).toContainText("policy_admission_missing");
    await expect(flow).toContainText("unappointed");
    await expect(flow).not.toContainText("active_epoch");

    const requestReview = flow.getByRole("button", {
      name: "Request accountable review",
    });
    await requestReview.focus();
    await expect(requestReview).toBeFocused();
    await page.keyboard.press("Enter");

    const accountability = page.locator("#human-decision-accountability");
    await expect(accountability).toBeFocused();
    await accountability.fill("I accept accountability for this acquisition.");
    await page
      .locator("#human-decision-dissent")
      .fill("Disconfirming evidence was reviewed and remains visible.");
    await page.getByRole("button", { name: "approve", exact: true }).click();

    await expect(
      page.getByTestId("acquisition-timeline-focus-target"),
    ).toBeFocused();
    await expect(page.getByTestId("acquisition-job-phase")).toContainText(
      "terminal",
      { timeout: 10_000 },
    );
    await expect(flow).toContainText("quarantined_no_growth");
    await expect(flow).toContainText("deeper_terminal");
    await expect(flow.getByText(digest("6"), { exact: true })).toBeVisible();

    const liveStatus = flow.locator('[aria-live="polite"]').first();
    await expect(liveStatus).toContainText("quarantined_no_growth");
    const accessibility = await new AxeBuilder({ page })
      .include('[data-testid="acquisition-approval-flow"]')
      .analyze();
    expect(accessibility.violations).toEqual([]);

    const downloadPromise = page.waitForEvent("download");
    await flow
      .getByRole("button", {
        name: "Export acquisition route MACHINE packet",
      })
      .click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(
      `policyos-run-${runId}-acquisition-route.json`,
    );
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(Buffer.from(chunk));
    expect(Buffer.concat(chunks).toString("utf8")).toBe(fixture.routeWire);

    await expect(flow).toHaveScreenshot("ds15-acquisition-route-loop.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 100,
    });
  });

  test("keeps the pending production refusal readable in dark mobile 200%", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 900 });
    await installDashboardTestState(page, { theme: "dark" });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const runId = readFixtureMetadata().core_run_id;
    await installAcquisitionFixture(page, runId);

    await page.goto(`/runs/${encodeURIComponent(runId)}/case`);
    const flow = page.getByTestId("acquisition-approval-flow");
    await expect(page.getByTestId("case-workspace-page")).toBeVisible({
      timeout: 30_000,
    });
    await expect(flow).toBeVisible({ timeout: 30_000 });
    await page.evaluate(() => {
      document.documentElement.style.setProperty("zoom", "200%");
    });
    await expect(flow).toContainText("not_established");
    await expect(flow).toContainText("policy_admission_missing");
    expect(await horizontalOverflowOffenders(flow)).toEqual([]);
    const layout = await flow.evaluate((element) => {
      const zoom =
        Number.parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
      return {
        normalizedFlowWidth: element.getBoundingClientRect().width / zoom,
        normalizedScrollWidth: document.documentElement.scrollWidth / zoom,
        viewportWidth: document.documentElement.clientWidth,
      };
    });
    expect(
      layout.normalizedFlowWidth,
      JSON.stringify(layout),
    ).toBeLessThanOrEqual(layout.viewportWidth + 1);
    expect(layout.normalizedScrollWidth).toBeLessThanOrEqual(
      layout.viewportWidth + 1,
    );

    await expect(flow).toHaveScreenshot(
      "ds15-pending-production-dark-mobile.png",
      {
        animations: "disabled",
        caret: "hide",
        maxDiffPixels: 100,
      },
    );
  });
});
