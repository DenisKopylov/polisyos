import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import HTEOutcomeView, {
  type HTEOutcomeDisplayModel,
  type HTEOutcomeDisplayModelCommon,
} from "./HTEOutcomeView";

const profileSha256 = `sha256:${"a".repeat(64)}`;

function ref(artifactId: string, kind: string) {
  return {
    artifact_id: `sha256:${artifactId.padEnd(64, "0").slice(0, 64)}`,
    kind,
    media_type: "application/json",
    manifest_profile_sha256: profileSha256,
  } as const;
}

function common(
  overrides: Partial<HTEOutcomeDisplayModelCommon> = {},
): HTEOutcomeDisplayModelCommon {
  return {
    schema_version: "1.0",
    authority_status: "candidate",
    method_fqn: "causal.hte.causal_forest",
    method_abi: "2.0.0",
    method_abi_digest: "b".repeat(64),
    method_profile_id: "econml_native_mean_over_selected_x@1.0",
    input_profile_id: "all_source_rows_in_input_order@1.0",
    selected_input_sha256: "c".repeat(64),
    selected_rows_sha256: "d".repeat(64),
    selected_x_sha256: "e".repeat(64),
    selected_row_order_sha256: "f".repeat(64),
    resolved_params_sha256: "1".repeat(64),
    n_selected_rows: 12,
    source_data_ref: ref("2", "datasets.policy-input"),
    invocation_basis_ref: null,
    invocation_basis_status: "not_established",
    invocation_basis_reason: "no_invocation_basis_artifact_contract",
    owned_attempt_anchor_ref: ref("3", "runtime.owned_attempt_anchor"),
    method_result_ref: ref("4", "scientist.method_result.causal.hte"),
    method_evidence_ref: ref("5", "scientist.method_evidence"),
    request_estimand_status: "declared",
    request_estimand: "population_average_treatment_effect",
    request_target_scope_status: "declared",
    request_target_scope: "population_ate",
    outcome_variable_status: "not_established",
    outcome_variable_id: null,
    treatment_variable_status: "not_established",
    treatment_variable_id: null,
    request_alpha_status: "not_established",
    requested_alpha: null,
    contrast_status: "not_established",
    control_value: null,
    treated_value: null,
    limitations: [
      "Population scope and sampling coverage are not established by this selected-row result.",
    ],
    ...overrides,
  };
}

const pointOutcome: HTEOutcomeDisplayModel = {
  ...common(),
  kind: "point_estimate",
  point_estimate: {
    schema_version: "1.0",
    value: 0.42,
    estimand: "mean_effect_over_selected_x",
    computed_target_scope_status: "recomputed",
    computed_target_scope: "selected_evaluation_rows",
    measure_unit_status: "not_established",
    measure_unit: null,
  },
  inference_status: "unsupported",
  inference_reason: "method_profile_not_qualified",
};

const intervalOutcome: HTEOutcomeDisplayModel = {
  ...common({
    request_estimand: "mean_effect_over_selected_x",
    request_target_scope: "selected_evaluation_rows",
    outcome_variable_status: "declared",
    outcome_variable_id: "outcome:income",
    treatment_variable_status: "declared",
    treatment_variable_id: "policy:eligibility",
    request_alpha_status: "declared",
    requested_alpha: 0.1,
    contrast_status: "established",
    control_value: 0,
    treated_value: 1,
    limitations: [
      "Population sampling coverage, causal identification, transport validity, and empirical calibration are not established.",
    ],
  }),
  kind: "interval_estimate",
  point_estimate: {
    schema_version: "1.0",
    value: 0.42,
    estimand: "mean_effect_over_selected_x",
    computed_target_scope_status: "recomputed",
    computed_target_scope: "selected_evaluation_rows",
    measure_unit_status: "established",
    measure_unit: "USD/person/year",
  },
  lower_bound: 0.12,
  upper_bound: 0.72,
  confidence_level: 0.9,
  interval_semantics: "native_mean_confidence_interval",
  inference_status: "native_ate_inference_validated",
  inference_basis_ref: ref("6", "ir.ate_inference_basis"),
  hte_result_ref: ref("7", "ir.hte_result"),
};

const refusalOutcome: HTEOutcomeDisplayModel = {
  ...common({ authority_status: "refusal" }),
  kind: "refusal",
  refusal_stage: "fit",
  refusal_reason: "method_execution_failed",
  diagnostic_code: "method_fit_failed",
};

describe("HTEOutcomeView", () => {
  it("keeps a point-only result visible and separates its requested and computed scope", () => {
    renderWithProviders(<HTEOutcomeView outcome={pointOutcome} />);

    expect(
      screen.getByRole("heading", { name: "Heterogeneous treatment effect" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("hte-outcome-point-value")).toHaveTextContent(
      "0.42",
    );
    expect(screen.getByText("Point estimate only")).toBeInTheDocument();
    expect(screen.getByText("population_ate")).toBeInTheDocument();
    expect(screen.getByText("selected_evaluation_rows")).toBeInTheDocument();
    expect(screen.getByText("Unit not established")).toBeInTheDocument();
    expect(
      screen.queryByTestId("hte-outcome-interval"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /owned attempt/i }),
    ).toHaveAttribute(
      "href",
      expect.stringContaining("runtime.owned_attempt_anchor"),
    );
  });

  it("labels the selected-row native interval as conditional and keeps limits visible", () => {
    renderWithProviders(<HTEOutcomeView outcome={intervalOutcome} />);

    expect(screen.getByTestId("hte-outcome-point-value")).toHaveTextContent(
      "0.42",
    );
    expect(screen.getByTestId("hte-outcome-interval")).toHaveTextContent(
      "0.12",
    );
    expect(screen.getByTestId("hte-outcome-interval")).toHaveTextContent(
      "0.72",
    );
    expect(screen.getByTestId("hte-outcome-interval")).toHaveTextContent("90%");
    expect(
      screen.getByText(
        /conditional on the selected model and evaluation rows/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/population sampling coverage.*not established/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /inference basis/i }),
    ).toHaveAttribute(
      "href",
      expect.stringContaining("ir.ate_inference_basis"),
    );
    expect(
      screen.queryByText(/statistically significant/i),
    ).not.toBeInTheDocument();
  });

  it("renders typed refusal without a numeric placeholder", () => {
    renderWithProviders(<HTEOutcomeView outcome={refusalOutcome} />);

    expect(screen.getByText("Result refused")).toBeInTheDocument();
    expect(screen.getByText("method_execution_failed")).toBeInTheDocument();
    expect(screen.getByText("method_fit_failed")).toBeInTheDocument();
    expect(
      screen.queryByTestId("hte-outcome-point-value"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("hte-outcome-interval"),
    ).not.toBeInTheDocument();
  });
});
