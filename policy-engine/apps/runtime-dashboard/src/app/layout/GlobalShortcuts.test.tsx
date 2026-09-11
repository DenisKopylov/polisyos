import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { GlobalShortcuts } from "@/app/layout/GlobalShortcuts";
import {
  resetPreferencesStore,
  readPreferencesFromStorage,
} from "@/app/state/usePreferencesStore";
import { renderWithProviders } from "@/test/render";

function LocationWitness() {
  return <output aria-label="Current route">{useLocation().pathname}</output>;
}

beforeEach(() => {
  localStorage.clear();
  resetPreferencesStore();
});

describe("GlobalShortcuts component contract", () => {
  it("navigates through registered keyboard actions and removes them on unmount", () => {
    const view = renderWithProviders(
      <>
        <GlobalShortcuts />
        <LocationWitness />
      </>,
      { initialEntries: ["/initial"] },
    );
    for (const [key, route] of [
      ["1", "/"],
      ["2", "/compose"],
      ["3", "/runs"],
      ["4", "/evidence"],
      ["5", "/knowledge"],
      ["6", "/platform"],
      ["n", "/compose"],
    ]) {
      fireEvent.keyDown(window, { key, metaKey: true });
      expect(screen.getByLabelText("Current route").textContent).toBe(route);
    }
    view.unmount();
    const event = new KeyboardEvent("keydown", {
      key: "3",
      metaKey: true,
      cancelable: true,
    });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
  });

  it("shows discoverable shortcut help while preserving ordinary typing", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <GlobalShortcuts />
        <input aria-label="Policy question" />
      </>,
    );
    const input = screen.getByRole("textbox", { name: "Policy question" });
    fireEvent.keyDown(input, { key: "?", shiftKey: true });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.keyDown(window, { key: "?", shiftKey: true });
    expect(screen.getByRole("dialog")).toHaveTextContent("Scenario Composer");
    expect(screen.getByRole("dialog")).toHaveTextContent("Ctrl+2");
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("persists sidebar and density actions and applies theme changes", () => {
    renderWithProviders(<GlobalShortcuts />);
    fireEvent.keyDown(window, { key: "b", metaKey: true });
    expect(readPreferencesFromStorage().sidebarCollapsed).toBe(true);
    fireEvent.keyDown(window, { key: "d", metaKey: true, shiftKey: true });
    expect(document.documentElement).toHaveAttribute("data-density", "compact");
    expect(readPreferencesFromStorage().density).toBe("compact");
    fireEvent.keyDown(window, { key: "l", metaKey: true, shiftKey: true });
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    fireEvent.keyDown(window, { key: "l", metaKey: true, shiftKey: true });
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });

  it("moves focus within the active list without wrapping or stealing input keys", () => {
    renderWithProviders(
      <>
        <GlobalShortcuts />
        <div data-vim-list>
          <button data-vim-item>First</button>
          <button data-vim-item>Last</button>
        </div>
        <input aria-label="Notes" />
      </>,
    );
    const first = screen.getByRole("button", { name: "First" });
    const last = screen.getByRole("button", { name: "Last" });
    fireEvent.keyDown(window, { key: "j" });
    expect(first).toHaveFocus();
    fireEvent.keyDown(first, { key: "j" });
    expect(last).toHaveFocus();
    fireEvent.keyDown(last, { key: "j" });
    expect(last).toHaveFocus();
    fireEvent.keyDown(last, { key: "k" });
    expect(first).toHaveFocus();
    fireEvent.keyDown(first, { key: "k" });
    expect(first).toHaveFocus();
    const notes = screen.getByRole("textbox", { name: "Notes" });
    notes.focus();
    fireEvent.keyDown(notes, { key: "j" });
    expect(notes).toHaveFocus();
  });
});
