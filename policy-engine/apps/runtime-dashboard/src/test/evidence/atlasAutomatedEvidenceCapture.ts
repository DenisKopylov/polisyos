import { createHash } from "node:crypto";

import { z } from "zod";

import {
  ATLAS_EVIDENCE_DENIED_USES,
  ATLAS_EVIDENCE_PAYLOAD_SCHEMA,
  ATLAS_EVIDENCE_RECEIPT_SCHEMA,
  ATLAS_EVIDENCE_STORAGE_CONVENTION,
  assertAtlasEvidencePayloadBinding,
  atlasEvidencePayloadSchema,
  atlasEvidenceReceiptSchema,
  type AtlasEvidencePayload,
  type AtlasEvidenceReceipt,
} from "./atlasEvidenceArtifact";

export const ATLAS_AUTOMATED_CAPTURE_PROTOCOL = {
  id: "polisyos.atlas.automated-evidence-capture",
  version: "1.0.0",
} as const;

export const ATLAS_CAPTURE_IMPLEMENTATION_PATHS = [
  "apps/runtime-dashboard/src/test/evidence/atlasEvidenceArtifact.ts",
  "apps/runtime-dashboard/src/test/evidence/atlasAutomatedEvidenceCapture.ts",
  "apps/runtime-dashboard/src/test/evidence/captureAtlasEvidence.ts",
  "apps/runtime-dashboard/scripts/capture_atlas_evidence.mjs",
  "apps/runtime-dashboard/scripts/persist_atlas_evidence.py",
] as const;

const exactKeyboardTests = [
  {
    file: "src/test/a11y/keyboard-journeys.spec.ts",
    title:
      "runtime-dashboard keyboard-only journeys > opens a run and downloads the decision packet with keyboard only in at most 20 tab stops",
  },
] as const;

const exactOpaqueTests = [
  {
    file: "src/test/a11y/OpaqueBackgroundContrast.stories.tsx",
    title: "Seven Declared Sources",
  },
] as const;

export const ATLAS_AUTOMATED_RUNNER_PROFILES = {
  keyboard_playwright: {
    profile_id: "keyboard_playwright",
    evidence_kind: "automated_keyboard",
    runner_id: "atlas-playwright-keyboard-runner",
    runner_version: "playwright@1.59.1",
    verifier_id: "atlas-playwright-result-normalizer",
    verifier_version: ATLAS_AUTOMATED_CAPTURE_PROTOCOL.version,
    report_format: "playwright_json",
    atomic_observation_denominator: 1,
    rule_id: "atlas.keyboard-only-journey",
    rule_version: "1.0.0",
    command_argv: [
      "corepack",
      "pnpm",
      "exec",
      "playwright",
      "test",
      "e2e/a11y/keyboard-journeys.spec.ts",
      "--project=chromium",
      "--reporter=json",
    ],
    subject: {
      kind: "surface",
      subject_id: "runtime-dashboard",
      state_id: "keyboard-only-journey",
    },
    exact_tests: exactKeyboardTests,
  },
  opaque_storybook: {
    profile_id: "opaque_storybook",
    evidence_kind: "automated_browser",
    runner_id: "atlas-storybook-axe-runner",
    runner_version: "vitest-browser@4.1.5",
    verifier_id: "atlas-opaque-background-classifier",
    verifier_version: ATLAS_AUTOMATED_CAPTURE_PROTOCOL.version,
    report_format: "vitest_json",
    atomic_observation_denominator: 7,
    rule_id: "wcag-2.2-aa-color-contrast",
    rule_version: "axe-core@4.11.4",
    command_argv: [
      "corepack",
      "pnpm",
      "exec",
      "vitest",
      "run",
      "--config",
      "vitest.storybook.config.ts",
      "src/test/a11y/OpaqueBackgroundContrast.stories.tsx",
      "--reporter=json",
    ],
    subject: {
      kind: "surface",
      subject_id: "atlas-opaque-background-contrast",
      state_id: "seven-declared-sources",
    },
    exact_tests: exactOpaqueTests,
  },
} as const;

export type AtlasAutomatedRunnerProfileId =
  keyof typeof ATLAS_AUTOMATED_RUNNER_PROFILES;

const nonEmptyString = z
  .string()
  .min(1)
  .refine((value) => value.trim() === value, {
    message: "value must have no surrounding whitespace",
  });
const repositoryRevision = z.string().regex(/^[0-9a-f]{40}$/);
const sha256Hex = z.string().regex(/^[0-9a-f]{64}$/);
const utcTimestamp = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
  .refine((value) => {
    const parsed = new Date(value);
    return !Number.isNaN(parsed.valueOf()) && parsed.toISOString() === value;
  }, "timestamp must be a real millisecond-precision UTC instant");

const normalizedTestSchema = z
  .object({
    file: nonEmptyString,
    title: nonEmptyString,
    outcome: z.enum(["pass", "fail", "incomplete"]),
    duration_ms: z.number().nonnegative(),
    findings: z
      .array(
        z
          .object({
            code: z
              .string()
              .min(1)
              .regex(/^[a-z0-9][a-z0-9._:@/-]*$/),
            detail: nonEmptyString,
          })
          .strict(),
      ),
  })
  .strict()
  .superRefine((test, context) => {
    if (test.outcome === "pass" && test.findings.length > 0) {
      context.addIssue({
        code: "custom",
        path: ["findings"],
        message: "a passing test cannot contain findings",
      });
    }
    if (test.outcome !== "pass" && test.findings.length === 0) {
      context.addIssue({
        code: "custom",
        path: ["findings"],
        message: "a non-passing test must contain a finding",
      });
    }
  });

export const atlasNormalizedRunnerReportSchema = z
  .object({
    report_schema: z
      .object({
        id: z.literal("polisyos.atlas.normalized-runner-report"),
        version: z.literal("1.0.0"),
      })
      .strict(),
    runner: z
      .object({
        profile_id: z.enum(["keyboard_playwright", "opaque_storybook"]),
        runner_id: nonEmptyString,
        runner_version: nonEmptyString,
        report_format: z.enum(["playwright_json", "vitest_json"]),
      })
      .strict(),
    repository_revision: repositoryRevision,
    command_argv: z.array(nonEmptyString).min(1),
    started_at: utcTimestamp,
    finished_at: utcTimestamp,
    summary: z
      .object({
        total: z.number().int().nonnegative(),
        passed: z.number().int().nonnegative(),
        failed: z.number().int().nonnegative(),
        incomplete: z.number().int().nonnegative(),
      })
      .strict(),
    tests: z.array(normalizedTestSchema),
  })
  .strict();

export type AtlasNormalizedRunnerReport = z.infer<
  typeof atlasNormalizedRunnerReportSchema
>;

const captureImplementationProvenanceSchema = z
  .object({
    implementation_sha256: sha256Hex,
    files: z.tuple([
      z
        .object({
          path: z.literal(ATLAS_CAPTURE_IMPLEMENTATION_PATHS[0]),
          sha256: sha256Hex,
        })
        .strict(),
      z
        .object({
          path: z.literal(ATLAS_CAPTURE_IMPLEMENTATION_PATHS[1]),
          sha256: sha256Hex,
        })
        .strict(),
      z
        .object({
          path: z.literal(ATLAS_CAPTURE_IMPLEMENTATION_PATHS[2]),
          sha256: sha256Hex,
        })
        .strict(),
      z
        .object({
          path: z.literal(ATLAS_CAPTURE_IMPLEMENTATION_PATHS[3]),
          sha256: sha256Hex,
        })
        .strict(),
      z
        .object({
          path: z.literal(ATLAS_CAPTURE_IMPLEMENTATION_PATHS[4]),
          sha256: sha256Hex,
        })
        .strict(),
    ]),
    repository_revision: repositoryRevision,
    dirty: z.boolean(),
  })
  .strict()
  .superRefine((provenance, context) => {
    const aggregate = createHash("sha256");
    for (const file of provenance.files) {
      aggregate.update(`${file.path}\0${file.sha256}\n`);
    }
    if (aggregate.digest("hex") !== provenance.implementation_sha256) {
      context.addIssue({
        code: "custom",
        path: ["implementation_sha256"],
        message: "capture implementation aggregate does not bind its files",
      });
    }
  });

export type AtlasCaptureImplementationProvenance = z.infer<
  typeof captureImplementationProvenanceSchema
>;

export type AtlasAutomatedCaptureInput = {
  profile_id: AtlasAutomatedRunnerProfileId;
  normalized_report: unknown;
  raw_report_bytes: Uint8Array;
  verified_at: string;
  implementation_provenance: unknown;
};

export type AtlasAutomatedCapturePair = {
  payload: AtlasEvidencePayload;
  receipt_without_payload_ref: Omit<
    AtlasEvidenceReceipt,
    "evidence_payload_ref"
  >;
};

function testIdentity(test: { file: string; title: string }): string {
  return `${test.file}::${test.title}`;
}

function compareExactPopulation(
  profile: (typeof ATLAS_AUTOMATED_RUNNER_PROFILES)[AtlasAutomatedRunnerProfileId],
  tests: AtlasNormalizedRunnerReport["tests"],
): void {
  const expected = profile.exact_tests.map(testIdentity).sort();
  const actual = tests.map(testIdentity).sort();
  if (new Set(actual).size !== actual.length) {
    throw new TypeError("automated evidence report contains duplicate test identities");
  }
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new TypeError(
      `automated evidence population mismatch: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
    );
  }
}

function assertDeclaredCommand(
  profile: (typeof ATLAS_AUTOMATED_RUNNER_PROFILES)[AtlasAutomatedRunnerProfileId],
  commandArgv: string[],
): void {
  const runnerArgv =
    commandArgv[0] === "/usr/bin/time" && commandArgv[1] === "-p"
      ? commandArgv.slice(2)
      : commandArgv;
  const expected = [...profile.command_argv];
  const candidate = [...runnerArgv];
  if (
    profile.profile_id === "opaque_storybook" &&
    candidate.at(-1)?.startsWith("--outputFile=")
  ) {
    candidate.pop();
  }
  if (JSON.stringify(candidate) !== JSON.stringify(expected)) {
    throw new TypeError("automated evidence command does not match its declared runner");
  }
}

function assertSummary(
  report: AtlasNormalizedRunnerReport,
): "pass" | "fail" | "incomplete" {
  const measured = {
    total: report.tests.length,
    passed: report.tests.filter(({ outcome }) => outcome === "pass").length,
    failed: report.tests.filter(({ outcome }) => outcome === "fail").length,
    incomplete: report.tests.filter(({ outcome }) => outcome === "incomplete")
      .length,
  };
  if (JSON.stringify(report.summary) !== JSON.stringify(measured)) {
    throw new TypeError(
      `automated evidence summary contradicts individual results: ${JSON.stringify(measured)}`,
    );
  }
  if (measured.failed > 0) {
    return "fail";
  }
  if (measured.incomplete > 0) {
    return "incomplete";
  }
  if (measured.total === 0 || measured.passed !== measured.total) {
    throw new TypeError("automated evidence pass requires the complete declared population");
  }
  return "pass";
}

function addDays(timestamp: string, days: number): string {
  return new Date(Date.parse(timestamp) + days * 86_400_000).toISOString();
}

export function buildAtlasAutomatedEvidenceCapture(
  input: AtlasAutomatedCaptureInput,
): AtlasAutomatedCapturePair {
  const profile = ATLAS_AUTOMATED_RUNNER_PROFILES[input.profile_id];
  if (!profile) {
    throw new TypeError(`undeclared automated evidence runner: ${input.profile_id}`);
  }
  const report = atlasNormalizedRunnerReportSchema.parse(
    input.normalized_report,
  );
  const implementationProvenance = captureImplementationProvenanceSchema.parse(
    input.implementation_provenance,
  );
  if (
    report.runner.profile_id !== profile.profile_id ||
    report.runner.runner_id !== profile.runner_id ||
    report.runner.runner_version !== profile.runner_version ||
    report.runner.report_format !== profile.report_format
  ) {
    throw new TypeError("automated evidence runner declaration mismatch");
  }
  if (Date.parse(report.finished_at) < Date.parse(report.started_at)) {
    throw new TypeError("runner finish cannot precede runner start");
  }
  const verifiedAt = utcTimestamp.parse(input.verified_at);
  if (Date.parse(verifiedAt) < Date.parse(report.finished_at)) {
    throw new TypeError("evidence verification cannot precede report collection");
  }
  compareExactPopulation(profile, report.tests);
  assertDeclaredCommand(profile, report.command_argv);
  const outcome = assertSummary(report);
  const findings = report.tests.flatMap(({ file, title, findings: testFindings }) =>
    testFindings.map((finding) => ({
      code: finding.code,
      detail: `${file} / ${title}: ${finding.detail}`,
    })),
  );
  if (outcome !== "pass" && findings.length === 0) {
    throw new TypeError("non-passing automated evidence must retain a finding");
  }

  const provenance = {
    producer: {
      producer_id: profile.runner_id,
      producer_version: profile.runner_version,
    },
    verifier: {
      verifier_id: profile.verifier_id,
      verifier_version: profile.verifier_version,
    },
    repository_revision: report.repository_revision,
    command_argv: report.command_argv,
    predicate_provenance: "recomputed" as const,
  };
  const times = {
    observed_at: report.started_at,
    collected_at: report.finished_at,
    verified_at: verifiedAt,
  };
  const result = { outcome, findings };
  const payload: AtlasEvidencePayload = atlasEvidencePayloadSchema.parse({
    payload_schema: ATLAS_EVIDENCE_PAYLOAD_SCHEMA,
    evidence_kind: profile.evidence_kind,
    subject: profile.subject,
    rule: {
      rule_id: profile.rule_id,
      rule_version: profile.rule_version,
    },
    provenance,
    times,
    result,
    details: {
      capture_protocol: ATLAS_AUTOMATED_CAPTURE_PROTOCOL,
      capture_implementation: implementationProvenance,
      raw_report_sha256: createHash("sha256")
        .update(input.raw_report_bytes)
        .digest("hex"),
      report_schema: report.report_schema,
      runner: report.runner,
      summary: report.summary,
      tests: report.tests,
      atomic_observations: {
        declared: profile.atomic_observation_denominator,
        admitted: outcome === "pass" ? profile.atomic_observation_denominator : 0,
        mode: "all_or_nothing",
      },
      field_provenance: {
        runner_result: "recomputed",
        raw_report_sha256: "recomputed",
        test_population: "recomputed",
        runner_identity: "independently_reconciled",
        runner_version:
          profile.profile_id === "keyboard_playwright"
            ? "recomputed"
            : "institutionally_supplied",
        verifier_identity: "independently_reconciled",
        rule_identity: "institutionally_supplied",
        capture_implementation: "independently_reconciled",
        command_argv: "institutionally_supplied",
        repository_revision: "institutionally_supplied",
      },
    },
  });
  const receiptWithoutPayloadRef: Omit<
    AtlasEvidenceReceipt,
    "evidence_payload_ref"
  > = {
    receipt_schema: ATLAS_EVIDENCE_RECEIPT_SCHEMA,
    authority: {
      authoritative_for: ["atlas_evidence_capture"],
      may_not_use_for: [...ATLAS_EVIDENCE_DENIED_USES],
    },
    evidence_kind: payload.evidence_kind,
    subject: payload.subject,
    rule: payload.rule,
    provenance: payload.provenance,
    audiences: ["REVIEWER", "EXPERT", "MACHINE"],
    times: payload.times,
    result: payload.result,
    retention: {
      retention_class: ATLAS_EVIDENCE_STORAGE_CONVENTION.retention_class,
      retention_days: ATLAS_EVIDENCE_STORAGE_CONVENTION.retention_days,
      retain_until: addDays(
        payload.times.collected_at,
        ATLAS_EVIDENCE_STORAGE_CONVENTION.retention_days,
      ),
      cleanup_policy: ATLAS_EVIDENCE_STORAGE_CONVENTION.cleanup_policy,
    },
  };
  return {
    payload,
    receipt_without_payload_ref: receiptWithoutPayloadRef,
  };
}

const persistenceResultSchema = z
  .object({
    ok: z.literal(true),
    operation: z.literal("persist_atlas_evidence"),
    raw_report_ref: z
      .object({
        artifact_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
        kind: z.literal("atlas_evidence_raw_runner_report"),
        media_type: z.literal("application/json"),
      })
      .strict(),
    payload_ref: z
      .object({
        artifact_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
        kind: z.literal("atlas_evidence_verification_payload"),
        media_type: z.literal("application/json"),
      })
      .strict(),
    receipt_ref: z
      .object({
        artifact_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
        kind: z.literal("atlas_evidence_receipt"),
        media_type: z.literal("application/json"),
      })
      .strict(),
    raw_report_verification: z
      .object({
        ok: z.literal(true),
        artifact_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
        expected_sha256_hex: z.string().regex(/^[0-9a-f]{64}$/),
        actual_sha256_hex: z.string().regex(/^[0-9a-f]{64}$/),
        byte_size: z.number().int().positive(),
        error: z.null(),
      })
      .strict(),
    payload_verification: z
      .object({
        ok: z.literal(true),
        artifact_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
        expected_sha256_hex: z.string().regex(/^[0-9a-f]{64}$/),
        actual_sha256_hex: z.string().regex(/^[0-9a-f]{64}$/),
        byte_size: z.number().int().positive(),
        error: z.null(),
      })
      .strict(),
    receipt_verification: z
      .object({
        ok: z.literal(true),
        artifact_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
        expected_sha256_hex: z.string().regex(/^[0-9a-f]{64}$/),
        actual_sha256_hex: z.string().regex(/^[0-9a-f]{64}$/),
        byte_size: z.number().int().positive(),
        error: z.null(),
      })
      .strict(),
    receipt_manifest_input: z
      .object({
        artifact_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
        role: z.literal("verification_payload"),
      })
      .strict(),
    payload_manifest_input: z
      .object({
        artifact_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
        role: z.literal("runner_report"),
      })
      .strict(),
    resolved_payload: z
      .object({
        artifact_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
        payload: atlasEvidencePayloadSchema,
      })
      .strict(),
    resolved_receipt: z
      .object({
        artifact_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
        receipt: atlasEvidenceReceiptSchema,
      })
      .strict(),
  })
  .strict();

export type AtlasEvidencePersistenceResult = z.infer<
  typeof persistenceResultSchema
>;

export function assertAtlasEvidencePersistenceResult(
  value: unknown,
): AtlasEvidencePersistenceResult {
  const result = persistenceResultSchema.parse(value);
  const rawReportId = result.raw_report_ref.artifact_id;
  const payloadId = result.payload_ref.artifact_id;
  const receiptId = result.receipt_ref.artifact_id;
  const rawReportDigest = result.resolved_payload.payload.details.raw_report_sha256;
  if (
    typeof rawReportDigest !== "string" ||
    result.raw_report_verification.artifact_id !== rawReportId ||
    result.raw_report_verification.expected_sha256_hex !== rawReportId.slice(7) ||
    result.raw_report_verification.actual_sha256_hex !== rawReportId.slice(7) ||
    rawReportDigest !== rawReportId.slice(7) ||
    result.payload_manifest_input.artifact_id !== rawReportId
  ) {
    throw new TypeError("persisted raw runner report integrity binding mismatch");
  }
  if (
    result.payload_verification.artifact_id !== payloadId ||
    result.payload_verification.expected_sha256_hex !== payloadId.slice(7) ||
    result.payload_verification.actual_sha256_hex !== payloadId.slice(7) ||
    result.resolved_payload.artifact_id !== payloadId ||
    result.receipt_manifest_input.artifact_id !== payloadId
  ) {
    throw new TypeError("persisted verification payload integrity binding mismatch");
  }
  if (
    result.receipt_verification.artifact_id !== receiptId ||
    result.receipt_verification.expected_sha256_hex !== receiptId.slice(7) ||
    result.receipt_verification.actual_sha256_hex !== receiptId.slice(7) ||
    result.resolved_receipt.artifact_id !== receiptId
  ) {
    throw new TypeError("persisted evidence receipt integrity binding mismatch");
  }
  const receipt = result.resolved_receipt.receipt;
  if (
    receipt.evidence_payload_ref.artifact_id !== payloadId ||
    result.receipt_manifest_input.role !==
      ATLAS_EVIDENCE_STORAGE_CONVENTION.receipt_input_role
  ) {
    throw new TypeError("persisted evidence manifest lineage mismatch");
  }
  if (result.payload_manifest_input.role !== "runner_report") {
    throw new TypeError("persisted evidence raw-report lineage mismatch");
  }
  assertAtlasEvidencePayloadBinding(receipt, result.resolved_payload);
  return result;
}
