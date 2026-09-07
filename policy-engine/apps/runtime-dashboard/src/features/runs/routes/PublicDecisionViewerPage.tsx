import { Link } from "react-router-dom";

import { RouteIconProvider } from "@/app/providers/RouteIconProvider";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Badge, Button } from "@polisyos/atlas-ui";

export default function PublicDecisionViewerPage() {
  const { t } = useI18n();
  // No admitted server record/verifier is connected. URL content is never evidence.
  // Keep the route a nonreceipt until the governed PUBLIC verification chain exists.

  return (
    <div className="min-h-screen bg-[var(--canvas)]">
      <RouteIconProvider surface="public" />
      <header className="border-line bg-panel/90 sticky top-0 z-20 border-b px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
          <Link
            to="/welcome"
            className="font-sans text-lg font-extrabold tracking-tight text-[var(--ink)]"
          >
            PolicyOS
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <Badge kind="neutral">{t("phase35.viewer.unavailable")}</Badge>
            <Badge kind="neutral">{t("phase35.viewer.readOnly")}</Badge>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <section
          className="border-line bg-panel rounded-2xl border p-6"
          data-testid="public-decision-unavailable"
        >
          <p className="eyebrow">{t("phase35.viewer.errorEyebrow")}</p>
          <h1 className="text-2xl font-semibold">
            {t("phase35.viewer.unavailableTitle")}
          </h1>
          <p className="text-muted mt-2 max-w-2xl text-sm">
            {t("phase35.viewer.unavailableBody")}
          </p>
          <div className="mt-4">
            <Button to="/welcome" variant="ghost">
              {t("phase35.viewer.back")}
            </Button>
          </div>
        </section>
      </main>
    </div>
  );
}
