import {
  resetRunsListUiStore,
  useRunsListUiStore,
} from "@/features/runs/state/useRunsListUiStore";

describe("useRunsListUiStore", () => {
  beforeEach(() => {
    window.localStorage.clear();
    resetRunsListUiStore();
  });

  it("keeps runs list drafts and cursor state in memory only", () => {
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");

    useRunsListUiStore.getState().replaceDraftFilters({
      fromInput: "2026-03-01",
      queryInput: "inflation",
      statusInput: "completed",
      toInput: "2026-03-09",
    });
    useRunsListUiStore.getState().pushCursor("cursor-1");
    useRunsListUiStore.getState().pushCursor("cursor-1");
    useRunsListUiStore.getState().setActiveRunId("run-1");
    useRunsListUiStore
      .getState()
      .setActiveRunId((currentRunId) =>
        currentRunId === "run-1" ? "run-2" : currentRunId,
      );

    expect(useRunsListUiStore.getState()).toMatchObject({
      activeRunId: "run-2",
      fromInput: "2026-03-01",
      queryInput: "inflation",
      statusInput: "completed",
      toInput: "2026-03-09",
    });
    expect(useRunsListUiStore.getState().cursorTrail).toEqual(["", "cursor-1"]);
    expect(setItemSpy).not.toHaveBeenCalled();
  });

  it("supports direct setters and reset helpers", () => {
    const store = useRunsListUiStore.getState();

    store.setCursorTrail(["", "cursor-2"]);
    store.resetCursorTrail();
    store.setFromInput("2026-03-10");
    store.setQueryInput("gdp");
    store.setStatusInput("running");
    store.setTableScrollTop(128);
    store.setToInput("2026-03-11");

    expect(useRunsListUiStore.getState()).toMatchObject({
      cursorTrail: [""],
      fromInput: "2026-03-10",
      queryInput: "gdp",
      statusInput: "running",
      tableScrollTop: 128,
      toInput: "2026-03-11",
    });

    store.reset();
    expect(useRunsListUiStore.getState()).toMatchObject({
      activeRunId: null,
      cursorTrail: [""],
      fromInput: "",
      queryInput: "",
      statusInput: "",
      tableScrollTop: 0,
      toInput: "",
    });
  });
});
