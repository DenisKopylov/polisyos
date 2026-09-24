import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ReproduceRunButton } from "@/features/runs/components/ReproduceRunButton";
import { renderWithProviders } from "@/test/render";

describe("ReproduceRunButton component contract", () => {
  it("requires confirmation and permits cancellation without starting a run", async () => {
    const user = userEvent.setup();
    let requests = 0;
    renderWithProviders(
      <ReproduceRunButton
        runId="source-run"
        onReproduce={async () => {
          requests += 1;
          return { runId: "new-run" };
        }}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Reproduce run/ }));
    expect(
      screen.getByText("Re-run source-run with same parameters?"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(requests).toBe(0);
    expect(screen.getByRole("button", { name: /Reproduce run/ })).toBeEnabled();
  });

  it("submits the source parameters once and shows the returned run after completion", async () => {
    const user = userEvent.setup();
    const submitted: unknown[] = [];
    let finish!: (result: { runId: string }) => void;
    const pending = new Promise<{ runId: string }>((resolve) => {
      finish = resolve;
    });
    renderWithProviders(
      <ReproduceRunButton
        runId="source-run"
        parameters={{ seed: 42, scenario: "tax-credit" }}
        onReproduce={(request) => {
          submitted.push(request);
          return pending;
        }}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Reproduce run/ }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    const submitting = screen.getByRole("button", { name: "Submitting..." });
    expect(submitting).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    await user.click(submitting);
    expect(submitted).toEqual([
      {
        sourceRunId: "source-run",
        parameters: { seed: 42, scenario: "tax-credit" },
      },
    ]);
    await act(async () => {
      finish({ runId: "reproduced-run" });
    });
    expect(screen.getByText("Run reproduced")).toHaveTextContent(
      "reproduced-run",
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("exposes a failed reproduction and allows dismissal before retry", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <ReproduceRunButton
        runId="source-run"
        onReproduce={async () => {
          throw new Error("Source snapshot is unavailable");
        }}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Reproduce run/ }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(
      await screen.findByText("Source snapshot is unavailable"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Run reproduced")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.getByRole("button", { name: /Reproduce run/ })).toBeEnabled();
    expect(
      screen.queryByText("Source snapshot is unavailable"),
    ).not.toBeInTheDocument();
  });

  it("does not offer confirmation while reproduction is disabled", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <ReproduceRunButton
        runId="source-run"
        disabled
        onReproduce={async () => undefined}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Reproduce run/ }));
    expect(
      screen.queryByRole("button", { name: "Confirm" }),
    ).not.toBeInTheDocument();
  });
});
