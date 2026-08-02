import type { LegacyProvingGroundPayload } from "@polisyos/runtime-api-client";
import { AuthorityBadge, EvidenceLink } from "@polisyos/atlas-ui";

describe("fixture-only authority compile barrier", () => {
  it("rejects fixture_only at an authority-bearing prop boundary", () => {
    const fixtureAuthority =
      "fixture_only" satisfies LegacyProvingGroundPayload["fixture_authority"];
    const widenedFixture: string = fixtureAuthority;
    const structuralLookalike = {
      authority: "approved",
      presentation: "recognized" as const,
      source: "opaque_extension" as const,
      tone: "ok" as const,
    };
    const compileOnly = () => (
      <>
        {/* @ts-expect-error A raw generated literal is not owner-derived presentation. */}
        <AuthorityBadge presentation={fixtureAuthority} />
        {/* @ts-expect-error Widening cannot evade the nominal presentation barrier. */}
        <AuthorityBadge presentation={widenedFixture} />
        {/* @ts-expect-error A structural lookalike cannot forge private issuance. */}
        <AuthorityBadge presentation={structuralLookalike} />
        <EvidenceLink
          evidenceRef="fixture:evidence"
          // @ts-expect-error A raw flag is not generated-payload provenance proof.
          fixtureProvenance={fixtureAuthority}
        />
      </>
    );

    expect(compileOnly).toBeTypeOf("function");
  });
});
