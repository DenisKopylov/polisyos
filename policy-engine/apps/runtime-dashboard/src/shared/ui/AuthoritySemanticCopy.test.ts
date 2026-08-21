import { describe, expect, it } from "vitest";

import {
  admitAuthoritySemanticReviewReceipt,
  assertIssuedAuthoritySemanticCopy,
  presentMayNotUseFor,
  presentSemanticCopy,
} from "./AuthoritySemanticCopy";

describe("AuthoritySemanticCopy", () => {
  it("limited semantic ID cannot upgrade strength", () => {
    const presentation = presentSemanticCopy({
      locale: "en",
      semanticId: "phase34.harm.risk.limited",
      sourceToken: "harm_risk",
      scope: "governed_projection.rights_bar",
    });

    expect(presentation.strength).toBe("limited");
    expect(presentation.authorityClass).toBe("verification_missing");
  });

  it("may_not_use_for cannot become optional recommendation", () => {
    const presentation = presentMayNotUseFor({
      ownerToken: "optional_recommendation",
      scope: "governed_projection.rights_bar",
    });

    expect(presentation.text).toBe("optional_recommendation");
    expect(presentation.strength).toBe("limited");
    expect(presentation.authorityClass).toBe("verification_missing");
  });

  it("authority copy requires branded semantic receipt", () => {
    expect(() =>
      admitAuthoritySemanticReviewReceipt({
        contentHash:
          "sha256:28fb42a4a99f4293d47318a3cb821e26c3f83482583bbba7f12459d32db23a07",
        reviewerIdentity: "external-reviewer:policy-language",
        reviewerScope: "authority-copy.en.governed_projection.rights_bar",
        reviewerVersion: "v1",
        semanticId: "phase34.harm.risk.limited",
      }),
    ).toThrow("not accepted");
  });

  it("same semantic ID has one active copy per locale and scope", () => {
    expect(() =>
      presentSemanticCopy({
        locale: "uk",
        semanticId: "phase34.harm.risk.limited",
        sourceToken: "harm_risk",
        scope: "governed_projection.rights_bar",
      }),
    ).toThrow("semantic review receipt");
  });

  it("refuses mismatched and novel scope before issuing copy", () => {
    expect(() =>
      presentSemanticCopy({
        locale: "en",
        semanticId: "phase34.harm.risk.limited",
        sourceToken: "harm_risk",
        scope: "other" as never,
      }),
    ).toThrow("scope");
    expect(() =>
      presentMayNotUseFor({
        ownerToken: "harm_risk",
        scope: "other" as never,
      }),
    ).toThrow("scope");
  });

  it("rejects forged, stale, and scope-mismatched review inputs", () => {
    const input = {
      contentHash:
        "sha256:28fb42a4a99f4293d47318a3cb821e26c3f83482583bbba7f12459d32db23a07",
      reviewerIdentity: "external-reviewer:policy-language",
      reviewerScope: "authority-copy.en.governed_projection.rights_bar",
      reviewerVersion: "v1",
      semanticId: "phase34.harm.risk.limited" as const,
    };

    for (const mutation of [
      { ...input, contentHash: "sha256:" + "0".repeat(64) },
      { ...input, reviewerIdentity: "external-reviewer:forged" },
      { ...input, reviewerScope: "authority-copy.en.unrelated" },
      { ...input, reviewerVersion: "stale" },
    ]) {
      expect(() => admitAuthoritySemanticReviewReceipt(mutation)).toThrow(
        "content-bound",
      );
    }

    expect(() =>
      assertIssuedAuthoritySemanticCopy({
        authorityClass: "verification_missing",
        semanticId: "phase34.harm.risk.limited",
        strength: "limited",
        text: "Limited harm-risk authority",
      }),
    ).toThrow("issuer-derived");
  });

  it("freezes issued copy and preserves opaque novel owner tokens", () => {
    const presentation = presentMayNotUseFor({
      ownerToken: "novel_owner_token",
      scope: "governed_projection.rights_bar",
    });

    expect(Object.isFrozen(presentation)).toBe(true);
    expect(() => assertIssuedAuthoritySemanticCopy(presentation)).not.toThrow();
    expect(presentation.text).toBe("novel_owner_token");
    expect(presentation.semanticId).toBe(
      "generated:GovernedProjectionPacket.may_not_use_for:novel_owner_token",
    );
  });
});
