import {
  authorityStatusBadgeProps,
  issueApprovalAvailabilityPresentation,
  issueAuthorityCountPresentation,
  issueHumanDecisionEvidencePresentation,
  issueHumanDecisionGatePresentation,
  issueHumanDecisionReviewCoveragePresentation,
  issueLegalReviewPresentation,
  issueOpaqueAuthorityStatusPresentation,
  issueReviewRequiredPresentation,
} from "./AuthorityStatusPresentation";

describe("AuthorityStatusPresentation", () => {
  it("weakest mixed outcome wins and novelty is unrecognized", () => {
    const mixed = issueApprovalAvailabilityPresentation(
      [true, false],
      "approval_ready",
    );
    const novel = issueOpaqueAuthorityStatusPresentation("future-owner-state");

    expect(mixed).toMatchObject({
      ownerLabel: "approval_ready",
      recognition: "recognized",
      tone: "fail",
    });
    expect(novel).toMatchObject({
      ownerLabel: "future-owner-state",
      recognition: "unrecognized",
      tone: "neutral",
    });
    expect(Object.isFrozen(mixed)).toBe(true);
    expect(Object.isFrozen(novel)).toBe(true);
    expect(authorityStatusBadgeProps(novel)).toMatchObject({
      "data-authority-recognition": "unrecognized",
      "data-presentation-tone": "neutral",
      kind: "neutral",
    });

    const forged = { ...novel } as typeof novel;
    expect(() => authorityStatusBadgeProps(forged)).toThrow(
      "authority status presentation must be privately issued",
    );
  });

  it("keeps legal review exhaustive while rejecting runtime novelty", () => {
    expect(
      issueLegalReviewPresentation("pending_external_review"),
    ).toMatchObject({ recognition: "recognized", tone: "warn" });
    expect(issueLegalReviewPresentation("approved")).toMatchObject({
      recognition: "recognized",
      tone: "ok",
    });
    expect(issueLegalReviewPresentation("rejected")).toMatchObject({
      recognition: "recognized",
      tone: "fail",
    });
    expect(
      issueLegalReviewPresentation(
        "future-owner-state" as Parameters<
          typeof issueLegalReviewPresentation
        >[0],
      ),
    ).toMatchObject({ recognition: "unrecognized", tone: "neutral" });
  });

  it("issues generated human-decision vocabularies and rejects novelty", () => {
    expect(issueHumanDecisionGatePresentation("available")).toMatchObject({
      recognition: "recognized",
      tone: "ok",
    });
    expect(issueHumanDecisionGatePresentation("blocked")).toMatchObject({
      recognition: "recognized",
      tone: "fail",
    });
    expect(
      issueHumanDecisionGatePresentation(
        "future-gate" as Parameters<
          typeof issueHumanDecisionGatePresentation
        >[0],
      ),
    ).toMatchObject({ recognition: "unrecognized", tone: "neutral" });
    expect(issueHumanDecisionEvidencePresentation(true)).toMatchObject({
      recognition: "recognized",
      tone: "ok",
    });
    expect(issueHumanDecisionEvidencePresentation(false)).toMatchObject({
      recognition: "recognized",
      tone: "fail",
    });
    expect(
      issueHumanDecisionReviewCoveragePresentation("incomplete"),
    ).toMatchObject({ recognition: "recognized", tone: "warn" });
  });

  it("missing or malformed review facts cannot present a stable queue", () => {
    expect(issueReviewRequiredPresentation(undefined)).toMatchObject({
      ownerLabel: "unrecognized",
      recognition: "unrecognized",
      tone: "neutral",
    });
    expect(issueReviewRequiredPresentation([false, undefined])).toMatchObject({
      recognition: "unrecognized",
      tone: "neutral",
    });
    expect(issueReviewRequiredPresentation([false, false])).toMatchObject({
      ownerLabel: "not_required",
      recognition: "recognized",
      tone: "ok",
    });
    expect(issueReviewRequiredPresentation([false, true])).toMatchObject({
      ownerLabel: "review_required",
      recognition: "recognized",
      tone: "warn",
    });
  });

  it("governance counts remain informational rather than composed authority", () => {
    for (const kind of ["passed", "failed", "warnings"] as const) {
      expect(issueAuthorityCountPresentation(kind, 7)).toMatchObject({
        ownerLabel: `${kind}:7`,
        recognition: "informational",
        tone: "outline",
      });
    }
  });
});
