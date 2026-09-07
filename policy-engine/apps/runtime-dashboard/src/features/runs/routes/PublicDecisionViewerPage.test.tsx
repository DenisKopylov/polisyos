import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import {
  buildPublicDecisionPacket as buildPublicDecisionPacketRaw,
  type PublicDecisionPacketInput,
} from "@/features/runs/domain/publicationPacket";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";
import {
  epochNonreceipt,
  type EpochSemantics,
} from "@/shared/ui/temporal/TimeSemanticsLabel";
import type { PolicyDesignCaseProjection } from "@polisyos/runtime-api-client";

import { publicDecisionViewerRoute } from "@/features/runs/routes.public";
import { forgeLegacyPublicDecisionUrl } from "@/test/forgeLegacyPublicDecisionUrl";

type PacketTestInput = Omit<PublicDecisionPacketInput, "epochSemantics"> & {
  epochSemantics?: EpochSemantics;
};

function buildPublicDecisionPacket(input: PacketTestInput) {
  return buildPublicDecisionPacketRaw({
    ...input,
    epochSemantics: input.epochSemantics ?? epochNonreceipt(),
  });
}

const testDecisionScore = () =>
  untracedDecisionQuantity({ metricId: "test.decision_score", point: 0.74 });

const opaqueProjectionStates = [
  ["missing", "missing evidence label"],
  ["stale", "stale evidence label"],
  ["conflicting", "conflicting evidence label"],
  ["reissued", "reissued evidence label"],
  ["withdrawn", "withdrawn evidence label"],
  ["non_authoritative", "non-authoritative evidence label"],
  ["projection_only", "projection-only evidence label"],
] as const;

function ownerProjection(primaryState: string): PolicyDesignCaseProjection {
  return {
    audience: "public",
    audit_refs: [],
    authoritative_for: [],
    capability_reality_state: "implemented",
    contested_records: [],
    contract_verification_refs: [],
    contract_verification_status: "not_verified",
    deficit_register: [],
    labels: [],
    may_be_used_for: [],
    omission_manifest: [],
    participation_requirements: [],
    projection_gaps: [],
    redacted: false,
    schema_version: "policyos.runtime.policy_design_case.projection.v1",
    authority_role: "projection_only",
    closeout_truth: {
      blocker_codes: [],
      blockers: [],
      can_closeout: false,
      contested_state: "not_contested",
      limitation_codes: [],
      omission_codes: [],
      status: "owner-limited",
      verdict: "owner-contested",
    },
    evidence_class: "owner-extension",
    generated_at: "2026-05-19T10:00:00.000Z",
    may_not_be_used_for: ["scorecard_authority"],
    primary_state: primaryState,
    projection_policy: "reads_policy_design_case_only",
    provenance_kind: "runtime_projection",
    states: [primaryState],
    surface: "public_decision",
  };
}

function renderPublicRoute(url: string) {
  const router = createMemoryRouter([publicDecisionViewerRoute], {
    initialEntries: [url],
  });
  return render(
    <LocaleProvider>
      <RouterProvider router={router} />
    </LocaleProvider>,
  );
}

describe("PublicDecisionViewerPage", () => {
  it("refuses a browser-signed public decision without server verification", async () => {
    const packet = buildPublicDecisionPacket({
      decisionScore: testDecisionScore(),
      runId: "public-run",
    });
    packet.decision.headline = "Forged policy recommendation";
    const forgedUrl = forgeLegacyPublicDecisionUrl(packet);
    renderPublicRoute(forgedUrl);

    // The real registered public route must not treat a recomputed token as evidence.
    expect(await screen.findByText("PolicyOS")).toBeInTheDocument();
    expect(screen.queryByText("signature verified")).not.toBeInTheDocument();
    expect(
      screen.queryByText(packet.decision.headline),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("publication-packet-panel"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Verification unavailable")).toBeInTheDocument();
  });

  it.each([["publishable", "publishable"] as const, ...opaqueProjectionStates])(
    "does not admit a client-supplied %s owner state",
    async (caseId, label) => {
      const packet = buildPublicDecisionPacket({
        policyDesignCaseProjection: ownerProjection(label),
        runId: `public-run-projection-${caseId}`,
      });
      // All framing, state, signature and hash markers remain available to the attacker.
      packet.decision.headline = "Forged owner-issued decision";
      packet.trustFraming.integritySignatureNotice.badge = "Verified";
      packet.trustFraming.integritySignatureNotice.authorityCaveat =
        "Publication authorized";
      renderPublicRoute(forgeLegacyPublicDecisionUrl(packet));

      expect(await screen.findByText("PolicyOS")).toBeInTheDocument();
      expect(screen.queryByText("signature verified")).not.toBeInTheDocument();
      expect(screen.queryByText("Verified")).not.toBeInTheDocument();
      expect(
        screen.queryByText("Publication authorized"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("publication-projection-semantics"),
      ).not.toBeInTheDocument();
      expect(screen.getByText("Verification unavailable")).toBeInTheDocument();
    },
  );

  it.each(["not-valid", "e30.deadbeef", "server-record-looking-id"])(
    "does not invent verification for %s",
    async (id) => {
      renderPublicRoute(`/public/decisions/${id}`);
      expect(await screen.findByText("PolicyOS")).toBeInTheDocument();
      expect(screen.queryByText("signature verified")).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("publication-packet-panel"),
      ).not.toBeInTheDocument();
      expect(screen.getByText("Verification unavailable")).toBeInTheDocument();
    },
  );
});
