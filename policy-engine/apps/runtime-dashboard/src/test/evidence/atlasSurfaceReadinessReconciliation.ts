import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { isValidElement } from "react";
import { Navigate, type RouteObject } from "react-router-dom";
import { z } from "zod";

import { APP_ROUTES } from "@/app/routes/routes";

import {
  ATLAS_EVIDENCE_RECONCILIATION_PAYLOAD_SCHEMA,
  ATLAS_EVIDENCE_RECONCILIATION_RECEIPT_SCHEMA,
  ATLAS_EVIDENCE_STORAGE_CONVENTION,
  ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT,
  atlasEvidencePayloadSchema,
  type AtlasEvidencePayload,
  type AtlasEvidenceReceipt,
} from "./atlasEvidenceArtifact";

const currentFile = fileURLToPath(import.meta.url);
const dashboardRoot = path.resolve(path.dirname(currentFile), "../../..");
const policyEngineRoot = path.resolve(dashboardRoot, "../..");

export const C10_RECONCILIATION_CODES = {
  stable_evidence_reference_unresolved:
    "stable_evidence_reference_unresolved",
  implemented_negative_test_missing: "implemented_negative_test_missing",
  implemented_semantic_test_missing: "implemented_semantic_test_missing",
  implemented_deprecated_redirect_unverified:
    "implemented_deprecated_redirect_unverified",
  redirect_test_receipt_invalid: "redirect_test_receipt_invalid",
  ledger_vocabulary_invalid: "ledger_vocabulary_invalid",
  ledger_duplicate_identity: "ledger_duplicate_identity",
} as const;

const REDIRECTS = [
  { surface_id: "route-redirect-launch", from: "/launch", to: "/compose" },
  { surface_id: "route-redirect-sources", from: "/sources", to: "/evidence" },
  { surface_id: "route-redirect-data", from: "/data", to: "/evidence" },
  { surface_id: "route-redirect-lex", from: "/lex", to: "/knowledge" },
  { surface_id: "route-redirect-health", from: "/health", to: "/platform" },
] as const;

type CanonicalRedirect = (typeof REDIRECTS)[number];
type Finding = { code: string; detail: string };

const nonEmptyString = z.string().min(1);
const identity = nonEmptyString.regex(/^[a-z0-9][a-z0-9-]*$/);
const ownerDateSchema = z.iso.date();
const ownerDateTimeSchema = z.iso.datetime({ offset: true });
const maturitySchema = z.enum(["experimental", "beta", "stable", "deprecated"]);
const readinessStateSchema = z.enum([
  "contract_only",
  "producer_missing",
  "bridge_missing",
  "consumer_missing",
  "verification_missing",
  "surface_missing",
  "semantic_test_missing",
  "implemented",
]);
const chainStateSchema = z.enum(["implemented", "missing", "out_of_scope"]);

const audienceSchema = z.enum(["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]);
const owningSliceSchema = z.enum([
  "DS0",
  "DS1",
  "DS2",
  "DS3",
  "DS4",
  "DS5",
  "DS6",
  "DS7",
  "DS8",
  "DS9",
  "DS10",
  "DS11",
  "DS12",
  "DS13",
  "DS14",
  "DS15",
  "DS16",
  "DS17",
  "DS18",
  "DS19",
  "DS20",
]);
const uniqueAudienceArraySchema = z
  .array(audienceSchema)
  .min(1)
  .refine((values) => new Set(values).size === values.length, {
    message: "canonical owner audience items must be unique",
  });
const uniqueOwningSliceArraySchema = z
  .array(owningSliceSchema)
  .min(1)
  .refine((values) => new Set(values).size === values.length, {
    message: "canonical owner slice items must be unique",
  });
const authorityBoundarySchema = z
  .object({
    authoritative_for: z.array(nonEmptyString).min(1),
    may_not_use_for: z.array(nonEmptyString).min(1),
  })
  .strict();
const chainSchema = z
  .object({
    contract: chainStateSchema,
    producer: chainStateSchema,
    persisted: chainStateSchema,
    bridge: chainStateSchema,
    consumer: chainStateSchema,
    verification: chainStateSchema,
    surface: chainStateSchema,
    negative_test: chainStateSchema,
    semantic_test: chainStateSchema,
  })
  .strict();
const adoptionEntrySchema = z
  .object({
    id: identity,
    title: nonEmptyString,
    kind: z.enum(["token_set", "component", "pattern", "package", "doc", "archive"]),
    source: z.enum(["v4_code", "v4_doc", "v7_doc", "v15_archive"]),
    source_disposition: z.enum([
      "retained_current_production_baseline",
      "superseded_as_canonical",
      "retained_as_material",
      "evidence_source_pending_adjudication",
    ]),
    adoption_verdict: z.enum([
      "admit_as_is",
      "admit_after_refactor",
      "wrap_then_strangle",
      "reject",
      "defer",
    ]),
    maturity: maturitySchema,
    audiences: uniqueAudienceArraySchema,
    owner: nonEmptyString,
    decided_at: ownerDateSchema,
    evidence_refs: z
      .array(
        z
          .object({
            kind: z.enum([
              "code_reference",
              "document",
              "archive_report",
              "contract_test",
              "storybook",
              "visual_snapshot",
              "browser",
              "at_manual",
            ]),
            ref: nonEmptyString,
            as_of: ownerDateSchema,
          })
          .strict(),
      )
      .min(1),
    reason: nonEmptyString,
    rejected_alternatives: z.array(nonEmptyString).min(1),
    revisit_condition: nonEmptyString,
    sunset_condition: nonEmptyString,
    consuming_surfaces: uniqueOwningSliceArraySchema,
    next_adjudication: z
      .object({
        owner_slices: uniqueOwningSliceArraySchema,
        scope: z.array(nonEmptyString).min(1),
        completion_signal: nonEmptyString,
      })
      .strict(),
    not_yet: z.array(nonEmptyString).min(1),
    authority: authorityBoundarySchema,
  })
  .strict();
const readinessEntrySchema = z
  .object({
    surface_id: identity,
    title: nonEmptyString,
    owning_slice: owningSliceSchema,
    audiences: uniqueAudienceArraySchema,
    readiness_state: readinessStateSchema,
    maturity: maturitySchema,
    provenance_posture: z.enum(["live", "replay", "fixture_only"]),
    freshness: z
      .object({
        state: z.enum(["live", "cached", "stale", "offline_queued"]),
        as_of: ownerDateTimeSchema,
      })
      .strict(),
    chain: chainSchema,
    evidence_refs: z.array(nonEmptyString).min(1),
    reason: nonEmptyString,
    not_yet: z.array(nonEmptyString).min(1),
    owner: nonEmptyString,
    updated_at: ownerDateTimeSchema,
  })
  .strict();
const adoptionLedgerSchema = z
  .object({
    schema_version: z.literal("1.0"),
    ledger_id: identity,
    as_of: ownerDateTimeSchema,
    controlled_vocabulary_source: z.literal(
      "docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md",
    ),
    authority: authorityBoundarySchema,
    source_hashes: z
      .object({
        v15_archive_sha256: z.literal(
          "28d3e51dd452a074d30b7a0afa439302c48d4c208307a6a2d09beb935f71a969",
        ),
      })
      .strict(),
    entries: z.array(adoptionEntrySchema).min(1),
  })
  .strict();
const readinessLedgerSchema = z
  .object({
    schema_version: z.literal("1.0"),
    ledger_id: identity,
    as_of: ownerDateTimeSchema,
    controlled_vocabulary_source: z.literal(
      "docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md",
    ),
    authority: authorityBoundarySchema,
    entries: z.array(readinessEntrySchema).min(1),
  })
  .strict();

type AdoptionEntry = z.infer<typeof adoptionEntrySchema>;
type ReadinessEntry = z.infer<typeof readinessEntrySchema>;

type RouteTestReceipt = {
  receipt_schema: {
    id: "polisyos.atlas.c10-route-test-receipt";
    version: "1.0.0";
  };
  test_file: "src/app/routes/routes.test.tsx";
  report_sha256: string;
  process_exit_code: number;
  outcome: "pass" | "fail";
  required_assertions: {
    full_name: string;
    status: "pass" | "fail" | "missing";
  }[];
  failure_code?: "redirect_test_receipt_invalid";
};

export type AtlasSurfaceReadinessReconciliationInput = {
  adoption_ledger: unknown;
  readiness_ledger: unknown;
  route_test_report_bytes: Uint8Array;
  route_test_exit_code: number;
  observed_at: string;
  verified_at: string;
};

export type AtlasSurfaceReadinessReconciliation = {
  raw_report: Record<string, unknown>;
  raw_report_bytes: Uint8Array;
  payload: AtlasEvidencePayload;
  receipt_without_payload_ref: Omit<AtlasEvidenceReceipt, "evidence_payload_ref">;
  exit_code: 0 | 1;
};

function ledgerError(code: string, detail: string): TypeError {
  return new TypeError(`${code}: ${detail}`);
}

function assertUniqueIdentities(
  entries: { id?: string; surface_id?: string }[],
  identityField: "id" | "surface_id",
  ledgerName: string,
): void {
  const identities = new Set<string>();
  for (const entry of entries) {
    const entryIdentity = entry[identityField];
    if (!entryIdentity) {
      throw ledgerError(C10_RECONCILIATION_CODES.ledger_vocabulary_invalid, ledgerName);
    }
    if (identities.has(entryIdentity)) {
      throw ledgerError(
        C10_RECONCILIATION_CODES.ledger_duplicate_identity,
        `${ledgerName} duplicates ${identityField}=${entryIdentity}`,
      );
    }
    identities.add(entryIdentity);
  }
}

function parseAdoptionEntries(value: unknown): AdoptionEntry[] {
  const parsed = adoptionLedgerSchema.safeParse(value);
  if (!parsed.success) {
    throw ledgerError(
      C10_RECONCILIATION_CODES.ledger_vocabulary_invalid,
      "adoption ledger is not the canonical strict owner shape",
    );
  }
  assertUniqueIdentities(parsed.data.entries, "id", "adoption ledger");
  return parsed.data.entries;
}

function parseReadinessEntries(value: unknown): ReadinessEntry[] {
  const parsed = readinessLedgerSchema.safeParse(value);
  if (!parsed.success) {
    throw ledgerError(
      C10_RECONCILIATION_CODES.ledger_vocabulary_invalid,
      "surface-readiness ledger is not the canonical strict owner shape",
    );
  }
  assertUniqueIdentities(
    parsed.data.entries,
    "surface_id",
    "surface-readiness ledger",
  );
  return parsed.data.entries;
}

function addDays(timestamp: string, days: number): string {
  return new Date(Date.parse(timestamp) + days * 86_400_000).toISOString();
}

function routePath(pathValue: unknown): string | undefined {
  if (typeof pathValue !== "string" || !pathValue) {
    return undefined;
  }
  return pathValue.startsWith("/") ? pathValue : `/${pathValue}`;
}

function collectNavigateRoutes(routes: readonly RouteObject[]): CanonicalRedirect[] {
  const redirects: CanonicalRedirect[] = [];
  const visit = (routeList: readonly RouteObject[]): void => {
    for (const route of routeList) {
      if (isValidElement(route.element) && route.element.type === Navigate) {
        // The wildcard fallback is not a deprecated ledger redirect. Every
        // other Navigate object is an exact, structural C10 candidate.
        if (route.path !== "*" && route.index !== true) {
          const from = routePath(route.path);
          const props = route.element.props as {
            replace?: unknown;
            to?: unknown;
          };
          if (!from || typeof props.to !== "string" || props.replace !== true) {
            throw ledgerError(
              C10_RECONCILIATION_CODES.implemented_deprecated_redirect_unverified,
              "a runtime Navigate redirect lacks an exact path, string target, or replace=true",
            );
          }
          redirects.push({
            surface_id: `route-redirect-${from.slice(1)}`,
            from,
            to: props.to,
          } as CanonicalRedirect);
        }
      }
      if (route.children) {
        visit(route.children);
      }
    }
  };
  visit(routes);
  return redirects;
}

/** Derive the exception from real APP_ROUTES objects, never route/test text. */
export function collectCanonicalDeprecatedRedirects(
  routes: readonly RouteObject[],
): CanonicalRedirect[] {
  const actual = collectNavigateRoutes(routes);
  if (
    actual.length !== REDIRECTS.length ||
    REDIRECTS.some(
      (expected, index) =>
        actual[index]?.surface_id !== expected.surface_id ||
        actual[index]?.from !== expected.from ||
        actual[index]?.to !== expected.to,
    )
  ) {
    throw ledgerError(
      C10_RECONCILIATION_CODES.implemented_deprecated_redirect_unverified,
      "runtime APP_ROUTES does not expose the exact five deprecated redirects",
    );
  }
  return [...REDIRECTS];
}

function failedRouteTestReceipt(
  reportSha256: string,
  processExitCode: number,
): RouteTestReceipt {
  return {
    receipt_schema:
      ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.route_test.receipt_schema,
    test_file: ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.route_test.test_file,
    report_sha256: reportSha256,
    process_exit_code: processExitCode,
    outcome: "fail",
    required_assertions:
      ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.route_test.assertions.map(
        (fullName): RouteTestReceipt["required_assertions"][number] => ({
          full_name: fullName,
          status: "missing",
        }),
      ),
    failure_code: C10_RECONCILIATION_CODES.redirect_test_receipt_invalid,
  };
}

/** Parse the launcher-owned Vitest JSON receipt and require all five identities. */
export function buildRouteTestReceipt(
  bytes: Uint8Array,
  processExitCode: number,
): RouteTestReceipt {
  const reportSha256 = createHash("sha256").update(bytes).digest("hex");
  if (!Number.isInteger(processExitCode) || processExitCode < 0) {
    return failedRouteTestReceipt(reportSha256, -1);
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return failedRouteTestReceipt(reportSha256, processExitCode);
  }
  if (typeof parsed !== "object" || parsed === null) {
    return failedRouteTestReceipt(reportSha256, processExitCode);
  }
  const report = parsed as { success?: unknown; testResults?: unknown };
  const testResults = Array.isArray(report.testResults) ? report.testResults : [];
  const matchingResults = testResults.filter((result) => {
    if (typeof result !== "object" || result === null) {
      return false;
    }
    const name = (result as { name?: unknown }).name;
    return (
      typeof name === "string" &&
      name.replaceAll("\\", "/").endsWith(
        `/${ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.route_test.test_file}`,
      )
    );
  });
  const testResult = matchingResults.length === 1 ? matchingResults[0] : undefined;
  const assertions =
    typeof testResult === "object" &&
    testResult !== null &&
    Array.isArray((testResult as { assertionResults?: unknown }).assertionResults)
      ? (testResult as { assertionResults: unknown[] }).assertionResults
      : [];
  const requiredAssertions =
    ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.route_test.assertions.map(
      (fullName) => {
        const matchingAssertions = assertions.filter(
          (assertion) =>
            typeof assertion === "object" &&
            assertion !== null &&
            (assertion as { fullName?: unknown }).fullName === fullName,
        );
        const status =
          matchingAssertions.length === 1 &&
          (matchingAssertions[0] as { status?: unknown }).status === "passed"
            ? "pass"
            : matchingAssertions.length === 0
              ? "missing"
              : "fail";
        return {
          full_name: fullName,
          status: status as RouteTestReceipt["required_assertions"][number]["status"],
        };
      },
    );
  const passed =
    processExitCode === 0 &&
    report.success === true &&
    typeof testResult === "object" &&
    testResult !== null &&
    (testResult as { status?: unknown }).status === "passed" &&
    requiredAssertions.every((assertion) => assertion.status === "pass");
  if (!passed) {
    return {
      receipt_schema:
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.route_test.receipt_schema,
      test_file: ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.route_test
        .test_file,
      report_sha256: reportSha256,
      process_exit_code: processExitCode,
      outcome: "fail",
      required_assertions: requiredAssertions,
      failure_code: C10_RECONCILIATION_CODES.redirect_test_receipt_invalid,
    };
  }
  return {
    receipt_schema:
      ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.route_test.receipt_schema,
    test_file: ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.route_test.test_file,
    report_sha256: reportSha256,
    process_exit_code: processExitCode,
    outcome: "pass",
    required_assertions: requiredAssertions,
  };
}

function implementationProvenance(): Record<string, unknown> {
  const files = ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.implementation_paths.map(
    (relativePath) => ({
      path: relativePath,
      sha256: createHash("sha256")
        .update(readFileSync(path.resolve(policyEngineRoot, relativePath)))
        .digest("hex"),
    }),
  );
  const aggregate = createHash("sha256");
  for (const file of files) {
    aggregate.update(`${file.path}\0${file.sha256}\n`);
  }
  return {
    implementation_sha256: aggregate.digest("hex"),
    files,
    repository_revision: execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: policyEngineRoot,
      encoding: "utf8",
    }).trim(),
    dirty:
      execFileSync("git", ["status", "--porcelain=v1"], {
        cwd: policyEngineRoot,
        encoding: "utf8",
      }).trim().length > 0,
  };
}

function canonicalSourceArtifacts(): Record<string, unknown> {
  const files =
    ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.source_artifact_paths.map(
      (relativePath) => ({
        path: relativePath,
        sha256: createHash("sha256")
          .update(readFileSync(path.resolve(policyEngineRoot, relativePath)))
          .digest("hex"),
      }),
    );
  const aggregate = createHash("sha256");
  for (const file of files) {
    aggregate.update(`${file.path}\0${file.sha256}\n`);
  }
  return { source_set_sha256: aggregate.digest("hex"), files };
}

function routeTestReportForInspection(bytes: Uint8Array): Record<string, unknown> {
  try {
    const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes));
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

function addFinding(findings: Finding[], code: string, detail: string): void {
  findings.push({ code, detail });
}

function expectedDeprecatedLedgerSet(
  entries: ReadinessEntry[],
  redirects: readonly CanonicalRedirect[],
  findings: Finding[],
): CanonicalRedirect[] {
  const deprecatedImplemented = entries.filter(
    (entry) =>
      entry.readiness_state === "implemented" && entry.maturity === "deprecated",
  );
  const identities = deprecatedImplemented.map((entry) => entry.surface_id);
  const exactLedgerSet =
    identities.length === redirects.length &&
    redirects.every((redirect) =>
      identities.some((identity) => identity === redirect.surface_id),
    );
  if (!exactLedgerSet) {
    addFinding(
      findings,
      C10_RECONCILIATION_CODES.implemented_deprecated_redirect_unverified,
      "deprecated implemented ledger identities do not equal the exact runtime redirect set",
    );
    return [];
  }
  return [...redirects];
}

/**
 * Recompute C10's full ledger denominator and narrow route exception. Stable
 * admission stays contract_only pending the contended typed evidence bridge.
 */
export function buildAtlasSurfaceReadinessReconciliation(
  input: AtlasSurfaceReadinessReconciliationInput,
): AtlasSurfaceReadinessReconciliation {
  const adoptionEntries = parseAdoptionEntries(input.adoption_ledger);
  const readinessEntries = parseReadinessEntries(input.readiness_ledger);
  const findings: Finding[] = [];
  const adoptionStable = adoptionEntries.filter(
    (entry) => entry.maturity === "stable",
  );
  const readinessStable = readinessEntries.filter(
    (entry) => entry.maturity === "stable",
  );
  const implemented = readinessEntries.filter(
    (entry) => entry.readiness_state === "implemented",
  );
  const nonDeprecatedImplemented = implemented.filter(
    (entry) => entry.maturity !== "deprecated",
  );

  for (const stable of adoptionStable) {
    addFinding(
      findings,
      C10_RECONCILIATION_CODES.stable_evidence_reference_unresolved,
      `stable adoption entry ${stable.id} has no typed subject-bound Core evidence`,
    );
  }
  for (const stable of readinessStable) {
    addFinding(
      findings,
      C10_RECONCILIATION_CODES.stable_evidence_reference_unresolved,
      `stable readiness entry ${stable.surface_id} has no typed subject-bound Core evidence`,
    );
  }
  for (const row of nonDeprecatedImplemented) {
    addFinding(
      findings,
      C10_RECONCILIATION_CODES.implemented_negative_test_missing,
      `implemented entry ${row.surface_id} lacks typed negative-test evidence`,
    );
    addFinding(
      findings,
      C10_RECONCILIATION_CODES.implemented_semantic_test_missing,
      `implemented entry ${row.surface_id} lacks typed semantic-test evidence`,
    );
  }

  let canonicalRedirects: CanonicalRedirect[] = [];
  try {
    canonicalRedirects = collectCanonicalDeprecatedRedirects(APP_ROUTES);
  } catch (error) {
    addFinding(
      findings,
      C10_RECONCILIATION_CODES.implemented_deprecated_redirect_unverified,
      error instanceof Error ? error.message : "runtime redirect verification failed",
    );
  }
  const verifiedDeprecatedRedirects = expectedDeprecatedLedgerSet(
    readinessEntries,
    canonicalRedirects,
    findings,
  );
  const parsedRouteTestReceipt = buildRouteTestReceipt(
    input.route_test_report_bytes,
    input.route_test_exit_code,
  );
  if (parsedRouteTestReceipt.outcome !== "pass") {
    addFinding(
      findings,
      C10_RECONCILIATION_CODES.redirect_test_receipt_invalid,
      "the launcher did not receive five exact passing runtime redirect assertions",
    );
  }

  const outcome = findings.length === 0 ? "pass" : "fail";
  const reconciliation = {
    adoption_entries: adoptionEntries.length,
    adoption_stable: adoptionStable.length,
    adoption_stable_ids: adoptionStable.map((entry) => entry.id),
    readiness_entries: readinessEntries.length,
    readiness_stable: readinessStable.length,
    readiness_stable_ids: readinessStable.map((entry) => entry.surface_id),
    readiness_implemented: implemented.length,
    implemented_surface_ids: implemented.map((entry) => entry.surface_id),
    nondeprecated_implemented_ids: nonDeprecatedImplemented.map(
      (entry) => entry.surface_id,
    ),
    verified_deprecated_redirects: verifiedDeprecatedRedirects,
  };
  const rawReport = routeTestReportForInspection(input.route_test_report_bytes);
  const rawReportBytes = input.route_test_report_bytes;
  const captureImplementation = implementationProvenance();
  const payload = atlasEvidencePayloadSchema.parse({
    payload_schema: ATLAS_EVIDENCE_RECONCILIATION_PAYLOAD_SCHEMA,
    evidence_kind: ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.evidence_kind,
    subject: ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.subject,
    rule: ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.rule,
    provenance: {
      producer: ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.producer,
      verifier: ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.verifier,
      repository_revision: String(captureImplementation.repository_revision),
      command_argv: ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.command_argv,
      predicate_provenance:
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.predicate_provenance,
    },
    times: {
      observed_at: input.observed_at,
      collected_at: input.observed_at,
      verified_at: input.verified_at,
    },
    result: { outcome, findings },
    details: {
      reconciliation,
      route_test_receipt: parsedRouteTestReceipt,
      route_test_report_sha256: parsedRouteTestReceipt.report_sha256,
      raw_report_sha256: createHash("sha256").update(rawReportBytes).digest("hex"),
      source_artifacts: canonicalSourceArtifacts(),
      capture_implementation: captureImplementation,
      field_provenance:
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.field_provenance,
    },
  });
  return {
    raw_report: rawReport,
    raw_report_bytes: rawReportBytes,
    payload,
    receipt_without_payload_ref: {
      receipt_schema: ATLAS_EVIDENCE_RECONCILIATION_RECEIPT_SCHEMA,
      authority: {
        authoritative_for: [
          ...ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.authority
            .authoritative_for,
        ],
        may_not_use_for: [
          ...ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.authority
            .may_not_use_for,
        ],
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
    },
    exit_code: outcome === "pass" ? 0 : 1,
  };
}
