import { createHash } from "node:crypto";

import { render, screen } from "@testing-library/react";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";

import { RunHteExecutionSummary } from "@/features/runs/components/RunHteExecutionSummary";
import { parseRunExecutionHteProjection } from "@/features/runs/domain/runExecutionHte";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import actualResponseBytes from "./__fixtures__/r7-run-details-response.content?raw";
import { runDetailsQueryOptions } from "./useRunDetails";

const RUN_ALIAS = "R_5c3bb8a8acc05740";
const CORE_RUN_ID =
  "control-17657e6688a431dd68caf2d7cdf99035a803bb211f6f970e666808e337b88313";
const RESPONSE_SHA256 =
  "8b6e5157f3b707242c300b10b23f1aa4db130ea702e7ce63c6b89cc6dd8fe86b";

// Node's Request needs an absolute URL; browsers resolve the production default
// against the page origin. Keep the real client and mock only the HTTP transport.
vi.hoisted(() => {
  vi.stubEnv("VITE_RUNTIME_API_URL", "http://localhost");
});
afterAll(() => vi.unstubAllEnvs());

type CapturedResponse = {
  run: {
    run_id: string;
    source_kind: string;
    method_execution_selection: unknown;
  };
};

function asRecord(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("Expected a record in the captured Run Details response");
  }
  return value as Record<string, unknown>;
}

function capturedProjection(): Record<string, unknown> {
  const wire = JSON.parse(actualResponseBytes) as CapturedResponse;
  return structuredClone(asRecord(wire.run.method_execution_selection));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Run Details HTE actual Python/FastAPI response", () => {
  it("loads the untouched captured GET bytes through the runtime client and renders the owner-selected point summary", async () => {
    expect(
      createHash("sha256").update(actualResponseBytes, "utf8").digest("hex"),
    ).toBe(RESPONSE_SHA256);

    const captured = JSON.parse(actualResponseBytes) as CapturedResponse;
    expect(captured.run.run_id).toBe(CORE_RUN_ID);
    expect(captured.run.source_kind).toBe("core_run");
    const capturedProjection = asRecord(
      captured.run.method_execution_selection,
    );
    const capturedSelection = asRecord(capturedProjection.selection);
    expect(capturedSelection.run_id).toBe(RUN_ALIAS);
    expect(capturedSelection.point_result_ref).toMatchObject({
      kind: "ir.hte_point_result",
    });
    expect(capturedSelection.hte_result_ref).toBeNull();
    const capturedSummary = asRecord(capturedSelection.hte);
    expect(capturedSummary.materialization_binding_ref).toMatchObject({
      kind: "foundry.hte.physical_source_materialization_binding",
    });
    expect(
      asRecord(capturedSelection.owned_hte_request_context),
    ).not.toHaveProperty("materialization_binding_ref");
    expect(
      asRecord(asRecord(capturedProjection.request).owned_hte_request_context),
    ).not.toHaveProperty("materialization_binding_ref");

    let fetchedUrl = "";
    let fetchedMethod = "";
    const fetchSpy = vi.fn(
      async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const request =
          input instanceof Request ? input : new Request(input, init);
        fetchedUrl = request.url;
        fetchedMethod = request.method;
        return new Response(actualResponseBytes, {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      },
    );
    vi.stubGlobal("fetch", fetchSpy);

    const result = await runDetailsQueryOptions(RUN_ALIAS).queryFn();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(fetchedMethod).toBe("GET");
    expect(fetchedUrl).toContain("/api/v1/runs/" + RUN_ALIAS);
    expect(result.run.run_id).toBe(CORE_RUN_ID);
    expect(result.run.source_kind).toBe("core_run");

    const projection = result.run.method_execution_selection;
    const parsed = parseRunExecutionHteProjection(projection);
    expect(parsed.kind).toBe("hte");
    if (parsed.kind !== "hte" || parsed.summary.kind !== "point_estimate") {
      throw new Error("Captured owner-selected HTE point summary was refused");
    }
    expect(parsed.summary.point_estimate).toBeCloseTo(0.5001850324245991, 12);
    expect(parsed.summary.point_result_ref).toMatchObject({
      kind: "ir.hte_point_result",
    });
    expect(parsed.summary.hte_result_ref).toBeNull();
    expect(parsed.summary.materialization_binding_ref).toMatchObject({
      kind: "foundry.hte.physical_source_materialization_binding",
    });
    expect(parsed.summary.resource_evidence.owner_policy_revision).toBe("r5");

    render(
      <LocaleProvider>
        <RunHteExecutionSummary projection={projection} />
      </LocaleProvider>,
    );
    const summary = screen.getByTestId("run-hte-execution-summary");
    expect(summary).toHaveTextContent(
      "Candidate only. This display is not a causal or publication finding.",
    );
    expect(summary).toHaveTextContent("0.5002");
  });

  it("refuses the invented native-result alias and R5 bindings that are absent from or disagree with the owner summary", () => {
    const inventedAlias = capturedProjection();
    const inventedSelection = asRecord(inventedAlias.selection);
    inventedSelection.native_mean_result_ref =
      inventedSelection.point_result_ref;
    expect(parseRunExecutionHteProjection(inventedAlias).kind).toBe("invalid");

    const missingOwnerBinding = capturedProjection();
    const missingSelection = asRecord(missingOwnerBinding.selection);
    const missingSummary = asRecord(missingSelection.hte);
    delete missingSummary.materialization_binding_ref;
    expect(parseRunExecutionHteProjection(missingOwnerBinding).kind).toBe(
      "invalid",
    );

    const mismatchedContextBinding = capturedProjection();
    const projectionRequest = asRecord(mismatchedContextBinding.request);
    const requestContext = asRecord(
      projectionRequest.owned_hte_request_context,
    );
    const selected = asRecord(mismatchedContextBinding.selection);
    const selectedContext = asRecord(selected.owned_hte_request_context);
    const ownerSummary = asRecord(selected.hte);
    const ownerBinding = asRecord(ownerSummary.materialization_binding_ref);
    const falseBinding = {
      ...ownerBinding,
      artifact_id: "sha256:" + "0".repeat(64),
    };
    requestContext.materialization_binding_ref = falseBinding;
    selectedContext.materialization_binding_ref = falseBinding;
    expect(parseRunExecutionHteProjection(mismatchedContextBinding).kind).toBe(
      "invalid",
    );
  });
});
