import { describe, expect, expectTypeOf, it } from "vitest";

import {
  createInteractionState,
  type GeneratedAuthorityValue,
  type InteractionState,
  presentAuthority,
} from "./statusOwnership";

describe("status ownership compile barriers", () => {
  it("rejects divergent DisputeStatus vocabularies", () => {
    type CanonicalDisputeStatus =
      | "none"
      | "disputed"
      | "under_review"
      | "resolved";
    type DivergentDisputeStatus = CanonicalDisputeStatus | "open";

    const canonical =
      "disputed" as GeneratedAuthorityValue<CanonicalDisputeStatus>;
    presentAuthority(canonical);

    const divergent = "open" as DivergentDisputeStatus;
    const transport = createInteractionState("open", "transport");
    const compileOnly = () => {
      // @ts-expect-error A naked or divergent local union is not generated authority.
      presentAuthority(divergent);
      // @ts-expect-error InteractionState is structurally barred from authority slots.
      presentAuthority(transport);
    };

    expect(compileOnly).toBeTypeOf("function");
    expectTypeOf(transport).toEqualTypeOf<InteractionState<"open">>();
  });
});
