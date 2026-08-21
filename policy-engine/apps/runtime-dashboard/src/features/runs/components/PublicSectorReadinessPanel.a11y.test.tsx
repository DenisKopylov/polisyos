import { render } from "@testing-library/react";
import { axe } from "vitest-axe";
import { QueryClientProvider } from "@tanstack/react-query";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import { createTestQueryClient } from "@/test/queryClient";

import { PublicSectorReadinessPanel } from "./PublicSectorReadinessPanel";

describe("PublicSectorReadinessPanel accessibility", () => {
  it("has no accessibility violations while rendering producer refusals", async () => {
    const { container } = render(
      <QueryClientProvider client={createTestQueryClient()}>
        <LocaleProvider>
          <PublicSectorReadinessPanel runId="run-a11y" />
        </LocaleProvider>
      </QueryClientProvider>,
    );

    expect((await axe(container)).violations).toHaveLength(0);
  });
});
