import type { AvailableGovernedProjectionPacket } from "@polisyos/runtime-api-client";
import { createGovernedAuthorityPurpose } from "@polisyos/atlas-ui";
import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { DecisionCard } from "./DecisionCard";

const GOVERNED_PACKET = {
  absence_reason: null,
  as_of: "2026-08-02T00:00:00.000Z",
  authoritative_for: ["publication_review"],
  availability: "available",
  export_replay_contract: "policyos.runtime.export_replay_binding.v1",
  freshness: {
    basis: "source_timestamp",
    observed_at: "2026-08-02T00:00:01.000Z",
    source_as_of: "2026-08-02T00:00:00.000Z",
    state: "observed",
  },
  intended_audience: "REVIEWER",
  may_not_use_for: [],
  packet_schema_version: "policyos.runtime.governed_projection_packet.v1",
  payload: {
    authority: {},
    controlled_vocabulary_source: "fixture://surface-readiness/vocabulary",
    entries: [],
    ledger_id: "fixture-surface-readiness",
  },
  projection_hash: "sha256:governed-projection",
  projection_id: "surface-readiness",
  projection_rule_version: "policyos.runtime.governed_projection.v1",
  replay_address: "fixture://surface-readiness/replay",
  source: {
    artifact_content_hash: "sha256:governed-source",
    declared_content_hash: "sha256:governed-source",
    related_artifact_bindings: [],
    relative_path: "fixture://surface-readiness",
    validation: {
      bound_artifact_content_hash: "sha256:governed-source",
      bound_dependency_aggregate_identity: "sha256:dependencies",
      bound_dependency_count: 0,
      issue_codes: [],
      status: "passed",
      validator_id: "fixture-validator",
      validator_version: "1",
    },
  },
  source_dependency_hash: "sha256:dependencies",
  source_rule_version: "fixture.source.v1",
  source_schema_version: "fixture.schema.v1",
  stable_address: "fixture://surface-readiness",
} satisfies AvailableGovernedProjectionPacket;

const FIXTURE_PACKET = {
  ...GOVERNED_PACKET,
  authoritative_for: ["publication_review"],
  payload: {
    fixture_authority: "fixture_only",
    fixture_identities: [],
    fixture_records: [],
    runtime_outcomes: {
      availability: "artifact_missing",
      reason: "fixture carries no producer-signed runtime outcome",
    },
  },
  projection_id: "legacy-proving-ground",
} satisfies AvailableGovernedProjectionPacket;

describe("DecisionCard", () => {
  it("keeps candidate and authority postures visually distinct for the same copy", () => {
    const authorityPurpose = createGovernedAuthorityPurpose(
      GOVERNED_PACKET,
      "publication_review",
    );

    renderWithProviders(
      <>
        <DecisionCard title="Candidate" verdict="publishable" />
        <DecisionCard
          authorityPurpose={authorityPurpose}
          title="Governed"
          verdict="publishable"
        />
      </>,
    );

    const candidate = screen.getByTestId("decision-card-candidate");
    const governed = screen.getByTestId("decision-card-governed");

    expect(candidate).toHaveAttribute("data-authority-posture", "candidate");
    expect(governed).toHaveAttribute(
      "data-authority-posture",
      "governed-authority",
    );
    expect(candidate.className).not.toBe(governed.className);
    expect(screen.getAllByText("publishable")).toHaveLength(2);
    expect(candidate).toHaveAttribute(
      "data-decision-grade-presentation",
      "unrecognized",
    );
    expect(governed).toHaveAttribute(
      "data-decision-grade-presentation",
      "unrecognized",
    );
  });

  it("bars fixture-backed packets from governed authority clothing", () => {
    const authorityPurpose = createGovernedAuthorityPurpose(
      FIXTURE_PACKET,
      "publication_review",
    );

    renderWithProviders(
      <DecisionCard
        authorityPurpose={authorityPurpose}
        title="Fixture packet"
        verdict="future-owner-grade"
      />,
    );

    const card = screen.getByTestId("decision-card-fixture");
    expect(card).toHaveAttribute("data-authority-posture", "fixture-only");
    expect(card).toHaveAttribute("data-fixture-authority", "fixture_only");
    expect(card).not.toHaveAttribute(
      "data-authority-posture",
      "governed-authority",
    );
    expect(card.className).toContain("border-dashed");
  });

  it("preserves owner diagnostic labels without caller-controlled authority clothing", () => {
    renderWithProviders(
      <DecisionCard
        title="Opaque diagnostics"
        verdict="future-owner-grade"
        diagnostics={[
          { kind: "publishable", label: "Owner says publishable" },
          { kind: "blocked", label: "Owner says blocked" },
        ]}
      />,
    );

    const publishable = screen.getByText("Owner says publishable");
    const blocked = screen.getByText("Owner says blocked");

    expect(publishable).toHaveAttribute(
      "data-owner-diagnostic-kind",
      "publishable",
    );
    expect(blocked).toHaveAttribute("data-owner-diagnostic-kind", "blocked");
    expect(publishable.className).toBe(blocked.className);
  });
});
