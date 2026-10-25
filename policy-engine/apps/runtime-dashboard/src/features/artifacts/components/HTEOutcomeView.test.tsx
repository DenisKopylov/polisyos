import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import {
  intervalSummary,
  legacyLimitedProjection,
  legacyUnavailableProjection,
  pointSummary,
  r5DualObservationSummary,
  refusalSummary,
} from "@/features/artifacts/domain/__test__/decisionPacketHteFixtures";
import HTEOutcomeView from "./HTEOutcomeView";
import {
  parseDecisionPacketHTEProjection,
  parseDirectMethodExecutionHTESummary,
} from "@/features/artifacts/domain/decisionPacketHte";

function parseSummary(summary: Record<string, unknown>) {
  const parsed = parseDecisionPacketHTEProjection({ hte: summary });
  if (parsed.status !== "valid") {
    throw new Error(`Expected a valid HTE summary, got ${parsed.status}.`);
  }
  return parsed.outcome;
}

function parseRuntimeSummary(summary: Record<string, unknown>) {
  const parsed = parseDirectMethodExecutionHTESummary(summary);
  if (!parsed) {
    throw new Error("Expected a valid R5 HTE runtime summary.");
  }
  return parsed;
}

describe("HTEOutcomeView", () => {
  it("keeps a scalar point visible and separates requested from computed scope", () => {
    const populationRequest = pointSummary();
    populationRequest.request_estimand = "population_average_treatment_effect";
    populationRequest.request_target_scope = "population";
    populationRequest.target_relation = {
      ...(populationRequest.target_relation as Record<string, unknown>),
      requested_scope: "population",
      scope_disposition: "requested_claim_not_satisfied",
      overall_disposition: "requested_claim_not_satisfied",
    };
    renderWithProviders(
      <HTEOutcomeView outcome={parseSummary(populationRequest)} />,
    );

    expect(
      screen.getByRole("heading", { name: "Heterogeneous treatment effect" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("hte-outcome-point-value")).toHaveTextContent(
      "0.25",
    );
    expect(screen.getByText("Point estimate only")).toBeInTheDocument();
    expect(screen.getByText("Candidate result")).toBeInTheDocument();
    expect(screen.getByTestId("hte-outcome")).toHaveTextContent(
      "selected_evaluation_rows",
    );
    expect(
      screen.queryByTestId("hte-outcome-resource-estimator"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("hte-outcome-resource-joblib")).toHaveTextContent(
      "joblib returned",
    );
    expect(screen.getByTestId("hte-outcome")).not.toHaveTextContent(
      "population_ate",
    );
    expect(screen.getByTestId("hte-outcome")).toHaveTextContent(
      "population_average_treatment_effect",
    );
    expect(screen.getByTestId("hte-outcome")).toHaveTextContent(
      "mean_effect_over_selected_x",
    );
    expect(screen.getByTestId("hte-outcome")).toHaveTextContent(
      "Unit not established",
    );
    expect(screen.getByTestId("hte-target-relation")).toHaveAttribute(
      "data-overall-disposition",
      "requested_claim_not_satisfied",
    );
    expect(
      screen.queryByTestId("hte-outcome-interval"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /owned attempt/i }),
    ).toHaveAttribute(
      "href",
      expect.stringContaining("runtime.owned_attempt_anchor"),
    );
    expect(
      screen
        .getAllByRole("link")
        .find((link) => link.getAttribute("href")?.includes("ir.hte_outcome")),
    ).toHaveAttribute("href", expect.stringContaining("ir.hte_outcome"));
  });

  it("labels the native interval as conditional and links its result and basis", () => {
    renderWithProviders(
      <HTEOutcomeView outcome={parseSummary(intervalSummary())} />,
    );

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
      screen.getByText(/not a validated population interval/i),
    ).toBeInTheDocument();
    expect(
      screen
        .getAllByRole("link")
        .find((link) =>
          link.getAttribute("href")?.includes("ir.ate_inference_basis"),
        ),
    ).toHaveAttribute(
      "href",
      expect.stringContaining("ir.ate_inference_basis"),
    );
    expect(
      screen
        .getAllByRole("link")
        .some((link) =>
          link.getAttribute("href")?.includes("ir.hte_point_result"),
        ),
    ).toBe(false);
    expect(
      screen
        .getAllByRole("link")
        .find((link) => link.getAttribute("href")?.includes("ir.hte_result")),
    ).toHaveAttribute("href", expect.stringContaining("ir.hte_result"));
    expect(screen.getByRole("link", { name: /source data/i })).toHaveAttribute(
      "href",
      expect.stringContaining("foundry.data_snapshot"),
    );
    expect(
      screen.queryByText(/statistically significant/i),
    ).not.toBeInTheDocument();
  });

  it("renders refusal without numeric placeholders and retains evidence pins", () => {
    renderWithProviders(
      <HTEOutcomeView outcome={parseSummary(refusalSummary())} />,
    );

    expect(screen.getByText("Result refused")).toBeInTheDocument();
    expect(screen.getByText("method_execution_failed")).toBeInTheDocument();
    expect(screen.getByText("hte_fit_failed")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /refusal diagnostic/i }),
    ).toHaveAttribute(
      "href",
      expect.stringContaining("ir.hte_refusal_diagnostic"),
    );
    expect(
      screen.queryByTestId("hte-outcome-point-value"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("hte-outcome-interval"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /owned attempt/i }),
    ).toHaveAttribute(
      "href",
      expect.stringContaining("runtime.owned_attempt_anchor"),
    );
    expect(
      screen
        .getAllByRole("link")
        .find((link) =>
          link
            .getAttribute("href")
            ?.includes("runtime.observational_input_resource_policy"),
        ),
    ).toHaveAttribute(
      "href",
      expect.stringContaining("runtime.observational_input_resource_policy"),
    );
  });

  it("renders both R5 recomputed resource observations separately", () => {
    const summary = r5DualObservationSummary();
    renderWithProviders(
      <HTEOutcomeView outcome={parseRuntimeSummary(summary)} />,
    );

    const estimator = screen.getByTestId("hte-outcome-resource-estimator");
    const joblib = screen.getByTestId("hte-outcome-resource-joblib");

    expect(estimator).toHaveTextContent("econml.dml.CausalForestDML");
    expect(estimator).toHaveTextContent("n_jobs 1 → 1");
    expect(estimator).toHaveTextContent(
      `params SHA-256 ${"d".repeat(64)} → ${"d".repeat(64)}`,
    );
    expect(joblib).toHaveTextContent("joblib returned");
    expect(joblib).toHaveTextContent("version 1.5.3 → 1.5.3");
    expect(joblib).toHaveTextContent("effective jobs 1 → 1");
    expect(joblib).toHaveTextContent(
      "joblib._parallel_backends.SequentialBackend → joblib._parallel_backends.SequentialBackend",
    );
    expect(joblib).toHaveTextContent(
      `config SHA-256 ${"e".repeat(64)} → ${"e".repeat(64)}`,
    );
    expect(estimator).not.toBe(joblib);
    expect(
      screen.getAllByTestId(/^hte-outcome-resource-(?:estimator|joblib)$/u),
    ).toHaveLength(2);
  });

  it("renders the actual legacy projection as limited and never creates an artifact link", () => {
    const legacy = legacyLimitedProjection();
    legacy.warnings = ["legacy_warning_visible"];
    const parsed = parseDecisionPacketHTEProjection({
      hte_projection_status: "legacy_limited",
      hte: null,
      hte_legacy_limited: legacy,
    });
    expect(parsed.status).toBe("valid");
    if (parsed.status !== "valid") {
      throw new Error("Expected a valid limited legacy preview.");
    }

    renderWithProviders(<HTEOutcomeView outcome={parsed.outcome} />);

    const section = screen.getByTestId("hte-outcome");
    expect(section).toHaveAttribute("data-hte-outcome-kind", "legacy_limited");
    expect(section).toHaveTextContent("Legacy HTE fields (limited display)");
    expect(section).toHaveTextContent("Legacy ATE field");
    expect(section).toHaveTextContent("0.25");
    expect(section).toHaveTextContent(
      "Legacy bound fields; meaning and coverage are not established",
    );
    expect(section).toHaveTextContent(
      "This legacy summary does not establish source profile, target scope, conditional coverage, or population coverage.",
    );
    expect(screen.getByTestId("hte-legacy-warnings")).toHaveTextContent(
      "legacy_warning_visible",
    );
    expect(
      screen.queryByTestId("hte-outcome-point-value"),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("shows unavailable legacy parse output without numeric values or links", () => {
    const parsed = parseDecisionPacketHTEProjection({
      hte_projection_status: "legacy_limited",
      hte: null,
      hte_legacy_limited: legacyUnavailableProjection(),
    });
    expect(parsed.status).toBe("valid");
    if (parsed.status !== "valid") {
      throw new Error("Expected a valid unavailable legacy preview.");
    }

    renderWithProviders(<HTEOutcomeView outcome={parsed.outcome} />);

    const section = screen.getByTestId("hte-outcome-unavailable");
    expect(section).toHaveAttribute("data-hte-availability", "unavailable");
    expect(section).toHaveAttribute("role", "status");
    expect(section).toHaveTextContent("Legacy HTE result unavailable");
    expect(section).toHaveTextContent("hte_result_parse_failed");
    expect(section).not.toHaveTextContent("Legacy ATE field");
    expect(screen.queryByTestId("hte-legacy-ate")).not.toBeInTheDocument();
    expect(screen.queryByTestId("hte-legacy-bounds")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("hte-legacy-limitations"),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
