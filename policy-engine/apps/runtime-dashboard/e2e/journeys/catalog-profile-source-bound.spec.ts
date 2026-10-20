import { createHash } from "node:crypto";

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

function stringMapEntries(
  value: unknown,
  fieldName: string,
): Array<[string, string]> {
  const record = asRecord(value);
  if (record === null) {
    throw new Error(`${fieldName} is missing or is not an object`);
  }
  const entries: Array<[string, string]> = [];
  for (const [key, entryValue] of Object.entries(record)) {
    if (typeof entryValue !== "string") {
      throw new Error(`${fieldName}[${JSON.stringify(key)}] is not a string`);
    }
    entries.push([key, entryValue]);
  }
  return entries;
}

function requiredString(value: unknown, fieldName: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${fieldName} is missing or is not a non-empty string`);
  }
  return value;
}

function artifactRefIdentity(value: unknown): string | null {
  const ref = asRecord(value);
  if (
    ref === null ||
    typeof ref.artifact_id !== "string" ||
    typeof ref.kind !== "string" ||
    typeof ref.media_type !== "string"
  )
    return null;
  const profile = ref.manifest_profile_sha256;
  if (profile != null && typeof profile !== "string") return null;
  return JSON.stringify([
    ref.artifact_id,
    ref.kind,
    ref.media_type,
    profile ?? null,
  ]);
}

function assertSameCandidateHistory(payload: unknown, candidateId: string) {
  const run = asRecord(asRecord(payload)?.run);
  const projection = asRecord(run?.candidate_simulation);
  expect(projection?.artifact_status).toBe("resolved");
  expect(projection?.authority_purpose).toBe("candidate_observation_only");
  expect(projection?.publication_authority).toBe(false);
  const rows = Array.isArray(projection?.acquisition_history)
    ? projection.acquisition_history.map(asRecord)
    : [];
  const row = rows.find(
    (candidate) =>
      candidate?.terminal_outcome === "reentry_completed" &&
      candidate.old_candidate_id === candidateId &&
      candidate.new_candidate_id === candidateId,
  );
  expect(row).toBeTruthy();
  expect(row?.currentness_status).toBe("not_established");
  expect(row?.schema_version).toBe(
    "policyos.runtime.run_candidate_simulation_acquisition_history.v2",
  );
  expect(row?.reentry_receipt_schema_version).toBe(
    "policyos.runtime.acquisition_overlay_reentry.v3",
  );
  expect(row?.continuation_join_status).toBe("v3_occurrence_joined");
  expect(row?.origin_source_binding_status).toBe(
    "verified_same_candidate_root",
  );
  expect(artifactRefIdentity(row?.expected_origin_source_ref)).not.toBeNull();
  expect(artifactRefIdentity(row?.expected_origin_source_ref)).toBe(
    artifactRefIdentity(row?.origin_source_ref),
  );
  const continuation = asRecord(row?.continuation);
  expect(continuation?.currentness_status).toBe("not_established");
  expect(continuation?.continuation_currentness_status).toBe("not_established");
  expect(continuation?.publication_authority).toBe(false);
  expect(continuation?.n9_certified_candidate_ids).toEqual([]);
  expect(artifactRefIdentity(row?.new_candidate_source_ref)).not.toBeNull();
  expect(artifactRefIdentity(row?.new_candidate_source_ref)).toBe(
    artifactRefIdentity(continuation?.selected_n4_source_ref),
  );
  const occurrences = Array.isArray(continuation?.current_candidate_occurrences)
    ? continuation.current_candidate_occurrences.map(asRecord)
    : [];
  expect(
    occurrences.some(
      (occurrence) =>
        occurrence?.candidate_id === candidateId &&
        occurrence.cycle_index === continuation?.continued_cycle_index,
    ),
  ).toBe(true);
  return row;
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
  expect(legalSearchPayload?.legal_relation_refusal).toEqual({
    code: "legal_source_relation_verification_not_established",
    status: "verification_missing",
  });
  expect(legalSearchPayload?.results).toEqual([]);
  await expect(page.getByTestId("lex-search-result-mode")).toContainText(
    "Vector retrieval",
  );
  await expect(
    page.getByTestId("lex-search-legal-relation-refusal"),
  ).toContainText("verification_missing");
  await expect(
    page.getByText(/No results found for "annual leave"/i),
  ).toHaveCount(0);

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
  expect(asRecord(staleSearch.payload)?.legal_relation_refusal).toEqual({
    code: "legal_source_relation_verification_not_established",
    status: "verification_missing",
  });
  const staleResults = asRecord(staleSearch.payload)?.results;
  expect(staleResults).toEqual([]);

  const encodedRequest = metadata.source_bound_v1_request_json_base64;
  if (!encodedRequest) {
    throw new Error("source-bound V1 request metadata is missing");
  }
  const requestBody: unknown = JSON.parse(
    Buffer.from(encodedRequest, "base64").toString("utf8"),
  );
  expect(asRecord(requestBody)?.request).toEqual(expect.any(String));
  const predictiveDataSource = asRecord(asRecord(requestBody)?.data_source);
  const selectedPredictiveSnapshot = asRecord(
    predictiveDataSource?.data_snapshot_ref,
  );
  const selectedPredictiveProfile = asRecord(
    asRecord(requestBody)?.value_data_profile_ref,
  );
  const selectedPredictiveModel = asRecord(
    asRecord(requestBody)?.model_spec_ref,
  );
  const selectedPredictivePolicy = asRecord(
    asRecord(requestBody)?.policy_spec_ref,
  );
  const selectedPredictiveRule = asRecord(
    asRecord(requestBody)?.calibration_rule_ref,
  );
  expect(selectedPredictiveSnapshot?.kind).toBe("fabric.data_snapshot");
  expect(selectedPredictiveSnapshot?.manifest_profile_sha256).toMatch(
    /^sha256:[0-9a-f]{64}$/u,
  );
  expect(selectedPredictiveProfile?.kind).toBe("runtime.value_data_profile");
  expect(selectedPredictiveProfile?.manifest_profile_sha256).toMatch(
    /^sha256:[0-9a-f]{64}$/u,
  );
  expect(selectedPredictiveModel?.kind).toBe("ir.model_spec");
  expect(selectedPredictiveModel?.manifest_profile_sha256).toMatch(
    /^sha256:[0-9a-f]{64}$/u,
  );
  expect(selectedPredictivePolicy?.kind).toBe("ir.policy_spec");
  expect(selectedPredictivePolicy?.manifest_profile_sha256).toMatch(
    /^sha256:[0-9a-f]{64}$/u,
  );
  expect(selectedPredictiveRule?.kind).toBe("ir.forecast_calibration_rule");
  expect(selectedPredictiveRule?.manifest_profile_sha256).toMatch(
    /^sha256:[0-9a-f]{64}$/u,
  );
  expect(asRecord(requestBody)?.joint_interaction_candidate_intent).toBe(
    "n4_unique_parent_source_members.v1",
  );

  await page.goto(
    `/evidence?runId=${encodeURIComponent(metadata.core_run_id)}`,
  );
  await waitForDashboardSurface(page, "evidence");

  const requestBodyJson = JSON.stringify(requestBody);
  expect(requestBodyJson).toEqual(expect.any(String));
  const launchKey =
    "source-bound-e2e-v1-" +
    createHash("sha256").update(requestBodyJson!).digest("hex");
  const incompleteRequestBody = { ...asRecord(requestBody)! };
  delete incompleteRequestBody.policy_spec_ref;
  const incompleteLaunch = await page.evaluate(
    async ({ body, key }) => {
      const response = await fetch("/api/v1/control/runs/nl", {
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "Idempotency-Key": key,
        },
        body,
      });
      return { payload: await response.json(), status: response.status };
    },
    {
      body: JSON.stringify(incompleteRequestBody),
      key: `${launchKey}-incomplete-basis`,
    },
  );
  expect(incompleteLaunch.status).toBe(422);
  expect(asRecord(incompleteLaunch.payload)?.job_id).toBeUndefined();

  const requestText = requiredString(
    asRecord(requestBody)?.request,
    "source-bound NL request text",
  );
  const fixtureModelId = requiredString(
    asRecord(requestBody)?.llm_model,
    "source-bound LLM model id",
  );
  expect(metadata.source_bound_v1_model_id).toBe(fixtureModelId);
  const predictiveUnitId = requiredString(
    asRecord(requestBody)?.value_data_unit_id,
    "source-bound value data unit id",
  );
  expect(metadata.source_bound_predictive_unit_id).toBe(predictiveUnitId);

  const composerInputs: Array<[string, string]> = [
    [
      "composer-nl-data-snapshot",
      requiredString(
        selectedPredictiveSnapshot?.artifact_id,
        "snapshot artifact id",
      ),
    ],
    [
      "composer-nl-snapshot-profile",
      requiredString(
        selectedPredictiveSnapshot?.manifest_profile_sha256,
        "snapshot manifest profile",
      ),
    ],
    [
      "composer-nl-value-profile-id",
      requiredString(
        selectedPredictiveProfile?.artifact_id,
        "value profile artifact id",
      ),
    ],
    [
      "composer-nl-value-profile-digest",
      requiredString(
        selectedPredictiveProfile?.manifest_profile_sha256,
        "value profile manifest profile",
      ),
    ],
    ["composer-nl-value-unit", predictiveUnitId],
    [
      "composer-nl-model-spec-id",
      requiredString(
        selectedPredictiveModel?.artifact_id,
        "model spec artifact id",
      ),
    ],
    [
      "composer-nl-model-spec-digest",
      requiredString(
        selectedPredictiveModel?.manifest_profile_sha256,
        "model spec manifest profile",
      ),
    ],
    [
      "composer-nl-policy-spec-id",
      requiredString(
        selectedPredictivePolicy?.artifact_id,
        "policy spec artifact id",
      ),
    ],
    [
      "composer-nl-policy-spec-digest",
      requiredString(
        selectedPredictivePolicy?.manifest_profile_sha256,
        "policy spec manifest profile",
      ),
    ],
    [
      "composer-nl-rule-id",
      requiredString(
        selectedPredictiveRule?.artifact_id,
        "calibration rule artifact id",
      ),
    ],
    [
      "composer-nl-rule-digest",
      requiredString(
        selectedPredictiveRule?.manifest_profile_sha256,
        "calibration rule manifest profile",
      ),
    ],
  ];

  await page.goto("/compose?mode=nl");
  await waitForDashboardSurface(page, "composer");
  await page.getByTestId("composer-nl-brief").fill(requestText);
  const selectedModel = page.getByTestId(`llm-profile-${fixtureModelId}`);
  await expect(selectedModel).toBeVisible();
  await selectedModel.click();

  const predictiveInputsDisclosure = page.locator("details").filter({
    has: page.getByTestId("composer-nl-value-profile-id"),
  });
  await expect(predictiveInputsDisclosure).toHaveCount(1);
  await predictiveInputsDisclosure.locator("summary").click();
  for (const [testId, value] of composerInputs) {
    await page.getByTestId(testId).fill(value);
  }

  const ordinaryLaunchResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v1/control/runs/nl",
  );
  const launchButton = page.getByTestId("composer-launch-nl");
  await expect(launchButton).toBeEnabled();
  await launchButton.click();
  const ordinaryLaunchResponse = await ordinaryLaunchResponsePromise;
  expect(ordinaryLaunchResponse.status()).toBe(200);
  const ordinaryLaunchRequest = ordinaryLaunchResponse.request();
  expect(ordinaryLaunchRequest.headers()["idempotency-key"]).toBeTruthy();
  const ordinaryLaunchBody = asRecord(ordinaryLaunchRequest.postDataJSON());
  expect(ordinaryLaunchBody?.request).toBe(requestText);
  expect(ordinaryLaunchBody?.llm_model).toBe(fixtureModelId);
  expect(ordinaryLaunchBody?.llm_models).toEqual([fixtureModelId]);
  expect(ordinaryLaunchBody?.joint_interaction_candidate_intent).toBe(
    "n4_unique_parent_source_members.v1",
  );
  const ordinaryDataSource = asRecord(ordinaryLaunchBody?.data_source);
  expect(artifactRefIdentity(ordinaryDataSource?.data_snapshot_ref)).toBe(
    artifactRefIdentity(selectedPredictiveSnapshot),
  );
  expect(artifactRefIdentity(ordinaryLaunchBody?.value_data_profile_ref)).toBe(
    artifactRefIdentity(selectedPredictiveProfile),
  );
  expect(ordinaryLaunchBody?.value_data_unit_id).toBe(predictiveUnitId);
  expect(artifactRefIdentity(ordinaryLaunchBody?.model_spec_ref)).toBe(
    artifactRefIdentity(selectedPredictiveModel),
  );
  expect(artifactRefIdentity(ordinaryLaunchBody?.policy_spec_ref)).toBe(
    artifactRefIdentity(selectedPredictivePolicy),
  );
  expect(artifactRefIdentity(ordinaryLaunchBody?.calibration_rule_ref)).toBe(
    artifactRefIdentity(selectedPredictiveRule),
  );
  await expect(page).toHaveURL(/\/runs\/[^/]+\/overview$/u);

  const launchPayload = asRecord(await ordinaryLaunchResponse.json());
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
  expect(v1Run).toBeTruthy();
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
  const selectedBasisRefs = [
    selectedPredictiveSnapshot,
    selectedPredictiveProfile,
    selectedPredictiveModel,
    selectedPredictivePolicy,
    selectedPredictiveRule,
  ];
  const runRootRefs = [
    ...(Array.isArray(v1Run?.root_input_artifacts)
      ? v1Run.root_input_artifacts
      : []),
    ...(Array.isArray(v1Run?.root_artifacts) ? v1Run.root_artifacts : []),
  ];
  for (const ref of selectedBasisRefs) {
    expect(ref).not.toBeNull();
    expect(
      runRootRefs.some(
        (runRef) => artifactRefIdentity(runRef) === artifactRefIdentity(ref),
      ),
    ).toBe(true);
  }

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
  const predictiveForm = page.getByTestId(
    "overview-predictive-calibration-form",
  );
  await expect(predictiveForm).toBeVisible();
  const runCandidateRef = asRecord(
    n5Observations
      .map(asRecord)
      .find((row) => row?.status === "joint_simulated"),
  )?.n4_source_ref;
  expect(artifactRefIdentity(runCandidateRef)).not.toBeNull();
  const predictiveProfile = selectedPredictiveProfile;
  const predictiveSnapshot = selectedPredictiveSnapshot;
  const predictiveModel = selectedPredictiveModel;
  const predictivePolicy = selectedPredictivePolicy;
  const predictiveRule = selectedPredictiveRule;
  const rootRefKey = (value: unknown) => artifactRefIdentity(value);
  const selectedFormRefs: Array<[string, unknown]> = [
    ["candidate_source_ref", runCandidateRef],
    ["observed_source_ref", predictiveSnapshot],
    ["model_spec_ref", predictiveModel],
    ["policy_spec_ref", predictivePolicy],
    ["calibration_rule_ref", predictiveRule],
    ["value_data_profile_ref", predictiveProfile],
  ];
  for (const [name, ref] of selectedFormRefs) {
    const value = rootRefKey(ref);
    expect(value).not.toBeNull();
    await predictiveForm.locator(`[name="${name}"]`).selectOption(value!);
  }
  await predictiveForm
    .locator('[name="value_data_unit_id"]')
    .fill(String(metadata.source_bound_predictive_unit_id));
  await predictiveForm
    .locator('[name="target_metric"]')
    .fill(String(metadata.source_bound_predictive_target_metric));
  const predictiveValues: Record<string, string> = {
    calibration_threshold: "0.9",
    seed: "0",
    train_start: "0",
    train_end: "10",
    holdout_start: "10",
    holdout_end: "14",
    horizon: "4",
    alpha: "0.3",
    beta: "0.1",
    data_valid_time: "2026-01-01T00:00",
    calibration_window_start: "2026-01-02T00:00",
    calibration_window_end: "2026-01-03T00:00",
    policy_effective_time: "2026-01-04T00:00",
    prediction_time: "2026-01-05T00:00",
    observation_time: "2026-01-06T00:00",
  };
  for (const [name, value] of Object.entries(predictiveValues)) {
    await predictiveForm.locator(`[name="${name}"]`).fill(value);
  }
  const predictivePostPromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/runs/${encodeURIComponent(v1RunId as string)}/predictive-calibration`,
  );
  await predictiveForm
    .getByRole("button", { name: /create|evaluate/i })
    .click();
  const predictivePost = await predictivePostPromise;
  expect(predictivePost.status()).toBe(201);
  const predictivePostBody = asRecord(predictivePost.request().postDataJSON());
  expect(artifactRefIdentity(predictivePostBody?.value_data_profile_ref)).toBe(
    artifactRefIdentity(predictiveProfile),
  );
  const predictiveResult = asRecord(await predictivePost.json());
  const predictiveAssociation = asRecord(predictiveResult?.association);
  expect(predictiveAssociation?.profile_join_status).toBe("joined_candidate");
  expect(predictiveAssociation?.value_data_profile_ref).toEqual(
    predictiveProfile,
  );
  expect(predictiveAssociation?.assessment).toBe("limited");
  expect(predictiveAssociation?.authority_scope).toBe("predictive_only");
  expect(predictiveAssociation?.source_time_status).toBe("not_established");

  const predictiveFreshGet = await freshGet(
    page,
    `/api/v1/runs/${encodeURIComponent(v1RunId as string)}/predictive-calibration`,
  );
  expect(predictiveFreshGet.status).toBe(200);
  const reopenedAssociation = asRecord(
    asRecord(predictiveFreshGet.payload)?.association,
  );
  expect(reopenedAssociation).toEqual(predictiveAssociation);
  await page.goto(`/runs/${encodeURIComponent(v1RunId as string)}/overview`);
  await waitForDashboardSurface(page, "run-overview");
  await expect(
    page.getByTestId("overview-predictive-calibration"),
  ).toContainText("limited");
  await expect(
    page.getByTestId("overview-predictive-calibration"),
  ).toContainText("not_established");

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
  const v6JobId = metadata.source_bound_v6_control_job_id;
  const v6JobState = metadata.source_bound_v6_control_job_status;
  const v6FailureCode = metadata.source_bound_v6_failure_code;
  const v6FailureMessage = metadata.source_bound_v6_failure_message;
  const v6ResultRef = metadata.source_bound_v6_success_result_ref;
  const v6ChildCount = Number(metadata.source_bound_v6_child_count);
  const v6SourceProfileHash =
    metadata.source_bound_v6_source_profile_content_hash;
  const v6SelectedSkgSnapshotRef =
    metadata.source_bound_v6_selected_skg_snapshot_ref;
  const v6SelectedSkgSnapshotSha256 =
    metadata.source_bound_v6_selected_skg_snapshot_sha256;
  expect(v6RunId).toBeTruthy();
  expect(v6JobId).toBeTruthy();
  expect(v6JobState).toBe("completed");
  expect(v6FailureCode).toBe("v6_controlled_second_n4_child_failure");
  expect(v6FailureMessage).toBeTruthy();
  expect(v6ResultRef).toBeTruthy();
  expect(v6SourceProfileHash).toMatch(/^sha256:[0-9a-f]{64}$/);
  expect(v6SelectedSkgSnapshotRef).toBeTruthy();
  expect(v6SelectedSkgSnapshotSha256).toMatch(/^[0-9a-f]{64}$/);
  expect(metadata.source_bound_v6_missing_result_ref_error_code).toBe(
    "joint_simulation_result_unavailable",
  );
  const v6Response = await freshGet(
    page,
    `/api/v1/runs/${encodeURIComponent(v6RunId as string)}`,
  );
  expect(v6Response.status).toBe(200);
  const v6Projection = asRecord(
    asRecord(asRecord(v6Response.payload)?.run)?.generic_cycle_simulation,
  );
  expect(v6Projection).toMatchObject({
    artifact_status: "resolved",
    authority_purpose: "cycle_input_candidate_only",
    publication_authority: false,
    currentness_status: "not_established",
    child_profile_status: "resolved",
  });
  const childBindings = Array.isArray(v6Projection?.child_profile_bindings)
    ? v6Projection.child_profile_bindings
    : [];
  expect(childBindings).toHaveLength(v6ChildCount);
  expect(
    childBindings.every(
      (binding) => asRecord(binding)?.currentness_status === "not_established",
    ),
  ).toBe(true);

  const observations = Array.isArray(v6Projection?.n5_observations)
    ? v6Projection.n5_observations
    : [];
  const successfulObservation = observations
    .map((observation) => asRecord(observation))
    .find((observation) => observation?.status === "joint_simulated");
  expect(successfulObservation).toBeTruthy();
  expect(
    asRecord(successfulObservation?.simulation_result_ref)?.artifact_id,
  ).toBe(v6ResultRef);

  const checkpoint = asRecord(v6Projection?.recursive_cycle_checkpoint);
  expect(checkpoint).toMatchObject({
    status: "partial",
    publication_authority: false,
  });
  expect(checkpoint?.budget_stop_node_ref).toBeNull();
  const failures = Array.isArray(checkpoint?.failed_branches)
    ? checkpoint.failed_branches
    : [];
  const actualFailure = failures
    .map((failure) => asRecord(failure))
    .find((failure) => failure?.error_code === v6FailureCode);
  expect(actualFailure?.error_message).toBe(v6FailureMessage);

  await page.goto(`/runs/${encodeURIComponent(v6RunId as string)}/overview`);
  await waitForDashboardSurface(page, "run-overview");
  await expect(
    page.getByTestId("overview-generic-cycle-simulation"),
  ).toBeVisible();
  await expect(
    page.getByTestId("overview-generic-cycle-simulation-result-ref"),
  ).toHaveText(v6ResultRef as string);
  const visibleFailure = page.getByTestId(
    "overview-generic-cycle-failed-branches",
  );
  await expect(visibleFailure).toContainText(v6FailureCode as string);
  await expect(visibleFailure).toContainText(v6FailureMessage as string);

  const v7RunId = metadata.source_bound_v7_run_id;
  const v7JobId = metadata.source_bound_v7_control_job_id;
  const v7JobState = metadata.source_bound_v7_control_job_status;
  const v7BudgetStopRef = metadata.source_bound_v7_budget_stop_node_ref;
  const v7ChildCount = Number(metadata.source_bound_v7_child_count);
  expect(v7RunId).toBeTruthy();
  expect(v7JobId).toBeTruthy();
  expect(v7JobState).toBe("completed");
  expect(v7BudgetStopRef).toBeTruthy();
  expect(v7ChildCount).toBe(2);

  const v7JobResponse = await freshGet(
    page,
    `/api/v1/control/jobs/${encodeURIComponent(v7JobId as string)}`,
  );
  expect(v7JobResponse.status).toBe(200);
  const v7Job = asRecord(v7JobResponse.payload);
  expect(v7Job).toMatchObject({ job_id: v7JobId, state: "completed" });
  const v7JobProgress = asRecord(v7Job?.progress);
  expect(v7JobProgress?.recursive_budget_resolution).toEqual({
    requested_max_iterations: 1,
    effective_max_iterations: 1,
    recursive_budget: {
      max_depth: 1,
      max_nodes: 3,
      min_cycles_per_leaf: 1,
      max_cycles_per_leaf: 1,
    },
    clamp_reason: "none",
    requested_candidate_children: 2,
    effective_candidate_children: 2,
    child_budget_profile: "n4-source-complete-child-set.v1",
  });

  const v7Response = await freshGet(
    page,
    "/api/v1/runs/" + encodeURIComponent(v7RunId as string),
  );
  expect(v7Response.status).toBe(200);
  const v7Projection = asRecord(
    asRecord(asRecord(v7Response.payload)?.run)?.generic_cycle_simulation,
  );
  expect(v7Projection).toMatchObject({
    artifact_status: "resolved",
    authority_purpose: "cycle_input_candidate_only",
    publication_authority: false,
    currentness_status: "not_established",
    child_profile_status: "resolved",
  });
  const v7ChildBindings = Array.isArray(v7Projection?.child_profile_bindings)
    ? v7Projection.child_profile_bindings
        .map((binding) => asRecord(binding))
        .filter((binding): binding is JsonRecord => binding !== null)
    : [];
  const v7ChildNodeRefs = v7ChildBindings
    .map((binding) => binding.node_ref)
    .filter((nodeRef): nodeRef is string => typeof nodeRef === "string")
    .sort();
  expect(v7ChildNodeRefs).toHaveLength(v7ChildCount);
  expect(new Set(v7ChildNodeRefs).size).toBe(v7ChildCount);

  const v7Checkpoint = asRecord(v7Projection?.recursive_cycle_checkpoint);
  expect(v7Checkpoint).toMatchObject({
    schema_version: "policyos.runtime.recursive_cycle_checkpoint.v1",
    status: "partial",
    publication_authority: false,
    budget_stop_node_ref: v7BudgetStopRef,
    root_n9_status: "not_run",
    failed_branches: [],
  });
  const v7PendingFrontier = Array.isArray(v7Checkpoint?.pending_frontier)
    ? v7Checkpoint.pending_frontier.filter(
        (nodeRef): nodeRef is string => typeof nodeRef === "string",
      )
    : [];
  const v7CompletedRefs = Array.isArray(v7Checkpoint?.completed_design_refs)
    ? v7Checkpoint.completed_design_refs.filter(
        (nodeRef): nodeRef is string => typeof nodeRef === "string",
      )
    : [];
  expect(v7PendingFrontier).toHaveLength(1);
  expect([...v7PendingFrontier].sort()).toEqual(
    v7ChildNodeRefs.filter((nodeRef) => nodeRef !== v7BudgetStopRef).sort(),
  );
  expect(v7CompletedRefs).toContain(v7BudgetStopRef);
  const v7LeafTerminalKinds = asRecord(v7Checkpoint?.leaf_terminal_kinds);
  const v7LeafTerminalKindEntries = stringMapEntries(
    v7Checkpoint?.leaf_terminal_kinds,
    "recursive_cycle_checkpoint.leaf_terminal_kinds",
  );
  expect(v7LeafTerminalKindEntries.length).toBeGreaterThan(0);
  expect(v7LeafTerminalKinds?.[v7BudgetStopRef as string]).toBe(
    "budget_exhausted",
  );

  await page.goto(
    "/runs/" + encodeURIComponent(v7RunId as string) + "/overview",
  );
  await waitForDashboardSurface(page, "run-overview");
  const visibleBudgetCheckpoint = page.getByTestId(
    "overview-recursive-checkpoint",
  );
  await expect(visibleBudgetCheckpoint).toContainText(
    "Root outcome remains pending.",
  );
  await expect(visibleBudgetCheckpoint).toContainText(
    v7BudgetStopRef as string,
  );
  await expect(visibleBudgetCheckpoint).toContainText("budget_exhausted");
  await expect(visibleBudgetCheckpoint).toContainText(
    v7PendingFrontier[0] as string,
  );

  const visibleGenericCheckpoint = page.getByTestId(
    "overview-generic-cycle-checkpoint",
  );
  await expect(visibleGenericCheckpoint).toBeVisible();
  await expect(
    page.getByTestId("overview-generic-cycle-terminal-kind"),
  ).toHaveText(
    v7LeafTerminalKindEntries.map(
      ([nodeRef, terminalKind]) => nodeRef + ": " + terminalKind,
    ),
  );
  await expect(visibleGenericCheckpoint).toContainText(
    "Pending frontier: " + v7PendingFrontier.join(", "),
  );
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

test("keeps a caller-selected DataViewRequest profile through ordinary POST, worker, fresh GET, and evidence UI", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.POLISYOS_DASHBOARD_SOURCE_BOUND_PROFILE_FIXTURE !== "1",
    "requires the opt-in source-bound runtime fixture",
  );
  test.skip(
    testInfo.project.name !== "chromium",
    "the controlled CPU-backed workflow witness runs in desktop Chromium only",
  );
  test.setTimeout(180_000);
  await installDashboardTestState(page);
  await page.addInitScript(() => {
    window.localStorage.setItem("polisyos.runtime.locale", "en");
  });

  const metadata = readFixtureMetadata();
  expect(metadata.source_bound_workflow_profile_fixture_boundary).toContain(
    "controlled local SQLite source",
  );
  const artifactId =
    metadata.source_bound_workflow_data_view_request_artifact_id;
  const selectedProfile =
    metadata.source_bound_workflow_data_view_request_profile;
  const trinityRef = metadata.source_bound_workflow_trinity_bundle_ref;
  expect(artifactId).toMatch(/^sha256:[0-9a-f]{64}$/u);
  expect(selectedProfile).toMatch(/^sha256:[0-9a-f]{64}$/u);
  expect(trinityRef).toMatch(/^sha256:[0-9a-f]{64}$/u);

  await page.goto("/compose?mode=workflow");
  await waitForDashboardSurface(page, "composer");
  await page.getByLabel("Data view request ref", { exact: true }).check();
  await page.locator("#workflow-data-source-ref").fill(artifactId!);
  await page.getByTestId("composer-data-source-profile").fill(selectedProfile!);
  await page.locator("#workflow-trinity-ref").fill(trinityRef!);

  const addParam = page.getByRole("button", { name: "Add param", exact: true });
  await addParam.click();
  await page.getByLabel("param key 1").fill("control_plane_transition");
  await page.getByLabel("param value 1").fill("legacy_shadow");
  await addParam.click();
  await page.getByLabel("param key 2").fill("workflow_id");
  await page.getByLabel("param value 2").fill("scientist_default");
  await addParam.click();
  await page.getByLabel("param key 3").fill("data_view_request_profile_status");
  await page.getByLabel("param value 3").fill("worker_default_limited");

  const launchResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v1/control/runs",
  );
  await page.getByTestId("composer-launch-workflow").click();
  const launchResponse = await launchResponsePromise;
  expect(launchResponse.status()).toBe(200);
  const requestBody = asRecord(launchResponse.request().postDataJSON());
  const dataSource = asRecord(requestBody?.data_source);
  expect(dataSource?.data_view_request_ref).toEqual({
    artifact_id: artifactId,
    kind: "ir.data_view_request",
    media_type: "application/json",
    manifest_profile_sha256: selectedProfile,
  });
  const params = asRecord(requestBody?.params);
  expect(params?.data_view_request_profile_status).toBe(
    "worker_default_limited",
  );
  expect(params?.control_plane_transition).toBe("legacy_shadow");

  const launchPayload = asRecord(await launchResponse.json());
  expect(launchPayload?.status).toBe("accepted");
  expect(typeof launchPayload?.job_id).toBe("string");
  expect(typeof launchPayload?.run_id).toBe("string");
  const completedJob = await page.evaluate(async (jobId) => {
    const deadline = Date.now() + 120_000;
    while (Date.now() < deadline) {
      const response = await fetch(
        `/api/v1/control/jobs/${encodeURIComponent(jobId)}`,
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
    throw new Error(
      "ordinary workflow profile job did not finish before timeout",
    );
  }, launchPayload!.job_id as string);
  expect(completedJob.state).toBe("completed");

  const runId = launchPayload!.run_id as string;
  const evidenceResponse = await freshGet(
    page,
    `/api/v1/runs/${encodeURIComponent(runId)}/evidence-context`,
  );
  expect(evidenceResponse.status).toBe(200);
  const evidenceContext = asRecord(asRecord(evidenceResponse.payload)?.context);
  expect(evidenceContext?.data_view_request_profile_status).toBe(
    "caller_selected_profile",
  );
  expect(evidenceContext?.data_view_request_ref).toMatchObject({
    artifact_id: artifactId,
    kind: "ir.data_view_request",
    media_type: "application/json",
    manifest_profile_sha256: selectedProfile,
  });

  await page.goto(`/evidence?runId=${encodeURIComponent(runId)}`);
  await waitForDashboardSurface(page, "evidence");
  const profileStatus = page.getByTestId(
    "evidence-data-view-request-profile-status",
  );
  await expect(profileStatus).toHaveAttribute(
    "data-profile-status",
    "caller_selected_profile",
  );
  await expect(profileStatus).toContainText("Caller-selected profile");
  await expect(profileStatus).toContainText(
    "does not establish authority or currentness",
  );

  const malformedBody = {
    ...requestBody,
    data_source: {
      ...dataSource,
      data_view_request_ref: {
        ...(asRecord(dataSource?.data_view_request_ref) ?? {}),
        manifest_profile_sha256: null,
      },
    },
  };
  const malformedPost = await page.evaluate(async (body) => {
    const response = await fetch("/api/v1/control/runs", {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    return { body: await response.json(), status: response.status };
  }, malformedBody);
  expect(malformedPost.status).toBe(422);
  expect(JSON.stringify(malformedPost.body)).toContain(
    "workflow_data_view_request_profile_explicit_null",
  );
});

test("serves same-candidate root lineage through a fresh API read and overview", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.POLISYOS_DASHBOARD_SOURCE_BOUND_PROFILE_FIXTURE !== "1",
    "requires the opt-in source-bound runtime fixture",
  );
  test.skip(
    testInfo.project.name !== "chromium",
    "controlled producer witness runs in Chromium",
  );
  await installDashboardTestState(page);
  const metadata = readFixtureMetadata();
  const runId = metadata.source_bound_same_candidate_run_id;
  const candidateId = metadata.source_bound_same_candidate_candidate_id;
  expect(runId).toBeTruthy();
  expect(candidateId).toBeTruthy();
  expect(metadata.source_bound_same_candidate_fixture_boundary).toContain(
    "test-only",
  );
  const apiResponse = await freshGet(
    page,
    "/api/v1/runs/" + encodeURIComponent(runId!),
  );
  expect(apiResponse.status).toBe(200);
  const row = assertSameCandidateHistory(apiResponse.payload, candidateId!);
  const uiRunResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname ===
        "/api/v1/runs/" + encodeURIComponent(runId!),
  );
  await page.goto("/runs/" + encodeURIComponent(runId!) + "/overview");
  expect((await uiRunResponse).status()).toBe(200);
  await waitForDashboardSurface(page, "run-overview");
  const history = page.getByTestId("overview-acquisition-history");
  await expect(history).toContainText(candidateId!);
  await expect(history).toContainText(
    String(asRecord(row?.origin_source_ref)?.artifact_id),
  );
  await expect(history).toContainText("Observed origin source (forensic only)");
  await expect(history).toContainText("Producer-verified candidate root");
  await expect(history).toContainText(
    "Occurrence binding: v3_occurrence_joined",
  );
  await expect(history).toContainText("not_established");
  expect(row?.old_candidate_id).toBe(row?.new_candidate_id);
});
