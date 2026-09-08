import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import { act, render, screen, waitFor } from "@testing-library/react";
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
  render(
    <LocaleProvider>
      <RouterProvider router={router} />
    </LocaleProvider>,
  );
  return router;
}

const recordId = "record-authenticated-1";
const dimensionNames = [
  "issuer_issuance",
  "projection_faithfulness",
  "public_history_establishment",
  "durable_verifiability",
  "current_authority",
  "status_snapshot_selection",
  "public_evidence_obtainability",
] as const;

function authenticatedRecord() {
  return {
    record_id: recordId,
    report_authentication: "verified",
    cryptographic_signature: "valid",
    report_key_status: "trusted",
    reason_codes: [],
    decision_id: "candidate-decision-1",
    issuer_id: "verification-report-service",
    issued_at: "2026-09-07T12:00:00Z",
    public_document_digest: `sha256:${"a".repeat(64)}`,
    public_document: { title: "Authenticated candidate preview" },
    promoted_record: null,
    dimensions: Object.fromEntries(
      dimensionNames.map((name) => [name, "not_established"]),
    ),
  };
}

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
}

const fetchVerification = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchVerification.mockReset();
  fetchVerification.mockImplementation(async (input) => {
    const id = new URL(String(input)).searchParams.get("record_id");
    return jsonResponse({
      record_id: id,
      report_authentication: id?.includes(".") ? "invalid" : "not_established",
      cryptographic_signature: "not_established",
      report_key_status: "not_established",
      reason_codes: [
        id?.includes(".")
          ? "client_token_not_server_issued"
          : "record_not_issued",
      ],
      decision_id: null,
      issuer_id: null,
      issued_at: null,
      public_document_digest: null,
      public_document: null,
      promoted_record: null,
      dimensions: Object.fromEntries(
        dimensionNames.map((name) => [name, "not_established"]),
      ),
    });
  });
  vi.stubGlobal("fetch", fetchVerification);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

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
    expect(
      await screen.findByText(/client_token_not_server_issued/),
    ).toBeInTheDocument();
    const request = new URL(String(fetchVerification.mock.calls[0]?.[0]));
    expect(request.pathname).toBe("/api/v1/public-decisions/verification");
    expect(request.searchParams.get("record_id")).toBe(
      forgedUrl.split("/").at(-1),
    );
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
      expect(
        await screen.findByText(/client_token_not_server_issued/),
      ).toBeInTheDocument();
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
      expect(
        await screen.findByText(
          /client_token_not_server_issued|record_not_issued/,
        ),
      ).toBeInTheDocument();
    },
  );

  it("authenticates a server record without granting decision authority", async () => {
    fetchVerification.mockResolvedValue(jsonResponse(authenticatedRecord()));
    renderPublicRoute(`/public/decisions/${recordId}`);

    expect(
      await screen.findByText("Verification record authenticated"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Authenticated candidate preview" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/does not establish publication authority/i),
    ).toBeInTheDocument();
    for (const dimension of dimensionNames) {
      expect(
        screen.getByTestId(`verification-dimension-${dimension}`),
      ).toHaveTextContent("Not established");
    }
    expect(
      screen.queryByText("Decision verified", { exact: true }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("signature verified")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("publication-packet-panel"),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["report authentication", { report_authentication: "invalid" }],
    ["cryptographic signature", { cryptographic_signature: "invalid" }],
    ["revoked report key", { report_key_status: "revoked" }],
    ["untrusted report key", { report_key_status: "untrusted" }],
    ["record identity", { record_id: "different-record" }],
    ["unknown status", { report_authentication: "VERIFIED" }],
    ["invented decision authority", { promoted_record: { verified: true } }],
    ["extra authority marker", { decision_verified: true }],
    ["missing dimensions", { dimensions: {} }],
    [
      "claimed current authority",
      {
        dimensions: {
          ...authenticatedRecord().dimensions,
          current_authority: "verified",
        },
      },
    ],
    ["malformed reasons", { reason_codes: "verified" }],
    ["freeform authority reason", { reason_codes: ["Decision verified"] }],
  ])(
    "withholds the document when %s is removed or substituted",
    async (_, changed) => {
      // Keep document, issuer, digest and positive status markers except the tested property.
      fetchVerification.mockResolvedValue(
        jsonResponse({ ...authenticatedRecord(), ...changed }),
      );
      renderPublicRoute(`/public/decisions/${recordId}`);

      expect(
        await screen.findByTestId("public-decision-unavailable"),
      ).toBeInTheDocument();
      expect(
        screen.queryByText("Authenticated candidate preview"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByText("Verification record authenticated"),
      ).not.toBeInTheDocument();
    },
  );

  it("fails closed when the verifier cannot respond", async () => {
    fetchVerification.mockRejectedValue(new TypeError("Network unavailable"));
    renderPublicRoute(`/public/decisions/${recordId}`);
    expect(
      await screen.findByText(/verification_request_failed/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Verification record authenticated"),
    ).not.toBeInTheDocument();
  });

  it("does not display a late authenticated response after the record changes", async () => {
    let completeOldRequest!: (response: Response) => void;
    fetchVerification.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          completeOldRequest = resolve;
        }),
    );
    const router = renderPublicRoute(`/public/decisions/${recordId}`);
    await waitFor(() => expect(fetchVerification).toHaveBeenCalledTimes(1));
    const firstSignal = fetchVerification.mock.calls[0]?.[1]?.signal;
    await act(() => router.navigate("/public/decisions/another-record"));
    expect(firstSignal?.aborted).toBe(true);
    expect(await screen.findByText(/record_not_issued/)).toBeInTheDocument();
    await act(async () => {
      completeOldRequest(jsonResponse(authenticatedRecord()));
    });

    expect(
      screen.queryByText("Authenticated candidate preview"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Verification record authenticated"),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/record_not_issued/)).toBeInTheDocument();
  });
});
