import { useEffect, useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AlertDialogProvider, useAlertDialog } from "./AlertDialogProvider";

function ConfirmQueueProbe() {
  const { confirm } = useAlertDialog();
  const [result, setResult] = useState("");

  return (
    <div>
      <button
        type="button"
        onClick={() => {
          const first = confirm({ title: "First dialog" });
          const second = confirm({ title: "Second dialog" });
          void Promise.all([first, second]).then((values) => {
            setResult(values.join(","));
          });
        }}
      >
        open dialogs
      </button>
      <span data-testid="confirm-results">{result}</span>
    </div>
  );
}

function ConfirmUnmountProbe({
  onResolved,
}: {
  onResolved: (value: boolean) => void;
}) {
  const { confirm } = useAlertDialog();

  useEffect(() => {
    void confirm({ title: "Unmount dialog" }).then(onResolved);
  }, [confirm, onResolved]);

  return null;
}

describe("AlertDialogProvider", () => {
  it("resolves queued confirmations in FIFO order", async () => {
    const user = userEvent.setup();

    render(
      <AlertDialogProvider>
        <ConfirmQueueProbe />
      </AlertDialogProvider>,
    );

    await user.click(screen.getByRole("button", { name: "open dialogs" }));

    expect(screen.getByRole("alertdialog")).toHaveTextContent("First dialog");
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    expect(screen.getByRole("alertdialog")).toHaveTextContent("Second dialog");
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() =>
      expect(screen.getByTestId("confirm-results")).toHaveTextContent(
        "true,false",
      ),
    );
  });

  it("resolves pending confirmations with false when the provider unmounts", async () => {
    let resolvedValue: boolean | null = null;

    const view = render(
      <AlertDialogProvider>
        <ConfirmUnmountProbe
          onResolved={(value) => {
            resolvedValue = value;
          }}
        />
      </AlertDialogProvider>,
    );

    expect(screen.getByRole("alertdialog")).toHaveTextContent("Unmount dialog");

    view.unmount();

    await waitFor(() => expect(resolvedValue).toBe(false));
  });
});
