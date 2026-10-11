import { expect, test } from "@playwright/test";

import {
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "../helpers/runtime-dashboard";

type JsonRecord = Record<string, unknown>;

function asRecord(value: unknown): JsonRecord | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

async function freshGet(page: import("@playwright/test").Page, path: string) {
  return page.evaluate(async (requestPath) => {
    const response = await fetch(requestPath, { cache: "no-store" });
    const payload: unknown = await response.json();
    return { payload, status: response.status };
  }, path);
}

test("serves source-bound candidate, unknown cost, recursive history limit, and catalog intent", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.POLISYOS_DASHBOARD_SOURCE_BOUND_PROFILE_FIXTURE !== "1",
    "requires the opt-in source-bound runtime fixture",
  );
  test.skip(
    testInfo.project.name !== "chromium",
    "the controlled CPU-backed producer witness runs in desktop Chromium only",
  );
  test.setTimeout(180_000);
  await installDashboardTestState(page);

  const metadata = readFixtureMetadata();
  expect(metadata.source_bound_fixture).toBe("1");
  expect(metadata.source_bound_cost_scope).toBe(
    "real_traced_producer_unknown_cost_not_manual_event",
  );

  const legalOutputDir = metadata.legal_search_output_dir;
  expect(legalOutputDir).toBeTruthy();
  expect(metadata.legal_search_fixture_boundary).toContain(
    "selected snapshot only",
  );
  await page.goto("/knowledge");
  await waitForDashboardSurface(page, "knowledge");
  const initialProfileResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname ===
        "/api/v1/control/lex/search-profile" &&
      new URL(response.url()).searchParams.get("output_dir") === legalOutputDir,
  );
  await page.getByLabel("Output directory").fill(legalOutputDir!);
  const initialProfile = await initialProfileResponse;
  expect(initialProfile.status()).toBe(200);
  const selectedProfile = asRecord(await initialProfile.json());
  expect(selectedProfile?.status).toBe("available");
  expect(selectedProfile?.output_dir).toBe(legalOutputDir);
  const selectedIntent = Array.isArray(selectedProfile?.query_generation_intent)
    ? selectedProfile.query_generation_intent
    : [];
  expect(selectedIntent).toHaveLength(1);
  expect(asRecord(selectedIntent[0])?.basis_kind).toBe(
    "legal_lex_facts_embedding",
  );

  await page.getByLabel("Knowledge search").fill("annual leave");
  const legalSearchResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v1/control/lex/search",
  );
  await page.getByRole("button", { name: "Search" }).click();
  const legalSearch = await legalSearchResponse;
  expect(legalSearch.status()).toBe(200);
  const legalSearchRequest = asRecord(legalSearch.request().postDataJSON());
  expect(legalSearchRequest?.output_dir).toBe(legalOutputDir);
  expect(legalSearchRequest?.query_generation_intent).toEqual(selectedIntent);
  const legalSearchPayload = asRecord(await legalSearch.json());
  expect(legalSearchPayload?.search_mode).toBe("vector");
  expect(legalSearchPayload?.vector_refusal_code).toBeNull();
  await expect(page.getByTestId("lex-search-result-mode")).toContainText(
    "Vector retrieval",
  );
  await expect(
    page.getByText("Worker is entitled to annual leave"),
  ).toBeVisible();

  const staleIntent = selectedIntent.map((item) => ({ ...asRecord(item)! }));
  const originalInventoryJson = asRecord(staleIntent[0])?.inventory_json;
  staleIntent[0] = {
    ...asRecord(staleIntent[0]),
    generation_id: "f".repeat(32),
  };
  expect(asRecord(staleIntent[0])?.inventory_json).toBe(originalInventoryJson);
  const staleSearch = await page.evaluate(
    async ({ outputDir, intent }) => {
      const response = await fetch("/api/v1/control/lex/search", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          query: "annual leave",
          top_k: 5,
          output_dir: outputDir,
          query_generation_intent: intent,
        }),
      });
      return { payload: await response.json(), status: response.status };
    },
    { outputDir: legalOutputDir!, intent: staleIntent },
  );
  expect(staleSearch.status).toBe(200);
  expect(asRecord(staleSearch.payload)?.search_mode).toBe("text");
  expect(asRecord(staleSearch.payload)?.vector_refusal_code).toBe(
    "query_profile_stale_or_mismatched",
  );
  const staleResults = asRecord(staleSearch.payload)?.results;
  expect(Array.isArray(staleResults)).toBe(true);
  expect(asRecord((staleResults as unknown[])[0])?.fact_id).toBe(
    "fact-annual-leave",
  );

  const encodedRequest = metadata.source_bound_v1_request_json_base64;
  if (!encodedRequest) {
    throw new Error("source-bound V1 request metadata is missing");
  }
  const requestBody: unknown = JSON.parse(
    Buffer.from(encodedRequest, "base64").toString("utf8"),
  );
  expect(asRecord(requestBody)?.request).toEqual(expect.any(String));

  await page.goto(
    `/evidence?runId=${encodeURIComponent(metadata.core_run_id)}`,
  );
  await waitForDashboardSurface(page, "evidence");

  const launch = await page.evaluate(async (body) => {
    const response = await fetch("/api/v1/control/runs/nl", {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    return { payload: await response.json(), status: response.status };
  }, requestBody);
  expect(launch.status).toBe(200);
  const launchPayload = asRecord(launch.payload);
  expect(launchPayload?.status).toBe("accepted");
  const jobId = launchPayload?.job_id;
  expect(typeof jobId).toBe("string");

  const completedJob = await page.evaluate(async (acceptedJobId) => {
    const deadline = Date.now() + 150_000;
    while (Date.now() < deadline) {
      const response = await fetch(
        `/api/v1/control/jobs/${encodeURIComponent(acceptedJobId)}`,
        { cache: "no-store", credentials: "include" },
      );
      const payload: unknown = await response.json();
      if (!response.ok) {
        throw new Error(`control job read failed: ${response.status}`);
      }
      const job =
        typeof payload === "object" && payload !== null
          ? (payload as Record<string, unknown>)
          : {};
      if (job.state === "completed" || job.state === "failed") {
        return job;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 500));
    }
    throw new Error("source-bound control job did not complete before timeout");
  }, jobId as string);
  expect(completedJob.state).toBe("completed");
  const progress = asRecord(completedJob.progress);
  const v1RunId = progress?.core_run_id;
  expect(typeof v1RunId).toBe("string");

  const runResponse = await freshGet(
    page,
    `/api/v1/runs/${encodeURIComponent(v1RunId as string)}`,
  );
  expect(runResponse.status).toBe(200);
  const v1Run = asRecord(asRecord(runResponse.payload)?.run);
  const v1Projection = asRecord(v1Run?.candidate_simulation);
  expect(v1Projection?.artifact_status).toBe("resolved");
  expect(v1Projection?.authority_purpose).toBe("candidate_observation_only");
  expect(v1Projection?.publication_authority).toBe(false);
  const n5Observations = Array.isArray(v1Projection?.n5_observations)
    ? v1Projection.n5_observations
    : [];
  expect(
    n5Observations.some(
      (observation) => asRecord(observation)?.status === "joint_simulated",
    ),
  ).toBe(true);
  expect(Array.isArray(v1Projection?.acquisition_history)).toBe(true);

  const agentsResponse = await freshGet(
    page,
    `/api/v1/runs/${encodeURIComponent(v1RunId as string)}/agents`,
  );
  expect(agentsResponse.status).toBe(200);
  const pipeline = asRecord(asRecord(agentsResponse.payload)?.pipeline);
  const attempts = Array.isArray(pipeline?.attempts) ? pipeline.attempts : [];
  const costEvents = attempts.flatMap((attempt) => {
    const steps = asRecord(attempt)?.steps;
    return Array.isArray(steps)
      ? steps.flatMap((step) => {
          const events = asRecord(step)?.cost_events;
          return Array.isArray(events) ? events : [];
        })
      : [];
  });
  expect(
    costEvents.some((event) => {
      const row = asRecord(event);
      return (
        row?.cost_origin === "unknown" &&
        (row.amount === null || typeof row.amount === "undefined")
      );
    }),
  ).toBe(true);

  const renderedAgentsResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname ===
        `/api/v1/runs/${encodeURIComponent(v1RunId as string)}/agents`,
  );
  await page.goto(`/runs/${encodeURIComponent(v1RunId as string)}/agents`);
  const renderedAgentsResponse = await renderedAgentsResponsePromise;
  expect(renderedAgentsResponse.status()).toBe(200);
  await waitForDashboardSurface(page, "run-agents");
  const agentsTab = page.getByTestId("run-tab-agents");
  await expect(agentsTab).toBeVisible();
  const visibleCostSummary = agentsTab
    .getByText("Cost", { exact: true })
    .first()
    .locator("..");
  await expect(
    visibleCostSummary.getByText("Unknown", { exact: true }),
  ).toBeVisible();

  await page.goto(`/runs/${encodeURIComponent(v1RunId as string)}/overview`);
  await waitForDashboardSurface(page, "run-overview");
  await expect(page.getByTestId("overview-candidate-simulation")).toBeVisible();

  await page.goto(
    `/evidence?runId=${encodeURIComponent(metadata.core_run_id)}`,
  );
  await waitForDashboardSurface(page, "evidence");
  await page.getByTestId("evidence-metric-input").fill("inflation");
  await page
    .locator("#evidence-catalog-run-profile-select")
    .selectOption("catalog_refresh");
  const resolveResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v1/control/data/resolve",
  );
  await page.getByTestId("evidence-resolve").click();
  const resolveResponse = await resolveResponsePromise;
  expect(resolveResponse.status()).toBe(422);
  expect(resolveResponse.request().postDataJSON()).toMatchObject({
    catalog_run_profile: "catalog_refresh",
  });
  await expect(page.getByText(/catalog_run_profile_conflict/)).toBeVisible();

  const v6RunId = metadata.source_bound_v6_run_id;
  const v6FailureCode = metadata.source_bound_v6_failure_code;
  expect(v6RunId).toBeTruthy();
  expect(v6FailureCode).toBe("controlled_sibling_generation_failure");
  const v6Response = await freshGet(
    page,
    `/api/v1/runs/${encodeURIComponent(v6RunId as string)}`,
  );
  expect(v6Response.status).toBe(200);
  const v6Projection = asRecord(
    asRecord(asRecord(v6Response.payload)?.run)?.candidate_simulation,
  );
  expect(v6Projection?.recursive_cycle_checkpoint).toMatchObject({
    schema_version: "policyos.runtime.recursive_cycle_checkpoint.v2",
    status: "partial",
    publication_authority: false,
  });
  const checkpoint = asRecord(v6Projection?.recursive_cycle_checkpoint);
  const failures = Array.isArray(checkpoint?.failed_branches)
    ? checkpoint.failed_branches
    : [];
  expect(
    failures.some((failure) => asRecord(failure)?.error_code === v6FailureCode),
  ).toBe(true);
  expect(v6Projection?.acquisition_history).toEqual([]);
  expect(v6Projection?.acquisition_history_limitation_code).toBe(
    "acquisition_n4_source_not_established",
  );

  await page.goto(`/runs/${encodeURIComponent(v6RunId as string)}/overview`);
  await waitForDashboardSurface(page, "run-overview");
  await expect(page.getByTestId("overview-candidate-simulation")).toBeVisible();
  await expect(
    page.getByTestId("overview-acquisition-history-limitation"),
  ).toHaveText("acquisition_n4_source_not_established");
});

test("switches profile-qualified artifact views and refuses mismatched or absent profiles", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.POLISYOS_DASHBOARD_SOURCE_BOUND_PROFILE_FIXTURE !== "1",
    "requires the opt-in source-bound runtime fixture",
  );
  test.skip(
    testInfo.project.name !== "chromium",
    "the controlled source-bound browser witness runs in desktop Chromium only",
  );
  test.setTimeout(60_000);
  await installDashboardTestState(page);

  const metadata = readFixtureMetadata();
  expect(metadata.source_bound_fixture).toBe("1");
  expect(metadata.source_bound_profile_inspector_authority_scope).toBe(
    "controlled_fixture_runtime_inspector_and_dashboard_only_no_publication_claim",
  );
  const metadataText = (key: string): string => {
    const value = metadata[key];
    if (!value) {
      throw new Error(
        `source-bound profile inspector metadata is missing: ${key}`,
      );
    }
    return value;
  };
  const artifactId = metadataText("source_bound_profile_inspector_artifact_id");
  const primaryRef = {
    artifact_id: artifactId,
    kind: metadataText("source_bound_profile_inspector_primary_kind"),
    media_type: metadataText(
      "source_bound_profile_inspector_primary_media_type",
    ),
    manifest_profile_sha256: metadataText(
      "source_bound_profile_inspector_primary_profile",
    ),
  };
  const siblingRef = {
    artifact_id: artifactId,
    kind: metadataText("source_bound_profile_inspector_sibling_kind"),
    media_type: metadataText(
      "source_bound_profile_inspector_sibling_media_type",
    ),
    manifest_profile_sha256: metadataText(
      "source_bound_profile_inspector_sibling_profile",
    ),
  };
  expect(primaryRef.kind).not.toBe(siblingRef.kind);
  expect(primaryRef.manifest_profile_sha256).not.toBe(
    siblingRef.manifest_profile_sha256,
  );

  const fullRefHref = (ref: typeof primaryRef): string => {
    const search = new URLSearchParams({
      tab: "content",
      artifactRefKey: JSON.stringify([
        ref.artifact_id,
        ref.kind,
        ref.media_type,
        ref.manifest_profile_sha256,
      ]),
    });
    return `/artifacts/${ref.artifact_id}?${search.toString()}`;
  };
  const waitForSelectedArtifactResponse = (suffix: string, profile: string) =>
    page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        response.request().method() === "GET" &&
        decodeURIComponent(url.pathname) ===
          `/api/v1/artifacts/${artifactId}${suffix}` &&
        url.searchParams.get("manifest_profile_sha256") === profile
      );
    });
  const changeBrowserSelector = (href: string) =>
    page.evaluate((nextHref) => {
      window.history.pushState(window.history.state, "", nextHref);
      window.dispatchEvent(
        new PopStateEvent("popstate", { state: window.history.state }),
      );
    }, href);

  const primaryManifestResponse = waitForSelectedArtifactResponse(
    "",
    primaryRef.manifest_profile_sha256,
  );
  const primaryContentResponse = waitForSelectedArtifactResponse(
    "/content",
    primaryRef.manifest_profile_sha256,
  );
  await page.goto(fullRefHref(primaryRef));
  await waitForDashboardSurface(page, "artifact");
  const [primaryManifest, primaryContent] = await Promise.all([
    primaryManifestResponse,
    primaryContentResponse,
  ]);
  expect(primaryManifest.status()).toBe(200);
  expect(primaryContent.status()).toBe(200);
  const primaryManifestArtifact = asRecord(
    asRecord(await primaryManifest.json())?.artifact,
  );
  const primaryContentArtifact = asRecord(
    asRecord(await primaryContent.json())?.artifact,
  );
  expect(primaryManifestArtifact).toMatchObject({
    artifact_id: artifactId,
    kind: primaryRef.kind,
    manifest_profile_sha256: primaryRef.manifest_profile_sha256,
  });
  expect(primaryContentArtifact).toMatchObject({
    artifact_id: artifactId,
    kind: primaryRef.kind,
    manifest_profile_sha256: primaryRef.manifest_profile_sha256,
    preview: {
      fixture: "source_bound_profile_inspector",
      marker: "same-bytes-across-profile-views",
    },
  });
  const primaryEtag = primaryContent.headers()["etag"];
  if (!primaryEtag) {
    throw new Error("primary selected artifact content response has no ETag");
  }
  await expect(page.getByTestId("artifact-reference-selection")).toContainText(
    primaryRef.manifest_profile_sha256,
  );
  await expect(page.getByTestId("artifact-resolved-profile")).toContainText(
    primaryRef.manifest_profile_sha256,
  );
  await expect(page.getByTestId("artifact-page")).toContainText(
    "same-bytes-across-profile-views",
  );
  await expect(page.getByText(primaryRef.kind, { exact: true })).toBeVisible();

  const siblingManifestResponse = waitForSelectedArtifactResponse(
    "",
    siblingRef.manifest_profile_sha256,
  );
  const siblingContentResponse = waitForSelectedArtifactResponse(
    "/content",
    siblingRef.manifest_profile_sha256,
  );
  await changeBrowserSelector(fullRefHref(siblingRef));
  const [siblingManifest, siblingContent] = await Promise.all([
    siblingManifestResponse,
    siblingContentResponse,
  ]);
  expect(siblingManifest.status()).toBe(200);
  expect(siblingContent.status()).toBe(200);
  const siblingManifestArtifact = asRecord(
    asRecord(await siblingManifest.json())?.artifact,
  );
  const siblingContentArtifact = asRecord(
    asRecord(await siblingContent.json())?.artifact,
  );
  expect(siblingManifestArtifact).toMatchObject({
    artifact_id: artifactId,
    kind: siblingRef.kind,
    manifest_profile_sha256: siblingRef.manifest_profile_sha256,
  });
  expect(siblingContentArtifact).toMatchObject({
    artifact_id: artifactId,
    kind: siblingRef.kind,
    manifest_profile_sha256: siblingRef.manifest_profile_sha256,
    preview: {
      fixture: "source_bound_profile_inspector",
      marker: "same-bytes-across-profile-views",
    },
  });
  const siblingEtag = siblingContent.headers()["etag"];
  if (!siblingEtag) {
    throw new Error("sibling selected artifact content response has no ETag");
  }
  expect(siblingEtag).not.toBe(primaryEtag);
  await expect(page.getByTestId("artifact-reference-selection")).toContainText(
    siblingRef.manifest_profile_sha256,
  );
  await expect(page.getByTestId("artifact-resolved-profile")).toContainText(
    siblingRef.manifest_profile_sha256,
  );
  await expect(page.getByText(siblingRef.kind, { exact: true })).toBeVisible();
  await expect(page.getByTestId("artifact-page")).toContainText(
    "same-bytes-across-profile-views",
  );

  const crossProfileRevalidation = await page.evaluate(
    async ({ selectedArtifactId, selectedProfile, priorProfileEtag }) => {
      const url = new URL(
        `/api/v1/artifacts/${selectedArtifactId}/content`,
        window.location.origin,
      );
      url.searchParams.set("max_bytes", "65536");
      url.searchParams.set("manifest_profile_sha256", selectedProfile);
      const response = await fetch(url, {
        cache: "no-store",
        credentials: "include",
        headers: { "If-None-Match": priorProfileEtag },
      });
      return {
        etag: response.headers.get("etag"),
        payload: (await response.json()) as unknown,
        status: response.status,
      };
    },
    {
      selectedArtifactId: artifactId,
      selectedProfile: siblingRef.manifest_profile_sha256,
      priorProfileEtag: primaryEtag,
    },
  );
  expect(crossProfileRevalidation.status).toBe(200);
  expect(crossProfileRevalidation.etag).toBe(siblingEtag);
  expect(
    asRecord(asRecord(crossProfileRevalidation.payload)?.artifact)
      ?.manifest_profile_sha256,
  ).toBe(siblingRef.manifest_profile_sha256);

  const mismatchedRef = {
    ...primaryRef,
    manifest_profile_sha256: siblingRef.manifest_profile_sha256,
  };
  const mismatchedManifestResponse = waitForSelectedArtifactResponse(
    "",
    siblingRef.manifest_profile_sha256,
  );
  const mismatchedContentResponse = waitForSelectedArtifactResponse(
    "/content",
    siblingRef.manifest_profile_sha256,
  );
  await changeBrowserSelector(fullRefHref(mismatchedRef));
  const [mismatchedManifest, mismatchedContent] = await Promise.all([
    mismatchedManifestResponse,
    mismatchedContentResponse,
  ]);
  expect(mismatchedManifest.status()).toBe(200);
  expect(mismatchedContent.status()).toBe(200);
  expect(
    asRecord(asRecord(await mismatchedManifest.json())?.artifact),
  ).toMatchObject({
    kind: siblingRef.kind,
    manifest_profile_sha256: siblingRef.manifest_profile_sha256,
  });
  expect(
    asRecord(asRecord(await mismatchedContent.json())?.artifact),
  ).toMatchObject({
    kind: siblingRef.kind,
    manifest_profile_sha256: siblingRef.manifest_profile_sha256,
  });
  await expect(
    page.getByText("Unable to load artifact manifest"),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Error: Resolved artifact manifest does not match the selected ref",
    ),
  ).toBeVisible();
  await expect(page.getByText("Unable to load artifact content")).toBeVisible();
  await expect(
    page.getByText(
      "Error: Resolved artifact content does not match the selected ref",
    ),
  ).toBeVisible();
  await expect(page.getByTestId("artifact-viewer")).not.toBeVisible();
  await expect(page.getByTestId("artifact-page")).not.toContainText(
    "same-bytes-across-profile-views",
  );

  const absentProfile = `sha256:${"f".repeat(64)}`;
  const absentRef = { ...primaryRef, manifest_profile_sha256: absentProfile };
  const absentManifestResponse = waitForSelectedArtifactResponse(
    "",
    absentProfile,
  );
  const absentContentResponse = waitForSelectedArtifactResponse(
    "/content",
    absentProfile,
  );
  await changeBrowserSelector(fullRefHref(absentRef));
  const [absentManifest, absentContent] = await Promise.all([
    absentManifestResponse,
    absentContentResponse,
  ]);
  expect(absentManifest.status()).toBe(404);
  expect(asRecord(await absentManifest.json())?.code).toBe(
    "artifact_manifest_profile_not_found",
  );
  expect(absentContent.status()).toBe(404);
  expect(asRecord(await absentContent.json())?.code).toBe(
    "artifact_manifest_profile_not_found",
  );
  await expect(
    page.getByText("Unable to load artifact manifest"),
  ).toBeVisible();
  await expect(page.getByText("Unable to load artifact content")).toBeVisible();
  await expect(page.getByTestId("artifact-page")).toContainText(absentProfile);
  await expect(page.getByTestId("artifact-page")).not.toContainText(
    "same-bytes-across-profile-views",
  );
});
