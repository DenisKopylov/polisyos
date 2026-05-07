import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/shared/lib/utils";
import { JanusGlyph } from "@/shared/brand/JanusGlyph";

export type MobileNavItem = {
  Icon: LucideIcon;
  active: boolean;
  label: string;
  path: string;
};

type MobileNavProps = {
  ariaLabel: string;
  atlasEnabled: boolean;
  items: readonly MobileNavItem[];
  renderItem: (
    item: MobileNavItem,
    className: string,
    children: ReactNode,
  ) => ReactNode;
};

/**
 * Bottom tab navigation bar for mobile viewports (< 640px).
 * Replaces the sidebar with 4-5 icon tabs following USWDS mobile-first patterns.
 */
export function MobileNav({
  ariaLabel,
  atlasEnabled,
  items,
  renderItem,
}: MobileNavProps) {
  return (
    <nav
      className="mobile-nav fixed inset-x-0 bottom-0 z-[var(--z-sticky)] flex items-stretch border-t border-[var(--line)] bg-[var(--panel)] backdrop-blur-lg"
      style={{
        height:
          "calc(var(--mobile-nav-height, 64px) + var(--safe-area-inset-bottom, 0px))",
        paddingBottom: "var(--safe-area-inset-bottom, 0px)",
        paddingLeft: "var(--safe-area-inset-left, 0px)",
        paddingRight: "var(--safe-area-inset-right, 0px)",
      }}
      aria-label={ariaLabel}
    >
      {atlasEnabled ? (
        <div
          className="border-line/70 bg-surface/70 mx-2 my-2 flex min-w-[72px] shrink-0 items-center justify-center gap-2 rounded-[20px] border px-3 text-[10px] font-semibold tracking-[0.14em] text-[var(--slate)] uppercase"
          data-testid="mobile-nav-brand-point"
        >
          <JanusGlyph decorative size={24} variant="mark" />
        </div>
      ) : null}
      {items.map((item) => {
        const className = cn(
          "flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium transition-colors",
          item.active
            ? "text-[var(--teal)]"
            : "text-[var(--slate)] hover:text-[var(--ink)]",
        );

        return (
          <div key={item.path}>
            {renderItem(
              item,
              className,
              <>
                <item.Icon
                  className={cn("h-5 w-5", item.active && "stroke-[2.5]")}
                  aria-hidden="true"
                />
                <span>{item.label}</span>
              </>,
            )}
          </div>
        );
      })}
    </nav>
  );
}
