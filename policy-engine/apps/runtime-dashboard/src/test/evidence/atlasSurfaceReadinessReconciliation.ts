import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { isValidElement } from "react";
import { Navigate, type RouteObject } from "react-router-dom";
import { z } from "zod";

export const ATLAS_SURFACE_READINESS_REPORT_SCHEMA = {
  id: "polisyos.atlas.surface-readiness-claim-report",
  version: "1.0.0",
} as const;

export const ATLAS_SURFACE_READINESS_PROJECTION_SCHEMA = {
  id: "polisyos.atlas.surface-readiness-claim-projection",
  version: "1.0.0",
} as const;

export const ATLAS_SURFACE_READINESS_PERSISTENCE_OPERATION =
  "persist_atlas_surface_readiness_claims" as const;

export const ATLAS_CITED_SURFACE_READINESS_REPORT_SCHEMA = {
  id: "polisyos.atlas.cited-surface-readiness-report",
  version: "1.0.0",
} as const;

const PRODUCER_ID = "polisyos.atlas.surface_readiness_reconciler";
const PRODUCER_VERSION = "1.0.0";
const CITED_REPORT_VERIFIER_ID =
  "polisyos.atlas.cited_report_consistency_verifier";
const READINESS_LEDGER =
  "architecture/atlas_surfaces/live-application-readiness-ledger.json";
const READINESS_SCHEMA =
  "architecture/atlas_surfaces/surface-readiness-ledger.schema.json";
const ROUTE_SOURCE = "apps/runtime-dashboard/src/app/routes/routes.tsx";
const ROUTE_TEST = "apps/runtime-dashboard/src/app/routes/routes.test.tsx";
const SOURCE_VALIDATOR =
  "apps/runtime-dashboard/scripts/validate_atlas_health_sources.py";
const RECONCILER_SOURCE =
  "apps/runtime-dashboard/src/test/evidence/atlasSurfaceReadinessReconciliation.ts";
const RECONCILER_SCRIPT =
  "apps/runtime-dashboard/scripts/reconcile_atlas_surface_readiness.mjs";
const VITE_ENTRY =
  "apps/runtime-dashboard/node_modules/vite/dist/node/index.js";
const VITE_PACKAGE = "apps/runtime-dashboard/node_modules/vite/package.json";

const CHILD_ENV = {
  HOME: "/var/empty",
  LANG: "C",
  LC_ALL: "C",
  PATH: "/usr/bin:/bin",
  TZ: "UTC",
} as const;

const nonEmptyString = z
  .string()
  .min(1)
  .refine((value) => value.trim() === value, {
    message: "value must have no surrounding whitespace",
  });
const identity = nonEmptyString.regex(/^[a-z0-9][a-z0-9._:@/-]*$/u);
const sha256 = z.string().regex(/^[0-9a-f]{64}$/u);
const artifactId = z.string().regex(/^sha256:[0-9a-f]{64}$/u);

const sourceRefSchema = z
  .object({
    path: nonEmptyString,
    sha256,
    role: identity,
  })
  .strict();

const ownerValidationSchema = z
  .object({
    predicate_provenance: z.literal("recomputed"),
    report_sha256: sha256,
    validator_ref: sourceRefSchema,
  })
  .strict();

const runnerSchema = z
  .object({
    path: nonEmptyString,
    sha256,
    version: nonEmptyString,
  })
  .strict();

const runtimeRouteSchema = z
  .object({
    status: z.enum(["matched", "mismatched", "unavailable"]),
    reason: identity.nullable(),
    declared_from: nonEmptyString,
    declared_to: nonEmptyString,
    observed_to: nonEmptyString.nullable(),
    replace: z.boolean().nullable(),
  })
  .strict()
  .superRefine((fact, context) => {
    if (
      fact.status === "matched" &&
      (fact.reason !== null ||
        fact.observed_to !== fact.declared_to ||
        fact.replace !== true)
    ) {
      context.addIssue({
        code: "custom",
        path: ["status"],
        message:
          "matched runtime redirect must bind target and replace semantics",
      });
    }
    if (fact.status !== "matched" && fact.reason === null) {
      context.addIssue({
        code: "custom",
        path: ["reason"],
        message: "non-matching runtime redirect must carry a reason",
      });
    }
    if (
      fact.status === "unavailable" &&
      (fact.observed_to !== null || fact.replace !== null)
    ) {
      context.addIssue({
        code: "custom",
        path: ["status"],
        message: "unavailable runtime redirect cannot invent observed facts",
      });
    }
  });

const canonicalCheckSchema = z
  .object({
    check_id: identity,
    executable: z
      .object({
        path: nonEmptyString,
        sha256,
        version: nonEmptyString,
      })
      .strict(),
    runner: runnerSchema.nullable(),
    report_sha256: sha256.nullable(),
    assertion_name: nonEmptyString.nullable(),
    assertion_status: z.enum(["passed", "failed", "skipped"]).nullable(),
    runtime_route: runtimeRouteSchema.nullable(),
    test_ref: sourceRefSchema,
  })
  .strict();

const observedBasisSchema = z
  .object({
    kind: z.literal("observed_by_reconciler"),
    observation: z.discriminatedUnion("status", [
      z
        .object({
          status: z.literal("observed"),
          reason: z.null(),
        })
        .strict(),
      z
        .object({
          status: z.literal("not_observed"),
          reason: identity,
        })
        .strict(),
      z
        .object({
          status: z.literal("observation_unavailable"),
          reason: identity,
        })
        .strict(),
    ]),
    owner_validation: ownerValidationSchema,
    canonical_check: canonicalCheckSchema,
    source_refs: z.array(sourceRefSchema).min(1),
  })
  .strict()
  .superRefine((basis, context) => {
    const assertionStatus = basis.canonical_check.assertion_status;
    const reportSha256 = basis.canonical_check.report_sha256;
    const runner = basis.canonical_check.runner;
    const runtimeRoute = basis.canonical_check.runtime_route;
    const observationStatus = basis.observation.status;
    if (
      observationStatus === "observed" &&
      (assertionStatus !== "passed" || runtimeRoute?.status !== "matched")
    ) {
      context.addIssue({
        code: "custom",
        path: ["canonical_check", "assertion_status"],
        message: "observed_without_positive_canonical_facts",
      });
    }
    if (
      observationStatus === "not_observed" &&
      assertionStatus !== "failed" &&
      runtimeRoute?.status !== "mismatched"
    ) {
      context.addIssue({
        code: "custom",
        path: ["canonical_check", "assertion_status"],
        message: "negative_without_negative_canonical_fact",
      });
    }
    if (
      observationStatus === "observation_unavailable" &&
      (assertionStatus === "passed" || assertionStatus === "failed")
    ) {
      context.addIssue({
        code: "custom",
        path: ["canonical_check", "assertion_status"],
        message: "unavailable_with_completed_assertion",
      });
    }
    if (
      observationStatus !== "observation_unavailable" &&
      reportSha256 === null
    ) {
      context.addIssue({
        code: "custom",
        path: ["canonical_check", "report_sha256"],
        message: "completed_observation_without_report",
      });
    }
    if (observationStatus !== "observation_unavailable" && runner === null) {
      context.addIssue({
        code: "custom",
        path: ["canonical_check", "runner"],
        message: "completed_observation_without_runner",
      });
    }
  });

const citedFindingSchema = z
  .object({
    code: identity,
    message: nonEmptyString,
  })
  .strict();

const citedReportSchema = z
  .object({
    report_schema: z
      .object({
        id: z.literal(ATLAS_CITED_SURFACE_READINESS_REPORT_SCHEMA.id),
        version: z.literal(ATLAS_CITED_SURFACE_READINESS_REPORT_SCHEMA.version),
      })
      .strict(),
    producer: z
      .object({
        producer_id: identity,
        producer_version: nonEmptyString,
      })
      .strict(),
    execution_status: z.enum(["pass", "fail", "incomplete"]),
    findings: z.array(citedFindingSchema),
  })
  .strict();

const citedBasisSchema = z
  .object({
    kind: z.literal("consistent_with_cited_report"),
    artifact: z
      .object({
        artifact_id: artifactId,
        sha256,
        media_type: z.literal("application/json"),
        schema_id: identity,
        schema_version: nonEmptyString,
      })
      .strict(),
    producer: z
      .object({
        producer_id: identity,
        producer_version: nonEmptyString,
        predicate_provenance: z.literal("institutionally_supplied"),
      })
      .strict(),
    verifier: z
      .object({
        verifier_id: z.literal(CITED_REPORT_VERIFIER_ID),
        verifier_version: z.literal(PRODUCER_VERSION),
        predicate_provenance: z.literal("recomputed"),
      })
      .strict(),
    execution_status: z.enum(["pass", "fail", "incomplete"]),
    findings: z.array(citedFindingSchema),
  })
  .strict()
  .superRefine((basis, context) => {
    if (basis.artifact.artifact_id !== `sha256:${basis.artifact.sha256}`) {
      context.addIssue({
        code: "custom",
        path: ["artifact", "artifact_id"],
        message: "cited artifact identity must bind its digest",
      });
    }
    if (basis.producer.producer_id === basis.verifier.verifier_id) {
      context.addIssue({
        code: "custom",
        path: ["verifier", "verifier_id"],
        message: "cited report producer and verifier must be distinct",
      });
    }
    if (basis.execution_status === "pass" && basis.findings.length > 0) {
      context.addIssue({
        code: "custom",
        path: ["execution_status"],
        message: "cited_pass_with_findings",
      });
    }
    if (basis.execution_status !== "pass" && basis.findings.length === 0) {
      context.addIssue({
        code: "custom",
        path: ["execution_status"],
        message: "cited_nonpass_without_findings",
      });
    }
  });

const claimFields = {
  claim_id: identity,
  surface_id: identity,
  title: nonEmptyString,
  dimension: z.enum(["maturity", "readiness_state"]),
  declared_value: z.enum(["stable", "implemented"]),
};

const observedClaimSchema = z
  .object({
    ...claimFields,
    predicate_provenance: z.enum(["recomputed", "not_established"]),
    basis: observedBasisSchema,
  })
  .strict()
  .superRefine((claim, context) => {
    if (
      (claim.dimension === "maturity") !==
      (claim.declared_value === "stable")
    ) {
      context.addIssue({
        code: "custom",
        path: ["declared_value"],
        message: "gated dimension and declared value do not match",
      });
    }
    const expectedProvenance =
      claim.basis.observation.status === "observation_unavailable"
        ? "not_established"
        : "recomputed";
    if (claim.predicate_provenance !== expectedProvenance) {
      context.addIssue({
        code: "custom",
        path: ["predicate_provenance"],
        message:
          "claim predicate provenance does not match observation availability",
      });
    }
  });

const citedClaimSchema = z
  .object({
    ...claimFields,
    predicate_provenance: z.literal("institutionally_supplied"),
    basis: citedBasisSchema,
  })
  .strict()
  .superRefine((claim, context) => {
    if (
      (claim.dimension === "maturity") !==
      (claim.declared_value === "stable")
    ) {
      context.addIssue({
        code: "custom",
        path: ["declared_value"],
        message: "gated dimension and declared value do not match",
      });
    }
  });

const atlasSurfaceReadinessClaimSchema = z.union([
  observedClaimSchema,
  citedClaimSchema,
]);

const reportSchema = z
  .object({
    report_schema: z
      .object({
        id: z.literal(ATLAS_SURFACE_READINESS_REPORT_SCHEMA.id),
        version: z.literal(ATLAS_SURFACE_READINESS_REPORT_SCHEMA.version),
      })
      .strict(),
    producer: z
      .object({
        producer_id: z.literal(PRODUCER_ID),
        producer_version: z.literal(PRODUCER_VERSION),
        implementation_ref: sourceRefSchema,
        vite_loader: runnerSchema,
      })
      .strict(),
    claims: z.array(atlasSurfaceReadinessClaimSchema),
  })
  .strict();

export type AtlasSurfaceReadinessClaim = z.infer<
  typeof atlasSurfaceReadinessClaimSchema
>;
export type AtlasSurfaceReadinessReport = z.infer<typeof reportSchema>;

export class AtlasSurfaceReadinessContractError extends Error {
  constructor(
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "AtlasSurfaceReadinessContractError";
  }
}

function sha256Bytes(value: Uint8Array): string {
  return createHash("sha256").update(value).digest("hex");
}

function sourceRef(
  policyEngineRoot: string,
  relativePath: string,
  role: string,
) {
  return {
    path: relativePath,
    sha256: sha256Bytes(
      readFileSync(path.join(policyEngineRoot, relativePath)),
    ),
    role,
  };
}

function sourceRefFromBytes(
  relativePath: string,
  role: string,
  value: Uint8Array,
) {
  return {
    path: relativePath,
    sha256: sha256Bytes(value),
    role,
  };
}

function resolvedViteLoader(policyEngineRoot: string) {
  const entryPath = realpathSync(path.join(policyEngineRoot, VITE_ENTRY));
  const packageValue = z
    .object({ version: nonEmptyString })
    .loose()
    .parse(
      JSON.parse(
        readFileSync(path.join(policyEngineRoot, VITE_PACKAGE), "utf8"),
      ) as unknown,
    );
  return runnerSchema.parse({
    path: entryPath,
    sha256: sha256Bytes(readFileSync(entryPath)),
    version: packageValue.version,
  });
}

function parseJson(value: Uint8Array): unknown {
  return JSON.parse(Buffer.from(value).toString("utf8")) as unknown;
}

interface ReadinessEntry {
  surface_id: string;
  title: string;
  readiness_state: string;
  maturity: string;
}

interface ValidatedReadinessOwner {
  entries: ReadinessEntry[];
}

/** Bind the exact enumerated owner bytes to the full validator's source digest. */
export function assertValidatedReadinessOwnerBytes(
  ownerBytes: Uint8Array,
  validatedSha256: string,
  validatedEntryCount: number,
): ValidatedReadinessOwner {
  if (sha256Bytes(ownerBytes) !== sha256.parse(validatedSha256)) {
    throw new AtlasSurfaceReadinessContractError(
      "canonical_owner_bytes_changed",
      "readiness owner bytes changed after full-schema validation",
    );
  }
  const owner = z
    .object({
      entries: z.array(
        z
          .object({
            surface_id: identity,
            title: nonEmptyString,
            readiness_state: nonEmptyString,
            maturity: nonEmptyString,
          })
          .loose(),
      ),
    })
    .loose()
    .parse(parseJson(ownerBytes));
  if (owner.entries.length !== validatedEntryCount) {
    throw new AtlasSurfaceReadinessContractError(
      "canonical_owner_population_mismatch",
      "validated owner population changed before claim enumeration",
    );
  }
  return owner;
}

function runOwnerValidation(policyEngineRoot: string) {
  const pythonLocator = path.join(policyEngineRoot, ".venv/bin/python");
  const validatorPath = path.join(policyEngineRoot, SOURCE_VALIDATOR);
  const result = spawnSync(pythonLocator, ["-I", validatorPath], {
    cwd: policyEngineRoot,
    encoding: null,
    env: CHILD_ENV,
    input: undefined,
    maxBuffer: 10 * 1024 * 1024,
    timeout: 30_000,
  });
  if (result.error !== undefined || result.status !== 0) {
    const detail = Buffer.from(result.stderr ?? [])
      .toString("utf8")
      .trim();
    throw new AtlasSurfaceReadinessContractError(
      "canonical_owner_validation_unavailable",
      `fixed canonical owner validation could not complete: ${detail || String(result.error ?? result.status)}`,
    );
  }
  const projection = parseJson(result.stdout ?? new Uint8Array());
  const parsedProjection = z
    .object({
      readiness: z
        .object({
          entry_count: z.number().int().positive(),
          source_refs: z.array(sourceRefSchema).min(2),
        })
        .loose(),
    })
    .loose()
    .parse(projection);
  const readinessLedgerRef = parsedProjection.readiness.source_refs.find(
    (reference) => reference.path === READINESS_LEDGER,
  );
  const readinessSchemaRef = parsedProjection.readiness.source_refs.find(
    (reference) => reference.path === READINESS_SCHEMA,
  );
  if (readinessLedgerRef === undefined || readinessSchemaRef === undefined) {
    throw new AtlasSurfaceReadinessContractError(
      "canonical_owner_validation_unavailable",
      "full owner validator did not bind the readiness owner and schema",
    );
  }
  const owner = assertValidatedReadinessOwnerBytes(
    readFileSync(path.join(policyEngineRoot, READINESS_LEDGER)),
    readinessLedgerRef.sha256,
    parsedProjection.readiness.entry_count,
  );
  return {
    entryCount: parsedProjection.readiness.entry_count,
    ledgerRef: { ...readinessLedgerRef, role: "complete_readiness_owner" },
    owner,
    reportSha256: sha256Bytes(result.stdout ?? new Uint8Array()),
    schemaRef: { ...readinessSchemaRef, role: "readiness_owner_schema" },
    validatorRef: sourceRef(
      policyEngineRoot,
      SOURCE_VALIDATOR,
      "canonical_owner_validator",
    ),
  };
}

type RouteAssertionStatus = "passed" | "failed" | "skipped";

interface RouteRun {
  reportSha256: string | null;
  routeSourceRef: z.infer<typeof sourceRefSchema>;
  routeTestRef: z.infer<typeof sourceRefSchema>;
  runner: z.infer<typeof runnerSchema> | null;
  runtimeRoutes: RouteObject[] | null;
  unavailableReason: string | null;
  assertions: Map<string, RouteAssertionStatus[]>;
}

async function runCanonicalRouteMatrix(
  dashboardRoot: string,
): Promise<RouteRun> {
  const policyEngineRoot = path.resolve(dashboardRoot, "../..");
  const routeSourceBytes = readFileSync(
    path.join(policyEngineRoot, ROUTE_SOURCE),
  );
  const routeTestBytes = readFileSync(path.join(policyEngineRoot, ROUTE_TEST));
  const routeSourceRef = sourceRefFromBytes(
    ROUTE_SOURCE,
    "runtime_route_owner",
    routeSourceBytes,
  );
  const routeTestRef = sourceRefFromBytes(
    ROUTE_TEST,
    "canonical_behavior_check",
    routeTestBytes,
  );
  let vitestEntry: string;
  let runner: z.infer<typeof runnerSchema> | null = null;
  try {
    vitestEntry = realpathSync(
      path.join(dashboardRoot, "node_modules/vitest/vitest.mjs"),
    );
    const packageValue = z
      .object({ version: nonEmptyString })
      .loose()
      .parse(
        JSON.parse(
          readFileSync(
            path.join(path.dirname(vitestEntry), "package.json"),
            "utf8",
          ),
        ) as unknown,
      );
    runner = {
      path: vitestEntry,
      sha256: sha256Bytes(readFileSync(vitestEntry)),
      version: packageValue.version,
    };
  } catch {
    return {
      reportSha256: null,
      routeSourceRef,
      routeTestRef,
      runner: null,
      runtimeRoutes: null,
      unavailableReason: "canonical_route_harness_failed",
      assertions: new Map(),
    };
  }
  let runtimeRoutes: RouteObject[];
  try {
    const runtimeModule = await import("@/app/routes/routes");
    if (!Array.isArray(runtimeModule.APP_ROUTES)) {
      throw new TypeError("APP_ROUTES is not an array");
    }
    runtimeRoutes = runtimeModule.APP_ROUTES;
  } catch {
    return {
      reportSha256: null,
      routeSourceRef,
      routeTestRef,
      runner,
      runtimeRoutes: null,
      unavailableReason: "canonical_runtime_route_import_failed",
      assertions: new Map(),
    };
  }
  const reportDirectory = mkdtempSync(
    path.join(tmpdir(), "atlas-readiness-route-report-"),
  );
  const reportPath = path.join(reportDirectory, "route-matrix.json");
  try {
    const result = spawnSync(
      process.execPath,
      [
        vitestEntry,
        "run",
        "src/app/routes/routes.test.tsx",
        "--reporter=json",
        `--outputFile=${reportPath}`,
        "--maxWorkers=1",
      ],
      {
        cwd: dashboardRoot,
        encoding: null,
        env: CHILD_ENV,
        input: undefined,
        maxBuffer: 10 * 1024 * 1024,
        timeout: 45_000,
      },
    );
    let runnerUnchanged = false;
    try {
      const currentEntry = realpathSync(
        path.join(dashboardRoot, "node_modules/vitest/vitest.mjs"),
      );
      const currentPackage = z
        .object({ version: nonEmptyString })
        .loose()
        .parse(
          JSON.parse(
            readFileSync(
              path.join(path.dirname(currentEntry), "package.json"),
              "utf8",
            ),
          ) as unknown,
        );
      runnerUnchanged =
        currentEntry === runner.path &&
        sha256Bytes(readFileSync(currentEntry)) === runner.sha256 &&
        currentPackage.version === runner.version;
    } catch {
      runnerUnchanged = false;
    }
    if (!runnerUnchanged) {
      return {
        reportSha256: null,
        routeSourceRef,
        routeTestRef,
        runner,
        runtimeRoutes,
        unavailableReason: "canonical_route_runner_changed",
        assertions: new Map(),
      };
    }
    const sourcesUnchanged =
      sha256Bytes(readFileSync(path.join(policyEngineRoot, ROUTE_SOURCE))) ===
        routeSourceRef.sha256 &&
      sha256Bytes(readFileSync(path.join(policyEngineRoot, ROUTE_TEST))) ===
        routeTestRef.sha256;
    if (!sourcesUnchanged) {
      return {
        reportSha256: null,
        routeSourceRef,
        routeTestRef,
        runner,
        runtimeRoutes,
        unavailableReason: "canonical_route_sources_changed",
        assertions: new Map(),
      };
    }
    if (result.error !== undefined) {
      return {
        reportSha256: null,
        routeSourceRef,
        routeTestRef,
        runner,
        runtimeRoutes,
        unavailableReason: "canonical_route_harness_failed",
        assertions: new Map(),
      };
    }
    if (result.status === null) {
      return {
        reportSha256: null,
        routeSourceRef,
        routeTestRef,
        runner,
        runtimeRoutes,
        unavailableReason: "canonical_route_harness_failed",
        assertions: new Map(),
      };
    }

    let reportBytes: Buffer;
    try {
      reportBytes = readFileSync(reportPath);
    } catch {
      return {
        reportSha256: null,
        routeSourceRef,
        routeTestRef,
        runner,
        runtimeRoutes,
        unavailableReason: "canonical_route_report_missing",
        assertions: new Map(),
      };
    }

    let report: unknown;
    try {
      report = parseJson(reportBytes);
    } catch {
      return {
        reportSha256: sha256Bytes(reportBytes),
        routeSourceRef,
        routeTestRef,
        runner,
        runtimeRoutes,
        unavailableReason: "canonical_route_report_invalid",
        assertions: new Map(),
      };
    }
    const reportResult = z
      .object({
        testResults: z.array(
          z
            .object({
              name: nonEmptyString,
              assertionResults: z.array(
                z
                  .object({
                    fullName: nonEmptyString,
                    status: z.enum(["passed", "failed", "skipped", "pending"]),
                  })
                  .loose(),
              ),
            })
            .loose(),
        ),
      })
      .loose()
      .safeParse(report);
    if (!reportResult.success) {
      return {
        reportSha256: sha256Bytes(reportBytes),
        routeSourceRef,
        routeTestRef,
        runner,
        runtimeRoutes,
        unavailableReason: "canonical_route_report_invalid",
        assertions: new Map(),
      };
    }

    const routeTestPath = path.join(
      dashboardRoot,
      "src/app/routes/routes.test.tsx",
    );
    const assertions = new Map<string, RouteAssertionStatus[]>();
    for (const testResult of reportResult.data.testResults) {
      if (path.resolve(testResult.name) !== routeTestPath) {
        continue;
      }
      for (const assertion of testResult.assertionResults) {
        const status =
          assertion.status === "pending" ? "skipped" : assertion.status;
        const existing = assertions.get(assertion.fullName) ?? [];
        existing.push(status);
        assertions.set(assertion.fullName, existing);
      }
    }
    return {
      reportSha256: sha256Bytes(reportBytes),
      routeSourceRef,
      routeTestRef,
      runner,
      runtimeRoutes,
      unavailableReason: null,
      assertions,
    };
  } finally {
    rmSync(reportDirectory, { recursive: true, force: true });
  }
}

function routeDeclaration(
  entry: Pick<ReadinessEntry, "surface_id" | "title">,
): { from: string; to: string } | null {
  if (!entry.surface_id.startsWith("route-redirect-")) {
    return null;
  }
  const titleMatch = /^(\/[a-z0-9/-]+) to (\/[a-z0-9/-]+)$/u.exec(entry.title);
  const legacyPath = `/${entry.surface_id.slice("route-redirect-".length)}`;
  if (titleMatch === null || titleMatch[1] !== legacyPath) {
    return null;
  }
  return { from: titleMatch[1], to: titleMatch[2] };
}

function routeAssertionName(entry: ReadinessEntry): string | null {
  const declaration = routeDeclaration(entry);
  if (declaration === null) {
    return null;
  }
  return `APP_ROUTES wraps app routes with the shell and follows legacy redirect from '${declaration.from}'`;
}

/** Inspect both endpoints against the imported runtime route objects. */
export function inspectAtlasRuntimeRedirect(
  entry: Pick<ReadinessEntry, "surface_id" | "title">,
  runtimeRoutes: RouteObject[] | null,
): z.infer<typeof runtimeRouteSchema> | null {
  const declaration = routeDeclaration(entry);
  if (declaration === null) {
    return null;
  }
  if (runtimeRoutes === null) {
    return runtimeRouteSchema.parse({
      status: "unavailable",
      reason: "canonical_runtime_route_import_failed",
      declared_from: declaration.from,
      declared_to: declaration.to,
      observed_to: null,
      replace: null,
    });
  }
  const rootRoutes = runtimeRoutes.filter((route) => route.path === "/");
  const matchingRoutes =
    rootRoutes.length === 1
      ? (rootRoutes[0]?.children?.filter(
          (route) => route.path === declaration.from.slice(1),
        ) ?? [])
      : [];
  if (matchingRoutes.length !== 1) {
    return runtimeRouteSchema.parse({
      status: "unavailable",
      reason:
        matchingRoutes.length === 0
          ? "canonical_runtime_route_missing"
          : "canonical_runtime_route_ambiguous",
      declared_from: declaration.from,
      declared_to: declaration.to,
      observed_to: null,
      replace: null,
    });
  }
  const element = matchingRoutes[0]?.element;
  if (!isValidElement(element)) {
    return runtimeRouteSchema.parse({
      status: "mismatched",
      reason: "canonical_runtime_route_not_navigate",
      declared_from: declaration.from,
      declared_to: declaration.to,
      observed_to: null,
      replace: null,
    });
  }
  const props = element.props as { replace?: unknown; to?: unknown };
  const observedTo = typeof props.to === "string" ? props.to : null;
  const replace = typeof props.replace === "boolean" ? props.replace : null;
  const matched =
    element.type === Navigate &&
    observedTo === declaration.to &&
    replace === true;
  return runtimeRouteSchema.parse({
    status: matched ? "matched" : "mismatched",
    reason: matched ? null : "canonical_runtime_route_target_mismatch",
    declared_from: declaration.from,
    declared_to: declaration.to,
    observed_to: observedTo,
    replace,
  });
}

function observedBasisFor(
  policyEngineRoot: string,
  entry: ReadinessEntry,
  ownerValidation: ReturnType<typeof runOwnerValidation>,
  routeRun: RouteRun,
) {
  const assertionName = routeAssertionName(entry);
  const runtimeRoute = inspectAtlasRuntimeRedirect(
    entry,
    routeRun.runtimeRoutes,
  );
  const statuses =
    assertionName === null
      ? []
      : (routeRun.assertions.get(assertionName) ?? []);
  let status: "observed" | "not_observed" | "observation_unavailable";
  let reason: string | null;
  let assertionStatus: RouteAssertionStatus | null;

  if (assertionName === null || runtimeRoute === null) {
    status = "observation_unavailable";
    reason = "canonical_check_not_registered";
    assertionStatus = null;
  } else if (routeRun.unavailableReason !== null) {
    status = "observation_unavailable";
    reason = routeRun.unavailableReason;
    assertionStatus = null;
  } else if (runtimeRoute.status === "unavailable") {
    status = "observation_unavailable";
    reason = runtimeRoute.reason;
    assertionStatus = null;
  } else if (runtimeRoute.status === "mismatched") {
    status = "not_observed";
    reason = runtimeRoute.reason;
    assertionStatus = statuses.length === 1 ? statuses[0] : null;
  } else if (statuses.length !== 1) {
    status = "observation_unavailable";
    reason =
      statuses.length === 0
        ? "canonical_assertion_missing"
        : "canonical_assertion_ambiguous";
    assertionStatus = null;
  } else if (statuses[0] === "passed") {
    status = "observed";
    reason = null;
    assertionStatus = "passed";
  } else if (statuses[0] === "failed") {
    status = "not_observed";
    reason = "canonical_assertion_failed";
    assertionStatus = "failed";
  } else {
    status = "observation_unavailable";
    reason = "canonical_assertion_skipped";
    assertionStatus = "skipped";
  }

  return observedBasisSchema.parse({
    kind: "observed_by_reconciler",
    observation: { status, reason },
    owner_validation: {
      predicate_provenance: "recomputed",
      report_sha256: ownerValidation.reportSha256,
      validator_ref: ownerValidation.validatorRef,
    },
    canonical_check: {
      check_id: "runtime-dashboard.route-redirect.behavior",
      executable: {
        path: realpathSync(process.execPath),
        sha256: sha256Bytes(readFileSync(realpathSync(process.execPath))),
        version: process.version,
      },
      runner: routeRun.runner,
      report_sha256: routeRun.reportSha256,
      assertion_name: assertionName,
      assertion_status: assertionStatus,
      runtime_route: runtimeRoute,
      test_ref: routeRun.routeTestRef,
    },
    source_refs: [
      ownerValidation.ledgerRef,
      ownerValidation.schemaRef,
      routeRun.routeSourceRef,
      routeRun.routeTestRef,
      sourceRef(policyEngineRoot, RECONCILER_SOURCE, "closed_claim_reconciler"),
      sourceRef(
        policyEngineRoot,
        RECONCILER_SCRIPT,
        "closed_reconciler_launcher",
      ),
    ],
  });
}

function unavailableStableBasis(
  policyEngineRoot: string,
  ownerValidation: ReturnType<typeof runOwnerValidation>,
) {
  const executable = realpathSync(process.execPath);
  return observedBasisSchema.parse({
    kind: "observed_by_reconciler",
    observation: {
      status: "observation_unavailable",
      reason: "canonical_stable_observer_not_registered",
    },
    owner_validation: {
      predicate_provenance: "recomputed",
      report_sha256: ownerValidation.reportSha256,
      validator_ref: ownerValidation.validatorRef,
    },
    canonical_check: {
      check_id: "surface-readiness.stable.maturity-prerequisite",
      executable: {
        path: executable,
        sha256: sha256Bytes(readFileSync(executable)),
        version: process.version,
      },
      runner: null,
      report_sha256: null,
      assertion_name: null,
      assertion_status: null,
      runtime_route: null,
      test_ref: sourceRef(
        policyEngineRoot,
        RECONCILER_SOURCE,
        "unavailable_stable_observer_declaration",
      ),
    },
    source_refs: [
      ownerValidation.ledgerRef,
      ownerValidation.schemaRef,
      sourceRef(
        policyEngineRoot,
        RECONCILER_SOURCE,
        "unavailable_stable_observer_declaration",
      ),
      sourceRef(
        policyEngineRoot,
        RECONCILER_SCRIPT,
        "closed_reconciler_launcher",
      ),
    ],
  });
}

function claimFor(
  policyEngineRoot: string,
  entry: ReadinessEntry,
  dimension: "maturity" | "readiness_state",
  ownerValidation: ReturnType<typeof runOwnerValidation>,
  routeRun: RouteRun | null,
): AtlasSurfaceReadinessClaim {
  if (dimension === "maturity") {
    const basis = unavailableStableBasis(policyEngineRoot, ownerValidation);
    return observedClaimSchema.parse({
      claim_id: `${entry.surface_id}:maturity:stable`,
      surface_id: entry.surface_id,
      title: entry.title,
      dimension,
      declared_value: "stable",
      predicate_provenance: "not_established",
      basis,
    });
  }

  if (routeRun === null) {
    throw new AtlasSurfaceReadinessContractError(
      "canonical_route_run_missing",
      "implemented claim construction requires the closed route run",
    );
  }
  const basis = observedBasisFor(
    policyEngineRoot,
    entry,
    ownerValidation,
    routeRun,
  );
  return observedClaimSchema.parse({
    claim_id: `${entry.surface_id}:readiness_state:implemented`,
    surface_id: entry.surface_id,
    title: entry.title,
    dimension,
    declared_value: "implemented",
    predicate_provenance:
      basis.observation.status === "observation_unavailable"
        ? "not_established"
        : "recomputed",
    basis,
  });
}

/** Exercise the real stable producer arm without adding a claim to the owner. */
export function buildAtlasStableReadinessNegativeControl(): AtlasSurfaceReadinessClaim {
  const dashboardRoot = process.cwd();
  const policyEngineRoot = path.resolve(dashboardRoot, "../..");
  const ownerValidation = runOwnerValidation(policyEngineRoot);
  return claimFor(
    policyEngineRoot,
    {
      surface_id: "synthetic-stable-negative-control",
      title: "Synthetic stable negative control",
      readiness_state: "not_implemented",
      maturity: "stable",
    },
    "maturity",
    ownerValidation,
    null,
  );
}

/** Run the fixed canonical owners and return only separately based claim rows. */
export async function reconcileAtlasSurfaceReadinessClaims(): Promise<AtlasSurfaceReadinessReport> {
  const dashboardRoot = process.cwd();
  const policyEngineRoot = path.resolve(dashboardRoot, "../..");
  const ownerValidation = runOwnerValidation(policyEngineRoot);
  const routeRun = await runCanonicalRouteMatrix(dashboardRoot);
  const claims: AtlasSurfaceReadinessClaim[] = [];
  for (const entry of ownerValidation.owner.entries) {
    if (entry.maturity === "stable") {
      claims.push(
        claimFor(
          policyEngineRoot,
          entry,
          "maturity",
          ownerValidation,
          routeRun,
        ),
      );
    }
    if (entry.readiness_state === "implemented") {
      claims.push(
        claimFor(
          policyEngineRoot,
          entry,
          "readiness_state",
          ownerValidation,
          routeRun,
        ),
      );
    }
  }

  return reportSchema.parse({
    report_schema: ATLAS_SURFACE_READINESS_REPORT_SCHEMA,
    producer: {
      producer_id: PRODUCER_ID,
      producer_version: PRODUCER_VERSION,
      implementation_ref: sourceRef(
        policyEngineRoot,
        RECONCILER_SOURCE,
        "closed_claim_reconciler",
      ),
      vite_loader: resolvedViteLoader(policyEngineRoot),
    },
    claims,
  });
}

/** Resolve actual cited bytes into a reportable, never-observation basis. */
export function buildConsistentWithCitedReportClaim(
  claimValue: unknown,
  citedReportBytes: Uint8Array,
): AtlasSurfaceReadinessClaim {
  const claim = parseClaimShape(claimValue);
  const report = citedReportSchema.parse(parseJson(citedReportBytes));
  if (report.execution_status === "pass" && report.findings.length > 0) {
    throw new AtlasSurfaceReadinessContractError(
      "cited_pass_with_findings",
      "cited_pass_with_findings",
    );
  }
  if (report.execution_status !== "pass" && report.findings.length === 0) {
    throw new AtlasSurfaceReadinessContractError(
      "cited_nonpass_without_findings",
      "cited_nonpass_without_findings",
    );
  }
  const digest = sha256Bytes(citedReportBytes);
  return parseAtlasSurfaceReadinessClaim(
    {
      claim_id: claim.claim_id,
      surface_id: claim.surface_id,
      title: claim.title,
      dimension: claim.dimension,
      declared_value: claim.declared_value,
      predicate_provenance: "institutionally_supplied",
      basis: {
        kind: "consistent_with_cited_report",
        artifact: {
          artifact_id: `sha256:${digest}`,
          sha256: digest,
          media_type: "application/json",
          schema_id: report.report_schema.id,
          schema_version: report.report_schema.version,
        },
        producer: {
          ...report.producer,
          predicate_provenance: "institutionally_supplied",
        },
        verifier: {
          verifier_id: CITED_REPORT_VERIFIER_ID,
          verifier_version: PRODUCER_VERSION,
          predicate_provenance: "recomputed",
        },
        execution_status: report.execution_status,
        findings: report.findings,
      },
    },
    citedReportBytes,
  );
}

function parseClaimShape(value: unknown): AtlasSurfaceReadinessClaim {
  const result = atlasSurfaceReadinessClaimSchema.safeParse(value);
  if (!result.success) {
    const namedCodes = new Set([
      "cited_pass_with_findings",
      "cited_nonpass_without_findings",
      "unavailable_with_completed_assertion",
      "completed_observation_without_report",
      "completed_observation_without_runner",
      "observed_without_positive_canonical_facts",
      "negative_without_negative_canonical_fact",
    ]);
    const namedMismatch = result.error.issues.find((issue) =>
      namedCodes.has(issue.message),
    );
    if (namedMismatch !== undefined) {
      throw new AtlasSurfaceReadinessContractError(
        namedMismatch.message,
        namedMismatch.message,
      );
    }
    throw result.error;
  }
  return result.data;
}

/** Parse one reportable claim, resolving actual cited bytes when that basis is used. */
export function parseAtlasSurfaceReadinessClaim(
  value: unknown,
  citedReportBytes?: Uint8Array,
): AtlasSurfaceReadinessClaim {
  const claim = parseClaimShape(value);
  if (claim.basis.kind !== "consistent_with_cited_report") {
    return claim;
  }
  if (citedReportBytes === undefined) {
    throw new AtlasSurfaceReadinessContractError(
      "cited_report_bytes_required",
      "a cited basis is not reportable until its exact artifact bytes are resolved",
    );
  }
  const report = citedReportSchema.parse(parseJson(citedReportBytes));
  if (report.execution_status === "pass" && report.findings.length > 0) {
    throw new AtlasSurfaceReadinessContractError(
      "cited_pass_with_findings",
      "cited_pass_with_findings",
    );
  }
  if (report.execution_status !== "pass" && report.findings.length === 0) {
    throw new AtlasSurfaceReadinessContractError(
      "cited_nonpass_without_findings",
      "cited_nonpass_without_findings",
    );
  }
  const digest = sha256Bytes(citedReportBytes);
  const expectedBasis = citedBasisSchema.parse({
    kind: "consistent_with_cited_report",
    artifact: {
      artifact_id: `sha256:${digest}`,
      sha256: digest,
      media_type: "application/json",
      schema_id: report.report_schema.id,
      schema_version: report.report_schema.version,
    },
    producer: {
      ...report.producer,
      predicate_provenance: "institutionally_supplied",
    },
    verifier: {
      verifier_id: CITED_REPORT_VERIFIER_ID,
      verifier_version: PRODUCER_VERSION,
      predicate_provenance: "recomputed",
    },
    execution_status: report.execution_status,
    findings: report.findings,
  });
  if (JSON.stringify(claim.basis) !== JSON.stringify(expectedBasis)) {
    throw new AtlasSurfaceReadinessContractError(
      "cited_report_content_mismatch",
      "cited basis does not resolve to the supplied artifact bytes",
    );
  }
  return claim;
}
