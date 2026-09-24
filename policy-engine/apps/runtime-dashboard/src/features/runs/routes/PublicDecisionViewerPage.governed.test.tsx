import { act, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { publicDecisionViewerRoute } from "@/features/runs/routes.public";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

const recordId = `gpr_${"a".repeat(32)}`;
const notEstablished = {
  public_history_establishment: "not_established",
  durable_verifiability: "not_established",
  current_authority: "not_established",
  status_snapshot_selection: "not_established",
  public_evidence_obtainability: "not_established",
};

function governedRecord() {
  const publicDocumentDigest = `sha256:${"a".repeat(64)}`;
  const decisionId = `gph_${"d".repeat(32)}`;
  const runId = `gph_${"r".repeat(32)}`;
  const claimId = `gph_${"c".repeat(32)}`;
  return {
    record_id: recordId,
    publication_class: "governed_public_record",
    report_authentication: "verified",
    cryptographic_signature: "valid",
    report_key_status: "trusted",
    reason_codes: [] as string[],
    decision_id: decisionId,
    issuer_id: "appointed-publication-issuer",
    issued_at: "2026-09-12T12:00:00Z",
    public_document_digest: publicDocumentDigest,
    public_document: {
      schema_version: "polisyos.governed_public_document.v1",
      profile: "exact_owner_ledger_v1",
      ledger: {
        schema_version: "2.0",
        run_id: runId,
        base_ledger_ref: null,
        current_claims: [
          {
            schema_version: "1.0",
            claim_id: claimId,
            run_id: runId,
            claim_type: "factual",
            claim_family: null,
            claim_use: null,
            text: "The retained observation applies only within the declared interval.",
            normalized_subject: null,
            support_status: "supported",
            publishability: "publishable",
            readiness_level: "research_artifact",
            facet_refs: [],
            obligation_refs: [],
            concept_spine_refs: [],
            authority_profile_refs: [],
            baseline_refs: [],
            alternative_refs: [],
            comparison_refs: [],
            method_need_preconditions: [],
            decomposition_source_class: null,
            evidence_refs: [],
            counterevidence_refs: [],
            uncertainty_profile_ref: null,
            provenance_ref: null,
            source_attribution: [],
            reviewer_refs: [],
            blocked_reasons: [],
            metadata: {},
          },
        ],
        events: [
          {
            schema_version: "1.0",
            event_id: `gph_${"e".repeat(32)}`,
            claim_id: claimId,
            run_id: runId,
            action: "created",
            occurred_at: "2026-09-11T12:00:00Z",
            actor_id: `gph_${"o".repeat(32)}`,
            reason: "Claim entered the owner ledger.",
            previous_claim_ref: null,
            next_claim_ref: null,
            evidence_refs: [],
            reviewer_refs: [],
            metadata: {
              claim_type: "factual",
              support_status: "supported",
              publishability: "publishable",
              readiness_level: "research_artifact",
            },
          },
        ],
        retention_policy: { max_events: 20 },
        metadata: { base_schema_version: "1.0", created_by_node_id: null },
      },
      permitted_uses: ["bounded_public_custody"],
      denied_uses: [
        "policy_performance",
        "current_policy_authority",
        "complete_public_history",
        "first_publication",
      ],
      limitations: [
        "Exact assertions and statuses from the initial immutable owner-admitted root snapshot; transition heads are unsupported by this publication profile.",
        "No independent policy-performance claim.",
        "Publication time dates this issuance; historical or live snapshot selection and pending-event cutoff are not established.",
        "gph_ opaque reference handles preserve relations and JSON types; they are not CAS addresses or evidence retrieval URLs.",
        "Public evidence obtainability is not established.",
        "No claim of complete public history, first publication, current authority or indefinite durability.",
        "Disclosure proof covers this exact source tree and public proof metadata, not external side channels.",
      ],
    },
    promoted_record: {
      schema_version: "polisyos.governed_public_record.v1",
      record_id: recordId,
      decision_id: decisionId,
      issuer_id: "appointed-publication-issuer",
      signing_key_id: `sha256:${"b".repeat(64)}`,
      purpose: "governed_public_record",
      rule_version: "governed-public-record.v1",
      issued_at: "2026-09-12T12:00:00Z",
      public_document_digest: publicDocumentDigest,
      publication_class: "governed_public_record",
    },
    dimensions: {
      issuer_issuance: "established",
      projection_faithfulness: "established",
      ...notEstablished,
    },
  };
}

function unavailableRecord() {
  return {
    ...governedRecord(),
    report_authentication: "not_established",
    cryptographic_signature: "not_established",
    report_key_status: "not_established",
    reason_codes: ["record_not_issued"],
    decision_id: null,
    issuer_id: null,
    issued_at: null,
    public_document_digest: null,
    public_document: null,
    promoted_record: null,
    dimensions: {
      ...notEstablished,
      issuer_issuance: "not_established",
      projection_faithfulness: "not_established",
    },
  };
}

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
}

function renderPublicRoute(id = recordId) {
  const router = createMemoryRouter([publicDecisionViewerRoute], {
    initialEntries: [`/public/decisions/${id}`],
  });
  render(
    <LocaleProvider>
      <RouterProvider router={router} />
    </LocaleProvider>,
  );
  return router;
}

const fetchVerification = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchVerification.mockReset();
  vi.stubGlobal("fetch", fetchVerification);
});

afterEach(() => vi.unstubAllGlobals());

describe("governed public record viewer", () => {
  it.each(["trusted", "revoked"])(
    "retains the entire document and independent dimensions with a %s signing key",
    async (reportKeyStatus) => {
      const record = {
        ...governedRecord(),
        report_key_status: reportKeyStatus,
      };
      fetchVerification.mockResolvedValue(jsonResponse(record));
      renderPublicRoute();

      expect(
        await screen.findByRole("heading", { name: "Governed public record" }),
      ).toBeInTheDocument();
      const document = screen.getByTestId("governed-public-document");
      // Compare the whole consumed tree, including nested owner event statuses.
      expect(JSON.parse(document.textContent ?? "")).toEqual(
        record.public_document,
      );
      expect(document).toHaveTextContent('"publishability": "publishable"');
      expect(document).toHaveTextContent('"action": "created"');
      expect(screen.getByTestId("governed-record-issuer")).toHaveTextContent(
        record.issuer_id,
      );
      expect(screen.getByTestId("governed-record-issued-at")).toHaveTextContent(
        record.issued_at,
      );
      expect(
        screen.getByTestId("governed-record-key-status"),
      ).toHaveTextContent(
        reportKeyStatus === "trusted" ? "Trusted" : "Revoked",
      );
      for (const dimension of ["issuer_issuance", "projection_faithfulness"]) {
        expect(
          screen.getByTestId(`verification-dimension-${dimension}`),
        ).toHaveTextContent("Established");
        expect(
          screen.getByTestId(`verification-dimension-${dimension}`),
        ).not.toHaveTextContent("Not established");
      }
      for (const dimension of Object.keys(notEstablished)) {
        expect(
          screen.getByTestId(`verification-dimension-${dimension}`),
        ).toHaveTextContent("Not established");
      }
      expect(screen.getByText("Bounded public custody")).toBeInTheDocument();
      expect(screen.getByText("Current policy authority")).toBeInTheDocument();
      expect(
        screen.queryByText("Decision verified", { exact: true }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("public-verification-record"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("publication-packet-panel"),
      ).not.toBeInTheDocument();
      expect(screen.queryByText(/historical issuance/i) !== null).toBe(
        reportKeyStatus === "revoked",
      );
    },
  );

  it("renders every current claim's exact text and independent source states", async () => {
    const record = governedRecord();
    const ledger = record.public_document.ledger;
    const secondClaim = {
      ...ledger.current_claims[0]!,
      claim_id: `gph_${"s".repeat(32)}`,
      text: "The second retained assertion has a separate declared use.",
      readiness_level: "external_briefing",
    };
    ledger.current_claims.push(secondClaim);
    ledger.events.push({
      ...ledger.events[0]!,
      claim_id: secondClaim.claim_id,
      event_id: `gph_${"f".repeat(32)}`,
      metadata: {
        ...ledger.events[0]!.metadata,
        readiness_level: secondClaim.readiness_level,
      },
    });
    fetchVerification.mockResolvedValue(jsonResponse(record));
    renderPublicRoute();

    const claims = await screen.findByTestId("governed-public-claims");
    expect(within(claims).getAllByRole("article")).toHaveLength(
      ledger.current_claims.length,
    );
    for (const claim of ledger.current_claims) {
      const rendered = within(
        screen.getByTestId(`governed-public-claim-${claim.claim_id}`),
      );
      expect(
        rendered.getByText(claim.text, { exact: true }),
      ).toBeInTheDocument();
      expect(
        rendered.getByText(claim.support_status, { exact: true }),
      ).toBeInTheDocument();
      expect(
        rendered.getByText(claim.publishability, { exact: true }),
      ).toBeInTheDocument();
      expect(
        rendered.getByText(claim.readiness_level, { exact: true }),
      ).toBeInTheDocument();
    }
    expect(
      JSON.parse(
        screen.getByTestId("governed-public-document").textContent ?? "",
      ),
    ).toEqual(record.public_document);
  });

  const malformedRecords: [
    string,
    (record: ReturnType<typeof governedRecord>) => unknown,
  ][] = [
    ...(
      ["text", "support_status", "publishability", "readiness_level"] as const
    ).map(
      (
        field,
      ): [string, (record: ReturnType<typeof governedRecord>) => unknown] => [
        `malformed claim ${field}`,
        (r) => ({
          ...r,
          public_document: {
            ...r.public_document,
            ledger: {
              ...r.public_document.ledger,
              current_claims: r.public_document.ledger.current_claims.map(
                (claim) => ({
                  ...claim,
                  [field]: null,
                }),
              ),
            },
          },
        }),
      ],
    ),
    [
      "candidate publication class",
      (r) => ({ ...r, publication_class: "candidate" }),
    ],
    [
      "missing governed discriminator",
      (r) => ({ ...r, publication_class: undefined }),
    ],
    [
      "report-only document",
      (r) => ({ ...r, public_document: { title: "Candidate preview" } }),
    ],
    [
      "candidate profile",
      (r) => ({
        ...r,
        public_document: { ...r.public_document, profile: "candidate_preview" },
      }),
    ],
    [
      "different document schema",
      (r) => ({
        ...r,
        public_document: { ...r.public_document, schema_version: "1.0" },
      }),
    ],
    [
      "removed denied use",
      (r) => ({
        ...r,
        public_document: { ...r.public_document, denied_uses: [] },
      }),
    ],
    [
      "invented permitted use",
      (r) => ({
        ...r,
        public_document: {
          ...r.public_document,
          permitted_uses: ["policy_performance"],
        },
      }),
    ],
    [
      "missing limitations",
      (r) => ({
        ...r,
        public_document: { ...r.public_document, limitations: undefined },
      }),
    ],
    [
      "missing current claims",
      (r) => ({
        ...r,
        public_document: {
          ...r.public_document,
          ledger: { ...r.public_document.ledger, current_claims: [] },
        },
      }),
    ],
    [
      "malformed lifecycle",
      (r) => ({
        ...r,
        public_document: {
          ...r.public_document,
          ledger: { ...r.public_document.ledger, events: "withdrawn" },
        },
      }),
    ],
    [
      "candidate signing purpose",
      (r) => ({
        ...r,
        promoted_record: {
          ...r.promoted_record,
          purpose: "public_decision_verification_report",
        },
      }),
    ],
    [
      "different signing rule",
      (r) => ({
        ...r,
        promoted_record: { ...r.promoted_record, rule_version: "candidate.v1" },
      }),
    ],
    ["absent promoted record", (r) => ({ ...r, promoted_record: null })],
    [
      "invalid signature",
      (r) => ({ ...r, cryptographic_signature: "invalid" }),
    ],
    [
      "untrusted signing key",
      (r) => ({ ...r, report_key_status: "untrusted" }),
    ],
    [
      "unverified content",
      (r) => ({ ...r, report_authentication: "not_established" }),
    ],
    [
      "unestablished projection",
      (r) => ({
        ...r,
        dimensions: {
          ...r.dimensions,
          projection_faithfulness: "not_established",
        },
      }),
    ],
    [
      "invented current authority",
      (r) => ({
        ...r,
        dimensions: { ...r.dimensions, current_authority: "established" },
      }),
    ],
    ["extra authority marker", (r) => ({ ...r, decision_verified: true })],
    [
      "private ref on public record",
      (r) => ({
        ...r,
        promoted_record: {
          ...r.promoted_record,
          mandate_ref: { digest: `sha256:${"e".repeat(64)}` },
        },
      }),
    ],
    ...(
      [
        "record_id",
        "decision_id",
        "issuer_id",
        "issued_at",
        "public_document_digest",
      ] as const
    ).map(
      (
        field,
      ): [string, (record: ReturnType<typeof governedRecord>) => unknown] => [
        `unbound ${field}`,
        (r) => ({
          ...r,
          promoted_record: {
            ...r.promoted_record,
            [field]:
              field === "issued_at"
                ? "2026-09-11T12:00:00Z"
                : field === "public_document_digest"
                  ? `sha256:${"c".repeat(64)}`
                  : `gpr_${"z".repeat(32)}`,
          },
        }),
      ],
    ),
  ];

  it.each(malformedRecords)(
    "withholds the document for %s",
    async (_, substitute) => {
      fetchVerification.mockResolvedValue(
        jsonResponse(substitute(governedRecord())),
      );
      renderPublicRoute();
      expect(
        await screen.findByTestId("public-decision-unavailable"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("governed-public-document"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByText(/The retained observation applies/),
      ).not.toBeInTheDocument();
    },
  );

  it("does not interpret a report-only response as a governed record", async () => {
    const { publication_class: _, ...response } = unavailableRecord();
    fetchVerification.mockResolvedValue(jsonResponse(response));
    renderPublicRoute();
    expect(
      await screen.findByText(/verification_request_failed/),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("governed-public-document"),
    ).not.toBeInTheDocument();
  });

  it("withholds absent records and does not render freeform authority reasons", async () => {
    fetchVerification.mockResolvedValue(
      jsonResponse({
        ...unavailableRecord(),
        reason_codes: ["Decision verified"],
      }),
    );
    renderPublicRoute();
    expect(
      await screen.findByTestId("public-decision-unavailable"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Decision verified/)).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("governed-public-document"),
    ).not.toBeInTheDocument();
  });

  it.each([`gpr_${"a".repeat(31)}`, `gpr_${"a".repeat(33)}`, "gpr_candidate"])(
    "refuses a positive response for malformed public identifier %s",
    async (id) => {
      const record = governedRecord();
      fetchVerification.mockResolvedValue(
        jsonResponse({
          ...record,
          record_id: id,
          promoted_record: { ...record.promoted_record, record_id: id },
        }),
      );
      renderPublicRoute(id);
      expect(
        await screen.findByTestId("public-decision-unavailable"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("governed-public-document"),
      ).not.toBeInTheDocument();
    },
  );

  it("removes a governed record on navigation and ignores its late readback", async () => {
    let finishRead!: (response: Response) => void;
    fetchVerification.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishRead = resolve;
        }),
    );
    const nextId = `gpr_${"n".repeat(32)}`;
    fetchVerification.mockResolvedValueOnce(
      jsonResponse({ ...unavailableRecord(), record_id: nextId }),
    );
    const router = renderPublicRoute();
    await waitFor(() => expect(fetchVerification).toHaveBeenCalledTimes(1));
    const signal = fetchVerification.mock.calls[0]?.[1]?.signal;
    await act(() => router.navigate(`/public/decisions/${nextId}`));
    expect(signal?.aborted).toBe(true);
    expect(
      await screen.findByTestId("public-decision-unavailable"),
    ).toBeInTheDocument();
    await act(async () => finishRead(jsonResponse(governedRecord())));
    expect(
      screen.queryByTestId("governed-public-document"),
    ).not.toBeInTheDocument();
  });
});
