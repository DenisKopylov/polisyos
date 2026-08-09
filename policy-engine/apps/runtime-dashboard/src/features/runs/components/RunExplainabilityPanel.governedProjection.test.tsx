import type {
  ArtifactMissingGovernedProjectionPacket,
  AvailableGovernedProjectionPacket,
  DepthNCycleBoardPayload,
  DepthNDomainRunProjection,
  ProjectionSourceIdentity,
} from "@polisyos/runtime-api-client";
import { screen, within } from "@testing-library/react";

import type { RunInspectorSummary } from "@/features/runs/context/RunInspectorContext";
import { narrowDepthNCycleBoardProjection } from "@/features/runs/api/useDepthNCycleBoardProjection";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";
import { renderWithProviders } from "@/test/render";

import { RunExplainabilityPanel } from "./RunExplainabilityPanel";

type AvailableDepthProjectionPacket = Omit<
  AvailableGovernedProjectionPacket,
  "payload"
> & {
  payload: DepthNCycleBoardPayload;
};

const SOURCE: ProjectionSourceIdentity = {
  artifact_content_hash: "sha256:source",
  declared_content_hash: "sha256:source",
  related_artifact_bindings: [],
  relative_path: "artifacts/depth-n-cycle-board.json",
  validation: {
    bound_artifact_content_hash: "sha256:source",
    bound_dependency_aggregate_identity: "sha256:dependencies",
    bound_dependency_count: 1,
    issue_codes: [],
    semantic_projection_hash: "sha256:projection",
    semantic_projection_hash_rule_version: "depth-n.semantic.v1",
    status: "passed",
    validator_id: "depth-n-owner-validator",
    validator_version: "1",
  },
};

function summaryFixture(): RunInspectorSummary {
  return {
    artifactRefs: [],
    decisionHeadline: "Diagnostic run headline",
    decisionScore: untracedDecisionQuantity({
      metricId: "run.decision_score",
      point: null,
    }),
    decisionView: null,
    evidenceContext: null,
    governanceIssues: [],
    governanceSummary: null,
    impactRows: [],
    pipeline: null,
    primaryIssue: null,
    run: {
      run_id: "route-run-that-must-not-select-a-domain-row",
      started_at: "2026-07-29T09:00:00Z",
      status: "owner-run-state",
    },
    transportStatus: "owner-transport-state",
  } as unknown as RunInspectorSummary;
}

function domainRun(
  overrides: Partial<DepthNDomainRunProjection> = {},
): DepthNDomainRunProjection {
  return {
    acquisition_route: { route: "owner-supplied" },
    design_problem_ref: "design-problem://global-domain",
    domain_role: "legal",
    evidence_class: "recorded_owner_evidence",
    evidence_witness: { ref: "evidence://global-domain" },
    generation_cycle_run_id: "generation-cycle-global",
    terminal_distribution: { recorded_terminal: 0.6 },
    weakest_links: ["owner supplied weakest link"],
    ...overrides,
  };
}

function availablePacket(
  projection: DepthNDomainRunProjection = domainRun(),
): AvailableDepthProjectionPacket {
  return {
    as_of: "2026-07-29T10:00:00Z",
    authoritative_for: ["depth_n_cycle_board_projection"],
    availability: "available",
    export_replay_contract: "policyos.runtime.export_replay_binding.v1",
    freshness: {
      basis: "source_timestamp",
      observed_at: "2026-07-29T10:05:00Z",
      source_as_of: "2026-07-29T10:00:00Z",
      state: "observed",
    },
    intended_audience: "EXPERT",
    may_not_use_for: ["run_closeout"],
    packet_schema_version: "policyos.runtime.governed_projection_packet.v1",
    payload: {
      depth_evidence: { status: "recorded" },
      domain_runs: {
        "global-domain": projection,
        "global-sibling": domainRun({
          domain_role: "fiscal",
          generation_cycle_run_id: "generation-cycle-sibling",
        }),
      },
      terminal_distributions: {
        global: projection.terminal_distribution,
      },
    },
    projection_hash: "sha256:projection",
    projection_id: "depth-n-cycle-board",
    projection_rule_version: "policyos.runtime.governed_projection.v1",
    replay_address: "projection://depth-n-cycle-board",
    source: SOURCE,
    source_dependency_hash: "sha256:dependencies",
    source_rule_version: "depth-n.rule.v1",
    source_schema_version: "depth-n.schema.v1",
    stable_address: "projection://depth-n-cycle-board",
  };
}

function artifactMissingPacket(): ArtifactMissingGovernedProjectionPacket {
  return {
    absence_reason: "owner artifact is not present",
    as_of: "2026-07-29T10:00:00Z",
    authoritative_for: [],
    availability: "artifact_missing",
    export_replay_contract: "policyos.runtime.export_replay_binding.v1",
    freshness: {
      basis: "request_observation",
      observed_at: "2026-07-29T10:05:00Z",
      state: "artifact_missing",
    },
    intended_audience: "EXPERT",
    may_not_use_for: ["authority"],
    packet_schema_version: "policyos.runtime.governed_projection_packet.v1",
    projection_id: "depth-n-cycle-board",
    projection_rule_version: "policyos.runtime.governed_projection.v1",
    stable_address: "projection://depth-n-cycle-board",
  };
}

describe("RunExplainabilityPanel governed projection", () => {
  it("renders producer terminal evidence and as-of without local reclassification", () => {
    const packet = availablePacket();
    renderWithProviders(
      <RunExplainabilityPanel
        governedProjection={narrowDepthNCycleBoardProjection(packet)}
        level="summary"
        summary={summaryFixture()}
      />,
    );

    const projection = screen.getByTestId("governed-depth-projection");
    expect(projection).toHaveAttribute(
      "data-projection-availability",
      "available",
    );
    expect(
      within(projection).getAllByText("recorded_owner_evidence")[0],
    ).toHaveAttribute("data-authority-recognition", "unrecognized");
    expect(
      within(projection).getAllByText(/recorded_terminal/iu).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByTestId("time-semantics-payload-as-of"),
    ).toHaveTextContent("2026-07-29T10:00:00Z");
    expect(screen.getByText("depth_n_cycle_board_projection")).toHaveAttribute(
      "data-presentation-tone",
      "neutral",
    );
  });

  it("marks typed artifact absence as fixture-only and blocks authority posture", () => {
    renderWithProviders(
      <RunExplainabilityPanel
        governedProjection={narrowDepthNCycleBoardProjection(
          artifactMissingPacket(),
        )}
        level="summary"
        summary={summaryFixture()}
      />,
    );

    const projection = screen.getByTestId("governed-depth-projection");
    expect(projection).toHaveAttribute(
      "data-projection-availability",
      "artifact_missing",
    );
    expect(projection).toHaveAttribute("data-authority-posture", "unavailable");
    expect(within(projection).getByText(/fixture[_ ]only/iu)).toHaveAttribute(
      "data-fixture-authority",
      "fixture_only",
    );
    expect(
      within(projection).queryByText("depth_n_cycle_board_projection"),
    ).not.toBeInTheDocument();
    expect(
      within(projection).queryByText("recorded_owner_evidence"),
    ).not.toBeInTheDocument();
    expect(
      within(projection).queryByTestId("weakest-link-explainer"),
    ).not.toBeInTheDocument();
  });

  it("preserves an unseen terminal and evidence label verbatim", () => {
    const packet = availablePacket(
      domainRun({
        evidence_class: "future:owner/evidence-v99",
        terminal_distribution: {
          "future:owner/terminal-v99": { probability: "owner-opaque" },
        },
      }),
    );
    renderWithProviders(
      <RunExplainabilityPanel
        governedProjection={narrowDepthNCycleBoardProjection(packet)}
        level="summary"
        summary={summaryFixture()}
      />,
    );

    const evidence = screen.getByText("future:owner/evidence-v99");
    expect(evidence).toHaveAttribute(
      "data-authority-recognition",
      "unrecognized",
    );
    expect(evidence).toHaveAttribute("data-presentation-tone", "neutral");
    expect(
      screen.getAllByText(/future:owner\/terminal-v99/iu).length,
    ).toBeGreaterThan(0);
  });

  it("preserves a novel domain key as the section accessible name", () => {
    const packet = availablePacket();
    packet.payload.domain_runs = {
      "future owner/domain-v99": domainRun(),
    };
    renderWithProviders(
      <RunExplainabilityPanel
        governedProjection={narrowDepthNCycleBoardProjection(packet)}
        level="summary"
        summary={summaryFixture()}
      />,
    );

    expect(
      screen.getByRole("region", { name: "future owner/domain-v99" }),
    ).toBeInTheDocument();
  });

  it("uses only the producer weakest-link array without client recomputation", () => {
    const packet = availablePacket(
      domainRun({
        evidence_witness: { tempting_local_candidate: "do not select me" },
        terminal_distribution: { blocked: 0.999, ready: 0.001 },
        weakest_links: ["producer-selected weakest boundary"],
      }),
    );
    renderWithProviders(
      <RunExplainabilityPanel
        governedProjection={narrowDepthNCycleBoardProjection(packet)}
        level="summary"
        summary={summaryFixture()}
      />,
    );

    const weakestLinks = screen.getAllByTestId("weakest-link-explainer");
    expect(weakestLinks[0]).toHaveTextContent(
      "producer-selected weakest boundary",
    );
    expect(weakestLinks[0]).not.toHaveTextContent("blocked");
    expect(weakestLinks[0]).not.toHaveTextContent("do not select me");
  });
});
