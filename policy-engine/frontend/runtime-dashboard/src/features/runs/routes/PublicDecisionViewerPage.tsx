import { Link, useParams } from "react-router-dom";

import { RouteIconProvider } from "@/app/providers/RouteIconProvider";
import { PublicationPacketPanel } from "@/features/runs/components/PublicationPacketPanel";
import { verifySignedPublicDecisionPacket } from "@/features/runs/domain/publicationPacket";
import { useI18n } from "@/i18n/LocaleProvider";
import { Badge, Button } from "@/shared/ui";

export default function PublicDecisionViewerPage() {
  const { signedId } = useParams();
  const { t } = useI18n();
  const verification = verifySignedPublicDecisionPacket(signedId ?? "");

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
            <Badge kind={verification.valid ? "ok" : "fail"}>
              {verification.valid
                ? t("phase35.viewer.verified")
                : t("phase35.viewer.invalid")}
            </Badge>
            <Badge kind="neutral">{t("phase35.viewer.readOnly")}</Badge>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        {verification.valid ? (
          <PublicationPacketPanel packet={verification.packet} publicMode />
        ) : (
          <section
            className="border-danger/30 bg-danger/10 rounded-2xl border p-6"
            data-testid="public-decision-invalid"
          >
            <p className="eyebrow">{t("phase35.viewer.errorEyebrow")}</p>
            <h1 className="text-2xl font-semibold">
              {t("phase35.viewer.errorTitle")}
            </h1>
            <p className="text-muted mt-2 max-w-2xl text-sm">
              {t("phase35.viewer.errorBody", {
                reason: verification.reason ?? "unknown",
              })}
            </p>
            <div className="mt-4">
              <Button to="/welcome" variant="ghost">
                {t("phase35.viewer.back")}
              </Button>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
