import { useMaybeAuthz } from "@/app/authz/AuthzProvider";
import { useFeatureFlags } from "@/app/providers/FeatureFlagProvider";
import { useInterfaceMode } from "@/app/providers/InterfaceModeProvider";
import { PrefetchNavLink } from "@/app/routes/PrefetchNavLink";
import { getWorkspaceNavigationWithOptions } from "@/app/workspaces";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { JanusGlyph } from "@/shared/brand/JanusGlyph";
import { SegmentedControl } from "@polisyos/atlas-ui";

function ModeToggle() {
  const { t } = useI18n();
  const { mode, setMode, isClerk } = useInterfaceMode();
  const authz = useMaybeAuthz();
  const canSwitchToAnalyst = authz?.can("mode.analyst") ?? true;

  if (!canSwitchToAnalyst && isClerk) return null;

  return (
    <fieldset className="mt-4">
      <legend className="sr-only">{t("mode.interfaceLabel")}</legend>
      <SegmentedControl
        ariaLabel={t("mode.interfaceLabel")}
        name="interface-mode"
        tone="rail"
        size="sm"
        className="grid-cols-2"
        value={mode}
        onValueChange={setMode}
        options={(["clerk", "analyst"] as const).map((value) => ({
          label: t(`mode.${value}`),
          value,
        }))}
      />
    </fieldset>
  );
}

export default function Sidebar() {
  const { t } = useI18n();
  const { flags } = useFeatureFlags();
  const { mode, isClerk } = useInterfaceMode();
  const atlasEnabled = flags.enableAtlasV2;
  const authz = useMaybeAuthz();
  const navigation = getWorkspaceNavigationWithOptions(flags, {
    isAllowed: (workspace) =>
      authz ? authz.isWorkspaceAllowed(workspace.key) : true,
    mode,
  });

  return (
    <aside
      className="side-rail"
      data-testid="shell-sidebar"
      aria-label={t("shell.navAriaLabel")}
    >
      <div>
        {atlasEnabled ? (
          <div className="atlas-sidebar-brand" data-testid="atlas-logo-lockup">
            <div className="flex items-center gap-3">
              <JanusGlyph decorative inverted size={32} variant="mark" />
              <div className="grid gap-1">
                <p className="eyebrow">{t("shell.eyebrow")}</p>
                <h1 className="text-xl leading-none">{t("shell.title")}</h1>
              </div>
            </div>
            <p className="atlas-sidebar-note">
              {isClerk
                ? t("shell.atlasShellLiteSubtitle")
                : t("shell.atlasAnalystSubtitle")}
            </p>
          </div>
        ) : (
          <>
            <p className="eyebrow">{t("shell.eyebrow")}</p>
            <h1 className="mt-2">{t("shell.title")}</h1>
            <p className="mt-4 text-sm leading-7 text-[rgba(245,240,230,0.72)]">
              {t("shell.subtitle")}
            </p>
          </>
        )}
      </div>

      <nav aria-label={t("shell.navAriaLabel")}>
        {isClerk ? (
          <>
            <PrefetchNavLink
              to="/"
              data-testid="shell-nav-clerk-chat"
              prefetch="intent"
              className={({ isActive }) =>
                cn("block", isActive ? "active" : "")
              }
              end
            >
              {t("clerk.newAnalysis")}
            </PrefetchNavLink>
            <PrefetchNavLink
              to="/runs"
              data-testid="shell-nav-clerk-runs"
              prefetch="intent"
              className={({ isActive }) =>
                cn("block", isActive ? "active" : "")
              }
            >
              {t("clerk.myAnalyses")}
            </PrefetchNavLink>
          </>
        ) : (
          navigation.map((link) => (
            <PrefetchNavLink
              key={link.path}
              to={link.path}
              data-testid={`shell-nav-${link.key}`}
              prefetch="intent"
              className={({ isActive }) =>
                cn("block", isActive ? "active" : "")
              }
            >
              {t(`shell.nav.${link.key}`)}
            </PrefetchNavLink>
          ))
        )}
      </nav>

      <ModeToggle />

      {!isClerk && (
        <div className="rail-card">
          <p className="eyebrow">{t("shell.watchStatusTitle")}</p>
          <strong>{t("common.unavailable")}</strong>
        </div>
      )}
    </aside>
  );
}
