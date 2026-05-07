import { expectNoA11yViolations } from "@/test/a11y";

import { PolicyDiffView } from "./PolicyDiffView";
import { policyDiffFixture } from "./fixtures";

const { useDiffDataMock } = vi.hoisted(() => ({
  useDiffDataMock: vi.fn(),
}));

vi.mock("./useDiffData", () => ({
  useDiffData: (...args: unknown[]) => useDiffDataMock(...args),
}));

describe("PolicyDiffView accessibility", () => {
  beforeEach(() => {
    useDiffDataMock.mockReturnValue({
      data: policyDiffFixture,
      error: null,
      isError: false,
      isLoading: false,
    });
  });

  it("has no detectable accessibility violations", async () => {
    await expectNoA11yViolations(
      <PolicyDiffView runAId="run-a" runBId="run-b" />,
      { initialEntries: ["/compare/run-a/run-b"] },
    );
  });
});
