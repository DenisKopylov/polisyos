import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

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

const PRODUCER_ID = "polisyos.atlas.surface_readiness_reconciler";
const PRODUCER_VERSION = "1.0.0";
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
    report_sha256: sha256.nullable(),
    assertion_name: nonEmptyString.nullable(),
    assertion_status: z.enum(["passed", "failed", "skipped"]).nullable(),
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
    const observationStatus = basis.observation.status;
    if (observationStatus === "observed" && assertionStatus !== "passed") {
      context.addIssue({
        code: "custom",
        path: ["canonical_check", "assertion_status"],
        message: "an observed claim requires its canonical assertion to pass",
      });
    }
    if (observationStatus === "not_observed" && assertionStatus !== "failed") {
      context.addIssue({
        code: "custom",
        path: ["canonical_check", "assertion_status"],
        message: "a negative observation requires a completed failed assertion",
      });
    }
    if (
      observationStatus === "observation_unavailable" &&
      assertionStatus === "failed"
    ) {
      context.addIssue({
        code: "custom",
        path: ["canonical_check", "assertion_status"],
        message: "a completed failed assertion is a negative observation",
      });
    }
  });

const citedFindingSchema = z
  .object({
    code: identity,
    message: nonEmptyString,
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
        verifier_id: identity,
        verifier_version: nonEmptyString,
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

export const atlasSurfaceReadinessClaimSchema = z.union([
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

function parseJson(value: Uint8Array): unknown {
  return JSON.parse(Buffer.from(value).toString("utf8")) as unknown;
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
      readiness: z.object({ entry_count: z.number().int().positive() }).loose(),
    })
    .loose()
    .parse(projection);
  return {
    entryCount: parsedProjection.readiness.entry_count,
    reportSha256: sha256Bytes(result.stdout ?? new Uint8Array()),
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
  unavailableReason: string | null;
  assertions: Map<string, RouteAssertionStatus[]>;
}

function runCanonicalRouteMatrix(dashboardRoot: string): RouteRun {
  let vitestEntry: string;
  try {
    vitestEntry = realpathSync(
      path.join(dashboardRoot, "node_modules/vitest/vitest.mjs"),
    );
  } catch {
    return {
      reportSha256: null,
      unavailableReason: "canonical_route_harness_failed",
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
    if (result.error !== undefined) {
      return {
        reportSha256: null,
        unavailableReason: "canonical_route_harness_failed",
        assertions: new Map(),
      };
    }
    if (result.status === null) {
      return {
        reportSha256: null,
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
      unavailableReason: null,
      assertions,
    };
  } finally {
    rmSync(reportDirectory, { recursive: true, force: true });
  }
}

interface ReadinessEntry {
  surface_id: string;
  title: string;
  readiness_state: string;
  maturity: string;
}

function routeAssertionName(entry: ReadinessEntry): string | null {
  if (!entry.surface_id.startsWith("route-redirect-")) {
    return null;
  }
  const titleMatch = /^(\/[a-z0-9/-]+) to (\/[a-z0-9/-]+)$/u.exec(entry.title);
  const legacyPath = `/${entry.surface_id.slice("route-redirect-".length)}`;
  if (titleMatch === null || titleMatch[1] !== legacyPath) {
    return null;
  }
  return `APP_ROUTES wraps app routes with the shell and follows legacy redirect from '${legacyPath}'`;
}

function observedBasisFor(
  policyEngineRoot: string,
  entry: ReadinessEntry,
  ownerValidation: ReturnType<typeof runOwnerValidation>,
  routeRun: RouteRun,
) {
  const assertionName = routeAssertionName(entry);
  const statuses =
    assertionName === null
      ? []
      : (routeRun.assertions.get(assertionName) ?? []);
  let status: "observed" | "not_observed" | "observation_unavailable";
  let reason: string | null;
  let assertionStatus: RouteAssertionStatus | null;

  if (assertionName === null) {
    status = "observation_unavailable";
    reason = "canonical_check_not_registered";
    assertionStatus = null;
  } else if (routeRun.unavailableReason !== null) {
    status = "observation_unavailable";
    reason = routeRun.unavailableReason;
    assertionStatus = null;
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
      report_sha256: routeRun.reportSha256,
      assertion_name: assertionName,
      assertion_status: assertionStatus,
      test_ref: sourceRef(
        policyEngineRoot,
        ROUTE_TEST,
        "canonical_behavior_check",
      ),
    },
    source_refs: [
      sourceRef(policyEngineRoot, READINESS_LEDGER, "complete_readiness_owner"),
      sourceRef(policyEngineRoot, READINESS_SCHEMA, "readiness_owner_schema"),
      sourceRef(policyEngineRoot, ROUTE_SOURCE, "runtime_route_owner"),
      sourceRef(policyEngineRoot, ROUTE_TEST, "canonical_behavior_check"),
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
      report_sha256: null,
      assertion_name: null,
      assertion_status: null,
      test_ref: sourceRef(
        policyEngineRoot,
        RECONCILER_SOURCE,
        "unavailable_stable_observer_declaration",
      ),
    },
    source_refs: [
      sourceRef(policyEngineRoot, READINESS_LEDGER, "complete_readiness_owner"),
      sourceRef(policyEngineRoot, READINESS_SCHEMA, "readiness_owner_schema"),
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
  routeRun: RouteRun,
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

/** Run the fixed canonical owners and return only separately based claim rows. */
export function reconcileAtlasSurfaceReadinessClaims(): AtlasSurfaceReadinessReport {
  const dashboardRoot = process.cwd();
  const policyEngineRoot = path.resolve(dashboardRoot, "../..");
  const ownerValidation = runOwnerValidation(policyEngineRoot);
  const readiness = z
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
    .parse(
      JSON.parse(
        readFileSync(path.join(policyEngineRoot, READINESS_LEDGER), "utf8"),
      ) as unknown,
    );
  if (readiness.entries.length !== ownerValidation.entryCount) {
    throw new AtlasSurfaceReadinessContractError(
      "canonical_owner_population_mismatch",
      "validated owner population changed before claim enumeration",
    );
  }

  const routeRun = runCanonicalRouteMatrix(dashboardRoot);
  const claims: AtlasSurfaceReadinessClaim[] = [];
  for (const entry of readiness.entries) {
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
    },
    claims,
  });
}

/** Parse one independently reportable claim and enforce its exact basis. */
export function parseAtlasSurfaceReadinessClaim(
  value: unknown,
): AtlasSurfaceReadinessClaim {
  const result = atlasSurfaceReadinessClaimSchema.safeParse(value);
  if (!result.success) {
    const namedMismatch = result.error.issues.find(
      (issue) =>
        issue.message === "cited_pass_with_findings" ||
        issue.message === "cited_nonpass_without_findings",
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

export type AtlasSurfaceReadinessCiCode =
  | "canonical_claim_not_observed"
  | "claim_observation_unavailable"
  | "cited_report_not_observation";

/** Apply the CI gate to one row. The caller alone may conjoin row failures. */
export function assertAtlasSurfaceReadinessClaimForCi(value: unknown): void {
  const claim = parseAtlasSurfaceReadinessClaim(value);
  if (claim.basis.kind === "consistent_with_cited_report") {
    throw new AtlasSurfaceReadinessContractError(
      "cited_report_not_observation",
      `${claim.claim_id} cites a consistent report but is not observed`,
    );
  }
  if (claim.basis.observation.status === "observation_unavailable") {
    throw new AtlasSurfaceReadinessContractError(
      "claim_observation_unavailable",
      `${claim.claim_id} could not be observed: ${claim.basis.observation.reason}`,
    );
  }
  if (claim.basis.observation.status === "not_observed") {
    throw new AtlasSurfaceReadinessContractError(
      "canonical_claim_not_observed",
      `${claim.claim_id} was canonically observed not to hold`,
    );
  }
}
