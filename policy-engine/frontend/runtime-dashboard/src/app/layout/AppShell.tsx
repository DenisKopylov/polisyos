import type { PropsWithChildren } from "react";

import { AppMobileNav } from "@/app/layout/AppMobileNav";
import { GlobalRuntimeBanner } from "@/app/layout/GlobalRuntimeBanner";
import { CommandPalette } from "@/features/commandPalette";
import { useI18n } from "@/i18n/LocaleProvider";
import { useIsMobile } from "@/shared/ui/responsive";
import Header from "@/app/layout/Header";
import Sidebar from "@/app/layout/Sidebar";

export default function AppShell({ children }: PropsWithChildren) {
  const { t } = useI18n();
  const isMobile = useIsMobile();

  return (
    <div className="atlas-shell-frame" data-testid="app-shell">
      <CommandPalette />
      <a
        href="#main-content"
        className="border-line bg-panel text-text sr-only top-4 left-4 z-50 rounded-full border px-4 py-2 text-sm font-semibold focus:not-sr-only focus:absolute"
      >
        {t("common.skipToContent")}
      </a>
      <div className="atlas-shell">
        <div className="app-shell">
          <Sidebar />
          <div className="surface">
            <GlobalRuntimeBanner />
            <Header />
            <main id="main-content" className="shell-main" tabIndex={-1}>
              {children}
            </main>
          </div>
        </div>
      </div>
      {isMobile && <AppMobileNav />}
    </div>
  );
}
