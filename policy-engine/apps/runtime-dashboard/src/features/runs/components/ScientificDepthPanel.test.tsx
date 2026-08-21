import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";

import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/render";

import { ScientificDepthPanel } from "./ScientificDepthPanel";

describe("ScientificDepthPanel", () => {
  it("renders the producer's refusals and never re-derives the retired synthesis", async () => {
    server.use(
      http.get("*/api/v1/runs/:runId/authority-values", () =>
        HttpResponse.json({
          inventory_version: "ds16-c05.1",
          retirement_commit: "bc1d01001",
          run_id: "run-1",
          values: [
            {
              owner_surface: null,
              reason: "served refusal reason",
              refusal_code: "no_runtime_producer",
              retired_from: "x.ts",
              state: "refused",
              surface: "scientific",
              value_id: "scientific.stress_ranking",
            },
          ],
        }),
      ),
    );

    renderWithProviders(<ScientificDepthPanel runId="run-1" />);

    const served = await screen.findByText("served refusal reason");
    expect(served).toHaveAttribute("data-value-id", "scientific.stress_ranking");
    expect(screen.getByTestId("scientific-depth-panel")).toHaveTextContent("Unavailable");

    // The DS4-C23 synthesis stays deleted: no verdict, remedy, E-value, cohort or
    // stress ranking is re-derived on the glass.
    for (const retired of ["remedy", "e-value", "cohort", "stress", "ranking", "integrated"]) {
      expect(
        screen.queryByText(new RegExp(retired, "i")),
      ).not.toBeInTheDocument();
    }
  });
});
