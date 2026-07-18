import { useEffect, useRef, useState } from "react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Button } from "@polisyos/atlas-ui";

import { useDashboardLayoutStore } from "../state/useDashboardLayoutStore";

type DashboardToolbarProps = {
  className?: string;
};

export function DashboardToolbar({ className }: DashboardToolbarProps) {
  const { t } = useI18n();
  const {
    isEditing,
    setEditing,
    widgets,
    savedViews,
    saveView,
    loadView,
    deleteView,
    toggleWidgetVisibility,
    resetToDefault,
  } = useDashboardLayoutStore();

  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [viewName, setViewName] = useState("");
  const [showViewPicker, setShowViewPicker] = useState(false);
  const viewNameInputRef = useRef<HTMLInputElement | null>(null);

  const hiddenWidgets = widgets.filter((w) => !w.visible);

  useEffect(() => {
    if (showSaveDialog) {
      viewNameInputRef.current?.focus();
    }
  }, [showSaveDialog]);

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <Button
        type="button"
        variant={isEditing ? "secondary" : "ghost"}
        onClick={() => setEditing(!isEditing)}
      >
        {isEditing
          ? t("pages.dashboard.toolbar.doneEditing")
          : t("pages.dashboard.toolbar.customize")}
      </Button>

      {isEditing && (
        <>
          {hiddenWidgets.length > 0 && (
            <div className="relative">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  // Restore first hidden widget
                  toggleWidgetVisibility(hiddenWidgets[0].id);
                }}
              >
                {t("pages.dashboard.toolbar.addWidget", {
                  count: hiddenWidgets.length,
                })}
              </Button>
            </div>
          )}

          <Button type="button" variant="ghost" onClick={resetToDefault}>
            {t("pages.dashboard.toolbar.reset")}
          </Button>
        </>
      )}

      {/* Save view */}
      <div className="relative">
        <Button
          type="button"
          variant="ghost"
          onClick={() => setShowSaveDialog(!showSaveDialog)}
        >
          {t("pages.dashboard.toolbar.saveView")}
        </Button>
        {showSaveDialog && (
          <div className="bg-surface border-line absolute start-0 top-full z-20 mt-1 rounded-xl border p-3 shadow-lg">
            <input
              ref={viewNameInputRef}
              type="text"
              value={viewName}
              onChange={(e) => setViewName(e.target.value)}
              placeholder={t("pages.dashboard.toolbar.viewNamePlaceholder")}
              className="bg-surface border-line w-44 rounded-lg border px-2 py-1 text-sm"
            />
            <div className="mt-2 flex gap-2">
              <Button
                type="button"
                variant="primary"
                onClick={() => {
                  if (viewName.trim()) {
                    saveView(viewName.trim());
                    setViewName("");
                    setShowSaveDialog(false);
                  }
                }}
              >
                {t("pages.dashboard.toolbar.save")}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setShowSaveDialog(false)}
              >
                {t("common.cancel")}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Load view */}
      {savedViews.length > 0 && (
        <div className="relative">
          <Button
            type="button"
            variant="ghost"
            onClick={() => setShowViewPicker(!showViewPicker)}
          >
            {t("pages.dashboard.toolbar.views", {
              count: savedViews.length,
            })}
          </Button>
          {showViewPicker && (
            <div className="bg-surface border-line absolute start-0 top-full z-20 mt-1 w-56 rounded-xl border p-2 shadow-lg">
              {savedViews.map((view) => (
                <div
                  key={view.id}
                  className="flex items-center justify-between rounded-lg px-2 py-1.5 hover:bg-[var(--chart-primary)]/5"
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 truncate text-start text-sm font-medium"
                    onClick={() => {
                      loadView(view.id);
                      setShowViewPicker(false);
                    }}
                  >
                    {view.label}
                  </button>
                  <button
                    type="button"
                    className="text-muted shrink-0 ps-2 text-xs hover:text-[var(--chart-alert)]"
                    onClick={() => deleteView(view.id)}
                    aria-label={t("pages.dashboard.toolbar.deleteView", {
                      view: view.label,
                    })}
                  >
                    {"\u2715"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
