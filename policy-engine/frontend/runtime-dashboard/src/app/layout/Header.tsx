import { useLocation } from "react-router-dom";

import { useMaybeAuthz } from "@/app/authz/AuthzProvider";
import { useCapabilities } from "@/api/hooks/useCapabilities";
import { useHealth } from "@/api/hooks/useHealth";
import { useFeatureFlags } from "@/app/providers/FeatureFlagProvider";
import { useTheme } from "@/app/providers/ThemeProvider";
import { PrefetchButton } from "@/app/routes/PrefetchButton";
import {
  getWorkspaceNavigationWithOptions,
  resolveWorkspaceKey,
  WORKSPACES,
} from "@/app/workspaces";
import { useRunsLiveStatus } from "@/app/providers/RunsLiveProvider";
import { isRunInReview, useRunsSample } from "@/features/runs";
import { useI18n } from "@/i18n/LocaleProvider";
import { SUPPORTED_LOCALES } from "@/i18n/locale";
import { Badge, Button } from "@/shared/ui";

function resolveHealthBadge(
  status: string | undefined,
  t: ReturnType<typeof useI18n>["t"],
) {
  if (status === "ok") {
    return <Badge kind="ok">{t("shell.header.apiOk")}</Badge>;
  }
  if (status) {
    return <Badge kind="warn">{status}</Badge>;
  }
  return <Badge kind="neutral">{t("common.unknown")}</Badge>;
}

export default function Header() {
  const location = useLocation();
  const healthQuery = useHealth();
  const capabilitiesQuery = useCapabilities();
  const runsQuery = useRunsSample();
  const runsLive = useRunsLiveStatus();
  const authz = useMaybeAuthz();
  const { flags } = useFeatureFlags();
  const { theme, toggleTheme } = useTheme();
  const { locale, setLocale, t } = useI18n();
  const workspace = WORKSPACES[resolveWorkspaceKey(location.pathname)];
  const header = workspace.resolveHeader(location.pathname);
  const activeFeatures = (capabilitiesQuery.data?.features ?? []).filter(
    (feature) => feature.enabled,
  ).length;
  const reviewRuns = (runsQuery.data?.runs ?? []).filter((run) =>
    isRunInReview(run.status),
  ).length;
  const navigation = getWorkspaceNavigationWithOptions(flags, {
    isAllowed: (workspace) =>
      authz ? authz.isWorkspaceAllowed(workspace.key) : true,
  });
  const runsWorkspace = navigation.find((item) => item.key === "runsDecisions");
  const composerWorkspace = navigation.find(
    (item) => item.key === "scenarioComposer",
  );
  const liveUpdatedAt = runsLive.lastEventAt
    ? new Date(runsLive.lastEventAt).toLocaleTimeString()
    : null;

  return (
    <header className="topbar" data-testid="shell-header">
      <div className="topbar-copy">
        <p className="eyebrow">{t(header.eyebrowKey)}</p>
        <h2>{t(header.titleKey)}</h2>
        <p className="topbar-subtitle">{t(header.subtitleKey)}</p>
      </div>

      <div className="topbar-actions">
        {healthQuery.isLoading ? (
          <Badge kind="neutral">{t("shell.header.checking")}</Badge>
        ) : null}
        {healthQuery.isError ? (
          <Badge kind="fail">{t("shell.header.unavailable")}</Badge>
        ) : null}
        {!healthQuery.isLoading && !healthQuery.isError
          ? resolveHealthBadge(healthQuery.data?.status, t)
          : null}
        <Badge kind={runsLive.status === "live" ? "info" : "neutral"}>
          {runsLive.status === "live"
            ? t("shell.header.live")
            : t("shell.header.liveFallback")}
        </Badge>
        <Badge kind="neutral">
          {liveUpdatedAt
            ? `Updated ${liveUpdatedAt}`
            : t("shell.header.checking")}
        </Badge>
        <Badge kind="neutral">
          {t("shell.header.capabilities")}: {activeFeatures}
        </Badge>
        <Badge kind={reviewRuns > 0 ? "warn" : "ok"}>
          {reviewRuns > 0
            ? t("shell.header.runsInReview", { count: reviewRuns })
            : t("shell.header.queueStable")}
        </Badge>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          aria-label={t("shell.header.theme")}
          onClick={toggleTheme}
        >
          {t(`shell.header.themeMode.${theme}`)}
        </Button>
        {SUPPORTED_LOCALES.map((value) => (
          <Button
            key={value}
            type="button"
            size="sm"
            variant={locale === value ? "primary" : "ghost"}
            data-testid={`locale-switch-${value}`}
            aria-label={`${t("shell.header.locale")} ${t(`common.locale.${value}`)}`}
            onClick={() => setLocale(value)}
          >
            {t(`common.locale.${value}`)}
          </Button>
        ))}
        {runsWorkspace ? (
          <PrefetchButton
            to={runsWorkspace.path}
            prefetch="intent"
            variant="ghost"
          >
            {t("shell.header.openRuns")}
          </PrefetchButton>
        ) : null}
        {composerWorkspace ? (
          <PrefetchButton
            to={composerWorkspace.path}
            prefetch="intent"
            variant="primary"
          >
            {t("shell.header.launchScenario")}
          </PrefetchButton>
        ) : null}
      </div>
    </header>
  );
}
