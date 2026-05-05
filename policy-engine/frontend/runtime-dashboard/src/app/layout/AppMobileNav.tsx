import { BarChart3, FileText, Home, Layers, MessageSquare } from "lucide-react";
import { useLocation } from "react-router-dom";

import { useFeatureFlags } from "@/app/providers/FeatureFlagProvider";
import { useInterfaceMode } from "@/app/providers/InterfaceModeProvider";
import { PrefetchNavLink } from "@/app/routes/PrefetchNavLink";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { MobileNav, type MobileNavItem } from "@/shared/ui/responsive";

type AppMobileNavItem = Omit<MobileNavItem, "active">;

const ANALYST_NAV: readonly AppMobileNavItem[] = [
  { Icon: Home, label: "mobile.nav.home", path: "/" },
  { Icon: FileText, label: "mobile.nav.runs", path: "/runs" },
  { Icon: Layers, label: "mobile.nav.evidence", path: "/evidence" },
  { Icon: BarChart3, label: "mobile.nav.compose", path: "/compose" },
];

const CLERK_NAV: readonly AppMobileNavItem[] = [
  { Icon: MessageSquare, label: "mobile.nav.chat", path: "/" },
  { Icon: FileText, label: "mobile.nav.runs", path: "/runs" },
];

function isActive(itemPath: string, currentPath: string): boolean {
  if (itemPath === "/") {
    return currentPath === "/";
  }

  return currentPath.startsWith(itemPath);
}

export function AppMobileNav() {
  const { t } = useI18n();
  const location = useLocation();
  const { flags } = useFeatureFlags();
  const { isClerk } = useInterfaceMode();

  const items = (isClerk ? CLERK_NAV : ANALYST_NAV).map((item) => ({
    ...item,
    active: isActive(item.path, location.pathname),
    label: t(item.label),
  }));

  return (
    <MobileNav
      ariaLabel={t("mobile.nav.ariaLabel")}
      atlasEnabled={flags.enableAtlasV2}
      items={items}
      renderItem={(item, className, children) => (
        <PrefetchNavLink
          key={item.path}
          to={item.path}
          prefetch="intent"
          end={item.path === "/"}
          className={className}
          aria-current={item.active ? "page" : undefined}
        >
          {children}
        </PrefetchNavLink>
      )}
    />
  );
}
