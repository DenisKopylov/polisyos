import { describe, expect, expectTypeOf, it } from "vitest";

import {
  createInteractionState,
  type GeneratedAuthorityValue,
  type InteractionState,
  presentAuthority,
} from "./statusOwnership";
import type { SimulationMetric } from "./simulation";

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

  it("rejects C21 presentation taxonomies at authority slots", () => {
    expectTypeOf<
      SimulationMetric["severity"]
    >().toEqualTypeOf<InteractionState>();

    const simulation = createInteractionState(
      "future_magnitude",
      "candidate_display",
    );
    const compileOnly = () => {
      // @ts-expect-error Candidate simulation state cannot enter authority.
      presentAuthority(simulation);
    };

    expect(compileOnly).toBeTypeOf("function");
  });
});
