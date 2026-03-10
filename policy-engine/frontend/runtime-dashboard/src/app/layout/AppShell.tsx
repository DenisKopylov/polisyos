import type { PropsWithChildren } from "react";

import { GlobalRuntimeBanner } from "@/app/layout/GlobalRuntimeBanner";
import { useI18n } from "@/i18n/LocaleProvider";
import Header from "@/app/layout/Header";
import Sidebar from "@/app/layout/Sidebar";

export default function AppShell({ children }: PropsWithChildren) {
  const { t } = useI18n();

  return (
    <div className="atlas-shell-frame" data-testid="app-shell">
      <a
        href="#main-content"
        className="sr-only left-4 top-4 z-50 rounded-full border border-line bg-panel px-4 py-2 text-sm font-semibold text-text focus:not-sr-only focus:absolute"
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
    </div>
  );
}
