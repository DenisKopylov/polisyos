import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { isDeepStrictEqual } from "node:util";
import { fileURLToPath } from "node:url";

import { z } from "zod";

import {
  ATLAS_AUTOMATED_RUNNER_PROFILES,
  ATLAS_CAPTURE_IMPLEMENTATION_PATHS,
  assertAtlasEvidencePersistenceResult,
  buildAtlasAutomatedEvidenceCapture,
  type AtlasAutomatedCapturePair,
  type AtlasCaptureImplementationProvenance,
  type AtlasAutomatedRunnerProfileId,
  type AtlasEvidencePersistenceResult,
  type AtlasNormalizedRunnerReport,
} from "./atlasAutomatedEvidenceCapture";

/* Keep this import static: Storybook/Vitest exposes an http: import.meta.url. */

const currentFile = fileURLToPath(import.meta.url);
const dashboardRoot = path.resolve(path.dirname(currentFile), "../../..");
const policyEngineRoot = path.resolve(dashboardRoot, "../..");
const defaultBridgePath = path.resolve(
  dashboardRoot,
  "scripts/persist_atlas_evidence.py",
);

function runGit(args: string[]): string {
  const result = spawnSync("git", args, {
    cwd: policyEngineRoot,
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new TypeError(
      `capture implementation git provenance failed (${String(result.status)}): ${result.stderr.trim()}`,
    );
  }
  return result.stdout;
}

/** Recompute the exact implementation bytes and dirty state used by C08. */
export function computeCaptureImplementationProvenance(): AtlasCaptureImplementationProvenance {
  const files = ATLAS_CAPTURE_IMPLEMENTATION_PATHS.map((filePath) => ({
    path: filePath,
    sha256: createHash("sha256")
      .update(readFileSync(path.resolve(policyEngineRoot, filePath)))
      .digest("hex"),
  })) as AtlasCaptureImplementationProvenance["files"];
  const aggregate = createHash("sha256");
  for (const file of files) {
    aggregate.update(`${file.path}\0${file.sha256}\n`);
  }
  const repositoryRevision = runGit(["rev-parse", "HEAD"]).trim();
  const dirty = runGit(["status", "--porcelain=v1"]).trim().length > 0;
  return {
    implementation_sha256: aggregate.digest("hex"),
    files,
    repository_revision: repositoryRevision,
    dirty,
  };
}

const rawFindingSchema = z
  .object({
    message: z.string().optional(),
  })
  .loose();
const playwrightResultSchema = z
  .object({
    status: z
      .enum(["passed", "failed", "timedOut", "skipped", "interrupted"])
      .nullable(),
    duration: z.number().nonnegative(),
    errors: z.array(rawFindingSchema),
    startTime: z.string(),
  })
  .loose();
const playwrightTestSchema = z
  .object({
    expectedStatus: z.enum([
      "passed",
      "failed",
      "timedOut",
      "skipped",
      "interrupted",
    ]),
    projectName: z.string(),
    results: z.array(playwrightResultSchema).min(1),
    status: z.enum(["skipped", "expected", "unexpected", "flaky"]),
  })
  .loose();
const playwrightSpecSchema = z
  .object({
    title: z.string().min(1),
    file: z.string().min(1),
    tests: z.array(playwrightTestSchema).min(1),
  })
  .loose();
type RawPlaywrightSuite = {
  title: string;
  file: string;
  specs: z.infer<typeof playwrightSpecSchema>[];
  suites?: RawPlaywrightSuite[];
};
const playwrightSuiteSchema: z.ZodType<RawPlaywrightSuite> = z.lazy(() =>
  z
    .object({
      title: z.string(),
      file: z.string(),
      specs: z.array(playwrightSpecSchema),
      suites: z.array(playwrightSuiteSchema).optional(),
    })
    .loose(),
);
const playwrightReportSchema = z
  .object({
    config: z
      .object({
        version: z.literal("1.59.1"),
        workers: z.literal(1),
      })
      .loose(),
    suites: z.array(playwrightSuiteSchema),
    errors: z.array(rawFindingSchema),
    stats: z
      .object({
        startTime: z.string(),
        duration: z.number().nonnegative(),
        expected: z.number().int().nonnegative(),
        unexpected: z.number().int().nonnegative(),
        flaky: z.number().int().nonnegative(),
        skipped: z.number().int().nonnegative(),
      })
      .strict(),
  })
  .loose();

const vitestAssertionSchema = z
  .object({
    ancestorTitles: z.array(z.string()),
    fullName: z.string().min(1),
    status: z.enum(["passed", "failed", "pending", "skipped", "todo"]),
    title: z.string().min(1),
    duration: z.number().nonnegative().nullable().optional(),
    failureMessages: z.array(z.string()),
  })
  .loose();
const vitestFileSchema = z
  .object({
    assertionResults: z.array(vitestAssertionSchema),
    startTime: z.number(),
    endTime: z.number(),
    status: z.enum(["passed", "failed", "pending"]),
    name: z.string().min(1),
  })
  .loose();
const vitestReportSchema = z
  .object({
    numTotalTestSuites: z.number().int().nonnegative(),
    numPassedTestSuites: z.number().int().nonnegative(),
    numFailedTestSuites: z.number().int().nonnegative(),
    numPendingTestSuites: z.number().int().nonnegative(),
    numTotalTests: z.number().int().nonnegative(),
    numPassedTests: z.number().int().nonnegative(),
    numFailedTests: z.number().int().nonnegative(),
    numPendingTests: z.number().int().nonnegative(),
    numTodoTests: z.number().int().nonnegative(),
    startTime: z.number(),
    success: z.boolean(),
    testResults: z.array(vitestFileSchema),
  })
  .loose();

function normalizeSourceFile(value: string): string {
  const normalized = value.replaceAll("\\", "/");
  const sourceIndex = normalized.lastIndexOf("/src/");
  if (sourceIndex >= 0) {
    return normalized.slice(sourceIndex + 1);
  }
  return normalized.replace(/^\.\.\//, "");
}

function isFileSuite(suite: RawPlaywrightSuite): boolean {
  return suite.title.endsWith(path.posix.basename(suite.file.replaceAll("\\", "/")));
}

type PlaywrightSpecAtPath = {
  parentTitles: string[];
  spec: z.infer<typeof playwrightSpecSchema>;
};

function flattenPlaywrightSpecs(
  suites: RawPlaywrightSuite[],
  parentTitles: string[] = [],
): PlaywrightSpecAtPath[] {
  return suites.flatMap((suite) => {
    const titles = isFileSuite(suite)
      ? parentTitles
      : [...parentTitles, suite.title];
    return [
      ...suite.specs.map((spec) => ({ parentTitles: titles, spec })),
      ...flattenPlaywrightSpecs(suite.suites ?? [], titles),
    ];
  });
}

function findingDetail(messages: string[], fallback: string): string {
  const detail = messages.map((message) => message.trim()).filter(Boolean).join("\n");
  return detail || fallback;
}

function normalizePlaywrightReport(
  raw: unknown,
  repositoryRevision: string,
  commandArgv: string[],
): AtlasNormalizedRunnerReport {
  const source = playwrightReportSchema.parse(raw);
  if (source.errors.length > 0) {
    throw new TypeError("Playwright report contains top-level collection errors");
  }
  const profile = ATLAS_AUTOMATED_RUNNER_PROFILES.keyboard_playwright;
  const tests = flattenPlaywrightSpecs(source.suites).flatMap(
    ({ parentTitles, spec }) =>
      spec.tests.map((test) => {
        const result = test.results.at(-1)!;
        if (test.projectName !== "chromium" || test.expectedStatus !== "passed") {
          throw new TypeError("keyboard evidence requires an expected-pass Chromium result");
        }
        const outcome =
          test.status === "expected" && result.status === "passed"
            ? ("pass" as const)
            : test.status === "unexpected" ||
                result.status === "failed" ||
                result.status === "timedOut"
              ? ("fail" as const)
              : ("incomplete" as const);
        const findings =
          outcome === "pass"
            ? []
            : [
                {
                  code:
                    outcome === "fail"
                      ? "playwright_test_failed"
                      : "playwright_test_incomplete",
                  detail: findingDetail(
                    result.errors.map(({ message }) => message ?? ""),
                    `Playwright outcome ${test.status}/${String(result.status)} did not pass.`,
                  ),
                },
              ];
        return {
          file: normalizeSourceFile(spec.file),
          title: [...parentTitles, spec.title].join(" > "),
          outcome,
          duration_ms: result.duration,
          findings,
        };
      }),
  );
  const measured = {
    total: tests.length,
    passed: tests.filter(({ outcome }) => outcome === "pass").length,
    failed: tests.filter(({ outcome }) => outcome === "fail").length,
    incomplete: tests.filter(({ outcome }) => outcome === "incomplete").length,
  };
  if (
    source.stats.expected !== measured.passed ||
    source.stats.unexpected !== measured.failed ||
    source.stats.flaky + source.stats.skipped !== measured.incomplete ||
    source.stats.expected +
      source.stats.unexpected +
      source.stats.flaky +
      source.stats.skipped !==
      measured.total
  ) {
    throw new TypeError("Playwright summary contradicts its individual results");
  }
  const startedAt = new Date(source.stats.startTime).toISOString();
  const finishedAt = new Date(
    Date.parse(startedAt) + source.stats.duration,
  ).toISOString();
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
    repository_revision: repositoryRevision,
    command_argv: commandArgv,
    started_at: startedAt,
    finished_at: finishedAt,
    summary: measured,
    tests,
  };
}

function normalizeVitestReport(
  raw: unknown,
  repositoryRevision: string,
  commandArgv: string[],
): AtlasNormalizedRunnerReport {
  const source = vitestReportSchema.parse(raw);
  const profile = ATLAS_AUTOMATED_RUNNER_PROFILES.opaque_storybook;
  const tests = source.testResults.flatMap((file) =>
    file.assertionResults.map((assertion) => {
      const outcome =
        assertion.status === "passed"
          ? ("pass" as const)
          : assertion.status === "failed"
            ? ("fail" as const)
            : ("incomplete" as const);
      return {
        file: normalizeSourceFile(file.name),
        title: assertion.fullName,
        outcome,
        duration_ms: assertion.duration ?? 0,
        findings:
          outcome === "pass"
            ? []
            : [
                {
                  code:
                    outcome === "fail"
                      ? "vitest_assertion_failed"
                      : "vitest_assertion_incomplete",
                  detail: findingDetail(
                    assertion.failureMessages,
                    `Vitest assertion outcome ${assertion.status} did not pass.`,
                  ),
                },
              ],
      };
    }),
  );
  const measured = {
    total: tests.length,
    passed: tests.filter(({ outcome }) => outcome === "pass").length,
    failed: tests.filter(({ outcome }) => outcome === "fail").length,
    incomplete: tests.filter(({ outcome }) => outcome === "incomplete").length,
  };
  const measuredSuites = {
    passed: source.testResults.filter(({ assertionResults }) =>
      assertionResults.every(({ status }) => status === "passed"),
    ).length,
    failed: source.testResults.filter(({ assertionResults }) =>
      assertionResults.some(({ status }) => status === "failed"),
    ).length,
    pending: source.testResults.filter(
      ({ assertionResults }) =>
        !assertionResults.some(({ status }) => status === "failed") &&
        assertionResults.some(({ status }) => status !== "passed"),
    ).length,
  };
  const fileStatusesMatch = source.testResults.every((file) => {
    const hasFailure = file.assertionResults.some(({ status }) => status === "failed");
    const hasIncomplete = file.assertionResults.some(
      ({ status }) => status !== "passed" && status !== "failed",
    );
    const expectedStatus = hasFailure
      ? "failed"
      : hasIncomplete
        ? "pending"
        : "passed";
    return file.status === expectedStatus;
  });
  if (
    source.numTotalTests !== measured.total ||
    source.numPassedTests !== measured.passed ||
    source.numFailedTests !== measured.failed ||
    source.numPendingTests + source.numTodoTests !== measured.incomplete ||
    source.numTotalTestSuites !== source.testResults.length ||
    source.numPassedTestSuites !== measuredSuites.passed ||
    source.numFailedTestSuites !== measuredSuites.failed ||
    source.numPendingTestSuites !== measuredSuites.pending ||
    !fileStatusesMatch ||
    source.success !==
      (measured.failed === 0 &&
        measured.incomplete === 0 &&
        measuredSuites.failed === 0 &&
        measuredSuites.pending === 0)
  ) {
    throw new TypeError("Vitest summary contradicts its individual results");
  }
  const finishedAt = Math.max(
    source.startTime,
    ...source.testResults.map(({ endTime }) => endTime),
  );
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
    repository_revision: repositoryRevision,
    command_argv: commandArgv,
    started_at: new Date(source.startTime).toISOString(),
    finished_at: new Date(finishedAt).toISOString(),
    summary: measured,
    tests,
  };
}

export function normalizeAtlasRunnerReport(
  profileId: AtlasAutomatedRunnerProfileId,
  raw: unknown,
  repositoryRevision: string,
  commandArgv: string[],
): AtlasNormalizedRunnerReport {
  if (profileId === "keyboard_playwright") {
    return normalizePlaywrightReport(raw, repositoryRevision, commandArgv);
  }
  if (profileId === "opaque_storybook") {
    return normalizeVitestReport(raw, repositoryRevision, commandArgv);
  }
  throw new TypeError(`undeclared automated evidence runner: ${String(profileId)}`);
}

type CommandOptions = {
  profileId: AtlasAutomatedRunnerProfileId;
  reportPath: string;
  repositoryRevision: string;
  commandArgv: string[];
  casRoot: string;
};

function readOptions(argv: string[]): CommandOptions {
  const values = new Map<string, string>();
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!flag?.startsWith("--") || !value) {
      throw new TypeError("capture arguments must be --name value pairs");
    }
    if (values.has(flag)) {
      throw new TypeError(`duplicate capture argument: ${flag}`);
    }
    values.set(flag, value);
  }
  const allowed = new Set([
    "--profile",
    "--report",
    "--revision",
    "--command-json",
    "--cas-root",
  ]);
  for (const flag of values.keys()) {
    if (!allowed.has(flag)) {
      throw new TypeError(`unknown capture argument: ${flag}`);
    }
  }
  const profileId = values.get("--profile");
  const reportPath = values.get("--report");
  const repositoryRevision = values.get("--revision");
  const commandJson = values.get("--command-json");
  const casRoot = values.get("--cas-root");
  if (
    (profileId !== "keyboard_playwright" && profileId !== "opaque_storybook") ||
    !reportPath ||
    !repositoryRevision ||
    !/^[0-9a-f]{40}$/.test(repositoryRevision) ||
    !commandJson ||
    !casRoot
  ) {
    throw new TypeError(
      "capture requires --profile keyboard_playwright|opaque_storybook, --report PATH, --revision 40HEX, --command-json JSON_ARRAY, and --cas-root PATH",
    );
  }
  let commandArgv: unknown;
  try {
    commandArgv = JSON.parse(commandJson);
  } catch (error) {
    throw new TypeError(`--command-json must be valid JSON: ${String(error)}`);
  }
  if (
    !Array.isArray(commandArgv) ||
    commandArgv.length === 0 ||
    commandArgv.some(
      (value) =>
        typeof value !== "string" || value.length === 0 || value.trim() !== value,
    )
  ) {
    throw new TypeError("--command-json must be a non-empty JSON array of trimmed strings");
  }
  return {
    profileId,
    reportPath: path.resolve(reportPath),
    repositoryRevision,
    commandArgv,
    casRoot: path.resolve(casRoot),
  };
}

function invokePersistenceBridge(
  options: CommandOptions,
  capture: AtlasAutomatedCapturePair,
  rawReportBytes: Uint8Array,
): unknown {
  const result = spawnSync("python3", [defaultBridgePath], {
    cwd: policyEngineRoot,
    encoding: "utf8",
    input: JSON.stringify({
      operation: "persist_atlas_evidence",
      raw_report_base64: Buffer.from(rawReportBytes).toString("base64"),
      payload: capture.payload,
      receipt: capture.receipt_without_payload_ref,
    }),
    env: {
      ...process.env,
      POLISYOS_CAS_BACKEND: "filesystem",
      POLISYOS_CAS_ROOT: options.casRoot,
    },
    maxBuffer: 8 * 1024 * 1024,
  });
  let response: unknown;
  try {
    response = JSON.parse(result.stdout);
  } catch (error) {
    throw new TypeError(
      `Atlas persistence bridge emitted invalid JSON: ${String(error)}; stderr=${result.stderr.trim()}`,
    );
  }
  if (result.status !== 0) {
    throw new TypeError(
      `Atlas persistence bridge failed (${String(result.status)}): ${JSON.stringify(response)}`,
    );
  }
  return response;
}

function assertExactResolvedPair(
  capture: AtlasAutomatedCapturePair,
  result: AtlasEvidencePersistenceResult,
): void {
  if (!isDeepStrictEqual(result.resolved_payload.payload, capture.payload)) {
    throw new TypeError("resolved verification payload differs from normalized capture");
  }
  const { evidence_payload_ref: _ref, ...receiptWithoutRef } =
    result.resolved_receipt.receipt;
  if (!isDeepStrictEqual(receiptWithoutRef, capture.receipt_without_payload_ref)) {
    throw new TypeError("resolved evidence receipt differs from normalized capture");
  }
}

export function captureAtlasEvidence(argv: string[]): unknown {
  const options = readOptions(argv);
  const rawReportBytes = readFileSync(options.reportPath);
  const rawReport = JSON.parse(rawReportBytes.toString("utf8")) as unknown;
  const normalizedReport = normalizeAtlasRunnerReport(
    options.profileId,
    rawReport,
    options.repositoryRevision,
    options.commandArgv,
  );
  const capture = buildAtlasAutomatedEvidenceCapture({
    profile_id: options.profileId,
    normalized_report: normalizedReport,
    raw_report_bytes: rawReportBytes,
    verified_at: new Date().toISOString(),
    implementation_provenance: computeCaptureImplementationProvenance(),
  });
  const persisted = assertAtlasEvidencePersistenceResult(
    invokePersistenceBridge(options, capture, rawReportBytes),
  );
  assertExactResolvedPair(capture, persisted);
  return {
    capture_protocol: "polisyos.atlas.automated-evidence-capture@1.0.0",
    profile_id: options.profileId,
    repository_revision: options.repositoryRevision,
    report_path: options.reportPath,
    raw_report_sha256: capture.payload.details.raw_report_sha256,
    result: persisted,
  };
}

function main(): void {
  try {
    const result = captureAtlasEvidence(process.argv.slice(2));
    const output = `${JSON.stringify(result)}\n`;
    process.stdout.write(output);
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
    process.exitCode = 1;
  }
}

if (path.resolve(process.argv[1] ?? "") === currentFile) {
  main();
}
