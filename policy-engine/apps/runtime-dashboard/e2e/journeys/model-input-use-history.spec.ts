import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Locator } from "@playwright/test";

import {
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "../helpers/runtime-dashboard";

type ArtifactRef = { artifact_id: string };

type CapturedResponse = {
  meta: Record<string, unknown>;
  result: {
    run_id: string;
    action_job_id: string;
    action_status: string;
    blocked_source: { source_job_id: string };
    current_use_decision_ref?: ArtifactRef | null;
    current_basis_ref?: ArtifactRef | null;
    selected_basis_ref?: ArtifactRef | null;
    original_result_ref?: ArtifactRef | null;
    original_action_job_id?: string | null;
    currentness_status: string;
    publication_authority: boolean;
  };
};

type ResultResponseMode = "captured" | "foreign-action" | "missing";

function capturedResponse(name: string): CapturedResponse {
  const fixture = new URL(
    `../../src/api/__fixtures__/${name}`,
    import.meta.url,
  );
  return JSON.parse(
    readFileSync(fileURLToPath(fixture), "utf8"),
  ) as CapturedResponse;
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Expected a run-details object from the fixture runtime");
  }
  return value as Record<string, unknown>;
}

function resultPath(runId: string, actionJobId: string): string {
  return `/api/v1/runs/${encodeURIComponent(runId)}/model-input-use/${encodeURIComponent(actionJobId)}/n5-result`;
}

async function expectCapturedRef(
  row: Locator,
  ref: ArtifactRef | null | undefined,
) {
  expect(ref?.artifact_id).toMatch(/^sha256:[0-9a-f]{64}$/);
  await expect(row).toContainText(ref!.artifact_id);
}

test.describe("model-input result history browser consumer (captured result responses)", () => {
  /**
   * Exercise only the mounted browser consumer with captured result JSON.
   * The fixture server's Core run is synthetic; discovery-only rows carrying
   * the captured Control run alias are injected here and do not prove Core to
   * Control ownership. The Python served API/CAS path is qualified separately
   * by test_program_graph_model_input_use_served.py. This is not live API
   * coverage or whole-lane acceptance.
   */
  test("shows current C and retained B, then refuses mismatched or missing results", async ({
    page,
  }) => {
    await installDashboardTestState(page);

    const metadata = readFixtureMetadata();
    const current = capturedResponse("model-input-use-current-c.json");
    const retained = capturedResponse("model-input-use-retained-b.json");
    expect(current.result.run_id).toBe(retained.result.run_id);
    expect(current.result.action_status).toBe("completed");
    expect(retained.result.action_status).toBe("completed");

    const actions = [current, retained]
      .map(({ result }) => ({
        action_job_id: result.action_job_id,
        job_state: "completed",
      }))
      .sort((left, right) =>
        left.action_job_id < right.action_job_id
          ? -1
          : left.action_job_id > right.action_job_id
            ? 1
            : 0,
      );
    const inventory = {
      run_id: current.result.run_id,
      source_job_id: current.result.blocked_source.source_job_id,
      scope: "discovery_only",
      actions,
      // Two captured response rows do not establish complete action discovery.
      inventory_status: "limited",
      inventory_truncated: false,
      limitation_codes: ["action_binding_not_established"],
    };

    const runDetailsPath = `/api/v1/runs/${encodeURIComponent(metadata.core_run_id)}`;
    await page.route("**/api/v1/runs/*", async (route) => {
      const requestUrl = new URL(route.request().url());
      if (
        route.request().method() !== "GET" ||
        requestUrl.pathname !== runDetailsPath
      ) {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      expect(response.status()).toBe(200);
      const payload = record(await response.json());
      record(payload.run).model_input_use_actions = inventory;
      await route.fulfill({ response, json: payload });
    });

    let resultResponseMode: ResultResponseMode = "captured";
    const resultReads: Array<{
      pathname: string;
      mode: ResultResponseMode;
    }> = [];
    await page.route(
      "**/api/v1/runs/*/model-input-use/*/n5-result",
      async (route) => {
        const request = route.request();
        const pathname = new URL(request.url()).pathname;
        if (request.method() !== "GET") {
          await route.continue();
          return;
        }
        if (
          pathname ===
          resultPath(current.result.run_id, current.result.action_job_id)
        ) {
          resultReads.push({ pathname, mode: resultResponseMode });
          if (resultResponseMode === "missing") {
            await route.fulfill({
              status: 404,
              contentType: "application/json",
              body: JSON.stringify({
                code: "model_input_use_result_not_found",
                detail: "The selected candidate result is unavailable.",
                request_id: "playwright-captured-history-removal",
                status: 404,
                title: "Not Found",
                type: "about:blank",
              }),
            });
            return;
          }
          if (resultResponseMode === "foreign-action") {
            await route.fulfill({
              status: 200,
              contentType: "application/json",
              body: JSON.stringify(retained),
            });
            return;
          }
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(current),
          });
          return;
        }
        if (
          pathname ===
          resultPath(retained.result.run_id, retained.result.action_job_id)
        ) {
          resultReads.push({ pathname, mode: resultResponseMode });
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(retained),
          });
          return;
        }
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({
            code: "model_input_use_result_not_found",
            detail: "No captured result exists for this selected action.",
            request_id: "playwright-captured-history-unknown-action",
            status: 404,
            title: "Not Found",
            type: "about:blank",
          }),
        });
      },
    );

    await page.goto(
      `/runs/${encodeURIComponent(metadata.core_run_id)}/overview`,
    );
    await waitForDashboardSurface(page, "run-overview");
    await expect(page.getByTestId("model-input-use-history")).toBeVisible();
    await expect(
      page.getByTestId("model-input-use-inventory-limited"),
    ).toContainText("action_binding_not_established");

    await page
      .locator(
        `[data-testid="model-input-use-action-selector"][data-action-job-id="${current.result.action_job_id}"]`,
      )
      .click();
    const currentRow = page.getByTestId("model-input-use-result-row");
    await expect(currentRow).toHaveAttribute(
      "data-frontier-selection",
      "selected",
    );
    await expect(
      currentRow.getByTestId("model-input-use-evaluation-provenance"),
    ).toContainText("new_execution");
    await expect(
      currentRow.getByTestId("model-input-use-currentness"),
    ).toContainText("not established");
    await expect(currentRow.getByTestId("model-input-use-scope")).toContainText(
      "Candidate-only N5 evidence",
    );
    await currentRow.locator("details").nth(1).locator("summary").click();
    const currentBody = currentRow.getByTestId("model-input-use-result-body");
    await expect(currentBody).toContainText("government.balance");
    await expect(currentBody).toContainText("565");
    await expect(currentBody).toContainText('"publication_authority": false');
    await expect(currentBody).not.toContainText(
      '"publication_authority": true',
    );
    await currentRow.locator("details").first().locator("summary").click();
    const currentReferences = currentRow.getByTestId(
      "model-input-use-references",
    );
    await expectCapturedRef(
      currentReferences,
      current.result.current_use_decision_ref,
    );
    await expectCapturedRef(
      currentReferences,
      current.result.current_basis_ref,
    );
    await expectCapturedRef(
      currentReferences,
      current.result.selected_basis_ref,
    );
    await expectCapturedRef(
      currentReferences,
      current.result.original_result_ref,
    );

    await page
      .locator(
        `[data-testid="model-input-use-action-selector"][data-action-job-id="${retained.result.action_job_id}"]`,
      )
      .click();
    const retainedRow = page.getByTestId("model-input-use-result-row");
    await expect(retainedRow).toHaveAttribute(
      "data-frontier-selection",
      "superseded",
    );
    await expect(
      retainedRow.getByTestId("model-input-use-evaluation-provenance"),
    ).toContainText("retained_prior");
    await expect(
      retainedRow.getByTestId("model-input-use-basis-comparison"),
    ).toContainText("equivalent");
    await expect(
      retainedRow.getByTestId("model-input-use-currentness"),
    ).toContainText("not established");
    await retainedRow.locator("details").nth(1).locator("summary").click();
    const retainedBody = retainedRow.getByTestId("model-input-use-result-body");
    await expect(retainedBody).toContainText("government.balance");
    await expect(retainedBody).toContainText("640");
    await expect(retainedBody).toContainText("602.5");
    await expect(retainedBody).not.toContainText(
      '"publication_authority": true',
    );
    await retainedRow.locator("details").first().locator("summary").click();
    const retainedReferences = retainedRow.getByTestId(
      "model-input-use-references",
    );
    expect(retained.result.original_action_job_id).toBeTruthy();
    await expect(retainedReferences).toContainText(
      retained.result.original_action_job_id!,
    );
    await expectCapturedRef(
      retainedReferences,
      retained.result.original_result_ref,
    );

    const currentResultPath = resultPath(
      current.result.run_id,
      current.result.action_job_id,
    );
    expect(resultReads).toEqual([
      { pathname: currentResultPath, mode: "captured" },
      {
        pathname: resultPath(
          retained.result.run_id,
          retained.result.action_job_id,
        ),
        mode: "captured",
      },
    ]);

    resultResponseMode = "foreign-action";
    await page.reload();
    await page
      .locator(
        `[data-testid="model-input-use-action-selector"][data-action-job-id="${current.result.action_job_id}"]`,
      )
      .click();
    await expect(
      page.getByTestId("model-input-use-result-unavailable"),
    ).toBeVisible();
    await expect(page.getByTestId("model-input-use-result-row")).toHaveCount(0);
    await expect(page.getByTestId("model-input-use-result-body")).toHaveCount(
      0,
    );
    expect(resultReads.at(-1)).toEqual({
      pathname: currentResultPath,
      mode: "foreign-action",
    });

    resultResponseMode = "missing";
    await page.reload();
    await page
      .locator(
        `[data-testid="model-input-use-action-selector"][data-action-job-id="${current.result.action_job_id}"]`,
      )
      .click();
    await expect(
      page.getByTestId("model-input-use-result-unavailable"),
    ).toBeVisible();
    await expect(page.getByTestId("model-input-use-result-row")).toHaveCount(0);
    await expect(page.getByTestId("model-input-use-result-body")).toHaveCount(
      0,
    );
    expect(resultReads.at(-1)).toEqual({
      pathname: currentResultPath,
      mode: "missing",
    });
  });
});
