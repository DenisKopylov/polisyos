import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Button } from "@/shared/ui";
import { useRuntimeApiIncident } from "@/app/providers/RuntimeApiProvider";

function resolveBannerTone(status: number) {
  if (status === 403) {
    return "border-gold/35 bg-gold/10 text-gold";
  }
  return "border-danger/30 bg-danger/10 text-danger";
}

function resolveTitle(status: number, t: ReturnType<typeof useI18n>["t"]) {
  if (status === 0) {
    return t("shell.runtimeBanner.networkTitle");
  }
  if (status === 403) {
    return t("shell.runtimeBanner.accessDeniedTitle");
  }
  return t("shell.runtimeBanner.serverErrorTitle");
}

export function GlobalRuntimeBanner() {
  const { dismissIncident, incident } = useRuntimeApiIncident();
  const { t } = useI18n();

  if (!incident) {
    return null;
  }

  return (
    <div
      data-testid="runtime-banner"
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
      className={`mx-6 mt-5 rounded-lg border px-5 py-4 ${resolveBannerTone(incident.status)}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm font-semibold">
            {resolveTitle(incident.status, t)}
          </p>
          <p className="text-sm">
            {incident.detail || t("shell.runtimeBanner.defaultBody")}
          </p>
          <p className="text-xs opacity-80">
            {t("shell.runtimeBanner.meta", {
              status: incident.status,
              code: incident.code,
              source: incident.source,
            })}
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={dismissIncident}
        >
          {t("shell.runtimeBanner.dismiss")}
        </Button>
      </div>
    </div>
  );
}
