import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const { tMock } = vi.hoisted(() => ({
  tMock: vi.fn((key: string) => key),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    t: tMock,
  }),
}));

import JsonPreview from "@/shared/ui/JsonPreview";

describe("JsonPreview", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("renders the empty label when there is no payload", () => {
    render(<JsonPreview data={undefined} emptyLabel="Nothing to show" />);

    expect(screen.getByText("Nothing to show")).toBeInTheDocument();
  });

  it("renders and copies structured payloads", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    render(<JsonPreview data={{ status: "ok", count: 2 }} />);

    expect(screen.getByText(/"status": "ok"/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "common.copy" }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(
        JSON.stringify({ status: "ok", count: 2 }, null, 2),
      );
      expect(
        screen.getByRole("button", { name: "common.copied" }),
      ).toBeInTheDocument();
    });

    await new Promise((resolve) => window.setTimeout(resolve, 1_100));
    expect(
      screen.getByRole("button", { name: "common.copy" }),
    ).toBeInTheDocument();
  });

  it("falls back to String(data) for circular values and skips copy without clipboard", async () => {
    const circular: { self?: unknown } = {};
    circular.self = circular;
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });

    render(<JsonPreview data={circular} />);

    expect(screen.getByText("[object Object]")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "common.copy" }));
  });
});
