import { describe, expect, it } from "vitest";

import {
  createInteractionState,
  inspectStatusOwner,
  isInteractionState,
  presentAuthority,
} from "./statusOwnership";

describe("status ownership", () => {
  it("rejects a revived UI-local authority status definition", () => {
    expect(() =>
      inspectStatusOwner({
        kind: "local_union",
        module: "@/shared/lib/domain/revivedAuthority",
        query: 'LocalDispute["status"]',
      }),
    ).toThrow(/UI-local authority vocabularies are forbidden/u);
  });

  it("accepts interaction state only when barred from authority slots", () => {
    const state = createInteractionState("ready", "transport");

    expect(isInteractionState(state)).toBe(true);
    expect(state.purpose).toBe("interaction_only");
    expect(() => presentAuthority(state as never)).toThrow(
      /interaction state cannot enter an authority slot/u,
    );
  });
});
