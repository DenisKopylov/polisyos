import actualResponseBytes from "./hooks/__fixtures__/r7-run-details-response.content?raw";
import producerDiagnosticBytes from "./__fixtures__/method-execution-producer-diagnostic.json?raw";
import populatedProducerDiagnosticBytes from "./__fixtures__/method-execution-producer-diagnostic-populated.json?raw";
import { describe, expect, it } from "vitest";

import { runDetailsSchema } from "@/api/validators";

function asRecord(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("expected a record");
  }
  return value as Record<string, unknown>;
}

function actualResponse(): Record<string, unknown> {
  return asRecord(JSON.parse(actualResponseBytes));
}

function diagnosticFromPythonDto(): unknown {
  return JSON.parse(producerDiagnosticBytes) as unknown;
}

describe("Run Details producer diagnostic schema", () => {
  it("accepts the actual null and strict Python DTO shape while refusing invalid diagnostics", () => {
    const actual = actualResponse();
    expect(
      runDetailsSchema.parse(actual).run.method_execution_producer_diagnostic,
    ).toBeNull();

    const withDiagnostic = actualResponse();
    asRecord(withDiagnostic.run).method_execution_producer_diagnostic =
      diagnosticFromPythonDto();
    const parsed = runDetailsSchema.parse(withDiagnostic);
    expect(
      parsed.run.method_execution_producer_diagnostic?.authority_status,
    ).toBe("candidate_only");
    expect(parsed.run.method_execution_producer_diagnostic?.emissions).toEqual(
      [],
    );

    const populatedResponse = actualResponse();
    asRecord(populatedResponse.run).method_execution_producer_diagnostic =
      JSON.parse(populatedProducerDiagnosticBytes) as unknown;
    const populated =
      runDetailsSchema.parse(populatedResponse).run
        .method_execution_producer_diagnostic;
    expect(
      populated?.emissions.map((emission) => emission.output_ref_status),
    ).toEqual(["complete", "partial"]);
    expect(populated?.emissions[0]?.simulation_result_ref?.kind).toBe(
      "foundry.simulation_result",
    );
    expect(
      populated?.emissions[0]?.method_execution_bundle_refs[0]
        ?.manifest_profile_sha256,
    ).toBe("sha256:" + "4".repeat(64));
    expect(populated?.emissions[1]?.method_execution_bundle_refs).toHaveLength(
      1,
    );

    const withUnknownDiagnosticField = actualResponse();
    const unknownDiagnostic = asRecord(diagnosticFromPythonDto());
    unknownDiagnostic.unmodeled_authority = "publishable";
    asRecord(
      withUnknownDiagnosticField.run,
    ).method_execution_producer_diagnostic = unknownDiagnostic;
    expect(runDetailsSchema.safeParse(withUnknownDiagnosticField).success).toBe(
      false,
    );

    const statusMismatch = actualResponse();
    const mismatchDiagnostic = asRecord(diagnosticFromPythonDto());
    mismatchDiagnostic.emissions = [
      {
        emission_index: 0,
        execute_result_status: "ok",
        output_ref_status: "complete",
        simulation_result_ref: null,
        method_execution_bundle_refs: [],
        method_metric_binding_set_refs: [],
      },
    ];
    asRecord(statusMismatch.run).method_execution_producer_diagnostic =
      mismatchDiagnostic;
    expect(runDetailsSchema.safeParse(statusMismatch).success).toBe(false);

    const wrongReferenceKind = actualResponse();
    const wrongKindDiagnostic = asRecord(diagnosticFromPythonDto());
    wrongKindDiagnostic.emissions = [
      {
        emission_index: 0,
        execute_result_status: "ok",
        output_ref_status: "partial",
        simulation_result_ref: {
          artifact_id: "sha256:" + "1".repeat(64),
          kind: "ir.hte_point_result",
          media_type: "application/json",
          manifest_profile_sha256: "sha256:" + "2".repeat(64),
        },
        method_execution_bundle_refs: [],
        method_metric_binding_set_refs: [],
      },
    ];
    asRecord(wrongReferenceKind.run).method_execution_producer_diagnostic =
      wrongKindDiagnostic;
    expect(runDetailsSchema.safeParse(wrongReferenceKind).success).toBe(false);

    const wrongMediaType = actualResponse();
    const wrongMediaDiagnostic = asRecord(
      JSON.parse(populatedProducerDiagnosticBytes) as unknown,
    );
    const wrongMediaEmissions = wrongMediaDiagnostic.emissions as unknown[];
    asRecord(
      asRecord(wrongMediaEmissions[0]).simulation_result_ref,
    ).media_type = "text/plain";
    asRecord(wrongMediaType.run).method_execution_producer_diagnostic =
      wrongMediaDiagnostic;
    expect(runDetailsSchema.safeParse(wrongMediaType).success).toBe(false);

    const missingManifestProfile = actualResponse();
    const missingProfileDiagnostic = asRecord(
      JSON.parse(populatedProducerDiagnosticBytes) as unknown,
    );
    const missingProfileEmissions =
      missingProfileDiagnostic.emissions as unknown[];
    asRecord(
      asRecord(missingProfileEmissions[0]).simulation_result_ref,
    ).manifest_profile_sha256 = null;
    asRecord(missingManifestProfile.run).method_execution_producer_diagnostic =
      missingProfileDiagnostic;
    expect(runDetailsSchema.safeParse(missingManifestProfile).success).toBe(
      false,
    );

    const tooManyOutputRefs = actualResponse();
    const tooManyRefsDiagnostic = asRecord(
      JSON.parse(populatedProducerDiagnosticBytes) as unknown,
    );
    const tooManyRefsEmissions = tooManyRefsDiagnostic.emissions as unknown[];
    const validPartialEmission = asRecord(tooManyRefsEmissions[1]);
    const validBundleRef = asRecord(
      (validPartialEmission.method_execution_bundle_refs as unknown[])[0],
    );
    tooManyRefsDiagnostic.emissions = [
      {
        ...validPartialEmission,
        emission_index: 0,
        method_execution_bundle_refs: Array.from({ length: 9 }, () => ({
          ...validBundleRef,
        })),
      },
    ];
    asRecord(tooManyOutputRefs.run).method_execution_producer_diagnostic =
      tooManyRefsDiagnostic;
    expect(runDetailsSchema.safeParse(tooManyOutputRefs).success).toBe(false);

    const tooManyEmissions = actualResponse();
    const tooManyEmissionsDiagnostic = asRecord(diagnosticFromPythonDto());
    tooManyEmissionsDiagnostic.emissions = Array.from(
      { length: 17 },
      (_, emission_index) => ({
        emission_index,
        execute_result_status: "ok",
        output_ref_status: "none",
        simulation_result_ref: null,
        method_execution_bundle_refs: [],
        method_metric_binding_set_refs: [],
      }),
    );
    asRecord(tooManyEmissions.run).method_execution_producer_diagnostic =
      tooManyEmissionsDiagnostic;
    expect(runDetailsSchema.safeParse(tooManyEmissions).success).toBe(false);

    const invalidAttempt = actualResponse();
    const invalidAttemptDiagnostic = asRecord(diagnosticFromPythonDto());
    invalidAttemptDiagnostic.attempt = 0;
    asRecord(invalidAttempt.run).method_execution_producer_diagnostic =
      invalidAttemptDiagnostic;
    expect(runDetailsSchema.safeParse(invalidAttempt).success).toBe(false);

    const outOfOrder = actualResponse();
    const unorderedDiagnostic = asRecord(diagnosticFromPythonDto());
    unorderedDiagnostic.emissions = [
      {
        emission_index: 1,
        execute_result_status: "ok",
        output_ref_status: "none",
        simulation_result_ref: null,
        method_execution_bundle_refs: [],
        method_metric_binding_set_refs: [],
      },
    ];
    asRecord(outOfOrder.run).method_execution_producer_diagnostic =
      unorderedDiagnostic;
    expect(runDetailsSchema.safeParse(outOfOrder).success).toBe(false);

    const overlongJobId = actualResponse();
    const overlongDiagnostic = asRecord(diagnosticFromPythonDto());
    overlongDiagnostic.job_id = "j".repeat(129);
    asRecord(overlongJobId.run).method_execution_producer_diagnostic =
      overlongDiagnostic;
    expect(runDetailsSchema.safeParse(overlongJobId).success).toBe(false);
  });
});
