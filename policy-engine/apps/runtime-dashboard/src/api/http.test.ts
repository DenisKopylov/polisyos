import { describe, expect, it } from "vitest";
import { z } from "zod";

import { toRuntimeApiProblem } from "./http";

// Frozen from the bound pre-change http.ts source preimage. Zod's default object
// behavior strips the additive fields while retaining the old envelope fields.
const legacyRuntimeApiProblemSchema = z.object({
  type: z.string().default("about:blank"),
  title: z.string().default("Runtime API error"),
  status: z.number().default(500),
  status_code: z.number().default(500),
  detail: z.string().default("Runtime API request failed"),
  code: z.string().default("runtime_api_error"),
  instance: z.string().nullable().optional().default(null),
  request_id: z.string().nullable().optional().default(null),
  error: z.string().nullable().optional().default(null),
});

const legacyDiagnosticKeys = [
  "actual",
  "artifact_ref_or_route",
  "authority_surface_decision",
  "expected",
  "field",
  "lineage_id",
  "manifest_temporal_scope",
  "mismatches",
  "nearest_event_points",
  "phase4_gate_verdict",
  "policy",
  "pre_admission_attempt_id",
  "pre_admission_attempt_status",
  "read_receipt",
  "reasons",
  "requested_temporal_scope",
  "retry_after_seconds",
  "run_id",
  "surface",
  "temporal_scope",
  "tx_range",
  "valid_range",
  "violations",
] as const;

describe("runtime API problem parsing", () => {
  it("preserves optional context and namespaced diagnostics", () => {
    const problem = toRuntimeApiProblem({
      title: "Conflict",
      detail: "Selected evidence needs review",
      code: "evidence_conflict",
      context: { run_id: "R1" },
      extensions: { read_receipt: { status: "UNRUN" } },
    });

    expect(problem?.context).toEqual({ run_id: "R1" });
    expect(problem?.extensions).toEqual({ read_receipt: { status: "UNRUN" } });
    expect(
      toRuntimeApiProblem({
        title: "Old server response",
        detail: "old",
        code: "old",
      }),
    ).not.toBeNull();
    expect(
      toRuntimeApiProblem({
        title: "Old server",
        detail: "legacy diagnostic location",
        code: "old",
        authority_surface_decision: { status: "blocked" },
      })?.extensions,
    ).toEqual({ authority_surface_decision: { status: "blocked" } });
  });

  it("normalizes the bounded current 23-key legacy diagnostic inventory", () => {
    const values: unknown[] = [
      "legacy",
      3,
      ["one", "two"],
      null,
      { status: "blocked", reason: ["unresolved"] },
    ];
    const diagnostics: Record<string, unknown> = {};
    legacyDiagnosticKeys.forEach((key, index) => {
      diagnostics[key] = values[index % values.length];
    });

    expect(
      toRuntimeApiProblem({
        title: "Old server",
        detail: "legacy diagnostics",
        code: "old",
        ...diagnostics,
      })?.extensions,
    ).toEqual(diagnostics);
  });

  it("keeps envelope-named keys nested without changing the outer problem", () => {
    const extensions = {
      code: "diagnostic-code",
      status: "diagnostic-status",
      status_code: [409, 422],
      error: null,
      context: { run_id: "diagnostic-only" },
      extensions: { code: "deeper-diagnostic" },
    };
    const problem = toRuntimeApiProblem({
      title: "Conflict",
      detail: "Outer envelope is authoritative for this response only",
      code: "outer-code",
      status: 409,
      status_code: 409,
      extensions,
    });

    expect(problem?.code).toBe("outer-code");
    expect(problem?.status).toBe(409);
    expect(problem?.status_code).toBe(409);
    expect(problem?.extensions).toEqual(extensions);
  });

  it("rejects unknown envelope keys and ambiguous legacy/nested duplicates", () => {
    expect(
      toRuntimeApiProblem({
        title: "Invalid",
        detail: "unknown envelope",
        code: "invalid",
        future_top_level: true,
      }),
    ).toBeNull();
    expect(
      toRuntimeApiProblem({
        title: "Invalid",
        detail: "duplicate legacy and namespaced diagnostic",
        code: "invalid",
        authority_surface_decision: { status: "legacy" },
        extensions: { authority_surface_decision: { status: "nested" } },
      }),
    ).toBeNull();
  });

  it("keeps the old parser's envelope fields when the server adds extensions", () => {
    const response = {
      title: "Conflict",
      detail: "new server response",
      code: "outer-code",
      status: 409,
      status_code: 409,
      context: { run_id: "R1" },
      extensions: { code: "diagnostic-code", authority_surface_decision: null },
    };
    const parsed = legacyRuntimeApiProblemSchema.parse(response);

    expect(parsed.code).toBe("outer-code");
    expect(parsed.status).toBe(409);
    expect(parsed.status_code).toBe(409);
    expect(parsed).not.toHaveProperty("context");
    expect(parsed).not.toHaveProperty("extensions");
  });
});
