import { create } from "zustand";
import { persist } from "zustand/middleware";

// ---------------------------------------------------------------------------
// Widget layout types
// ---------------------------------------------------------------------------

export type WidgetSize = "sm" | "md" | "lg" | "xl";

export type WidgetConfig = {
  id: string;
  type: string;
  title: string;
  size: WidgetSize;
  visible: boolean;
  order: number;
  settings?: Record<string, unknown>;
};

export type SavedView = {
  id: string;
  label: string;
  widgets: WidgetConfig[];
  createdAt: number;
};

// ---------------------------------------------------------------------------
// Default widgets
// ---------------------------------------------------------------------------

const DEFAULT_WIDGETS: WidgetConfig[] = [
  {
    id: "hero-metrics",
    type: "hero_metrics",
    title: "Key Metrics",
    size: "xl",
    visible: true,
    order: 0,
  },
  {
    id: "action-queue",
    type: "action_queue",
    title: "Action Queue",
    size: "lg",
    visible: true,
    order: 1,
  },
  {
    id: "status-chart",
    type: "status_chart",
    title: "Runs by Status",
    size: "md",
    visible: true,
    order: 2,
  },
  {
    id: "duration-trend",
    type: "duration_trend",
    title: "Duration Trend",
    size: "md",
    visible: true,
    order: 3,
  },
  {
    id: "source-coverage",
    type: "source_coverage",
    title: "Source Coverage",
    size: "md",
    visible: true,
    order: 4,
  },
  {
    id: "promotions",
    type: "promotions",
    title: "Promotion Candidates",
    size: "md",
    visible: true,
    order: 5,
  },
  {
    id: "quick-insights",
    type: "quick_insights",
    title: "Quick Insights",
    size: "lg",
    visible: true,
    order: 6,
  },
];

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

type DashboardLayoutState = {
  widgets: WidgetConfig[];
  savedViews: SavedView[];
  isEditing: boolean;

  // Actions
  setWidgets: (widgets: WidgetConfig[]) => void;
  reorderWidget: (activeId: string, overId: string) => void;
  toggleWidgetVisibility: (id: string) => void;
  resizeWidget: (id: string, size: WidgetSize) => void;
  updateWidgetSettings: (id: string, settings: Record<string, unknown>) => void;
  setEditing: (editing: boolean) => void;
  resetToDefault: () => void;
  saveView: (label: string) => void;
  loadView: (viewId: string) => void;
  deleteView: (viewId: string) => void;
};

export const useDashboardLayoutStore = create<DashboardLayoutState>()(
  persist(
    (set, get) => ({
      widgets: DEFAULT_WIDGETS,
      savedViews: [],
      isEditing: false,

      setWidgets: (widgets) => set({ widgets }),

      reorderWidget: (activeId, overId) => {
        set((state) => {
          const items = [...state.widgets];
          const activeIdx = items.findIndex((w) => w.id === activeId);
          const overIdx = items.findIndex((w) => w.id === overId);
          if (activeIdx === -1 || overIdx === -1) return state;

          const [moved] = items.splice(activeIdx, 1);
          items.splice(overIdx, 0, moved);
          return { widgets: items.map((w, i) => ({ ...w, order: i })) };
        });
      },

      toggleWidgetVisibility: (id) => {
        set((state) => ({
          widgets: state.widgets.map((w) =>
            w.id === id ? { ...w, visible: !w.visible } : w,
          ),
        }));
      },

      resizeWidget: (id, size) => {
        set((state) => ({
          widgets: state.widgets.map((w) => (w.id === id ? { ...w, size } : w)),
        }));
      },

      updateWidgetSettings: (id, settings) => {
        set((state) => ({
          widgets: state.widgets.map((w) =>
            w.id === id
              ? { ...w, settings: { ...w.settings, ...settings } }
              : w,
          ),
        }));
      },

      setEditing: (isEditing) => set({ isEditing }),

      resetToDefault: () => set({ widgets: DEFAULT_WIDGETS }),

      saveView: (label) => {
        const view: SavedView = {
          id: `view-${Date.now()}`,
          label,
          widgets: get().widgets,
          createdAt: Date.now(),
        };
        set((state) => ({
          savedViews: [...state.savedViews, view],
        }));
      },

      loadView: (viewId) => {
        const view = get().savedViews.find((v) => v.id === viewId);
        if (view) {
          set({ widgets: view.widgets });
        }
      },

      deleteView: (viewId) => {
        set((state) => ({
          savedViews: state.savedViews.filter((v) => v.id !== viewId),
        }));
      },
    }),
    {
      name: "polisyos.runtime.dashboard-layout",
      version: 1,
    },
  ),
);
