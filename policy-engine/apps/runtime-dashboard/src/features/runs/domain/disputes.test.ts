import { afterEach, describe, expect, it } from "vitest";

import { isInteractionState } from "@/shared/lib/domain/statusOwnership";

import { disputeStorageKey, readStoredDisputes } from "./disputes";

afterEach(() => {
  window.localStorage.clear();
});

describe("run dispute interaction state", () => {
  it("rebinds persisted workflow labels as interaction state", () => {
    window.localStorage.setItem(
      disputeStorageKey("run-1"),
      JSON.stringify({
        disputes: [
          {
            actor: "reviewer",
            basis: "legal",
            id: "local:run-1:appeal",
            openedAt: "2026-07-20T09:00:00Z",
            status: "open",
            target: "decision",
            title: "Appeal remains open",
          },
        ],
      }),
    );

    const [dispute] = readStoredDisputes("run-1");

    expect(dispute).toBeDefined();
    expect(isInteractionState(dispute?.status)).toBe(true);
    expect(dispute?.status.label).toBe("open");
    expect(dispute?.status.authorityPurpose).toBe("progress");
  });
});
