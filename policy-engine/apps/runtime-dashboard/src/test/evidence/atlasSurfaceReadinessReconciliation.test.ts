import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createElement } from "react";
import { Navigate, type RouteObject } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { APP_ROUTES } from "@/app/routes/routes";

import {
  ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT,
  atlasEvidencePayloadSchema,
  atlasEvidenceReceiptSchema,
} from "./atlasEvidenceArtifact";
import {
  C10_RECONCILIATION_CODES,
  buildAtlasSurfaceReadinessReconciliation,
  collectCanonicalDeprecatedRedirects,
  type AtlasSurfaceReadinessReconciliationInput,
} from "./atlasSurfaceReadinessReconciliation";

const currentFile = fileURLToPath(import.meta.url);
const dashboardRoot = path.resolve(path.dirname(currentFile), "../../..");
const policyEngineRoot = path.resolve(dashboardRoot, "../..");
const routeTestPath = "src/app/routes/routes.test.tsx";
const canonicalAdoptionLedger = JSON.parse(
  readFileSync(
    path.resolve(
      policyEngineRoot,
      "architecture/atlas_surfaces/atlas-v15-adoption-ledger.json",
    ),
    "utf8",
  ),
);
const canonicalReadinessLedger = JSON.parse(
  readFileSync(
    path.resolve(
      policyEngineRoot,
      "architecture/atlas_surfaces/live-application-readiness-ledger.json",
    ),
    "utf8",
  ),
);
const redirectAssertions = [
  "/launch",
  "/sources",
  "/data",
  "/lex",
  "/health",
].map(
  (initialEntry) =>
    `APP_ROUTES wraps app routes with the shell and follows legacy redirect from '${initialEntry}'`,
  );

type MutableJsonRecord = Record<string, unknown>;

function asMutableRecord(value: unknown): MutableJsonRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("test fixture must be a JSON object");
  }
  return value as MutableJsonRecord;
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function adoptionLedger(entries: unknown[]) {
  const ledger = clone(canonicalAdoptionLedger);
  ledger.entries = entries;
  return ledger;
}

function readinessLedger(entries: unknown[]) {
  const ledger = clone(canonicalReadinessLedger);
  ledger.entries = entries;
  return ledger;
}

function adoptionRow(overrides: Record<string, unknown> = {}) {
  return {
    ...clone(canonicalAdoptionLedger.entries[0]),
    ...overrides,
  };
}

function routeTestReport(
  statuses: Record<string, "passed" | "failed"> = {},
): Record<string, unknown> {
  const assertions = redirectAssertions.map((fullName) => ({
    ancestorTitles: ["APP_ROUTES"],
    fullName,
    status: statuses[fullName] ?? "passed",
    title: fullName,
    duration: 1,
    failureMessages: statuses[fullName] === "failed" ? ["structural witness"] : [],
  }));
  const passed = assertions.filter(({ status }) => status === "passed").length;
  const failed = assertions.length - passed;
  return {
    numTotalTestSuites: 1,
    numPassedTestSuites: failed === 0 ? 1 : 0,
    numFailedTestSuites: failed === 0 ? 0 : 1,
    numPendingTestSuites: 0,
    numTotalTests: assertions.length,
    numPassedTests: passed,
    numFailedTests: failed,
    numPendingTests: 0,
    numTodoTests: 0,
    startTime: Date.parse("2026-08-15T09:00:00.000Z"),
    success: failed === 0,
    testResults: [
      {
        assertionResults: assertions,
        endTime: Date.parse("2026-08-15T09:00:01.000Z"),
        name: `${dashboardRoot}/${routeTestPath}`,
        startTime: Date.parse("2026-08-15T09:00:00.000Z"),
        status: failed === 0 ? "passed" : "failed",
      },
    ],
  };
}

function input(
  overrides: Partial<AtlasSurfaceReadinessReconciliationInput> = {},
): AtlasSurfaceReadinessReconciliationInput {
  return {
    adoption_ledger: canonicalAdoptionLedger,
    readiness_ledger: canonicalReadinessLedger,
    observed_at: "2026-08-15T09:00:00.000Z",
    route_test_report_bytes: new TextEncoder().encode(
      JSON.stringify(routeTestReport()),
    ),
    route_test_exit_code: 0,
    verified_at: "2026-08-15T09:00:01.000Z",
    ...overrides,
  };
}

function implementedRow(overrides: Record<string, unknown> = {}) {
  return {
    ...clone(canonicalReadinessLedger.entries[0]),
    surface_id: "route-synthetic",
    title: "/synthetic",
    readiness_state: "implemented",
    maturity: "beta",
    chain: {
      ...clone(canonicalReadinessLedger.entries[0].chain),
      negative_test: "implemented",
      semantic_test: "implemented",
    },
    ...overrides,
  };
}

function persist(
  reconciliation: ReturnType<typeof buildAtlasSurfaceReadinessReconciliation>,
  casRoot: string,
  payload: unknown = reconciliation.payload,
  receipt: unknown = reconciliation.receipt_without_payload_ref,
  rawReportBytes = reconciliation.raw_report_bytes,
) {
  return spawnSync(
    "uv",
    [
      "run",
      "--frozen",
      "python",
      "apps/runtime-dashboard/scripts/persist_atlas_evidence.py",
    ],
    {
      cwd: policyEngineRoot,
      encoding: "utf8",
      env: {
        ...process.env,
        POLISYOS_CAS_BACKEND: "filesystem",
        POLISYOS_CAS_ROOT: casRoot,
      },
      input: JSON.stringify({
        operation: "persist_atlas_evidence",
        raw_report_base64: Buffer.from(rawReportBytes).toString("base64"),
        payload,
        receipt,
      }),
    },
  );
}

function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function canonicalSourceArtifacts(): {
  source_set_sha256: string;
  files: { path: string; sha256: string }[];
} {
  const files = ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.source_artifact_paths.map(
    (relativePath) => ({
      path: relativePath,
      sha256: sha256(readFileSync(path.resolve(policyEngineRoot, relativePath))),
    }),
  );
  const aggregate = createHash("sha256");
  for (const file of files) {
    aggregate.update(`${file.path}\0${file.sha256}\n`);
  }
  return { source_set_sha256: aggregate.digest("hex"), files };
}

describe("Atlas surface-readiness reconciliation", () => {
  it("recomputes the real zero-stable denominator and verifies the exact five runtime redirects", () => {
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(input());

    expect(collectCanonicalDeprecatedRedirects(APP_ROUTES)).toEqual([
      { surface_id: "route-redirect-launch", from: "/launch", to: "/compose" },
      { surface_id: "route-redirect-sources", from: "/sources", to: "/evidence" },
      { surface_id: "route-redirect-data", from: "/data", to: "/evidence" },
      { surface_id: "route-redirect-lex", from: "/lex", to: "/knowledge" },
      { surface_id: "route-redirect-health", from: "/health", to: "/platform" },
    ]);
    expect(reconciliation.payload.result).toEqual({ outcome: "pass", findings: [] });
    expect(reconciliation.payload.details.reconciliation).toMatchObject({
      adoption_entries: 233,
      adoption_stable: 0,
      readiness_entries: 261,
      readiness_stable: 0,
      readiness_implemented: 5,
    });
    expect(reconciliation.payload.details.field_provenance).toEqual({
      adoption_denominator: "recomputed",
      readiness_denominator: "recomputed",
      stable_claims: "recomputed",
      implemented_claims: "recomputed",
      redirect_route_identity: "independently_reconciled",
      redirect_behavioral_matrix: "independently_reconciled",
      route_test_receipt: "independently_reconciled",
      route_test_process_exit: "independently_reconciled",
      route_test_report_sha256: "recomputed",
      raw_report_sha256: "recomputed",
      canonical_source_artifacts: "recomputed",
      capture_implementation: "independently_reconciled",
    });
  });

  it("rejects every mirrored owner date/date-time and uniqueItems constraint", () => {
    const malformedAdoptionLedgers = [
      { ...adoptionLedger([adoptionRow()]), as_of: "not-a-date-time" },
      adoptionLedger([
        adoptionRow({
          evidence_refs: [{ ...canonicalAdoptionLedger.entries[0].evidence_refs[0], as_of: "not-a-date" }],
        }),
      ]),
      adoptionLedger([adoptionRow({ decided_at: "not-a-date" })]),
      adoptionLedger([adoptionRow({ audiences: ["PUBLIC", "PUBLIC"] })]),
      adoptionLedger([adoptionRow({ consuming_surfaces: ["DS6", "DS6"] })]),
      adoptionLedger([
        adoptionRow({
          next_adjudication: {
            ...canonicalAdoptionLedger.entries[0].next_adjudication,
            owner_slices: ["DS6", "DS6"],
          },
        }),
      ]),
    ];
    for (const adoption_ledger of malformedAdoptionLedgers) {
      expect(() =>
        buildAtlasSurfaceReadinessReconciliation(input({ adoption_ledger })),
      ).toThrow(C10_RECONCILIATION_CODES.ledger_vocabulary_invalid);
    }

    const malformedReadinessLedgers = [
      { ...readinessLedger([implementedRow()]), as_of: "not-a-date-time" },
      readinessLedger([
        implementedRow({
          audiences: ["PUBLIC", "PUBLIC"],
        }),
      ]),
      readinessLedger([
        implementedRow({
          freshness: {
            ...canonicalReadinessLedger.entries[0].freshness,
            as_of: "not-a-date-time",
          },
        }),
      ]),
      readinessLedger([implementedRow({ updated_at: "not-a-date-time" })]),
    ];
    for (const readiness_ledger of malformedReadinessLedgers) {
      expect(() =>
        buildAtlasSurfaceReadinessReconciliation(input({ readiness_ledger })),
      ).toThrow(C10_RECONCILIATION_CODES.ledger_vocabulary_invalid);
    }
  });

  it("uses the exact Vitest JSON bytes as the resolved C08 raw artifact", () => {
    const rawRouteReport = new TextEncoder().encode(JSON.stringify(routeTestReport()));
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(
      input({ route_test_report_bytes: rawRouteReport }),
    );
    const expectedRawSha256 = sha256(rawRouteReport);

    expect(reconciliation.raw_report_bytes).toEqual(rawRouteReport);
    expect(reconciliation.payload.details.raw_report_sha256).toBe(expectedRawSha256);
    expect(reconciliation.payload.details.route_test_report_sha256).toBe(expectedRawSha256);
    expect(reconciliation.payload.details.source_artifacts).toEqual(
      canonicalSourceArtifacts(),
    );

    const casRoot = mkdtempSync(path.join(tmpdir(), "polisyos-c10-raw-vitest-"));
    try {
      const persisted = persist(reconciliation, casRoot);
      expect(persisted.status).toBe(0);
      const result = JSON.parse(persisted.stdout);
      expect(result.raw_report_ref.artifact_id).toBe(`sha256:${expectedRawSha256}`);
      expect(result.raw_report_verification.actual_sha256_hex).toBe(expectedRawSha256);
    } finally {
      rmSync(casRoot, { recursive: true, force: true });
    }
  });

  it("rejects a C10 pass contradicted by stable counts or a failed route receipt", () => {
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(input());
    const stablePass = clone(reconciliation.payload) as MutableJsonRecord;
    const stableReconciliation = asMutableRecord(
      asMutableRecord(stablePass.details).reconciliation,
    );
    stableReconciliation.adoption_stable = 1;
    stableReconciliation.adoption_stable_ids = ["forged-stable"];
    expect(atlasEvidencePayloadSchema.safeParse(stablePass).success).toBe(false);

    const routePass = clone(reconciliation.payload) as MutableJsonRecord;
    const routeDetails = asMutableRecord(routePass.details);
    const originalRouteReceipt = asMutableRecord(routeDetails.route_test_receipt);
    routeDetails.route_test_receipt = {
      ...originalRouteReceipt,
      process_exit_code: 1,
      outcome: "fail",
      failure_code: C10_RECONCILIATION_CODES.redirect_test_receipt_invalid,
      required_assertions: (
        originalRouteReceipt.required_assertions as MutableJsonRecord[]
      ).map((assertion) => ({ ...assertion, status: "fail" })),
    };
    expect(atlasEvidencePayloadSchema.safeParse(routePass).success).toBe(false);
  });

  it("rejects a self-consistent derived reconciliation wrapper at the Python choke point", () => {
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(input());
    const payload = clone(reconciliation.payload) as MutableJsonRecord;
    const receipt = clone(reconciliation.receipt_without_payload_ref) as MutableJsonRecord;
    const payloadDetails = asMutableRecord(payload.details);
    const payloadReconciliation = asMutableRecord(payloadDetails.reconciliation);
    const legacyRaw = clone(reconciliation.raw_report) as MutableJsonRecord;
    legacyRaw.reconciliation = {
      ...payloadReconciliation,
      adoption_stable: 1,
      adoption_stable_ids: ["forged-stable"],
    };
    legacyRaw.result = { outcome: "pass", findings: [] };
    payloadReconciliation.adoption_stable = 1;
    const legacyBytes = new TextEncoder().encode(JSON.stringify(legacyRaw));
    payloadDetails.raw_report_sha256 = sha256(legacyBytes);
    const casRoot = mkdtempSync(path.join(tmpdir(), "polisyos-c10-derived-raw-"));
    try {
      const persisted = persist(reconciliation, casRoot, payload, receipt, legacyBytes);
      expect(persisted.status).toBe(1);
    } finally {
      rmSync(casRoot, { recursive: true, force: true });
    }
  });

  it("fails a structural runtime mutation even when route-test title markers remain", () => {
    const root = APP_ROUTES.find((route) => route.path === "/")!;
    const mutatedRoutes: RouteObject[] = APP_ROUTES.map((route) =>
      route === root
        ? {
            ...route,
            children: route.children?.map((child) =>
              child.path === "launch"
                ? {
                    ...child,
                    element: createElement(Navigate, {
                      replace: true,
                      to: "/wrong-target",
                    }),
                  }
                : child,
            ),
          }
        : route,
    ) as RouteObject[];

    expect(() => collectCanonicalDeprecatedRedirects(mutatedRoutes)).toThrow(
      C10_RECONCILIATION_CODES.implemented_deprecated_redirect_unverified,
    );
  });

  it("fails every stable claim despite shaped browser/manual references", () => {
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(
      input({
        adoption_ledger: {
          ...adoptionLedger([
            adoptionRow({
              id: "component-synthetic",
              maturity: "stable",
              evidence_refs: [
                {
                  kind: "browser",
                  ref: `sha256:${"a".repeat(64)}`,
                  as_of: "2026-08-15",
                },
                {
                  kind: "at_manual",
                  ref: `sha256:${"b".repeat(64)}`,
                  as_of: "2026-08-15",
                },
              ],
            }),
          ]),
        },
      }),
    );

    expect(reconciliation.payload.result.findings).toContainEqual(
      expect.objectContaining({
        code: C10_RECONCILIATION_CODES.stable_evidence_reference_unresolved,
      }),
    );
  });

  it("rejects unknown ledger states and duplicate canonical identities", () => {
    expect(() =>
      buildAtlasSurfaceReadinessReconciliation(
        input({
          adoption_ledger: adoptionLedger([
            adoptionRow({ id: "unknown", maturity: "legendary" }),
          ]),
        }),
      ),
    ).toThrow(C10_RECONCILIATION_CODES.ledger_vocabulary_invalid);
    expect(() =>
      buildAtlasSurfaceReadinessReconciliation(
        input({
          readiness_ledger: readinessLedger([implementedRow(), implementedRow()]),
        }),
      ),
    ).toThrow(C10_RECONCILIATION_CODES.ledger_duplicate_identity);
    const incompleteChain = implementedRow();
    delete incompleteChain.chain.semantic_test;
    expect(() =>
      buildAtlasSurfaceReadinessReconciliation(
        input({ readiness_ledger: readinessLedger([incompleteChain]) }),
      ),
    ).toThrow(C10_RECONCILIATION_CODES.ledger_vocabulary_invalid);
  });

  it("fails a non-deprecated implemented row even when its unbound chain strings claim tests", () => {
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(
      input({ readiness_ledger: readinessLedger([implementedRow()]) }),
    );

    expect(reconciliation.payload.result.findings).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          code: C10_RECONCILIATION_CODES.implemented_negative_test_missing,
        }),
        expect.objectContaining({
          code: C10_RECONCILIATION_CODES.implemented_semantic_test_missing,
        }),
      ]),
    );
  });

  it("fails the deprecated exception when the launcher receipt has one failed redirect assertion", () => {
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(
      input({
        readiness_ledger: readinessLedger([
          implementedRow({
            surface_id: "route-redirect-launch",
            maturity: "deprecated",
          }),
        ]),
        route_test_report_bytes: new TextEncoder().encode(
          JSON.stringify(
            routeTestReport({ [redirectAssertions[0]]: "failed" }),
          ),
        ),
      }),
    );

    expect(reconciliation.payload.result.findings).toContainEqual(
      expect.objectContaining({
        code: C10_RECONCILIATION_CODES.redirect_test_receipt_invalid,
      }),
    );
  });

  it("fails a success-shaped report when the real route-test process exits nonzero", () => {
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(
      input({ route_test_exit_code: 1 }),
    );

    expect(reconciliation.payload.result.findings).toContainEqual(
      expect.objectContaining({
        code: C10_RECONCILIATION_CODES.redirect_test_receipt_invalid,
      }),
    );
    expect(
      (reconciliation.payload.details.route_test_receipt as Record<string, unknown>)
        .process_exit_code,
    ).toBe(1);
    expect(reconciliation.exit_code).toBe(1);
  });

  it("fails a route matrix that omits one required redirect assertion", () => {
    const report = routeTestReport();
    const testResults = report.testResults as { assertionResults: unknown[] }[];
    testResults[0].assertionResults.pop();
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(
      input({
        route_test_report_bytes: new TextEncoder().encode(JSON.stringify(report)),
      }),
    );

    expect(reconciliation.exit_code).toBe(1);
    expect(reconciliation.payload.result.findings).toContainEqual(
      expect.objectContaining({
        code: C10_RECONCILIATION_CODES.redirect_test_receipt_invalid,
      }),
    );
  });

  it("rejects C10-shaped payload and receipt authority, provenance, subject, and rule drift", () => {
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(input());
    const payload = reconciliation.payload;
    const receipt = {
      ...reconciliation.receipt_without_payload_ref,
      evidence_payload_ref: {
        artifact_id: `sha256:${"c".repeat(64)}`,
        kind: "atlas_evidence_verification_payload",
        media_type: "application/json",
        schema_id: payload.payload_schema.id,
        schema_version: payload.payload_schema.version,
      },
    };

    for (const invalidPayload of [
      { ...payload, subject: { ...payload.subject, subject_id: "unrelated" } },
      { ...payload, rule: { ...payload.rule, rule_id: "unrelated-rule" } },
      ...[
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
      ].map((predicate_provenance) => ({
        ...payload,
        provenance: {
          ...payload.provenance,
          predicate_provenance,
        },
      })),
      {
        ...payload,
        details: {
          ...payload.details,
          field_provenance: {
            ...(payload.details.field_provenance as Record<string, string>),
            stable_claims: "not_established",
          },
        },
      },
    ]) {
      expect(atlasEvidencePayloadSchema.safeParse(invalidPayload).success).toBe(false);
    }
    expect(
      atlasEvidenceReceiptSchema.safeParse({
        ...receipt,
        authority: {
          ...receipt.authority,
          authoritative_for: ["atlas_evidence_capture"],
        },
      }).success,
    ).toBe(false);
  });

  it("returns named reconciliation RED without claiming canonical launcher persistence", () => {
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(
      input({
        adoption_ledger: {
          ...adoptionLedger([
            adoptionRow({ id: "stable-negative", maturity: "stable" }),
          ]),
        },
      }),
    );
    expect(reconciliation.exit_code).toBe(1);
    expect(reconciliation.payload.result).toMatchObject({ outcome: "fail" });
    expect(reconciliation.payload.result.findings).toContainEqual(
      expect.objectContaining({
        code: C10_RECONCILIATION_CODES.stable_evidence_reference_unresolved,
      }),
    );
  });

  it("rejects a synthetic stable reconciliation laundered into a canonical pass", () => {
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(
      input({
        adoption_ledger: {
          ...adoptionLedger([
            adoptionRow({ id: "stable-raw-witness", maturity: "stable" }),
          ]),
        },
      }),
    );
    const payload = JSON.parse(JSON.stringify(reconciliation.payload));
    const receipt = JSON.parse(
      JSON.stringify(reconciliation.receipt_without_payload_ref),
    );
    payload.result = { outcome: "pass", findings: [] };
    receipt.result = { outcome: "pass", findings: [] };
    const casRoot = mkdtempSync(path.join(tmpdir(), "polisyos-c10-raw-"));
    try {
      const persisted = persist(reconciliation, casRoot, payload, receipt);
      expect(persisted.status).toBe(1);
      expect(persisted.stdout).toContain(
        "C10 reconciliation does not equal independently recomputed canonical facts",
      );
    } finally {
      rmSync(casRoot, { recursive: true, force: true });
    }
  });

  it("rejects a failed raw route matrix laundered into a payload and receipt pass", () => {
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(
      input({
        route_test_report_bytes: new TextEncoder().encode(
          JSON.stringify(routeTestReport({ [redirectAssertions[0]]: "failed" })),
        ),
      }),
    );
    const payload = clone(reconciliation.payload) as MutableJsonRecord;
    const receipt = clone(reconciliation.receipt_without_payload_ref) as MutableJsonRecord;
    payload.result = { outcome: "pass", findings: [] };
    receipt.result = { outcome: "pass", findings: [] };
    const casRoot = mkdtempSync(path.join(tmpdir(), "polisyos-c10-route-launder-"));
    try {
      const persisted = persist(reconciliation, casRoot, payload, receipt);
      expect(persisted.status).toBe(1);
      expect(persisted.stdout).toContain(
        "C10 result does not equal independently recomputed canonical facts",
      );
    } finally {
      rmSync(casRoot, { recursive: true, force: true });
    }
  });

  it("rejects a forged canonical source-artifact hash before CAS write", () => {
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(input());
    const payload = clone(reconciliation.payload) as MutableJsonRecord;
    const sourceArtifacts = asMutableRecord(
      asMutableRecord(payload.details).source_artifacts,
    );
    (sourceArtifacts.files as MutableJsonRecord[])[0].sha256 = "0".repeat(64);
    const casRoot = mkdtempSync(path.join(tmpdir(), "polisyos-c10-source-hash-"));
    try {
      const persisted = persist(reconciliation, casRoot, payload);
      expect(persisted.status).toBe(1);
      expect(persisted.stdout).toContain(
        "C10 canonical source artifacts do not bind the current tree",
      );
    } finally {
      rmSync(casRoot, { recursive: true, force: true });
    }
  });

  it("rejects a forged repository revision even when payload and receipt agree", () => {
    const reconciliation = buildAtlasSurfaceReadinessReconciliation(input());
    const payload = JSON.parse(JSON.stringify(reconciliation.payload));
    const receipt = JSON.parse(
      JSON.stringify(reconciliation.receipt_without_payload_ref),
    );
    payload.provenance.repository_revision = "f".repeat(40);
    receipt.provenance.repository_revision = "f".repeat(40);
    const casRoot = mkdtempSync(path.join(tmpdir(), "polisyos-c10-revision-"));
    try {
      const persisted = persist(reconciliation, casRoot, payload, receipt);
      expect(persisted.status).toBe(1);
      expect(persisted.stdout).toContain("repository revision does not bind");
    } finally {
      rmSync(casRoot, { recursive: true, force: true });
    }
  });
});
