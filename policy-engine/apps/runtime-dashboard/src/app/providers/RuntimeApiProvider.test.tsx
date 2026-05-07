import { Link, Route, Routes, useLocation } from "react-router-dom";
import { act, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  RuntimeApiProvider,
  useRuntimeApiIncident,
} from "@/app/providers/RuntimeApiProvider";
import { emitRuntimeApiEvent } from "@/api/runtimeApiEvents";
import { renderWithProviders } from "@/test/render";

function RuntimeIncidentProbe() {
  const { incident, dismissIncident } = useRuntimeApiIncident();
  const location = useLocation();

  return (
    <div>
      <span data-testid="location">{`${location.pathname}${location.search}`}</span>
      <span data-testid="incident">
        {incident ? `${incident.status}:${incident.code}` : "none"}
      </span>
      <Link to="/platform">platform</Link>
      <button type="button" onClick={dismissIncident}>
        dismiss
      </button>
    </div>
  );
}

describe("RuntimeApiProvider", () => {
  it("surfaces dismissible incidents for 5xx responses", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <RuntimeApiProvider>
        <RuntimeIncidentProbe />
      </RuntimeApiProvider>,
      {
        initialEntries: ["/runs"],
      },
    );

    act(() => {
      emitRuntimeApiEvent({
        code: "runtime_failed",
        detail: "backend unavailable",
        requestId: "req-1",
        source: "runtime",
        status: 500,
        timestamp: Date.now(),
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("incident")).toHaveTextContent(
        "500:runtime_failed",
      ),
    );

    await user.click(screen.getByRole("button", { name: "dismiss" }));
    await waitFor(() =>
      expect(screen.getByTestId("incident")).toHaveTextContent("none"),
    );
  });

  it("redirects unauthorized incidents to login with next path", async () => {
    renderWithProviders(
      <RuntimeApiProvider>
        <RuntimeIncidentProbe />
      </RuntimeApiProvider>,
      {
        initialEntries: ["/runs?status=running"],
      },
    );

    act(() => {
      emitRuntimeApiEvent({
        code: "unauthorized",
        detail: "token expired",
        requestId: "req-2",
        source: "runtime",
        status: 401,
        timestamp: Date.now(),
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent(
        "/login?next=%2Fruns%3Fstatus%3Drunning",
      ),
    );
  });

  it("dedupes repeated incidents within the cooldown window", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <RuntimeApiProvider>
        <RuntimeIncidentProbe />
      </RuntimeApiProvider>,
      {
        initialEntries: ["/runs"],
      },
    );

    act(() => {
      emitRuntimeApiEvent({
        code: "runtime_failed",
        detail: "backend unavailable",
        requestId: "req-1",
        source: "runtime",
        status: 500,
        timestamp: 1_000,
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("incident")).toHaveTextContent(
        "500:runtime_failed",
      ),
    );

    await user.click(screen.getByRole("button", { name: "dismiss" }));
    await waitFor(() =>
      expect(screen.getByTestId("incident")).toHaveTextContent("none"),
    );

    act(() => {
      emitRuntimeApiEvent({
        code: "runtime_failed",
        detail: "backend unavailable",
        requestId: "req-2",
        source: "runtime",
        status: 500,
        timestamp: 2_000,
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("incident")).toHaveTextContent("none"),
    );

    act(() => {
      emitRuntimeApiEvent({
        code: "runtime_failed",
        detail: "backend unavailable",
        requestId: "req-3",
        source: "runtime",
        status: 500,
        timestamp: 7_000,
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("incident")).toHaveTextContent(
        "500:runtime_failed",
      ),
    );
  });

  it("clears dismissible incidents when the pathname changes", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <RuntimeApiProvider>
        <Routes>
          <Route path="/runs" element={<RuntimeIncidentProbe />} />
          <Route path="/platform" element={<RuntimeIncidentProbe />} />
        </Routes>
      </RuntimeApiProvider>,
      {
        initialEntries: ["/runs"],
      },
    );

    act(() => {
      emitRuntimeApiEvent({
        code: "forbidden",
        detail: "access denied",
        requestId: "req-4",
        source: "runtime",
        status: 403,
        timestamp: Date.now(),
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("incident")).toHaveTextContent("403:forbidden"),
    );

    await user.click(screen.getByRole("link", { name: "platform" }));

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent("/platform"),
    );
    await waitFor(() =>
      expect(screen.getByTestId("incident")).toHaveTextContent("none"),
    );
  });

  it("does not redirect again when unauthorized happens on the login route", async () => {
    renderWithProviders(
      <RuntimeApiProvider>
        <RuntimeIncidentProbe />
      </RuntimeApiProvider>,
      {
        initialEntries: ["/login"],
      },
    );

    act(() => {
      emitRuntimeApiEvent({
        code: "unauthorized",
        detail: "token expired",
        requestId: "req-5",
        source: "runtime",
        status: 401,
        timestamp: Date.now(),
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent("/login"),
    );
    expect(screen.getByTestId("incident")).toHaveTextContent("none");
  });

  it("requires useRuntimeApiIncident to be used inside the provider", () => {
    expect(() => renderHook(() => useRuntimeApiIncident())).toThrow(
      "useRuntimeApiIncident must be used within a RuntimeApiProvider",
    );
  });
});
