import { useLocation } from "react-router-dom";

import { useMaybeAuthz } from "@/app/authz/AuthzProvider";
import { useCapabilities } from "@/api/hooks/useCapabilities";
import { useHealth } from "@/api/hooks/useHealth";
import { useFeatureFlags } from "@/app/providers/FeatureFlagProvider";
import { useInterfaceMode } from "@/app/providers/InterfaceModeProvider";
import { useTheme } from "@/app/providers/ThemeProvider";
import { PrefetchButton } from "@/app/routes/PrefetchButton";
import {
  getWorkspaceNavigationWithOptions,
  resolveWorkspaceKey,
  WORKSPACES,
} from "@/app/workspaces";
import { useRunsLiveStatus } from "@/app/providers/RunsLiveProvider";
import { useRunsSample } from "@/features/runs";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { SUPPORTED_LOCALES } from "@/shared/i18n/locale";
import { formatTime } from "@/shared/lib/utils";
import { JanusGlyph } from "@/shared/brand/JanusGlyph";
import { Badge, Button } from "@polisyos/atlas-ui";
import { TrustViewToggle } from "@/shared/ui/trust-view";

function resolveHealthBadge(status: string | undefined, unavailable: string) {
  if (status) {
    return <Badge kind="neutral">{status}</Badge>;
  }
  return <Badge kind="neutral">{unavailable}</Badge>;
}

export default function Header() {
  const location = useLocation();
  const healthQuery = useHealth();
  const capabilitiesQuery = useCapabilities();
  const runsQuery = useRunsSample();
  const runsLive = useRunsLiveStatus();
  const authz = useMaybeAuthz();
  const { flags } = useFeatureFlags();
  const { isClerk, mode } = useInterfaceMode();
  const atlasEnabled = flags.enableAtlasV2;
  const { theme, toggleTheme } = useTheme();
  const { locale, setLocale, t } = useI18n();
  const workspace = WORKSPACES[resolveWorkspaceKey(location.pathname)];
  const header = workspace.resolveHeader(location.pathname);
  const activeFeatures = (capabilitiesQuery.data?.features ?? []).filter(
    (feature) => feature.enabled,
  ).length;
  const reviewRuns = (runsQuery.data?.runs ?? []).filter(
    (run) => run.decision_review_required === true,
  ).length;
  const navigation = getWorkspaceNavigationWithOptions(flags, {
    isAllowed: (ws) => (authz ? authz.isWorkspaceAllowed(ws.key) : true),
    mode,
  });
  const runsWorkspace = navigation.find((item) => item.key === "runsDecisions");
  const composerWorkspace = navigation.find(
    (item) => item.key === "scenarioComposer",
  );
  const liveUpdatedAt = runsLive.lastEventAt
    ? formatTime(runsLive.lastEventAt, locale)
    : null;

  return (
    <header className="topbar" data-testid="shell-header">
      <div className="topbar-copy">
        {atlasEnabled ? (
          <div className="topbar-brand-chip">
            <JanusGlyph
              decorative
              data-testid="atlas-logo-mark-24"
              inverted={theme === "dark"}
              size={24}
              variant="mark"
            />
            <span>
              {isClerk
                ? t("shell.header.shellLite")
                : t("shell.header.analystShell")}
            </span>
          </div>
        ) : null}
        <p className="eyebrow">{t(header.eyebrowKey)}</p>
        <h2>{t(header.titleKey)}</h2>
        <p className="topbar-subtitle">{t(header.subtitleKey)}</p>
      </div>

      <div className="topbar-actions">
        {!isClerk && (
          <>
            {healthQuery.isLoading ? (
              <Badge kind="neutral">{t("shell.header.checking")}</Badge>
            ) : null}
            {healthQuery.isError ? (
              <Badge kind="fail">{t("shell.header.unavailable")}</Badge>
            ) : null}
            {!healthQuery.isLoading && !healthQuery.isError
              ? resolveHealthBadge(
                  healthQuery.data?.status,
                  t("shell.header.unavailable"),
                )
              : null}
            <Badge kind={runsLive.status === "live" ? "info" : "neutral"}>
              {runsLive.status === "live"
                ? t("shell.header.live")
                : t("shell.header.liveFallback")}
            </Badge>
            <Badge kind="neutral">
              {liveUpdatedAt
                ? t("shell.header.updatedAt", { time: liveUpdatedAt })
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
          </>
        )}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          aria-label={t("shell.header.theme")}
          onClick={toggleTheme}
        >
          {t(`shell.header.themeMode.${theme}`)}
        </Button>
        <TrustViewToggle />
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
        {!isClerk && runsWorkspace ? (
          <PrefetchButton
            to={runsWorkspace.path}
            prefetch="intent"
            variant="ghost"
          >
            {t("shell.header.openRuns")}
          </PrefetchButton>
        ) : null}
        {!isClerk && composerWorkspace ? (
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
