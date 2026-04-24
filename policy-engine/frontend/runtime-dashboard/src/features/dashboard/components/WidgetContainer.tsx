import type { ReactNode } from "react";

import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";
import { Card } from "@/shared/ui/primitives";

import type { WidgetSize } from "../state/useDashboardLayoutStore";

type WidgetContainerProps = {
  title: string;
  size: WidgetSize;
  isEditing?: boolean;
  isDragging?: boolean;
  dragHandleProps?: Record<string, unknown>;
  onRemove?: () => void;
  children: ReactNode;
  className?: string;
};

const SIZE_CLASSES: Record<WidgetSize, string> = {
  sm: "col-span-1",
  md: "col-span-1 md:col-span-1",
  lg: "col-span-1 md:col-span-2",
  xl: "col-span-1 md:col-span-2 lg:col-span-3",
};

export function WidgetContainer({
  title,
  size,
  isEditing = false,
  isDragging = false,
  dragHandleProps,
  onRemove,
  children,
  className,
}: WidgetContainerProps) {
  const { t } = useI18n();
  return (
    <Card
      className={cn(
        SIZE_CLASSES[size],
        "relative transition-shadow",
        isDragging && "z-10 shadow-lg ring-2 ring-[var(--chart-primary)]",
        isEditing && "ring-dashed ring-1 ring-[var(--chart-neutral)]",
        className,
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {isEditing && (
            <span
              {...dragHandleProps}
              className="text-muted cursor-grab active:cursor-grabbing"
              aria-label={t("features.dashboard.widgets.dragToReorder")}
            >
              {"\u2630"}
            </span>
          )}
          <h4 className="text-sm font-semibold">{title}</h4>
        </div>
        {isEditing && onRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="text-muted text-xs hover:text-[var(--chart-alert)]"
            aria-label={`Hide ${title} widget`}
          >
            {"\u2715"}
          </button>
        )}
      </div>

      {/* Content */}
      <div className="mt-3">{children}</div>
    </Card>
  );
}
