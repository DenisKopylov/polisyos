import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  ATLAS_CAPTURE_IMPLEMENTATION_PATHS,
  ATLAS_AUTOMATED_RUNNER_PROFILES,
  assertAtlasEvidencePersistenceResult,
  atlasNormalizedRunnerReportSchema,
  buildAtlasAutomatedEvidenceCapture,
  type AtlasAutomatedRunnerProfileId,
  type AtlasEvidencePersistenceResult,
  type AtlasNormalizedRunnerReport,
} from "./atlasAutomatedEvidenceCapture";
import {
  captureAtlasEvidence,
  computeCaptureImplementationProvenance,
  normalizeAtlasRunnerReport,
} from "./captureAtlasEvidence";

const REVISION = "8a9e320588ba3378b4596a609bca3762501e577f";
const VERIFIED_AT = "2026-08-12T17:02:00.000Z";

function declaredImplementationProvenance() {
  const files = ATLAS_CAPTURE_IMPLEMENTATION_PATHS.map((filePath, index) => ({
    path: filePath,
    sha256: String(index + 1).repeat(64),
  }));
  const aggregate = createHash("sha256");
  for (const file of files) {
    aggregate.update(`${file.path}\0${file.sha256}\n`);
  }
  return {
    implementation_sha256: aggregate.digest("hex"),
    files,
    repository_revision: REVISION,
    dirty: true,
  };
}

function normalizedReport(
  profileId: AtlasAutomatedRunnerProfileId,
  outcome: "pass" | "fail" = "pass",
): AtlasNormalizedRunnerReport {
  const profile = ATLAS_AUTOMATED_RUNNER_PROFILES[profileId];
  const tests = profile.exact_tests.map((test) => ({
    ...test,
    outcome,
    duration_ms: 340,
    findings:
      outcome === "pass"
        ? []
        : [
            {
              code: "opaque_background_precondition_failed",
              detail: "Controlled harness was not opaque before classification.",
            },
          ],
  }));
  return {
    report_schema: {
      id: "polisyos.atlas.normalized-runner-report",
      version: "1.0.0",
    },
    runner: {
      profile_id: profile.profile_id,
      runner_id: profile.runner_id,
      runner_version: profile.runner_version,
      report_format: profile.report_format,
    },
    repository_revision: REVISION,
    command_argv: [...profile.command_argv],
    started_at: "2026-08-12T16:11:15.000Z",
    finished_at: "2026-08-12T16:11:35.140Z",
    summary: {
      total: tests.length,
      passed: outcome === "pass" ? tests.length : 0,
      failed: outcome === "fail" ? tests.length : 0,
      incomplete: 0,
    },
    tests,
  };
}

function persistedResult(): AtlasEvidencePersistenceResult {
  const capture = buildAtlasAutomatedEvidenceCapture({
    profile_id: "keyboard_playwright",
    normalized_report: normalizedReport("keyboard_playwright"),
    raw_report_bytes: new TextEncoder().encode("real report bytes"),
    verified_at: VERIFIED_AT,
    implementation_provenance: declaredImplementationProvenance(),
  });
  const rawDigest = capture.payload.details.raw_report_sha256;
  if (typeof rawDigest !== "string") {
    throw new TypeError("fixture raw report digest must be a string");
  }
  const rawReportId = `sha256:${rawDigest}`;
  const payloadId = `sha256:${"a".repeat(64)}`;
  const receiptId = `sha256:${"b".repeat(64)}`;
  const receipt = {
    ...capture.receipt_without_payload_ref,
    evidence_payload_ref: {
      artifact_id: payloadId,
      kind: "atlas_evidence_verification_payload" as const,
      media_type: "application/json" as const,
      schema_id: "polisyos.atlas.evidence-verification-payload" as const,
      schema_version: "1.0.0" as const,
    },
  };
  const verification = (artifactId: string) => ({
    ok: true as const,
    artifact_id: artifactId,
    expected_sha256_hex: artifactId.slice(7),
    actual_sha256_hex: artifactId.slice(7),
    byte_size: 100,
    error: null,
  });
  return {
    ok: true,
    operation: "persist_atlas_evidence",
    raw_report_ref: {
      artifact_id: rawReportId,
      kind: "atlas_evidence_raw_runner_report",
      media_type: "application/json",
    },
    payload_ref: {
      artifact_id: payloadId,
      kind: "atlas_evidence_verification_payload",
      media_type: "application/json",
    },
    receipt_ref: {
      artifact_id: receiptId,
      kind: "atlas_evidence_receipt",
      media_type: "application/json",
    },
    raw_report_verification: verification(rawReportId),
    payload_verification: verification(payloadId),
    receipt_verification: verification(receiptId),
    receipt_manifest_input: {
      artifact_id: payloadId,
      role: "verification_payload",
    },
    payload_manifest_input: {
      artifact_id: rawReportId,
      role: "runner_report",
    },
    resolved_payload: { artifact_id: payloadId, payload: capture.payload },
    resolved_receipt: { artifact_id: receiptId, receipt },
  };
}

function invokeCoreAdapter(
  casRoot: string,
  request: object,
): { status: number | null; value: unknown; stderr: string } {
  const dashboardRoot = process.cwd();
  const policyEngineRoot = path.resolve(dashboardRoot, "../..");
  const result = spawnSync(
    "python3",
    [path.join(dashboardRoot, "scripts/persist_atlas_evidence.py")],
    {
      cwd: policyEngineRoot,
      encoding: "utf8",
      input: JSON.stringify(request),
      env: {
        ...process.env,
        POLISYOS_CAS_BACKEND: "filesystem",
        POLISYOS_CAS_ROOT: casRoot,
      },
      timeout: 30_000,
    },
  );
  return {
    status: result.status,
    value: JSON.parse(result.stdout) as unknown,
    stderr: result.stderr,
  };
}

type StoredManifest = {
  governance: {
    classification: string;
    encryption?: {
      mode: string;
      enforced: boolean;
      verified: boolean;
    };
  };
  producer: {
    git?: { commit: string; dirty: boolean };
  };
};

function readStoredManifest(casRoot: string, artifactId: string): StoredManifest {
  const digest = artifactId.slice(7);
  const manifestPath = path.join(
    casRoot,
    "artifacts",
    "sha256",
    digest.slice(0, 2),
    digest.slice(2, 4),
    `${digest}.manifest.json`,
  );
  return JSON.parse(readFileSync(manifestPath, "utf8")) as StoredManifest;
}

describe("Atlas automated evidence capture", () => {
  it("freezes two declared runner profiles and rejects a new identity", () => {
    expect(Object.keys(ATLAS_AUTOMATED_RUNNER_PROFILES)).toEqual([
      "keyboard_playwright",
      "opaque_storybook",
    ]);
    expect(() =>
      buildAtlasAutomatedEvidenceCapture({
        profile_id: "invented_runner" as AtlasAutomatedRunnerProfileId,
        normalized_report: normalizedReport("keyboard_playwright"),
        raw_report_bytes: new Uint8Array(),
        verified_at: VERIFIED_AT,
        implementation_provenance: declaredImplementationProvenance(),
      }),
    ).toThrow(/undeclared automated evidence runner/);
  });

  it("builds a positive keyboard payload and bounded C07 receipt", () => {
    const implementationProvenance = declaredImplementationProvenance();
    const capture = buildAtlasAutomatedEvidenceCapture({
      profile_id: "keyboard_playwright",
      normalized_report: normalizedReport("keyboard_playwright"),
      raw_report_bytes: new TextEncoder().encode("keyboard report"),
      verified_at: VERIFIED_AT,
      implementation_provenance: implementationProvenance,
    });

    expect(capture.payload.evidence_kind).toBe("automated_keyboard");
    expect(capture.payload.result).toEqual({ outcome: "pass", findings: [] });
    expect(capture.payload.provenance.predicate_provenance).toBe("recomputed");
    expect(capture.payload.details.capture_implementation).toEqual(
      implementationProvenance,
    );
    expect(capture.payload.details).toMatchObject({
      field_provenance: {
        runner_version: "recomputed",
        verifier_identity: "independently_reconciled",
        capture_implementation: "independently_reconciled",
      },
    });
    expect(capture.receipt_without_payload_ref.authority.may_not_use_for).toContain(
      "stable",
    );
    expect(capture.receipt_without_payload_ref).not.toHaveProperty(
      "evidence_payload_ref",
    );
  });

  it("persists a negative opaque report without rounding 0/1 into a pass", () => {
    const capture = buildAtlasAutomatedEvidenceCapture({
      profile_id: "opaque_storybook",
      normalized_report: normalizedReport("opaque_storybook", "fail"),
      raw_report_bytes: new TextEncoder().encode("opaque report"),
      verified_at: VERIFIED_AT,
      implementation_provenance: declaredImplementationProvenance(),
    });

    expect(capture.payload.result.outcome).toBe("fail");
    expect(capture.payload.result.findings).toHaveLength(1);
    expect(capture.payload.details.summary).toEqual({
      total: 1,
      passed: 0,
      failed: 1,
      incomplete: 0,
    });
    expect(capture.payload.details.atomic_observations).toEqual({
      declared: 7,
      admitted: 0,
      mode: "all_or_nothing",
    });
    expect(capture.payload.details).toMatchObject({
      field_provenance: {
        runner_version: "institutionally_supplied",
      },
    });
  });

  it("rejects implementation provenance whose aggregate does not bind its files", () => {
    const provenance = declaredImplementationProvenance();
    provenance.implementation_sha256 = "f".repeat(64);
    expect(() =>
      buildAtlasAutomatedEvidenceCapture({
        profile_id: "keyboard_playwright",
        normalized_report: normalizedReport("keyboard_playwright"),
        raw_report_bytes: new TextEncoder().encode("keyboard report"),
        verified_at: VERIFIED_AT,
        implementation_provenance: provenance,
      }),
    ).toThrow(/aggregate does not bind its files/);
  });

  it("rejects command provenance outside the declared runner", () => {
    const report = normalizedReport("keyboard_playwright");
    report.command_argv = ["corepack", "pnpm", "exec", "vitest", "run"];
    expect(() =>
      buildAtlasAutomatedEvidenceCapture({
        profile_id: "keyboard_playwright",
        normalized_report: report,
        raw_report_bytes: new Uint8Array(),
        verified_at: VERIFIED_AT,
        implementation_provenance: declaredImplementationProvenance(),
      }),
    ).toThrow(/command does not match/);
  });

  it.each([
    ["--bridge", "synthetic-adapter.py"],
    ["--python", "synthetic-python"],
  ])(
    "rejects a sibling persistence override %s at the public capture intake",
    (flag, value) => {
      expect(() =>
        captureAtlasEvidence([
        "--profile",
        "keyboard_playwright",
        "--report",
        "report.json",
        "--revision",
        REVISION,
        "--command-json",
        JSON.stringify(ATLAS_AUTOMATED_RUNNER_PROFILES.keyboard_playwright.command_argv),
        "--cas-root",
        "cas",
          flag,
          value,
        ]),
      ).toThrow(new RegExp(`unknown capture argument: ${flag}`));
    },
  );

  it("rejects pass with a partial declared population", () => {
    const report = normalizedReport("keyboard_playwright");
    report.tests = [];
    report.summary = { total: 0, passed: 0, failed: 0, incomplete: 0 };

    expect(() =>
      buildAtlasAutomatedEvidenceCapture({
        profile_id: "keyboard_playwright",
        normalized_report: report,
        raw_report_bytes: new Uint8Array(),
        verified_at: VERIFIED_AT,
        implementation_provenance: declaredImplementationProvenance(),
      }),
    ).toThrow(/population mismatch/);
  });

  it("rejects a report whose summary contradicts its individual results", () => {
    const report = normalizedReport("keyboard_playwright");
    report.summary = { total: 1, passed: 0, failed: 1, incomplete: 0 };

    expect(() =>
      buildAtlasAutomatedEvidenceCapture({
        profile_id: "keyboard_playwright",
        normalized_report: report,
        raw_report_bytes: new Uint8Array(),
        verified_at: VERIFIED_AT,
        implementation_provenance: declaredImplementationProvenance(),
      }),
    ).toThrow(/summary contradicts/);
  });

  it("rejects malformed runner JSON and a declared-runner identity mismatch", () => {
    expect(
      atlasNormalizedRunnerReportSchema.safeParse({ marker: "runner report" })
        .success,
    ).toBe(false);
    const report = normalizedReport("keyboard_playwright");
    report.runner.runner_id = "unregistered-runner";
    expect(() =>
      buildAtlasAutomatedEvidenceCapture({
        profile_id: "keyboard_playwright",
        normalized_report: report,
        raw_report_bytes: new Uint8Array(),
        verified_at: VERIFIED_AT,
        implementation_provenance: declaredImplementationProvenance(),
      }),
    ).toThrow(/runner declaration mismatch/);
  });

  it("rejects shaped-but-unresolved, tampered, and unrelated CAS results", () => {
    expect(() =>
      assertAtlasEvidencePersistenceResult({
        ok: true,
        payload_ref: { artifact_id: `sha256:${"a".repeat(64)}` },
      }),
    ).toThrow();

    const tampered = persistedResult();
    tampered.payload_verification.actual_sha256_hex = "c".repeat(64);
    expect(() => assertAtlasEvidencePersistenceResult(tampered)).toThrow(
      /integrity binding mismatch/,
    );

    const unrelated = persistedResult();
    unrelated.resolved_payload.payload.subject = {
      ...unrelated.resolved_payload.payload.subject,
      subject_id: "unrelated-surface",
    };
    expect(() => assertAtlasEvidencePersistenceResult(unrelated)).toThrow(
      /semantic binding/,
    );
  });

  it("rejects a tampered receipt manifest lineage edge", () => {
    const result = persistedResult();
    result.receipt_manifest_input = {
      artifact_id: `sha256:${"c".repeat(64)}`,
      role: "verification_payload",
    };
    expect(() => assertAtlasEvidencePersistenceResult(result)).toThrow(
      /integrity binding mismatch|manifest lineage mismatch/,
    );
  });

  it("accepts a fully resolved, integrity-verified, semantically rebound pair", () => {
    const result = persistedResult();
    expect(assertAtlasEvidencePersistenceResult(result)).toEqual(result);
  });

  it("executes Core put, resolve, lineage, and integrity checks and fails on corruption", () => {
    const rawReportBytes = new TextEncoder().encode(
      '{"runner":"behavioral Core report"}',
    );
    const implementationProvenance = computeCaptureImplementationProvenance();
    const capture = buildAtlasAutomatedEvidenceCapture({
      profile_id: "keyboard_playwright",
      normalized_report: normalizedReport("keyboard_playwright"),
      raw_report_bytes: rawReportBytes,
      verified_at: VERIFIED_AT,
      implementation_provenance: implementationProvenance,
    });
    const request = {
      operation: "persist_atlas_evidence",
      raw_report_base64: Buffer.from(rawReportBytes).toString("base64"),
      payload: capture.payload,
      receipt: capture.receipt_without_payload_ref,
    };
    const scratchParent = path.resolve(
      process.cwd(),
      "../../_build/apps/runtime-dashboard",
    );
    const casRoot = mkdtempSync(path.join(scratchParent, "ds6-c08-core-test-"));
    try {
      const first = invokeCoreAdapter(casRoot, request);
      if (first.status !== 0) {
        throw new Error(`Core adapter failed: ${first.stderr}`);
      }
      const persisted = assertAtlasEvidencePersistenceResult(first.value);
      expect(persisted.receipt_manifest_input).toEqual({
        artifact_id: persisted.payload_ref.artifact_id,
        role: "verification_payload",
      });
      expect(persisted.payload_manifest_input).toEqual({
        artifact_id: persisted.raw_report_ref.artifact_id,
        role: "runner_report",
      });
      expect(persisted.resolved_payload.payload).toEqual(capture.payload);

      for (const artifactId of [
        persisted.raw_report_ref.artifact_id,
        persisted.payload_ref.artifact_id,
        persisted.receipt_ref.artifact_id,
      ]) {
        const manifest = readStoredManifest(casRoot, artifactId);
        expect(manifest.governance).toEqual(
          expect.objectContaining({
            classification: "internal",
            encryption: {
              mode: "none",
              enforced: false,
              verified: false,
            },
          }),
        );
        expect(manifest.producer.git).toEqual({
          commit: implementationProvenance.repository_revision,
          dirty: implementationProvenance.dirty,
        });
      }

      const provenanceTamper = JSON.parse(JSON.stringify(request)) as {
        payload: {
          details: {
            capture_implementation: { implementation_sha256: string };
          };
        };
      };
      provenanceTamper.payload.details.capture_implementation.implementation_sha256 =
        "f".repeat(64);
      const rejectedProvenance = invokeCoreAdapter(casRoot, provenanceTamper);
      expect(rejectedProvenance.status).toBe(1);
      expect(rejectedProvenance.value).toEqual(
        expect.objectContaining({
          ok: false,
          error: expect.objectContaining({
            message: expect.stringMatching(/capture implementation provenance mismatch/),
          }),
        }),
      );

      const digest = persisted.raw_report_ref.artifact_id.slice(7);
      const blobPath = path.join(
        casRoot,
        "artifacts",
        "sha256",
        digest.slice(0, 2),
        digest.slice(2, 4),
        `${digest}.blob`,
      );
      writeFileSync(blobPath, "marker-preserving corruption", "utf8");
      const corrupted = invokeCoreAdapter(casRoot, request);
      expect(corrupted.status).toBe(1);
      expect(corrupted.value).toEqual(
        expect.objectContaining({
          ok: false,
          error: expect.objectContaining({
            code: "atlas_evidence_persistence_failed",
            message: expect.stringMatching(/integrity verification failed/),
          }),
        }),
      );
    } finally {
      rmSync(casRoot, { recursive: true, force: true });
    }
  });

  it("normalizes the actual Playwright JSON shape instead of trusting a summary marker", () => {
    const normalized = normalizeAtlasRunnerReport(
      "keyboard_playwright",
      {
        config: { version: "1.59.1", workers: 1 },
        suites: [
          {
            title: "a11y/keyboard-journeys.spec.ts",
            file: "a11y/keyboard-journeys.spec.ts",
            specs: [],
            suites: [
              {
                title: "runtime-dashboard keyboard-only journeys",
                file: "../src/test/a11y/keyboard-journeys.spec.ts",
                specs: [
                  {
                    title:
                      "opens a run and downloads the decision packet with keyboard only in at most 20 tab stops",
                    file: "../src/test/a11y/keyboard-journeys.spec.ts",
                    tests: [
                      {
                        expectedStatus: "passed",
                        projectName: "chromium",
                        status: "expected",
                        results: [
                          {
                            status: "passed",
                            duration: 15_188,
                            errors: [],
                            startTime: "2026-08-12T17:00:33.220Z",
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
        errors: [],
        stats: {
          startTime: "2026-08-12T17:00:12.099Z",
          duration: 37_944.837,
          expected: 1,
          unexpected: 0,
          flaky: 0,
          skipped: 0,
        },
      },
      REVISION,
      [...ATLAS_AUTOMATED_RUNNER_PROFILES.keyboard_playwright.command_argv],
    );

    expect(normalized.summary).toEqual({
      total: 1,
      passed: 1,
      failed: 0,
      incomplete: 0,
    });
    expect(normalized.tests[0]).toEqual(
      expect.objectContaining({
        file: "src/test/a11y/keyboard-journeys.spec.ts",
        outcome: "pass",
      }),
    );
  });

  it("normalizes the actual failing Vitest JSON shape as negative evidence", () => {
    const normalized = normalizeAtlasRunnerReport(
      "opaque_storybook",
      {
        numTotalTestSuites: 1,
        numPassedTestSuites: 0,
        numFailedTestSuites: 1,
        numPendingTestSuites: 0,
        numTotalTests: 1,
        numPassedTests: 0,
        numFailedTests: 1,
        numPendingTests: 0,
        numTodoTests: 0,
        startTime: Date.parse("2026-08-12T17:01:34.318Z"),
        success: false,
        testResults: [
          {
            name: `${process.cwd()}/src/test/a11y/OpaqueBackgroundContrast.stories.tsx`,
            startTime: Date.parse("2026-08-12T17:01:45.593Z"),
            endTime: Date.parse("2026-08-12T17:01:46.036Z"),
            status: "failed",
            assertionResults: [
              {
                ancestorTitles: [],
                fullName: "Seven Declared Sources",
                title: "Seven Declared Sources",
                status: "failed",
                duration: 443.4,
                failureMessages: ["expected false to be true"],
              },
            ],
          },
        ],
      },
      REVISION,
      [...ATLAS_AUTOMATED_RUNNER_PROFILES.opaque_storybook.command_argv],
    );

    expect(normalized.summary).toEqual({
      total: 1,
      passed: 0,
      failed: 1,
      incomplete: 0,
    });
    expect(normalized.tests[0]).toEqual(
      expect.objectContaining({
        file: "src/test/a11y/OpaqueBackgroundContrast.stories.tsx",
        outcome: "fail",
      }),
    );
  });
});
