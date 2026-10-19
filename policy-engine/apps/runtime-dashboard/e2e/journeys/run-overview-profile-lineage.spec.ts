import { expect, test } from "@playwright/test";

import {
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "../helpers/runtime-dashboard";

test.describe("run overview profile-bound quantity lineage", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
  });

  test("loads real run quantities, binds one lineage batch, and opens the trust inspector", async ({
    page,
  }) => {
    const runId = readFixtureMetadata().core_run_id;
    const apiBase = new URL("http://127.0.0.1:8000");
    const fabricResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        new URL(response.url()).pathname ===
          `/api/v1/runs/${encodeURIComponent(runId)}/fabric-decision-data`,
    );
    const lineageResponses: import("@playwright/test").Response[] = [];
    page.on("response", (response) => {
      if (
        response.request().method() === "POST" &&
        new URL(response.url()).pathname === "/api/v1/lineage/batch"
      ) {
        lineageResponses.push(response);
      }
    });

    await page.goto(
      `/runs/${encodeURIComponent(runId)}/overview?trust=expanded`,
    );
    await waitForDashboardSurface(page, "run-overview");

    const fabricResponse = await fabricResponsePromise;
    expect(fabricResponse.status()).toBe(200);
    const fabric = (await fabricResponse.json()) as {
      decision_data?: Array<{
        kind?: string;
        value?: { metric_id?: string | null };
        lineage?: {
          id?: string;
          artifact_ref?: {
            artifact_id?: string;
            kind?: string;
            media_type?: string;
            manifest_profile_sha256?: string;
          } | null;
        };
      }>;
    };
    const quantityRows = (fabric.decision_data ?? []).filter(
      (row) => row.kind === "quantity",
    );
    expect(quantityRows.length).toBeGreaterThan(0);
    await expect(
      page.getByTestId("overview-decision-quantity").first(),
    ).toBeVisible();
    const summaryScore = page.getByTestId("overview-summary-decision-score");
    await expect(summaryScore).toBeVisible();
    await expect(summaryScore).toHaveAttribute(
      "data-lineage-status",
      "untraced",
    );
    await expect(summaryScore.locator(".trust-status-button")).toHaveCount(0);

    await expect.poll(() => lineageResponses.length).toBe(1);
    const lineageResponse = lineageResponses[0];
    expect(lineageResponse?.status()).toBe(200);
    const requestBody = lineageResponse?.request().postDataJSON() as {
      lineage_ids?: string[];
      run_id?: string;
      selected_artifact_refs?: Array<{
        artifact_id: string;
        kind: string;
        media_type: string;
        manifest_profile_sha256: string;
      } | null>;
    };
    expect(requestBody.run_id).toBe(runId);
    expect(requestBody.lineage_ids?.length).toBeGreaterThan(0);
    expect(requestBody.selected_artifact_refs).toHaveLength(
      requestBody.lineage_ids?.length ?? -1,
    );
    const selectedRef = requestBody.selected_artifact_refs?.find(
      (ref) => ref !== null,
    );
    expect(selectedRef?.manifest_profile_sha256).toMatch(
      /^sha256:[0-9a-f]{64}$/,
    );
    expect(
      quantityRows.some(
        (row) =>
          row.lineage?.artifact_ref?.artifact_id === selectedRef?.artifact_id &&
          row.lineage?.artifact_ref?.kind === selectedRef?.kind &&
          row.lineage?.artifact_ref?.media_type === selectedRef?.media_type &&
          row.lineage?.artifact_ref?.manifest_profile_sha256 ===
            selectedRef?.manifest_profile_sha256,
      ),
    ).toBe(true);

    const batch = (await lineageResponse?.json()) as {
      temporal_scope?: Record<string, unknown> | null;
      lineages?: Array<{
        id?: string;
        profile_binding_status?: string | null;
        selected_artifact_ref?: {
          artifact_id?: string;
          kind?: string;
          media_type?: string;
          manifest_profile_sha256?: string;
        } | null;
        source_run_id?: string | null;
        artifact_ref_provenance?: string | null;
        trust_metadata?: {
          temporal_scope?: Record<string, unknown> | null;
        } | null;
      }>;
    };
    const boundGraph = (batch.lineages ?? []).find(
      (lineage) =>
        lineage.profile_binding_status === "verified" &&
        lineage.selected_artifact_ref?.artifact_id ===
          selectedRef?.artifact_id &&
        lineage.selected_artifact_ref?.kind === selectedRef?.kind &&
        lineage.selected_artifact_ref?.media_type === selectedRef?.media_type &&
        lineage.selected_artifact_ref?.manifest_profile_sha256 ===
          selectedRef?.manifest_profile_sha256 &&
        lineage.source_run_id === runId &&
        lineage.artifact_ref_provenance !== null,
    );
    expect(boundGraph?.selected_artifact_ref).toMatchObject(selectedRef ?? {});
    expect(boundGraph?.source_run_id).toBe(runId);
    expect(boundGraph?.artifact_ref_provenance).toMatch(
      /^(run_output_ref|reader_materialized)$/,
    );
    expect(boundGraph?.trust_metadata?.temporal_scope ?? null).toEqual(
      batch.temporal_scope ?? null,
    );

    const selectedProfile = selectedRef?.manifest_profile_sha256;
    expect(selectedProfile).toBeTruthy();
    const boundGraphId = boundGraph?.id;
    expect(boundGraphId).toBeTruthy();
    const exactQuantity = quantityRows.find(
      (row) =>
        row.lineage?.id === boundGraphId &&
        row.lineage?.artifact_ref?.artifact_id === selectedRef?.artifact_id &&
        row.lineage?.artifact_ref?.kind === selectedRef?.kind &&
        row.lineage?.artifact_ref?.media_type === selectedRef?.media_type &&
        row.lineage?.artifact_ref?.manifest_profile_sha256 === selectedProfile,
    );
    const metricId = exactQuantity?.value?.metric_id;
    expect(metricId).toBeTruthy();
    const temporal = batch.temporal_scope;
    const expectedTemporal = JSON.stringify(
      temporal === undefined ? null : temporal,
    );
    const selectedQuantity = page.locator(
      `[data-testid="overview-decision-quantity"][data-selected-artifact-profile="${selectedProfile}"][data-source-run-id="${runId}"][data-lineage-id="${boundGraphId}"][data-quantity-metric-id="${metricId}"]`,
    );
    await expect(selectedQuantity).toHaveCount(1);
    await expect(selectedQuantity).toBeVisible();
    await expect(selectedQuantity).toHaveAttribute(
      "data-profile-binding-status",
      "verified",
    );
    await expect(selectedQuantity).toHaveAttribute(
      "data-profile-origin",
      boundGraph?.artifact_ref_provenance ?? "",
    );
    await expect(selectedQuantity).toHaveAttribute(
      "data-profile-temporal-scope",
      expectedTemporal,
    );
    const trustButton = selectedQuantity.locator(".trust-status-button");
    await expect(trustButton).toHaveCount(1);
    await trustButton.click();
    const inspector = page.getByRole("dialog");
    await expect(inspector).toBeVisible();
    await expect(
      inspector.getByTestId("trust-inspector-subject-id"),
    ).toHaveText(boundGraphId ?? "");
    await expect(
      inspector.getByTestId("trust-inspector-profile-lineage"),
    ).toHaveText(boundGraphId ?? "");
    await expect(
      inspector.getByTestId("trust-inspector-selected-artifact-ref"),
    ).toContainText(selectedRef?.artifact_id ?? "");
    await expect(
      inspector.getByTestId("trust-inspector-selected-artifact-ref"),
    ).toContainText(selectedProfile ?? "");
    await expect(
      inspector.getByTestId("trust-inspector-profile-origin"),
    ).toHaveText(boundGraph?.artifact_ref_provenance ?? "");
    await expect(
      inspector.getByTestId("trust-inspector-source-run"),
    ).toHaveText(runId);
    await expect(
      inspector.getByTestId("trust-inspector-profile-time"),
    ).toHaveText(expectedTemporal);
    await expect(
      inspector.getByTestId("trust-inspector-follow-on-generic"),
    ).toBeVisible();

    await inspector.getByRole("button", { name: "Close" }).click();
    const hashButton = selectedQuantity.locator(".trust-hash-chip");
    await expect(hashButton).toHaveCount(1);
    await hashButton.click();
    const hashInspector = page.getByRole("dialog");
    await expect(hashInspector).toBeVisible();
    await expect(
      hashInspector.getByTestId("trust-inspector-subject-id"),
    ).toHaveText(boundGraphId ?? "");
    await expect(
      hashInspector.getByTestId("trust-inspector-profile-lineage"),
    ).toHaveText(boundGraphId ?? "");
    await expect(
      hashInspector.getByTestId("trust-inspector-selected-artifact-ref"),
    ).toContainText(selectedProfile ?? "");
    await expect(
      hashInspector.getByTestId("trust-inspector-profile-origin"),
    ).toHaveText(boundGraph?.artifact_ref_provenance ?? "");
    await expect(
      hashInspector.getByTestId("trust-inspector-source-run"),
    ).toHaveText(runId);
    await expect(
      hashInspector.getByTestId("trust-inspector-profile-time"),
    ).toHaveText(expectedTemporal);
    await expect(
      hashInspector.getByTestId("trust-inspector-follow-on-generic"),
    ).toBeVisible();

    expect(new URL(lineageResponse!.url()).origin).toBe(apiBase.origin);
  });
});
