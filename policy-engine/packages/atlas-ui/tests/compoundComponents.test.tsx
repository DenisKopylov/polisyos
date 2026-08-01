import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import {
  JsonPreview,
  VirtualList,
  VirtualTable,
  VIRTUALIZATION_THRESHOLD,
} from "../src/index";

describe("compound components", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("exports the migrated virtual compounds from the package owner", () => {
    expect(VIRTUALIZATION_THRESHOLD).toBe(30);
    expect(VirtualList).toBeTypeOf("function");
    expect(VirtualTable).toBeTypeOf("function");
  });

  it("renders typed empty presentation copy", () => {
    render(
      <JsonPreview
        data={undefined}
        labels={{
          copied: "Copied payload",
          copy: "Copy payload",
          empty: "Nothing to show",
        }}
      />,
    );

    expect(screen.getByText("Nothing to show")).toBeInTheDocument();
  });

  it("renders and copies structured payloads with neutral default copy", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    render(<JsonPreview data={{ status: "ok", count: 2 }} />);

    expect(screen.getByText(/"status": "ok"/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(
        JSON.stringify({ status: "ok", count: 2 }, null, 2),
      );
      expect(
        screen.getByRole("button", { name: "Copied" }),
      ).toBeInTheDocument();
    });
  });

  it("falls back to String(data) and skips copy without clipboard", () => {
    const circular: { self?: unknown } = {};
    circular.self = circular;
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });

    render(<JsonPreview data={circular} />);

    expect(screen.getByText("[object Object]")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
  });
});
