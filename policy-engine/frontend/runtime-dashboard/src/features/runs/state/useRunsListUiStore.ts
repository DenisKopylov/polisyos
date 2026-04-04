import { create } from "zustand";

type RunsListUiState = {
  activeRunId: string | null;
  cursorTrail: string[];
  fromInput: string;
  queryInput: string;
  statusInput: string;
  tableScrollTop: number;
  toInput: string;
  pushCursor: (cursor: string) => void;
  reset: () => void;
  resetCursorTrail: () => void;
  replaceDraftFilters: (filters: {
    fromInput: string;
    queryInput: string;
    statusInput: string;
    toInput: string;
  }) => void;
  setActiveRunId: (
    runId: string | null | ((currentRunId: string | null) => string | null),
  ) => void;
  setCursorTrail: (cursorTrail: string[]) => void;
  setFromInput: (fromInput: string) => void;
  setQueryInput: (queryInput: string) => void;
  setStatusInput: (statusInput: string) => void;
  setTableScrollTop: (tableScrollTop: number) => void;
  setToInput: (toInput: string) => void;
};

const initialRunsListUiState = {
  activeRunId: null,
  cursorTrail: [""],
  fromInput: "",
  queryInput: "",
  statusInput: "",
  tableScrollTop: 0,
  toInput: "",
};

export const useRunsListUiStore = create<RunsListUiState>((set) => ({
  ...initialRunsListUiState,
  pushCursor: (cursor) => {
    set((state) => ({
      cursorTrail: state.cursorTrail.includes(cursor)
        ? state.cursorTrail
        : [...state.cursorTrail, cursor],
    }));
  },
  reset: () => {
    set(initialRunsListUiState);
  },
  resetCursorTrail: () => {
    set({ cursorTrail: [""] });
  },
  replaceDraftFilters: (filters) => {
    set(filters);
  },
  setActiveRunId: (nextActiveRunId) => {
    set((state) => ({
      activeRunId:
        typeof nextActiveRunId === "function"
          ? nextActiveRunId(state.activeRunId)
          : nextActiveRunId,
    }));
  },
  setCursorTrail: (cursorTrail) => {
    set({ cursorTrail });
  },
  setFromInput: (fromInput) => {
    set({ fromInput });
  },
  setQueryInput: (queryInput) => {
    set({ queryInput });
  },
  setStatusInput: (statusInput) => {
    set({ statusInput });
  },
  setTableScrollTop: (tableScrollTop) => {
    set({ tableScrollTop });
  },
  setToInput: (toInput) => {
    set({ toInput });
  },
}));

export function resetRunsListUiStore() {
  useRunsListUiStore.setState(initialRunsListUiState);
}
