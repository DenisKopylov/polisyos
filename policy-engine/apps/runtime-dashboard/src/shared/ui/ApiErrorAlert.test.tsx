import { screen } from "@testing-library/react";

import { RuntimeApiRequestError } from "@/api/http";
import { renderWithProviders } from "@/test/render";

import { ApiErrorAlert } from "./ApiErrorAlert";

describe("ApiErrorAlert", () => {
  it("renders runtime API problem details", () => {
    const error = new RuntimeApiRequestError(
      {
        code: "runtime_failed",
        detail: "Runtime queue unavailable",
        error: null,
        instance: null,
        request_id: "req-123",
        status: 503,
        status_code: 503,
        title: "Runtime API error",
        type: "about:blank",
      },
      503,
      "Fallback message",
    );

    renderWithProviders(<ApiErrorAlert error={error} title="Custom title" />);

    expect(screen.getByText("Custom title")).toBeInTheDocument();
    expect(screen.getByText("Runtime queue unavailable")).toBeInTheDocument();
    expect(screen.getByText("status=503")).toBeInTheDocument();
    expect(screen.getByText("code=runtime_failed")).toBeInTheDocument();
    expect(screen.getByText("request_id=req-123")).toBeInTheDocument();
  });

  it("renders generic errors when the payload is not a runtime API problem", () => {
    renderWithProviders(<ApiErrorAlert error="Something went wrong" />);

    expect(screen.getByText("Request failed")).toBeInTheDocument();
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });
});
