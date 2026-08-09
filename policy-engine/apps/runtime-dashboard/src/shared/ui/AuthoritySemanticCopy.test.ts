import { describe, expect, it } from "vitest";

import {
  createAuthoritySemanticReviewReceipt,
  presentMayNotUseFor,
} from "./AuthoritySemanticCopy";

describe("AuthoritySemanticCopy", () => {
  it("requires an admitted branded semantic receipt before closed authority copy is issued", () => {
    const receipt = createAuthoritySemanticReviewReceipt({
      contentHash:
        "sha256:28fb42a4a99f4293d47318a3cb821e26c3f83482583bbba7f12459d32db23a07",
      reviewerIdentity: "external-reviewer:policy-language",
      reviewerScope: "authority-copy.en.governed_projection.rights_bar",
      reviewerVersion: "v1",
      semanticId: "phase34.harm.risk.limited",
    });

    expect(() =>
      presentMayNotUseFor({
        canonicalSemanticId: "phase34.harm.risk.limited",
        locale: "en",
        ownerToken: "harm_risk",
        receipt,
        scope: "governed_projection.rights_bar",
      }),
    ).toThrow("semantic review receipt");
  });

  it("cannot upgrade a limited semantic ID through plausible copy", () => {
    const receipt = createAuthoritySemanticReviewReceipt({
      contentHash:
        "sha256:9a7ee02d480dedff8fe3c9308b1c7e72941d67265706ef7ecf8d0a9e6b85c41f",
      reviewerIdentity: "external-reviewer:policy-language",
      reviewerScope: "authority-copy.en.governed_projection.rights_bar",
      reviewerVersion: "v1",
      semanticId: "phase34.harm.risk.limited",
    });

    expect(() =>
      presentMayNotUseFor({
        canonicalSemanticId: "phase34.harm.risk.limited",
        locale: "en",
        ownerToken: "harm_risk",
        receipt,
        scope: "governed_projection.rights_bar",
      }),
    ).toThrow("semantic review receipt");
  });

  it("preserves may_not_use_for as a neutral owner token", () => {
    const presentation = presentMayNotUseFor({
      ownerToken: "optional_recommendation",
      scope: "governed_projection.rights_bar",
    });

    expect(presentation.text).toBe("optional_recommendation");
    expect(presentation.authorityClass).toBe("verification_missing");
    expect(presentation.strength).toBe("limited");
  });
});
