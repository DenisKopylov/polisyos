import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import { breakpointProjection } from "@polisyos/atlas-ui";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { BottomSheet } from "./BottomSheet";
import { PullToRefresh } from "./PullToRefresh";
import { SwipeableDrawer } from "./SwipeableDrawer";
import { useBreakpoint, useIsMobile } from "./useBreakpoint";

type MediaQueryListener = (event: MediaQueryListEvent) => void;

function matchesQuery(query: string, width: number): boolean {
  const maxWidth = query.match(/\(max-width:\s*(\d+)px\)/)?.[1];
  const minWidth = query.match(/\(min-width:\s*(\d+)px\)/)?.[1];
  return (
    (!maxWidth || width <= Number(maxWidth)) &&
    (!minWidth || width >= Number(minWidth))
  );
}

function installViewport(initialWidth: number) {
  let width = initialWidth;
  const lists = new Set<{
    listeners: Set<MediaQueryListener>;
    media: string;
    matches: boolean;
  }>();

  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    get: () => width,
  });
  window.matchMedia = vi.fn((query: string) => {
    const listeners = new Set<MediaQueryListener>();
    const state = {
      listeners,
      media: query,
      matches: matchesQuery(query, width),
    };
    lists.add(state);
    const addListener = (listener: MediaQueryListener) => {
      listeners.add(listener);
    };
    const removeListener = (listener: MediaQueryListener) => {
      listeners.delete(listener);
    };
    return {
      addEventListener: ((_type: string, listener: MediaQueryListener) =>
        addListener(listener)) as MediaQueryList["addEventListener"],
      addListener,
      dispatchEvent: () => false,
      get matches() {
        return state.matches;
      },
      media: query,
      onchange: null,
      removeEventListener: ((_type: string, listener: MediaQueryListener) =>
        removeListener(listener)) as MediaQueryList["removeEventListener"],
      removeListener,
    };
  });

  return {
    activeListeners: () =>
      [...lists].reduce((total, list) => total + list.listeners.size, 0),
    queries: () => new Set([...lists].map((list) => list.media)),
    resize(nextWidth: number) {
      width = nextWidth;
      for (const list of lists) {
        const nextMatches = matchesQuery(list.media, width);
        if (nextMatches === list.matches) continue;
        list.matches = nextMatches;
        const event = {
          matches: nextMatches,
          media: list.media,
        } as MediaQueryListEvent;
        for (const listener of list.listeners) listener(event);
      }
    },
  };
}

describe("responsive token parity", () => {
  it("preserves live breakpoint density and gesture behavior through the generated adapter", async () => {
    const viewport = installViewport(639);
    const breakpointView = renderHook(() => ({
      breakpoint: useBreakpoint(),
      isMobile: useIsMobile(),
    }));

    expect(breakpointView.result.current).toEqual({
      breakpoint: "mobile",
      isMobile: true,
    });
    for (const [width, expected] of [
      [640, "tablet"],
      [767, "tablet"],
      [768, "compact"],
      [1023, "compact"],
      [1024, "standard"],
      [1280, "standard"],
      [1281, "expanded"],
    ] as const) {
      act(() => viewport.resize(width));
      expect(breakpointView.result.current).toEqual({
        breakpoint: expected,
        isMobile: false,
      });
    }
    expect(viewport.queries()).toEqual(
      new Set([
        "(max-width: 639px)",
        "(max-width: 767px)",
        "(max-width: 1023px)",
        "(max-width: 1280px)",
      ]),
    );
    expect(viewport.activeListeners()).toBe(8);
    breakpointView.unmount();
    expect(viewport.activeListeners()).toBe(0);

    type MutableRuntimeProjection = {
      -readonly [Key in keyof typeof breakpointProjection.runtime]: number;
    };
    const runtimeProjection =
      breakpointProjection.runtime as MutableRuntimeProjection;
    const originalProjection = { ...runtimeProjection };
    Object.assign(runtimeProjection, {
      compactMin: 900,
      expandedMin: 1401,
      mobileMax: 699,
      standardMin: 1100,
      tabletMin: 700,
    });
    act(() => viewport.resize(800));
    const injectedView = renderHook(() => useBreakpoint());
    expect(injectedView.result.current).toBe("tablet");
    injectedView.unmount();
    Object.assign(runtimeProjection, originalProjection);

    const closeSheet = vi.fn();
    render(
      <BottomSheet
        open
        onClose={closeSheet}
        snapPoints={[0.4, 0.75, 1]}
        title="Decision actions"
      >
        Sheet content
      </BottomSheet>,
    );
    const sheet = screen.getByRole("dialog", { name: "Decision actions" });
    expect(sheet).toHaveStyle({ height: "40vh" });
    fireEvent.touchStart(sheet, { touches: [{ clientY: 200 }] });
    fireEvent.touchEnd(sheet, { changedTouches: [{ clientY: 100 }] });
    expect(sheet).toHaveStyle({ height: "75vh" });
    fireEvent.touchStart(sheet, { touches: [{ clientY: 100 }] });
    fireEvent.touchEnd(sheet, { changedTouches: [{ clientY: 220 }] });
    expect(sheet).toHaveStyle({ height: "40vh" });
    fireEvent.touchStart(sheet, { touches: [{ clientY: 100 }] });
    fireEvent.touchEnd(sheet, { changedTouches: [{ clientY: 220 }] });
    expect(closeSheet).toHaveBeenCalledOnce();

    const closeDrawer = vi.fn();
    render(
      <SwipeableDrawer
        open
        onClose={closeDrawer}
        title="Navigation"
        width={200}
      >
        Drawer content
      </SwipeableDrawer>,
    );
    const drawer = screen.getByRole("dialog", { name: "Navigation" });
    fireEvent.touchStart(drawer, { touches: [{ clientX: 200 }] });
    fireEvent.touchMove(drawer, { touches: [{ clientX: 100 }] });
    expect(drawer).toHaveStyle({ transform: "translateX(-100px)" });
    fireEvent.touchEnd(drawer);
    expect(closeDrawer).toHaveBeenCalledOnce();

    const refresh = vi.fn(async () => undefined);
    render(
      <LocaleProvider>
        <PullToRefresh onRefresh={refresh} threshold={80}>
          Refreshable content
        </PullToRefresh>
      </LocaleProvider>,
    );
    const refreshContent = screen.getByText("Refreshable content");
    fireEvent.touchStart(refreshContent, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(refreshContent, { touches: [{ clientY: 350 }] });
    expect(screen.getByText("Release to refresh")).toBeVisible();
    fireEvent.touchEnd(refreshContent);
    await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
    await waitFor(() =>
      expect(screen.queryByText("Release to refresh")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Pull to refresh")).toBeInTheDocument();
  });
});
