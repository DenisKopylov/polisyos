import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";
import {
  PageErrorBoundary,
  PanelErrorBoundary,
} from "@/shared/components/ErrorBoundary";

function Crash(): never {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  it("renders page fallback when a page crashes", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    renderWithProviders(
      <PageErrorBoundary title="Page failed" body="Reload the page">
        <Crash />
      </PageErrorBoundary>,
    );

    expect(screen.getByText("Page failed")).toBeInTheDocument();
    expect(screen.getByText("Reload the page")).toBeInTheDocument();
  });

  it("renders panel fallback when a panel crashes", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    renderWithProviders(
      <PanelErrorBoundary title="Panel failed" body="Retry this panel">
        <Crash />
      </PanelErrorBoundary>,
    );

    expect(screen.getByText("Panel failed")).toBeInTheDocument();
    expect(screen.getByText("Retry this panel")).toBeInTheDocument();
  });
});
