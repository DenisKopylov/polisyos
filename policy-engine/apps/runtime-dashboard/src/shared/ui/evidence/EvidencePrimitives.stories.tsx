import type { PropsWithChildren } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";
import type {
  AvailableGovernedProjectionPacket,
  DecisionPacketAuthoredBlock,
  DepthNDomainRunProjection,
  LegacyProvingGroundPayload,
  PolicyDesignCaseProjectionBlocker,
  ProjectionFreshness,
} from "@polisyos/runtime-api-client";
import {
  createOpaqueAuthorityPresentation,
  createFixtureProvenance,
  createGovernedAuthorityPurpose,
  EnvelopeChip,
  EvidenceLink,
} from "@polisyos/atlas-ui";

import { BlockerCard } from "@/shared/ui/compounds/BlockerCard";
import { CandidateFrame } from "@/shared/ui/compounds/CandidateFrame";
import { WeakestLinkExplainer } from "@/shared/ui/compounds/WeakestLinkExplainer";
import { ProvenancePopover } from "@/shared/ui/quantity/ProvenancePopover";
import type { QuantityValue } from "@/shared/ui/quantity/quantity.types";
import { TimeSemanticsLabel } from "@/shared/ui/temporal/TimeSemanticsLabel";
import { depthNDomainRunFixture } from "@/test/fixtures/depthNCycleBoard";

const fixturePayload = {
  fixture_authority: "fixture_only",
  fixture_identities: [],
  fixture_records: [],
  runtime_outcomes: {
    availability: "artifact_missing",
    reason: "Storybook has no producer-signed runtime outcome.",
  },
} satisfies LegacyProvingGroundPayload;

const fixturePacket = {
  absence_reason: null,
  as_of: "2026-07-20T12:00:00.000Z",
  authoritative_for: ["storybook_boundary_demonstration"],
  availability: "available",
  export_replay_contract: "policyos.runtime.export_replay_binding.v1",
  freshness: {
    basis: "source_timestamp",
    observed_at: "2026-07-20T12:00:00.000Z",
    source_as_of: "2026-07-20T11:58:00.000Z",
    state: "observed",
  },
  intended_audience: "REVIEWER",
  may_not_use_for: ["approval", "publication", "runtime_authority"],
  packet_schema_version: "policyos.runtime.governed_projection_packet.v1",
  payload: fixturePayload,
  projection_hash: "fixture-only-storybook-projection",
  projection_id: "legacy-proving-ground",
  projection_rule_version: "policyos.runtime.governed_projection.v1",
  replay_address: "fixture://storybook/evidence-primitives/replay",
  source: {
    artifact_content_hash: "fixture-only-storybook-source",
    declared_content_hash: null,
    related_artifact_bindings: [],
    relative_path: "fixture://storybook/evidence-primitives",
    validation: {
      bound_artifact_content_hash: "fixture-only-storybook-source",
      bound_dependency_aggregate_identity: "fixture-only",
      bound_dependency_count: 0,
      issue_codes: ["fixture_only"],
      status: "not_run",
      validator_id: "fixture-only",
      validator_version: "0",
    },
  },
  source_dependency_hash: "fixture-only",
  source_rule_version: null,
  source_schema_version: null,
  stable_address: "fixture://storybook/evidence-primitives",
} satisfies AvailableGovernedProjectionPacket;

const fixtureProvenance = createFixtureProvenance(fixturePayload);
const fixturePurpose = createGovernedAuthorityPurpose(
  fixturePacket,
  fixturePacket.authoritative_for[0],
);

function fixtureAuthorityRejectionMessage() {
  try {
    createOpaqueAuthorityPresentation(fixturePayload.fixture_authority);
  } catch (error) {
    if (!(error instanceof TypeError)) {
      throw error;
    }
    return error.message;
  }
  throw new Error("fixture_only unexpectedly entered authority presentation");
}

const authorityRejection = fixtureAuthorityRejectionMessage();

const candidateBlock = {
  author: "drafter",
  author_agent_version: "storybook-fixture",
  confidence: 0.61,
  content:
    "Candidate prose remains model-authored and deliberately uses different clothing. This long copy demonstrates wrapping without converting a proposal into an owner-signed conclusion.",
  reviewed_by_human: false,
  sources: [
    {
      href: "#fixture-evidence",
      ref: "fixture://evidence/candidate-source",
    },
  ],
  timestamp: "2026-07-20T11:54:00.000Z",
} satisfies DecisionPacketAuthoredBlock;

const blocker = {
  code: "fixture_missing_grounded_effect",
  evidence_ref: "fixture://evidence/missing-grounded-effect",
  message:
    "The story fixture contains no producer-signed grounded effect, so authority presentation remains unavailable.",
  module_id: "storybook-fixture",
  next_action: "Load a producer-signed projection before rendering authority.",
  owner: "fixture-only",
  severity: "blocking",
} satisfies PolicyDesignCaseProjectionBlocker;

const domainProjection = depthNDomainRunFixture({
  design_problem_ref: "fixture://design-problem/storybook",
  domain_role: "fixture_only",
  evidence_class: "fixture_only",
  evidence_witness: { availability: "artifact_missing" },
  generation_cycle_run_id: "fixture://generation-cycle/storybook",
  terminal_distribution: { fixture_only: 1 },
  weakest_links: [
    "Fixture only: no producer-signed weakest boundary is available in Storybook.",
  ],
} satisfies Partial<DepthNDomainRunProjection>);

const freshness = {
  basis: "source_timestamp",
  observed_at: "2026-07-20T12:00:00.000Z",
  source_as_of: null,
  state: "artifact_missing",
} satisfies ProjectionFreshness;

const provenanceQuantity = {
  label: "Fixture-only effect estimate",
  lineage: {
    freshness: "unknown",
    id: "untraced",
    reason_code: "fixture_only_storybook",
    status: "untraced",
    tracking_issue: "DS4-C19",
  },
  metric_id: "fixture_only_effect_estimate",
  point: null,
  quantity_class: "decision",
  time: {
    tx_at: "2026-07-20T12:00:00.000Z",
    valid_at: "2026-07-20T11:58:00.000Z",
  },
  unit: { code: "1", display: "ratio", system: "ucum" },
} satisfies QuantityValue;

const meta = {
  title: "DS4/Evidence Primitives",
  parameters: {
    a11y: {
      test: "error",
    },
    docs: {
      description: {
        component:
          "Fixture-only visual evidence for DS4 primitives. Static stories never supply a value to an authority-bearing slot.",
      },
    },
  },
  tags: ["autodocs"],
} satisfies Meta;

export default meta;

type Story = StoryObj<typeof meta>;

function FixtureBoundary({
  children,
  label,
}: PropsWithChildren<{ label: string }>) {
  return (
    <section
      className="border-line bg-surface/70 space-y-3 rounded-2xl border p-4"
      data-fixture-authority={fixturePayload.fixture_authority}
    >
      <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
        Fixture only · {label}
      </p>
      {children}
    </section>
  );
}

function AuthorityBadgeFixtureRejection() {
  return (
    <section
      className="border-line bg-surface rounded-2xl border p-4"
      data-fixture-rejection={authorityRejection}
      data-testid="authority-badge-fixture-rejection"
    >
      <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
        AuthorityBadge · fixture rejected
      </p>
      <p className="mt-2 text-sm font-semibold">Unavailable</p>
      <p className="text-muted-foreground mt-1 text-xs">{authorityRejection}</p>
    </section>
  );
}

export const CandidateClothing: Story = {
  render: () => (
    <div className="space-y-5">
      <FixtureBoundary label="candidate clothing comparison">
        <CandidateFrame
          block={candidateBlock}
          mayNotUseFor={fixturePacket.may_not_use_for}
          title="Model-authored candidate"
        />
        <div
          className="border-line bg-surface rounded-[var(--radius-panel)] border border-solid p-5"
          data-interaction-state="unavailable"
          data-testid="owner-projection-unavailable"
        >
          <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
            Owner projection clothing reference
          </p>
          <p className="mt-2 text-sm">
            Empty by design — no producer-signed value is available in this
            fixture story.
          </p>
        </div>
      </FixtureBoundary>
    </div>
  ),
};

export const FixtureOnly: Story = {
  render: () => (
    <div className="grid gap-4 sm:grid-cols-2">
      <FixtureBoundary label="typed fixture provenance">
        <EnvelopeChip
          authorityPurpose={fixturePurpose}
          id="story-fixture-envelope"
        />
        <EvidenceLink
          evidenceRef="fixture://evidence/storybook-only"
          fixtureProvenance={fixtureProvenance}
          href="#fixture-evidence"
          id="story-fixture-evidence"
          label="Story evidence"
        />
      </FixtureBoundary>
      <AuthorityBadgeFixtureRejection />
    </div>
  ),
};

export const AllPrimitives: Story = {
  render: () => (
    <div className="grid min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <AuthorityBadgeFixtureRejection />

      <FixtureBoundary label="CandidateFrame · long-copy posture">
        <CandidateFrame
          block={candidateBlock}
          title="Candidate recommendation"
        />
      </FixtureBoundary>

      <FixtureBoundary label="BlockerCard · blocked posture">
        <BlockerCard blocker={blocker} />
      </FixtureBoundary>

      <FixtureBoundary label="EnvelopeChip · unavailable posture">
        <EnvelopeChip
          authorityPurpose={fixturePurpose}
          id="story-envelope-chip"
        />
      </FixtureBoundary>

      <FixtureBoundary label="EvidenceLink · keyboard posture">
        <EvidenceLink
          evidenceRef="fixture://evidence/keyboard-target"
          fixtureProvenance={fixtureProvenance}
          href="#fixture-evidence-keyboard-target"
          id="story-evidence-link"
          label="Focusable fixture reference"
        />
      </FixtureBoundary>

      <FixtureBoundary label="ProvenancePopover · missing lineage posture">
        <div data-testid="provenance-popover-content">
          <ProvenancePopover
            onOpenChange={() => undefined}
            open
            quantity={provenanceQuantity}
          >
            <button className="underline" type="button">
              Fixture provenance details
            </button>
          </ProvenancePopover>
        </div>
      </FixtureBoundary>

      <FixtureBoundary label="TimeSemanticsLabel · artifact-missing posture">
        <TimeSemanticsLabel
          cacheAgeLabel="fixture_only"
          freshness={freshness}
          payloadAsOf={fixturePacket.as_of}
          txAt="2026-07-20T12:00:00.000Z"
          validAt="2026-07-20T11:58:00.000Z"
        />
      </FixtureBoundary>

      <FixtureBoundary label="WeakestLinkExplainer · producer-absent posture">
        <WeakestLinkExplainer projection={domainProjection} />
      </FixtureBoundary>
    </div>
  ),
};
