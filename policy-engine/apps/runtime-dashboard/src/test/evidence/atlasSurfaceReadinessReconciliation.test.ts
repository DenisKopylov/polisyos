import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import {
  assertAtlasSurfaceReadinessClaimForCi,
  AtlasSurfaceReadinessContractError,
  type AtlasSurfaceReadinessClaim,
  parseAtlasSurfaceReadinessClaim,
} from "./atlasSurfaceReadinessReconciliation";

const OPERATION = "persist_atlas_surface_readiness_claims";

interface PersistenceResult {
  status: number | null;
  stderr: string;
  value: Record<string, unknown>;
}

interface ProjectionResult {
  operation: string;
  claim_report_ref: { artifact_id: string };
  projection_ref: { artifact_id: string };
  claim_report_manifest_input: null;
  projection_manifest_input: { artifact_id: string; role: string };
  resolved_claim_report: {
    artifact_id: string;
    report: { claims: AtlasSurfaceReadinessClaim[] };
  };
  resolved_projection: {
    artifact_id: string;
    projection: {
      claim_report_ref: { artifact_id: string };
      claim_report_sha256: string;
      claims: AtlasSurfaceReadinessClaim[];
    };
  };
}

function invokePersistence(
  request: object,
  casRoot: string,
  extraEnv: NodeJS.ProcessEnv = {},
): PersistenceResult {
  const dashboardRoot = process.cwd();
  const policyEngineRoot = path.resolve(dashboardRoot, "../..");
  const result = spawnSync(
    path.join(policyEngineRoot, ".venv/bin/python"),
    [path.join(dashboardRoot, "scripts/persist_atlas_evidence.py")],
    {
      cwd: policyEngineRoot,
      encoding: "utf8",
      input: JSON.stringify(request),
      env: {
        ...process.env,
        ...extraEnv,
        POLISYOS_CAS_BACKEND: "filesystem",
        POLISYOS_CAS_ROOT: casRoot,
      },
      timeout: 60_000,
    },
  );
  return {
    status: result.status,
    stderr: result.stderr,
    value: JSON.parse(result.stdout) as Record<string, unknown>,
  };
}

function asProjectionResult(result: PersistenceResult): ProjectionResult {
  expect(result).toMatchObject({ status: 0, stderr: "" });
  return result.value as unknown as ProjectionResult;
}

function observedClaim(result: ProjectionResult): AtlasSurfaceReadinessClaim {
  const claim = result.resolved_projection.projection.claims[0];
  expect(claim?.basis.kind).toBe("observed_by_reconciler");
  if (claim === undefined) {
    throw new Error("current projection has no claim control row");
  }
  return claim;
}

function citedClaimFrom(
  claim: AtlasSurfaceReadinessClaim,
  executionStatus: "pass" | "fail" | "incomplete",
  findings: Array<{ code: string; message: string }>,
): unknown {
  const digest = "a".repeat(64);
  return {
    ...claim,
    predicate_provenance: "institutionally_supplied",
    basis: {
      kind: "consistent_with_cited_report",
      artifact: {
        artifact_id: `sha256:${digest}`,
        sha256: digest,
        media_type: "application/json",
        schema_id: "polisyos.test.cited-readiness",
        schema_version: "1.0.0",
      },
      producer: {
        producer_id: "institution.route-test-producer",
        producer_version: "1.0.0",
        predicate_provenance: "institutionally_supplied",
      },
      verifier: {
        verifier_id: "polisyos.cited-report-verifier",
        verifier_version: "1.0.0",
        predicate_provenance: "recomputed",
      },
      execution_status: executionStatus,
      findings,
    },
  };
}

function observedVariant(
  claim: AtlasSurfaceReadinessClaim,
  status: "not_observed" | "observation_unavailable",
): unknown {
  if (claim.basis.kind !== "observed_by_reconciler") {
    throw new Error("control claim must have an observed basis");
  }
  const unavailable = status === "observation_unavailable";
  return {
    ...claim,
    predicate_provenance: unavailable ? "not_established" : "recomputed",
    basis: {
      ...claim.basis,
      observation: {
        status,
        reason: unavailable
          ? "canonical_route_harness_failed"
          : "canonical_assertion_failed",
      },
      canonical_check: {
        ...claim.basis.canonical_check,
        report_sha256: unavailable
          ? null
          : claim.basis.canonical_check.report_sha256,
        assertion_status: unavailable ? null : "failed",
      },
    },
  };
}

function gateCode(value: unknown): string | null {
  try {
    assertAtlasSurfaceReadinessClaimForCi(value);
    return null;
  } catch (error) {
    expect(error).toBeInstanceOf(AtlasSurfaceReadinessContractError);
    return (error as AtlasSurfaceReadinessContractError).code;
  }
}

function keysNamedLikeAggregate(value: unknown, location = "root"): string[] {
  if (Array.isArray(value)) {
    return value.flatMap((item, index) =>
      keysNamedLikeAggregate(item, `${location}[${index}]`),
    );
  }
  if (value === null || typeof value !== "object") {
    return [];
  }
  const forbidden =
    /^(?:ok|success|outcome|result|aggregate.*|reconciliation.*)$/u;
  return Object.entries(value).flatMap(([key, item]) => [
    ...(forbidden.test(key) ? [`${location}.${key}`] : []),
    ...keysNamedLikeAggregate(item, `${location}.${key}`),
  ]);
}

describe("Atlas surface-readiness per-claim reconciliation", () => {
  const casRoot = mkdtempSync(path.join(tmpdir(), "atlas-readiness-cas-"));
  let persisted: ProjectionResult;

  beforeAll(() => {
    persisted = asProjectionResult(
      invokePersistence({ operation: OPERATION }, casRoot),
    );
  });

  afterAll(() => {
    rmSync(casRoot, { recursive: true, force: true });
  });

  it("persists one observed basis for each current implemented claim", () => {
    expect(persisted.operation).toBe(OPERATION);
    const projection = persisted.resolved_projection.projection;
    expect(projection.claims.map(({ claim_id }) => claim_id)).toEqual([
      "route-redirect-launch:readiness_state:implemented",
      "route-redirect-sources:readiness_state:implemented",
      "route-redirect-data:readiness_state:implemented",
      "route-redirect-lex:readiness_state:implemented",
      "route-redirect-health:readiness_state:implemented",
    ]);
    for (const claim of projection.claims) {
      expect(claim).toMatchObject({
        dimension: "readiness_state",
        declared_value: "implemented",
        predicate_provenance: "recomputed",
        basis: {
          kind: "observed_by_reconciler",
          observation: { status: "observed", reason: null },
        },
      });
    }
  });

  it("binds the claim report into the governed Core CAS audit projection", () => {
    expect(persisted.claim_report_manifest_input).toBeNull();
    expect(persisted.projection_manifest_input).toEqual({
      artifact_id: persisted.claim_report_ref.artifact_id,
      role: "claim_report",
    });
    expect(
      persisted.resolved_projection.projection.claim_report_ref.artifact_id,
    ).toBe(persisted.claim_report_ref.artifact_id);
    expect(persisted.resolved_claim_report.artifact_id).toBe(
      persisted.claim_report_ref.artifact_id,
    );
    expect(persisted.resolved_projection.artifact_id).toBe(
      persisted.projection_ref.artifact_id,
    );
    expect(persisted.resolved_claim_report.report.claims).toEqual(
      persisted.resolved_projection.projection.claims,
    );
  });

  it("uses Vitest discovery as the only conjunction and accepts every live row", () => {
    for (const claim of persisted.resolved_projection.projection.claims) {
      expect(() => assertAtlasSurfaceReadinessClaimForCi(claim)).not.toThrow();
    }
  });

  it("keeps every artifact byte when the CI exit-code calculation is deleted", () => {
    const artifactsWithoutGate = JSON.stringify({
      report: persisted.resolved_claim_report.report,
      projection: persisted.resolved_projection.projection,
    });

    for (const claim of persisted.resolved_projection.projection.claims) {
      assertAtlasSurfaceReadinessClaimForCi(claim);
    }

    const artifactsWithGate = JSON.stringify({
      report: persisted.resolved_claim_report.report,
      projection: persisted.resolved_projection.projection,
    });
    expect(artifactsWithGate).toBe(artifactsWithoutGate);
  });

  it("surfaces no aggregate reconciliation field in report or projection", () => {
    expect(
      keysNamedLikeAggregate({
        report: persisted.resolved_claim_report.report,
        projection: persisted.resolved_projection.projection,
      }),
    ).toEqual([]);
  });

  it("keeps a legitimate cited report reportable but ineligible as observation", () => {
    const cited = parseAtlasSurfaceReadinessClaim(
      citedClaimFrom(observedClaim(persisted), "pass", []),
    );

    expect(cited.basis.kind).toBe("consistent_with_cited_report");
    expect(gateCode(cited)).toBe("cited_report_not_observation");
  });

  it("rejects cited pass with canonical findings under its named mismatch", () => {
    const cited = citedClaimFrom(observedClaim(persisted), "pass", [
      { code: "route_missing", message: "The canonical route was absent." },
    ]);

    expect(() => parseAtlasSurfaceReadinessClaim(cited)).toThrow(
      expect.objectContaining({ code: "cited_pass_with_findings" }),
    );
  });

  it.each(["fail", "incomplete"] as const)(
    "rejects cited %s with zero findings under the opposite named mismatch",
    (executionStatus) => {
      const cited = citedClaimFrom(
        observedClaim(persisted),
        executionStatus,
        [],
      );

      expect(() => parseAtlasSurfaceReadinessClaim(cited)).toThrow(
        expect.objectContaining({ code: "cited_nonpass_without_findings" }),
      );
    },
  );

  it("distinguishes a completed negative from an unavailable observation", () => {
    const claim = observedClaim(persisted);
    const negative = parseAtlasSurfaceReadinessClaim(
      observedVariant(claim, "not_observed"),
    );
    const unavailable = parseAtlasSurfaceReadinessClaim(
      observedVariant(claim, "observation_unavailable"),
    );

    expect(gateCode(negative)).toBe("canonical_claim_not_observed");
    expect(gateCode(unavailable)).toBe("claim_observation_unavailable");
  });

  it("gates the zero-instance stable arm identically to implemented", () => {
    const implementedNegative = observedVariant(
      observedClaim(persisted),
      "not_observed",
    );
    const stableNegative = {
      ...(implementedNegative as Record<string, unknown>),
      claim_id: "synthetic-stable-negative-control:maturity:stable",
      surface_id: "synthetic-stable-negative-control",
      title: "Synthetic stable negative control",
      dimension: "maturity",
      declared_value: "stable",
    };

    expect(parseAtlasSurfaceReadinessClaim(stableNegative)).toMatchObject({
      dimension: "maturity",
      declared_value: "stable",
    });
    expect(gateCode(stableNegative)).toBe(gateCode(implementedNegative));
    expect(gateCode(stableNegative)).toBe("canonical_claim_not_observed");
  });

  it("rejects a row with no basis or a second basis-shaped field", () => {
    const claim = observedClaim(persisted);
    const { basis: _basis, ...withoutBasis } = claim;
    expect(() => parseAtlasSurfaceReadinessClaim(withoutBasis)).toThrow();
    expect(() =>
      parseAtlasSurfaceReadinessClaim({
        ...claim,
        cited_basis: citedClaimFrom(claim, "pass", []),
      }),
    ).toThrow();
  });

  it("makes the full canonical owner validator go red for a falsified constraint", () => {
    const dashboardRoot = process.cwd();
    const policyEngineRoot = path.resolve(dashboardRoot, "../..");
    const result = spawnSync(
      path.join(policyEngineRoot, ".venv/bin/python"),
      [
        "-I",
        path.join(dashboardRoot, "scripts/validate_atlas_health_sources.py"),
        "--corruption-probes",
      ],
      {
        cwd: policyEngineRoot,
        encoding: "utf8",
        env: {
          HOME: "/var/empty",
          LANG: "C",
          LC_ALL: "C",
          PATH: "/usr/bin:/bin",
          TZ: "UTC",
        },
        timeout: 30_000,
      },
    );

    expect(result).toMatchObject({ status: 0, stderr: "" });
    const report = JSON.parse(result.stdout) as {
      probes: string[];
    };
    expect(report.probes).toContain("readiness_additional_property");
    expect(report.probes).toContain("readiness_duplicate_surface_id");
  });

  it.each(["report", "exit_code", "basis", "root", "script"])(
    "rejects caller-supplied %s intake",
    (field) => {
      const result = invokePersistence(
        { operation: OPERATION, [field]: "supplied" },
        casRoot,
      );
      expect(result.status).toBe(1);
      expect(result.value).not.toHaveProperty("ok");
      expect(result.value.error).toMatchObject({
        code: "atlas_evidence_persistence_failed",
      });
    },
  );

  it("ignores inherited process-selection controls on the closed path", () => {
    const isolatedCas = mkdtempSync(
      path.join(tmpdir(), "atlas-readiness-env-cas-"),
    );
    try {
      const result = asProjectionResult(
        invokePersistence({ operation: OPERATION }, isolatedCas, {
          NODE_OPTIONS: "--require=/definitely/not/a/module.cjs",
          PATH: "/definitely/not/a/path",
          VITE_CONFIG: "/definitely/not/a/config.ts",
        }),
      );
      expect(result.resolved_projection.projection.claims).toHaveLength(5);
    } finally {
      rmSync(isolatedCas, { recursive: true, force: true });
    }
  });

  it("content-binds the exact per-row report bytes without a CI verdict", () => {
    expect(persisted.claim_report_ref.artifact_id).toBe(
      `sha256:${persisted.resolved_projection.projection.claim_report_sha256}`,
    );
  });
});
