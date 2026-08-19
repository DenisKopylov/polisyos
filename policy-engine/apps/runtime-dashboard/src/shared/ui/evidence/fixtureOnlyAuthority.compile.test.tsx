import type { LegacyProvingGroundPayload } from "@polisyos/runtime-api-client";
import {
  AuthorityBadge,
  createOpaqueAuthorityPresentation,
} from "@polisyos/atlas-ui";

describe("fixture-only authority compile barrier", () => {
  it("keeps runtime rejection beside a suppression-free branded consumer", () => {
    const fixtureAuthority =
      "fixture_only" satisfies LegacyProvingGroundPayload["fixture_authority"];
    const presentation = createOpaqueAuthorityPresentation("owner_extension");
    const compileOnly = () => <AuthorityBadge presentation={presentation} />;

    expect(() => createOpaqueAuthorityPresentation(fixtureAuthority)).toThrow(
      /fixture provenance/i,
    );
    expect(compileOnly).toBeTypeOf("function");
  });
});
