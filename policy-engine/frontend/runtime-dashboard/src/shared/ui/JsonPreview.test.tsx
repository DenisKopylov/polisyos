import { screen } from "@testing-library/react";
import { vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import JsonPreview from "./JsonPreview";

describe("JsonPreview", () => {
  it("renders the empty label when no payload is available", () => {
    renderWithProviders(<JsonPreview data={undefined} emptyLabel="No payload yet" />);

    expect(screen.getByText("No payload yet")).toBeInTheDocument();
  });

  it("renders structured payloads with a copy affordance", () => {
    renderWithProviders(
      <JsonPreview
        data={{
          decision: "approve",
          blockers: 0,
        }}
      />,
    );

    expect(screen.getByText(/"decision": "approve"/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy" })).toBeInTheDocument();
  });

  it("renders plain string payloads as-is", () => {
    renderWithProviders(<JsonPreview data="plain payload" />);

    expect(screen.getByText("plain payload")).toBeInTheDocument();
  });
});
