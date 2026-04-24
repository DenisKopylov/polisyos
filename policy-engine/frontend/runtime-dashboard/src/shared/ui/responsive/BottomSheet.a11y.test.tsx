import { vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { BottomSheet } from "./BottomSheet";

describe("BottomSheet accessibility", () => {
  it("has no WCAG AA violations", async () => {
    await expectNoA11yViolations(
      <BottomSheet open onClose={vi.fn()} title="Decision actions">
        <button type="button">Download packet</button>
      </BottomSheet>,
      { includeDocumentBody: true },
    );
  });
});
