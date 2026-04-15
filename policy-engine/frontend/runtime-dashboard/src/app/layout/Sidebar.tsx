import { useMaybeAuthz } from "@/app/authz/AuthzProvider";
import { useFeatureFlags } from "@/app/providers/FeatureFlagProvider";
import { useInterfaceMode } from "@/app/providers/InterfaceModeProvider";
import { PrefetchNavLink } from "@/app/routes/PrefetchNavLink";
import { getWorkspaceNavigationWithOptions } from "@/app/workspaces";
import { getBlockedRunCount, useRunsSample } from "@/features/runs";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

function ModeToggle() {
  const { t } = useI18n();
  const { mode, setMode, isClerk } = useInterfaceMode();
  const authz = useMaybeAuthz();
  const canSwitchToAnalyst = authz?.can("mode.analyst") ?? true;

  if (!canSwitchToAnalyst && isClerk) return null;

  return (
    <fieldset className="mt-4">
      <legend className="sr-only">{t("mode.interfaceLabel")}</legend>
      <div className="flex items-center gap-1 rounded-[var(--radius-pill)] bg-[rgba(255,255,255,0.08)] p-1">
        {(["clerk", "analyst"] as const).map((value) => (
          <label
            key={value}
            className={cn(
              "flex-1 cursor-pointer rounded-[var(--radius-pill)] px-3 py-1.5 text-center text-xs font-bold tracking-wider transition focus-within:outline-none focus-within:ring-2 focus-within:ring-white/40",
              mode === value
                ? "bg-[rgba(255,255,255,0.16)] text-white"
                : "text-[var(--rail-link)] hover:text-white",
            )}
          >
            <input
              type="radio"
              name="interface-mode"
              value={value}
              checked={mode === value}
              onChange={() => setMode(value)}
              className="sr-only"
            />
            <span>{t(`mode.${value}`)}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export default function Sidebar() {
  const { t } = useI18n();
  const { flags } = useFeatureFlags();
  const { mode, isClerk } = useInterfaceMode();
  const authz = useMaybeAuthz();
  const runsQuery = useRunsSample();
  const blockedCount = getBlockedRunCount(runsQuery.data?.runs ?? []);
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
        <p className="eyebrow">{t("shell.eyebrow")}</p>
        <h1 className="mt-2">{t("shell.title")}</h1>
        <p className="mt-4 text-sm leading-7 text-[rgba(245,240,230,0.72)]">
          {t("shell.subtitle")}
        </p>
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
          <strong>
            {blockedCount > 0
              ? t("shell.watchStatusBlocked")
              : t("shell.watchStatusStable")}
          </strong>
          <span>
            {blockedCount > 0
              ? t("shell.watchStatusBlockedDetail", {
                  count: String(blockedCount),
                })
              : t("shell.watchStatusStableDetail")}
          </span>
        </div>
      )}
    </aside>
  );
}
