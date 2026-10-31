import { render, screen, within } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";

import {
  legacyLimitedProjection,
  pointSummary,
} from "../domain/__test__/decisionPacketHteFixtures";

import {
  MonographLayout,
  buildDecisionPacketDocument,
} from "./MonographLayout";

const packetPreview = {
  analysis_limits: {
    decision_packet_degraded: true,
    labels: ["decision_packet_degraded", "missing_optional_inputs"],
  },
  causal: {
    point_estimate: 0.13,
    status: "transportable",
  },
  degraded_paths: [
    {
      reason: "source_verification_report_load_failed",
    },
  ],
  distributional: {
    breakdowns: [
      {
        cohorts: [
          {
            cohort_label: "Low income",
            delta: -0.7,
            impact_direction: "down",
            is_vulnerable: true,
            population_share: 0.22,
          },
          {
            cohort_label: "High income",
            delta: 0.14,
            impact_direction: "up",
            population_share: 0.78,
          },
        ],
        dimension_label: "Income",
      },
    ],
    losers_count: 4,
    losers_share: 0.24,
    overall_gini_after: 0.35,
    overall_gini_before: 0.4,
    overall_gini_delta: -0.05,
    winners_count: 12,
    winners_share: 0.76,
  },
  document_outline: [
    {
      section_id: "policy_answer",
      section_type: "policy",
      title: "Recommendation",
    },
    {
      section_id: "policy_summary",
      section_type: "intervention",
      title: "Intervention scope",
    },
    {
      section_id: "evidence",
      section_type: "evidence",
      title: "Evidence and uncertainty",
    },
    {
      section_id: "governance",
      section_type: "governance",
      title: "Governance and legal basis",
    },
  ],
  feedback: {
    issues: [{ pass_id: "transport", severity: "blocker" }],
    verdict: "reject",
  },
  generated_at: "2026-04-22T08:00:00Z",
  hypotheses: ["Pilot exemptions remain unverified."],
  intervention_legal_basis_map: {
    verified_option_1: ["Article 1"],
  },
  legal_verification: {
    verification_cycles_completed: 2,
    verified_claim_count: 4,
  },
  metric_significance: {
    gdp_change: {
      alpha: 0.05,
      p_adj: 0.02,
      p_value: 0.02,
      significant: true,
      test_label: "McNemar exact",
    },
  },
  metric_validation_comparisons: [
    {
      alpha: 0.05,
      assumption_warnings: ["paired_test"],
      baseline_model_id: "baseline",
      baseline_value: 0.71,
      candidate_model_id: "candidate",
      candidate_value: 0.76,
      delta_value: 0.05,
      metric_direction: "higher_is_better",
      metric_id: "accuracy",
      p_adj: 0.02,
      p_value: 0.02,
      significant: true,
      test_id: "mcnemar_exact",
      test_label: "McNemar exact",
    },
  ],
  metric_validation_family_adjustment: {
    alpha: 0.05,
    dependency_assumption: "arbitrary",
    error_rate_target: "FWER",
    hypotheses_total: 1,
    method: "holm",
  },
  notes: ["Export keeps provenance strip in print."],
  policy_answer: {
    executive_summary:
      "Reject the current package until source coverage is closed.",
    missing_evidence: ["Appendix 2 still lacks a verified citation."],
    needs_expert_review: true,
  },
  policy_summary: "Targeted licensing reform for regional carriers.",
  replay: {
    determinism_tier: "replay_grade",
    effective_seed: 123,
    missing_refs: ["norm_pack_ref"],
    readiness: "partial",
    strategy_hint: "scientist",
    suggested_next_step: "Persist norm_pack_ref for replay completeness.",
  },
  run_id: "run-monograph",
  run_timeline: {
    summary: {
      duration_ms: 4567,
    },
  },
  simulation_results: {
    gdp_change: 0.12,
    unemployment_change: -0.01,
  },
  source_coverage: {
    unresolved_critical_gaps: [
      {
        description: "Approval annex remains unverified.",
      },
    ],
  },
  uncertainty_bounds: {
    gdp_change_ci_level: 0.95,
    gdp_change_lower: 0.1,
    gdp_change_upper: 0.14,
  },
  verified_findings: ["Licensing remains mandatory under Article 1."],
};

describe("MonographLayout", () => {
  it("builds and renders a glyphed reading document from a decision packet", () => {
    const document = buildDecisionPacketDocument(packetPreview);
    expect(document).not.toBeNull();

    render(<MonographLayout document={document!} />);

    expect(
      screen.getByRole("heading", {
        name: /reject the current package until source coverage is closed/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", {
        name: /decision packet table of contents/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /evidence and uncertainty/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/previously reported findings \(unverified\)/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/4 previously reported claims/i),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/licensing remains mandatory/i).length,
    ).toBeGreaterThan(0);
  });

  it("shows the unresolved option-to-program match without inventing a human gate", () => {
    const limitation =
      "The selected policy option has not been matched to the final program.";
    const document = buildDecisionPacketDocument({
      ...packetPreview,
      legal_verification: undefined,
      verified_findings: [],
      policy_answer: {
        ...packetPreview.policy_answer,
        missing_evidence: [limitation],
        needs_expert_review: false,
        option_program_correspondence: {
          status: "not_established",
          reason_code: "option_program_correspondence_not_established",
        },
      },
    });
    expect(document).not.toBeNull();

    render(<MonographLayout document={document!} />);

    expect(screen.getByText(limitation)).toBeInTheDocument();
    expect(
      screen.getByText(/no explicit expert-review gate is attached/i),
    ).toBeInTheDocument();
  });

  it.each([
    {
      name: "explicitly unestablished",
      status: { verification_status: "not_established" },
    },
    { name: "missing marker", status: {} },
    {
      name: "caller-asserted current marker",
      status: { verification_status: "current" },
    },
  ])("keeps $name legal claims unverified", ({ status }) => {
    const document = buildDecisionPacketDocument({
      ...packetPreview,
      legal_verification: {
        candidate_claim_count: 2,
        needs_expert_review: false,
        reported_unbound_claim_count: 4,
        ...status,
        verified_claim_count: 4,
      },
      policy_answer: {
        ...packetPreview.policy_answer,
        needs_expert_review: false,
      },
    });
    expect(document).not.toBeNull();

    render(<MonographLayout document={document!} />);

    expect(
      screen.getByText(/verified legal claim count is unknown/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/2 candidate claims.*4 previously reported claims/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/previously reported findings \(unverified\)/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/recorded expert-review status does not establish/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/4 verified claims grounded/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/no additional expert-review escalation/i),
    ).not.toBeInTheDocument();
  });

  it("keeps reported findings unverified even without a legal section", () => {
    const document = buildDecisionPacketDocument({
      ...packetPreview,
      legal_verification: undefined,
      policy_answer: {
        ...packetPreview.policy_answer,
        needs_expert_review: false,
      },
    });
    expect(document).not.toBeNull();

    render(<MonographLayout document={document!} />);

    expect(
      screen.getByText(/previously reported findings \(unverified\)/i),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/verified legal claim count is unknown/i).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText(/^verified findings$/i)).not.toBeInTheDocument();
  });

  it("carries a bounded HTE preview into the reading and print document with traversable refs", () => {
    const document = buildDecisionPacketDocument({
      ...packetPreview,
      hte: pointSummary(),
    });
    expect(document).not.toBeNull();
    expect(
      document?.sections.find((section) => section.id === "hte_outcome"),
    ).toMatchObject({
      hteProjection: { status: "valid" },
    });

    renderWithProviders(<MonographLayout document={document!} />);

    expect(screen.getByTestId("hte-outcome-point-value")).toHaveTextContent(
      "0.25",
    );
    expect(screen.getByRole("link", { name: "Point result" })).toHaveAttribute(
      "href",
      expect.stringContaining("ir.hte_point_result"),
    );
    expect(screen.getByRole("navigation")).toHaveTextContent(/HTE outcome/i);
  });

  it("carries the typed limited legacy projection through the monograph reading surface", () => {
    const document = buildDecisionPacketDocument({
      ...packetPreview,
      hte: null,
      hte_projection_status: "legacy_limited",
      hte_legacy_limited: legacyLimitedProjection(),
    });
    expect(document).not.toBeNull();
    expect(
      document?.sections.find((section) => section.id === "hte_outcome"),
    ).toMatchObject({
      hteProjection: { status: "valid" },
    });

    renderWithProviders(<MonographLayout document={document!} />);

    const outcome = screen.getByTestId("hte-outcome");
    expect(outcome).toHaveAttribute("data-hte-outcome-kind", "legacy_limited");
    expect(outcome).toHaveTextContent("0.25");
    expect(outcome).toHaveTextContent(
      "meaning and coverage are not established",
    );
    expect(within(outcome).queryByRole("link")).not.toBeInTheDocument();
  });
});
