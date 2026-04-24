import type { ReactNode } from "react";
import { useCallback } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  rectSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

import type { WidgetConfig } from "../state/useDashboardLayoutStore";
import { useDashboardLayoutStore } from "../state/useDashboardLayoutStore";
import { WidgetContainer } from "./WidgetContainer";

type WidgetRendererMap = Record<string, (config: WidgetConfig) => ReactNode>;

type DashboardWidgetGridProps = {
  renderers: WidgetRendererMap;
  className?: string;
};

function SortableWidget({
  config,
  isEditing,
  onRemove,
  children,
}: {
  config: WidgetConfig;
  isEditing: boolean;
  onRemove: () => void;
  children: ReactNode;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: config.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes}>
      <WidgetContainer
        title={config.title}
        size={config.size}
        isEditing={isEditing}
        isDragging={isDragging}
        dragHandleProps={listeners}
        onRemove={onRemove}
      >
        {children}
      </WidgetContainer>
    </div>
  );
}

export function DashboardWidgetGrid({
  renderers,
  className,
}: DashboardWidgetGridProps) {
  const { t } = useI18n();
  const { widgets, isEditing, reorderWidget, toggleWidgetVisibility } =
    useDashboardLayoutStore();

  const visibleWidgets = widgets
    .filter((w) => w.visible)
    .sort((a, b) => a.order - b.order);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (over && active.id !== over.id) {
        reorderWidget(String(active.id), String(over.id));
      }
    },
    [reorderWidget],
  );

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={visibleWidgets.map((w) => w.id)}
        strategy={rectSortingStrategy}
        disabled={!isEditing}
      >
        <div
          className={cn(
            "grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3",
            className,
          )}
        >
          {visibleWidgets.map((config) => {
            const render = renderers[config.type];
            return (
              <SortableWidget
                key={config.id}
                config={config}
                isEditing={isEditing}
                onRemove={() => toggleWidgetVisibility(config.id)}
              >
                {render ? (
                  render(config)
                ) : (
                  <p className="text-muted text-sm">
                    {t("features.dashboard.widgets.unknownType", {
                      type: config.type,
                    })}
                  </p>
                )}
              </SortableWidget>
            );
          })}
        </div>
      </SortableContext>
    </DndContext>
  );
}
