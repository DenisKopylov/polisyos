import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { buildSignedPublicDecisionPacket } from "@/features/runs/domain/publicationPacket";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";
import type { PolicyDesignCaseProjection } from "@polisyos/runtime-api-client";

import PublicDecisionViewerPage from "./PublicDecisionViewerPage";

const testDecisionScore = () =>
  untracedDecisionQuantity({ metricId: "test.decision_score", point: 0.74 });

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) =>
      params?.reason ? `${key}:${params.reason}` : key,
  }),
}));

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

describe("PublicDecisionViewerPage", () => {
  it("renders a verified signed public decision without API context", async () => {
    const packet = buildSignedPublicDecisionPacket({
      decisionScore: testDecisionScore(),
      runId: "public-run",
    });

    render(
      <MemoryRouter initialEntries={[packet.publicUrlPath]}>
        <Routes>
          <Route
            path="/public/decisions/:signedId"
            element={<PublicDecisionViewerPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByTestId("publication-packet-panel"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("signed-public-summary")).toBeInTheDocument();
    expect(screen.getByTestId("argument-map-panel")).toBeInTheDocument();
    expect(screen.getByTestId("citation-model-card-panel")).toBeInTheDocument();
    expect(screen.getByTestId("coverage-caveat-panel")).toBeInTheDocument();
    expect(screen.getByTestId("threshold-contract-panel")).toBeInTheDocument();
    expect(screen.getByText("phase35.viewer.verified")).toBeInTheDocument();
  });

  it("renders an owner publishable state neutrally without inventing blocked", async () => {
    const packet = buildSignedPublicDecisionPacket({
      decisionScore: testDecisionScore(),
      policyDesignCaseProjection: ownerProjection("publishable"),
      runId: "public-run-projection",
    });

    render(
      <MemoryRouter initialEntries={[packet.publicUrlPath]}>
        <Routes>
          <Route
            path="/public/decisions/:signedId"
            element={<PublicDecisionViewerPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    const semantics = await screen.findByTestId(
      "publication-projection-semantics",
    );

    expect(semantics).toHaveTextContent("publishable");
    expect(semantics).toHaveTextContent("projection_only");
    expect(semantics).not.toHaveTextContent("blocked");
  });

  it.each(opaqueProjectionStates)(
    "preserves an opaque %s owner state in the public viewer",
    async (caseId, label) => {
      const packet = buildSignedPublicDecisionPacket({
        decisionScore: testDecisionScore(),
        policyDesignCaseProjection: ownerProjection(label),
        runId: `public-run-projection-${caseId}`,
      });

      render(
        <MemoryRouter initialEntries={[packet.publicUrlPath]}>
          <Routes>
            <Route
              path="/public/decisions/:signedId"
              element={<PublicDecisionViewerPage />}
            />
          </Routes>
        </MemoryRouter>,
      );

      const semantics = await screen.findByTestId(
        "publication-projection-semantics",
      );

      expect(semantics).toHaveTextContent(label);
      expect(semantics).toHaveTextContent("projection_only");
      expect(semantics).not.toHaveTextContent("blocked");
    },
  );

  it("rejects invalid signed ids", () => {
    render(
      <MemoryRouter initialEntries={["/public/decisions/not-valid"]}>
        <Routes>
          <Route
            path="/public/decisions/:signedId"
            element={<PublicDecisionViewerPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("public-decision-invalid")).toBeInTheDocument();
    expect(screen.getByText("phase35.viewer.invalid")).toBeInTheDocument();
  });
});
