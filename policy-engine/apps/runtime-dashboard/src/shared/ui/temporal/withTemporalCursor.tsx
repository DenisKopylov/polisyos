import type { ComponentType } from "react";

import type { TemporalScope } from "@/shared/lib/domain/temporal";

import { useTemporalCursor } from "./TemporalRuntimeBridge";

export type WithTemporalCursorProps = {
  temporalScope: TemporalScope | null;
};

export function withTemporalCursor<P extends WithTemporalCursorProps>(
  Component: ComponentType<P>,
) {
  function WithTemporalCursor(props: Omit<P, keyof WithTemporalCursorProps>) {
    const cursor = useTemporalCursor();
    return (
      <Component {...(props as P)} temporalScope={cursor.committedScope} />
    );
  }

  const displayName = Component.displayName || Component.name || "Component";
  WithTemporalCursor.displayName = `withTemporalCursor(${displayName})`;
  return WithTemporalCursor;
}
