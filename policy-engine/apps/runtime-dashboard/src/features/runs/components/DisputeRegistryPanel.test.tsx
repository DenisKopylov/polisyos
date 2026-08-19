import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { useAuthzMock } = vi.hoisted(() => ({
  useAuthzMock: vi.fn(),
}));

vi.mock("@/app/authz/AuthzProvider", () => ({
  useAuthz: () => useAuthzMock(),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/shared/lib/utils", () => ({
  formatDate: (value: unknown) => String(value),
  formatNumber: (value: unknown) => String(value),
}));

import {
  createDisputePersistence,
  createDisputeStatus,
} from "@/features/runs/domain/disputes";

import { DisputeRegistryPanel } from "./DisputeRegistryPanel";

const SCOPE_A = { tenantId: "a:b", userId: "c" };
const SCOPE_B = { tenantId: "a", userId: "b:c" };

function readyAuthz(scope = SCOPE_A) {
  return {
    status: "ready",
    user: { tenant_id: scope.tenantId, user_id: scope.userId },
  };
}

async function addDispute(title: string) {
  await userEvent.type(
    screen.getByLabelText("phase32.disputes.titleLabel"),
    title,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "phase32.disputes.add" }),
  );
}

describe("DisputeRegistryPanel persistence", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useAuthzMock.mockReset();
    useAuthzMock.mockReturnValue(readyAuthz());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("persists a reviewer objection only under the ready identity scope", async () => {
    const view = render(<DisputeRegistryPanel issues={[]} runId="run-a" />);

    await addDispute("Reviewer objection");
    expect(screen.getByTestId("dispute-registry-panel")).toHaveTextContent(
      "Reviewer objection",
    );

    view.unmount();
    render(<DisputeRegistryPanel issues={[]} runId="run-a" />);
    expect(screen.getByTestId("dispute-registry-panel")).toHaveTextContent(
      "Reviewer objection",
    );
  });

  it("does not load or persist while identity scope is unavailable", async () => {
    useAuthzMock.mockReturnValue({ status: "loading", user: undefined });
    const persistence = createDisputePersistence({
      clock: () => new Date(),
      storage: () => window.localStorage,
    });
    expect(
      persistence.write(SCOPE_A, "run-a", [
        {
          actor: "reviewer",
          basis: "legal",
          id: "private-a",
          openedAt: "2026-08-16T12:00:00.000Z",
          status: createDisputeStatus("open"),
          target: "decision",
          title: "Private A",
        },
      ]),
    ).toBe(true);
    const key = persistence.key(SCOPE_A, "run-a")!;
    const before = window.localStorage.getItem(key);

    const view = render(<DisputeRegistryPanel issues={[]} runId="run-a" />);
    expect(screen.getByTestId("dispute-registry-panel")).not.toHaveTextContent(
      "Private A",
    );
    await addDispute("Unscoped draft");
    expect(window.localStorage.getItem(key)).toBe(before);

    view.unmount();
    render(<DisputeRegistryPanel issues={[]} runId="run-a" />);
    expect(screen.getByTestId("dispute-registry-panel")).not.toHaveTextContent(
      "Unscoped draft",
    );
  });

  it.each(["absent", "throwing"] as const)(
    "keeps the rendered list and draft unchanged when storage is %s",
    async (failure) => {
      render(<DisputeRegistryPanel issues={[]} runId="run-a" />);
      await userEvent.type(
        screen.getByLabelText("phase32.disputes.titleLabel"),
        "Unstored objection",
      );
      const failureSpy =
        failure === "absent"
          ? vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
              throw new Error("storage unavailable");
            })
          : vi
              .spyOn(Storage.prototype, "setItem")
              .mockImplementationOnce(() => {
                throw new Error("storage write failed");
              });

      await userEvent.click(
        screen.getByRole("button", { name: "phase32.disputes.add" }),
      );

      expect(
        screen.getByTestId("dispute-registry-panel"),
      ).not.toHaveTextContent("Unstored objection");
      expect(screen.getByLabelText("phase32.disputes.titleLabel")).toHaveValue(
        "Unstored objection",
      );
      failureSpy.mockRestore();
    },
  );

  it("contains a consumer clock failure without emitting local or stored state", async () => {
    const timestamp = vi
      .spyOn(Date.prototype, "toISOString")
      .mockImplementationOnce(() => {
        throw new Error("consumer clock failed");
      });
    render(<DisputeRegistryPanel issues={[]} runId="run-a" />);
    await userEvent.type(
      screen.getByLabelText("phase32.disputes.titleLabel"),
      "Clock-failed objection",
    );

    await userEvent.click(
      screen.getByRole("button", { name: "phase32.disputes.add" }),
    );

    expect(screen.getByTestId("dispute-registry-panel")).not.toHaveTextContent(
      "Clock-failed objection",
    );
    expect(window.localStorage).toHaveLength(0);
    timestamp.mockRestore();
  });

  it("keeps delimiter-colliding bindings isolated before paint and write", async () => {
    const persistence = createDisputePersistence({
      clock: () => new Date(),
      storage: () => window.localStorage,
    });
    expect(
      persistence.write(SCOPE_A, "same-run", [
        {
          actor: "reviewer",
          basis: "legal",
          id: "private-a",
          openedAt: "2026-08-16T12:00:00.000Z",
          status: createDisputeStatus("open"),
          target: "decision",
          title: "Private A",
        },
      ]),
    ).toBe(true);
    const keyA = persistence.key(SCOPE_A, "same-run")!;
    const keyB = persistence.key(SCOPE_B, "same-run")!;
    const beforeA = window.localStorage.getItem(keyA);
    const view = render(<DisputeRegistryPanel issues={[]} runId="same-run" />);
    expect(screen.getByTestId("dispute-registry-panel")).toHaveTextContent(
      "Private A",
    );

    useAuthzMock.mockReturnValue(readyAuthz(SCOPE_B));
    view.rerender(<DisputeRegistryPanel issues={[]} runId="same-run" />);
    expect(screen.getByTestId("dispute-registry-panel")).not.toHaveTextContent(
      "Private A",
    );
    await addDispute("Private B");

    expect(window.localStorage.getItem(keyB)).toContain("Private B");
    expect(window.localStorage.getItem(keyB)).not.toContain("Private A");
    expect(window.localStorage.getItem(keyA)).toBe(beforeA);
  });

  it("does not prepaint or write the prior run after a dirty run transition", async () => {
    const persistence = createDisputePersistence({
      clock: () => new Date(),
      storage: () => window.localStorage,
    });
    const keyA = persistence.key(SCOPE_A, "run-a")!;
    const keyB = persistence.key(SCOPE_A, "run-b")!;
    const view = render(<DisputeRegistryPanel issues={[]} runId="run-a" />);
    await addDispute("A persisted objection");
    expect(window.localStorage.getItem(keyA)).toContain(
      "A persisted objection",
    );
    await userEvent.type(
      screen.getByLabelText("phase32.disputes.titleLabel"),
      "A dirty input",
    );

    view.rerender(<DisputeRegistryPanel issues={[]} runId="run-b" />);

    expect(screen.getByTestId("dispute-registry-panel")).not.toHaveTextContent(
      "A persisted objection",
    );
    expect(screen.getByLabelText("phase32.disputes.titleLabel")).toHaveValue(
      "",
    );
    expect(window.localStorage.getItem(keyB)).toBeNull();
  });
});
