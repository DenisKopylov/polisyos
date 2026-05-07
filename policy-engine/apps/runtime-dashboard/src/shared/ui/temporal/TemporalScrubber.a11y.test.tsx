import type { PropsWithChildren } from "react";
import { useEffect } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";

import {
  TemporalCursorProvider,
  useTemporalCursor,
} from "@/app/providers/TemporalCursorProvider";
import { createTestQueryClient } from "@/test/queryClient";
import { ReducedMotionProvider } from "@/shared/a11y";
import { TemporalScrubber } from "./TemporalScrubber";

function Harness() {
  const { setTemporalCapabilities } = useTemporalCursor();
  useEffect(() => {
    setTemporalCapabilities({
      defaultScope: { validAt: "2026-04-15T00:00:00Z" },
      eventPoints: [],
      resolution: "event",
      runId: "run-1",
      surfaces: [],
      txRange: {
        earliest: "2026-04-10T00:00:00Z",
        latest: "2026-04-20T00:00:00Z",
      },
      validRange: {
        earliest: "2026-04-10T00:00:00Z",
        latest: "2026-04-20T00:00:00Z",
      },
    });
  }, [setTemporalCapabilities]);
  return (
    <TemporalScrubber
      labels={{
        now: "Now",
        observed: "Observed",
        simulated: "Simulated",
        slider: "Temporal cursor",
      }}
    />
  );
}

function Wrapper({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter initialEntries={["/"]}>
        <ReducedMotionProvider>
          <TemporalCursorProvider>{children}</TemporalCursorProvider>
        </ReducedMotionProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("TemporalScrubber accessibility", () => {
  it("has no WCAG AA axe violations", async () => {
    const { container } = render(<Harness />, { wrapper: Wrapper });
    const results = await axe(container);

    expect(results.violations).toHaveLength(0);
  });
});
