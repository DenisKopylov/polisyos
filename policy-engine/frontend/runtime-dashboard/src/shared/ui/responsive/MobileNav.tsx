import { useLocation } from "react-router-dom";
import { BarChart3, FileText, Home, Layers, MessageSquare } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { PrefetchNavLink } from "@/app/routes/PrefetchNavLink";
import { useFeatureFlags } from "@/app/providers/FeatureFlagProvider";
import { useInterfaceMode } from "@/app/providers/InterfaceModeProvider";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";
import { AtlasBrand } from "@/shared/brand/AtlasBrand";

type NavItem = {
  Icon: LucideIcon;
  label: string;
  path: string;
};

const ANALYST_NAV: NavItem[] = [
  { Icon: Home, label: "mobile.nav.home", path: "/" },
  { Icon: FileText, label: "mobile.nav.runs", path: "/runs" },
  { Icon: Layers, label: "mobile.nav.evidence", path: "/evidence" },
  { Icon: BarChart3, label: "mobile.nav.compose", path: "/compose" },
];

const CLERK_NAV: NavItem[] = [
  { Icon: MessageSquare, label: "mobile.nav.chat", path: "/" },
  { Icon: FileText, label: "mobile.nav.runs", path: "/runs" },
];

function isActive(itemPath: string, currentPath: string): boolean {
  if (itemPath === "/") return currentPath === "/";
  return currentPath.startsWith(itemPath);
}

/**
 * Bottom tab navigation bar for mobile viewports (< 640px).
 * Replaces the sidebar with 4-5 icon tabs following USWDS mobile-first patterns.
 */
export function MobileNav() {
  const { t } = useI18n();
  const location = useLocation();
  const { flags } = useFeatureFlags();
  const { isClerk } = useInterfaceMode();
  const items = isClerk ? CLERK_NAV : ANALYST_NAV;
  const atlasEnabled = flags.enableAtlasV2;

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
      aria-label={t("mobile.nav.ariaLabel")}
    >
      {atlasEnabled ? (
        <div
          className="border-line/70 bg-surface/70 mx-2 my-2 flex min-w-[72px] shrink-0 items-center justify-center gap-2 rounded-[20px] border px-3 text-[10px] font-semibold tracking-[0.14em] text-[var(--slate)] uppercase"
          data-testid="mobile-nav-brand-point"
        >
          <AtlasBrand alt={t("shell.title")} size={24} variant="mark" />
          <span aria-hidden="true">Atlas</span>
        </div>
      ) : null}
      {items.map((item) => {
        const active = isActive(item.path, location.pathname);
        return (
          <PrefetchNavLink
            key={item.path}
            to={item.path}
            prefetch="intent"
            end={item.path === "/"}
            className={() =>
              cn(
                "flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium transition-colors",
                active
                  ? "text-[var(--teal)]"
                  : "text-[var(--slate)] hover:text-[var(--ink)]",
              )
            }
            aria-current={active ? "page" : undefined}
          >
            <item.Icon
              className={cn("h-5 w-5", active && "stroke-[2.5]")}
              aria-hidden="true"
            />
            <span>{t(item.label)}</span>
          </PrefetchNavLink>
        );
      })}
    </nav>
  );
}
